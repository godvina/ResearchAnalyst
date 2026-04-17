"""Download public domain photos of key persons and upload to S3 as demo face crops.

Usage:
    python scripts/setup_demo_photos.py --case-id <CASE_ID> [--bucket <BUCKET>] [--dry-run]

Photos are sourced from Wikipedia REST API (public domain / CC-licensed mugshots and
official portraits). Each image is resized to 200x200 JPEG and uploaded to:
    s3://bucket/cases/{case_id}/face-crops/demo/{entity_name}.jpg
"""

import argparse
import hashlib
import io
import json
import logging
import os
import sys
import time
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "research-analyst-data-lake-974220725866"

# Wikipedia REST API endpoints for public domain / CC photos
# These return JSON with a thumbnail.source URL
WIKIPEDIA_PHOTO_SOURCES = {
    "Jeffrey Epstein": "https://en.wikipedia.org/api/rest_v1/page/summary/Jeffrey_Epstein",
    "Ghislaine Maxwell": "https://en.wikipedia.org/api/rest_v1/page/summary/Ghislaine_Maxwell",
    "Prince Andrew": "https://en.wikipedia.org/api/rest_v1/page/summary/Prince_Andrew,_Duke_of_York",
    "Bill Clinton": "https://en.wikipedia.org/api/rest_v1/page/summary/Bill_Clinton",
    "Donald Trump": "https://en.wikipedia.org/api/rest_v1/page/summary/Donald_Trump",
    "Alan Dershowitz": "https://en.wikipedia.org/api/rest_v1/page/summary/Alan_Dershowitz",
    "Les Wexner": "https://en.wikipedia.org/api/rest_v1/page/summary/Les_Wexner",
    "Ehud Barak": "https://en.wikipedia.org/api/rest_v1/page/summary/Ehud_Barak",
}

USER_AGENT = "ResearchAnalystDemo/1.0 (investigative-intelligence-poc; contact: demo@example.com)"

# Color palette for mugshot-style placeholders
PERSON_COLORS = {
    "Jeffrey Epstein": (139, 28, 28),      # Dark red
    "Ghislaine Maxwell": (88, 28, 135),     # Purple
    "Prince Andrew": (30, 64, 175),         # Royal blue
    "Bill Clinton": (3, 105, 161),          # Blue
    "Donald Trump": (180, 83, 9),           # Amber
    "Alan Dershowitz": (4, 120, 87),        # Teal
    "Les Wexner": (109, 40, 217),           # Violet
    "Ehud Barak": (14, 116, 144),           # Cyan
}


def generate_mugshot_placeholder(person_name: str, size: int = 200) -> bytes:
    """Generate a professional mugshot-style placeholder image using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Pillow not installed. Run: pip install Pillow")
        return b""

    bg_color = PERSON_COLORS.get(person_name, (55, 65, 81))
    img = Image.new("RGB", (size, size), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Get initials
    parts = person_name.split()
    initials = "".join(p[0].upper() for p in parts if p)[:2]

    # Try to use Arial, fall back to default
    try:
        big_font = ImageFont.truetype("arial.ttf", 72)
        small_font = ImageFont.truetype("arial.ttf", 13)
    except (OSError, IOError):
        big_font = ImageFont.load_default()
        small_font = big_font

    # Draw initials centered
    bbox = draw.textbbox((0, 0), initials, font=big_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 15), initials, fill="white", font=big_font)

    # Draw name at bottom
    name_upper = person_name.upper()
    bbox2 = draw.textbbox((0, 0), name_upper, font=small_font)
    nw = bbox2[2] - bbox2[0]
    draw.text(((size - nw) // 2, size - 28), name_upper, fill="#cccccc", font=small_font)

    # Add subtle border
    draw.rectangle([(0, 0), (size - 1, size - 1)], outline="#ffffff40", width=2)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def fetch_wikipedia_thumbnail(api_url: str) -> bytes | None:
    """Fetch the thumbnail image from a Wikipedia REST API summary endpoint."""
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        img_url = data.get("thumbnail", {}).get("source", "")
        if not img_url:
            logger.warning("No thumbnail in Wikipedia response for %s", api_url)
            return None
        # Download the actual image
        img_req = urllib.request.Request(img_url, headers={"User-Agent": USER_AGENT})
        img_resp = urllib.request.urlopen(img_req, timeout=15)
        return img_resp.read()
    except Exception as e:
        logger.error("Failed to fetch from %s: %s", api_url, str(e)[:200])
        return None


def resize_to_square(image_bytes: bytes, size: int = 200) -> bytes:
    """Resize image to a square JPEG of the given size."""
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow not installed — uploading original image without resize")
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes))
    # Center crop to square
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((size, size), Image.LANCZOS)
    # Convert to RGB if needed (handles RGBA, palette modes)
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def upload_to_s3(bucket: str, key: str, data: bytes, dry_run: bool = False):
    """Upload bytes to S3."""
    if dry_run:
        logger.info("[DRY RUN] Would upload %d bytes to s3://%s/%s", len(data), bucket, key)
        return
    import boto3
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/jpeg")
    logger.info("Uploaded %d bytes to s3://%s/%s", len(data), bucket, key)


def main():
    parser = argparse.ArgumentParser(description="Setup demo face photos in S3")
    parser.add_argument("--case-id", required=True, help="Case ID to upload photos for")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket name")
    parser.add_argument("--dry-run", action="store_true", help="Only report what would be done")
    args = parser.parse_args()

    uploaded = 0
    skipped = 0
    errors = []

    for person_name, api_url in WIKIPEDIA_PHOTO_SOURCES.items():
        logger.info("Processing %s...", person_name)

        # Try Wikipedia first, fall back to generated mugshot placeholder
        img_bytes = fetch_wikipedia_thumbnail(api_url)
        if img_bytes:
            resized = resize_to_square(img_bytes, 200)
            source = "wikipedia"
        else:
            logger.info("Wikipedia unavailable for %s — generating mugshot placeholder", person_name)
            resized = generate_mugshot_placeholder(person_name, 200)
            source = "generated"
            if not resized:
                skipped += 1
                errors.append(f"{person_name}: Pillow not available for placeholder generation")
                continue

        # Upload to S3
        s3_key = f"cases/{args.case_id}/face-crops/demo/{person_name}.jpg"
        try:
            upload_to_s3(args.bucket, s3_key, resized, dry_run=args.dry_run)
            uploaded += 1
            logger.info("  Source: %s, Size: %d bytes", source, len(resized))
        except Exception as e:
            logger.error("Failed to upload %s: %s", person_name, str(e)[:200])
            errors.append(f"{person_name}: upload failed — {str(e)[:100]}")

        time.sleep(2)  # Rate limit between Wikipedia API calls

    print(f"\n{'=' * 50}")
    print(f"Demo Photo Setup Complete")
    print(f"  Uploaded: {uploaded}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {len(errors)}")
    if errors:
        for e in errors:
            print(f"    - {e}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
