"""Face detection on photograph-classified images using Rekognition detect_faces.

Loads image_classification.json from S3, filters to photographs only, calls
Rekognition detect_faces on each, and produces two artifacts:
  - face_detection_results.json  (bounding boxes, confidence, gender, age_range)
  - face_crop_metadata.json      (format consumed by crop_faces.py)

Supports --dry-run, --limit, --threshold, and --case-id arguments.
Rate-limits Rekognition calls with 100ms delay. Retries on throttle with backoff.

Usage:
    python scripts/detect_faces.py [--case-id CASE_ID] [--threshold 80] [--limit N] [--dry-run]
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
DEFAULT_CASE = "7f05e8d5-4492-4f19-8894-25367606db96"
COMBINED_CASE = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
MAX_RETRIES = 3
BASE_BACKOFF = 1.0  # seconds


def select_photographs(classifications: list) -> list:
    """Filter classification entries to only those classified as 'photograph'.

    This is a pure function with no side effects or I/O.

    Args:
        classifications: List of dicts, each with at least a 'classification' key.

    Returns:
        List of dicts where classification == 'photograph'.
    """
    return [entry for entry in classifications if entry.get("classification") == "photograph"]


def extract_document_id(s3_key: str) -> str:
    """Extract the source document ID from an S3 key filename.

    Looks for patterns like EFTA01234567 in the filename. Falls back to the
    filename stem (without extension) if no EFTA pattern is found.

    Args:
        s3_key: Full S3 key path.

    Returns:
        Extracted document ID string.
    """
    filename = s3_key.rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    # Try to find an EFTA-style document ID
    match = re.search(r"(EFTA\d+)", stem)
    if match:
        return match.group(1)
    return stem


def build_crop_s3_key(case_id: str, source_s3_key: str, face_index: int) -> str:
    """Build a unique crop S3 key for a detected face.

    Uses a hash of the source key + face index to create a short unique filename.

    Args:
        case_id: The case ID.
        source_s3_key: S3 key of the source image.
        face_index: Index of the face within the image.

    Returns:
        S3 key for the crop destination.
    """
    hash_input = f"{source_s3_key}:{face_index}"
    short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
    return f"cases/{case_id}/face-crops/unidentified/{short_hash}.jpg"


def build_face_detection_entry(s3_key: str, faces_response: list, threshold: float) -> dict:
    """Build a face detection result entry from Rekognition response.

    Args:
        s3_key: S3 key of the source image.
        faces_response: List of FaceDetail dicts from Rekognition detect_faces.
        threshold: Minimum confidence threshold.

    Returns:
        Dict with s3_key and list of face dicts.
    """
    faces = []
    for face_detail in faces_response:
        confidence = face_detail.get("Confidence", 0)
        if confidence < threshold:
            continue
        faces.append({
            "bounding_box": face_detail.get("BoundingBox", {}),
            "confidence": round(confidence, 1),
            "gender": face_detail.get("Gender", {}),
            "age_range": face_detail.get("AgeRange", {}),
        })
    return {"s3_key": s3_key, "faces": faces}


def build_crop_metadata_entries(
    case_id: str, s3_key: str, faces_response: list, threshold: float
) -> list:
    """Build face_crop_metadata entries compatible with crop_faces.py.

    Args:
        case_id: The case ID.
        s3_key: S3 key of the source image.
        faces_response: List of FaceDetail dicts from Rekognition detect_faces.
        threshold: Minimum confidence threshold.

    Returns:
        List of crop metadata dicts.
    """
    entries = []
    face_index = 0
    for face_detail in faces_response:
        confidence = face_detail.get("Confidence", 0)
        if confidence < threshold:
            continue

        bbox = face_detail.get("BoundingBox", {})
        gender_info = face_detail.get("Gender", {})
        age_info = face_detail.get("AgeRange", {})

        entries.append({
            "source_s3_key": s3_key,
            "crop_s3_key": build_crop_s3_key(case_id, s3_key, face_index),
            "bounding_box": {
                "Left": bbox.get("Left", 0),
                "Top": bbox.get("Top", 0),
                "Width": bbox.get("Width", 0),
                "Height": bbox.get("Height", 0),
            },
            "confidence": round(confidence, 1),
            "gender": gender_info.get("Value", "Unknown"),
            "age_range": f"{age_info.get('Low', 0)}-{age_info.get('High', 0)}",
            "source_document_id": extract_document_id(s3_key),
        })
        face_index += 1
    return entries


def detect_faces_with_retry(rek, bucket: str, s3_key: str) -> list:
    """Call Rekognition detect_faces with retry on throttle errors.

    Args:
        rek: Boto3 Rekognition client.
        bucket: S3 bucket name.
        s3_key: S3 key of the image.

    Returns:
        List of FaceDetail dicts from Rekognition.

    Raises:
        ClientError: If a non-throttle error occurs after retries.
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = rek.detect_faces(
                Image={"S3Object": {"Bucket": bucket, "Name": s3_key}},
                Attributes=["ALL"],
            )
            return resp.get("FaceDetails", [])
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("ThrottlingException", "ProvisionedThroughputExceededException"):
                wait = BASE_BACKOFF * (2 ** attempt)
                logger.warning("Throttled on %s, retrying in %.1fs (attempt %d/%d)",
                               s3_key.split("/")[-1], wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait)
            else:
                raise
    # Final attempt without catching
    resp = rek.detect_faces(
        Image={"S3Object": {"Bucket": bucket, "Name": s3_key}},
        Attributes=["ALL"],
    )
    return resp.get("FaceDetails", [])


def main():
    parser = argparse.ArgumentParser(
        description="Detect faces in photograph-classified images using Rekognition"
    )
    parser.add_argument("--case-id", default=DEFAULT_CASE,
                        help="Case ID to process")
    parser.add_argument("--threshold", type=float, default=80.0,
                        help="Minimum face confidence threshold (default: 80)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max photographs to process (0=all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run detection but don't upload artifacts to S3")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=REGION)
    rek = boto3.client("rekognition", region_name=REGION)

    # Load classification artifact from S3
    classification_key = f"cases/{args.case_id}/rekognition-artifacts/image_classification.json"
    logger.info("Loading classification artifact from %s", classification_key)
    try:
        resp = s3.get_object(Bucket=BUCKET, Key=classification_key)
        artifact = json.loads(resp["Body"].read().decode())
    except Exception as e:
        logger.error("Failed to load classification artifact: %s", e)
        sys.exit(1)

    classifications = artifact.get("classifications", [])
    logger.info("Loaded %d total classifications", len(classifications))

    # Filter to photographs only
    photographs = select_photographs(classifications)
    skipped = len(classifications) - len(photographs)
    logger.info("Selected %d photographs (%d non-photographs skipped)", len(photographs), skipped)

    if not photographs:
        logger.warning("No photographs found. Exiting.")
        return

    # Apply limit
    if args.limit > 0:
        photographs = photographs[:args.limit]
        logger.info("Limited to %d photographs", len(photographs))

    # Process each photograph
    detection_results = []
    crop_metadata = []
    total_faces = 0
    errors = 0

    for i, entry in enumerate(photographs):
        s3_key = entry.get("s3_key", "")
        filename = s3_key.rsplit("/", 1)[-1] if s3_key else f"image_{i}"

        try:
            face_details = detect_faces_with_retry(rek, BUCKET, s3_key)

            # Build detection result
            det_entry = build_face_detection_entry(s3_key, face_details, args.threshold)
            detection_results.append(det_entry)

            # Build crop metadata entries
            crop_entries = build_crop_metadata_entries(
                args.case_id, s3_key, face_details, args.threshold
            )
            crop_metadata.extend(crop_entries)

            face_count = len(det_entry["faces"])
            total_faces += face_count
            if face_count > 0:
                logger.info("  %s: %d face(s) detected", filename, face_count)

        except Exception as e:
            logger.error("Failed to detect faces in %s: %s", filename, str(e)[:150])
            errors += 1

        # Rate limit: 100ms between calls
        time.sleep(0.1)

        # Progress logging
        if (i + 1) % 25 == 0:
            logger.info("Progress: %d/%d photographs, %d faces, %d errors",
                        i + 1, len(photographs), total_faces, errors)

    # Upload artifacts
    detection_key = f"cases/{args.case_id}/rekognition-artifacts/face_detection_results.json"
    crop_meta_key = f"cases/{args.case_id}/rekognition-artifacts/face_crop_metadata.json"

    if args.dry_run:
        logger.info("[DRY RUN] Would upload face_detection_results.json (%d entries)", len(detection_results))
        logger.info("[DRY RUN] Would upload face_crop_metadata.json (%d entries)", len(crop_metadata))
    else:
        s3.put_object(
            Bucket=BUCKET, Key=detection_key,
            Body=json.dumps(detection_results, indent=2).encode(),
            ContentType="application/json",
        )
        logger.info("Uploaded face detection results to %s", detection_key)

        s3.put_object(
            Bucket=BUCKET, Key=crop_meta_key,
            Body=json.dumps(crop_metadata, indent=2).encode(),
            ContentType="application/json",
        )
        logger.info("Uploaded face crop metadata to %s", crop_meta_key)

    # Summary
    print(f"\n{'='*60}")
    print(f"Face Detection Complete")
    print(f"  Photographs processed: {len(photographs)}")
    print(f"  Total faces detected:  {total_faces}")
    print(f"  Images skipped:        {skipped}")
    print(f"  Errors:                {errors}")
    print(f"  Crop metadata entries: {len(crop_metadata)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
