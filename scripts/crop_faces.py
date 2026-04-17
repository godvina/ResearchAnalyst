"""Crop detected faces from extracted images using Rekognition bounding box metadata.

Reads face_crop_metadata.json from S3, downloads each source image, crops the face
region using the bounding box, resizes to 200x200, and uploads to S3.

Usage:
    python scripts/crop_faces.py [--case-id CASE_ID] [--dry-run]
"""

import argparse
import io
import json
import logging
import sys

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
DEFAULT_CASE = "7f05e8d5-4492-4f19-8894-25367606db96"


def crop_face(image_bytes: bytes, bbox: dict, padding: float = 0.3) -> bytes:
    """Crop a face from an image using Rekognition bounding box with padding."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    left = bbox["Left"]
    top = bbox["Top"]
    width = bbox["Width"]
    height = bbox["Height"]

    # Add padding around the face
    pad_w = width * padding
    pad_h = height * padding

    x1 = max(0, int((left - pad_w) * w))
    y1 = max(0, int((top - pad_h) * h))
    x2 = min(w, int((left + width + pad_w) * w))
    y2 = min(h, int((top + height + pad_h) * h))

    # Ensure minimum crop size
    if x2 - x1 < 20 or y2 - y1 < 20:
        return b""

    cropped = img.crop((x1, y1, x2, y2))

    # Resize to 200x200 square
    side = max(cropped.size)
    square = Image.new("RGB", (side, side), (0, 0, 0))
    offset_x = (side - cropped.size[0]) // 2
    offset_y = (side - cropped.size[1]) // 2
    square.paste(cropped, (offset_x, offset_y))
    square = square.resize((200, 200), Image.LANCZOS)

    buf = io.BytesIO()
    square.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser(description="Crop faces from extracted images")
    parser.add_argument("--case-id", default=DEFAULT_CASE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target-case", default=None,
                        help="Also copy crops to this case ID")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=REGION)

    # Load face crop metadata
    meta_key = f"cases/{args.case_id}/rekognition-artifacts/face_crop_metadata.json"
    logger.info("Loading face crop metadata from %s", meta_key)
    resp = s3.get_object(Bucket=BUCKET, Key=meta_key)
    metadata = json.loads(resp["Body"].read().decode())
    logger.info("Found %d face detections", len(metadata))

    # Cache source images to avoid re-downloading
    image_cache = {}
    cropped = 0
    errors = 0

    for i, face in enumerate(metadata):
        source_key = face["source_s3_key"]
        crop_key = face["crop_s3_key"]
        bbox = face["bounding_box"]

        # Download source image if not cached
        if source_key not in image_cache:
            try:
                obj = s3.get_object(Bucket=BUCKET, Key=source_key)
                image_cache[source_key] = obj["Body"].read()
                logger.info("Downloaded source: %s (%d bytes)",
                            source_key.split("/")[-1], len(image_cache[source_key]))
            except Exception as e:
                logger.error("Failed to download %s: %s", source_key, str(e)[:100])
                errors += 1
                continue

        # Crop the face
        try:
            crop_bytes = crop_face(image_cache[source_key], bbox)
            if not crop_bytes:
                logger.warning("Crop too small for face %d, skipping", i)
                continue

            if args.dry_run:
                logger.info("[DRY RUN] Would upload %d bytes to %s", len(crop_bytes), crop_key)
            else:
                s3.put_object(Bucket=BUCKET, Key=crop_key, Body=crop_bytes,
                              ContentType="image/jpeg")
                logger.info("Uploaded crop %d: %s (%d bytes)", i, crop_key.split("/")[-1],
                            len(crop_bytes))

                # Also copy to target case if specified
                if args.target_case:
                    target_key = crop_key.replace(args.case_id, args.target_case)
                    s3.put_object(Bucket=BUCKET, Key=target_key, Body=crop_bytes,
                                  ContentType="image/jpeg")

            cropped += 1
        except Exception as e:
            logger.error("Failed to crop face %d: %s", i, str(e)[:100])
            errors += 1

        if (i + 1) % 10 == 0:
            logger.info("Progress: %d/%d processed, %d cropped, %d errors",
                        i + 1, len(metadata), cropped, errors)

    print(f"\nDone! Cropped {cropped}/{len(metadata)} faces, {errors} errors")


if __name__ == "__main__":
    main()
