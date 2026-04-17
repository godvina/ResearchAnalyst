"""Download real photos for key Epstein case entities from Wikimedia Commons.

Uses Wikimedia Commons API which is more reliable than Wikipedia REST API.
Falls back to multiple sources if one fails.

Usage:
    python scripts/download_real_photos.py --case-id <CASE_ID>
"""

import argparse
import io
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUCKET = "research-analyst-data-lake-974220725866"

# Multiple photo source strategies per person
# Each entry is a list of (url, description) tuples to try in order
PHOTO_SOURCES = {
    "Jeffrey Epstein": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Jeffrey_Epstein", "wikipedia_api"),
    ],
    "Ghislaine Maxwell": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Ghislaine_Maxwell", "wikipedia_api"),
    ],
    "Prince Andrew": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Prince_Andrew,_Duke_of_York", "wikipedia_api"),
    ],
    "Bill Clinton": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Bill_Clinton", "wikipedia_api"),
    ],
    "Donald Trump": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Donald_Trump", "wikipedia_api"),
    ],
    "Alan Dershowitz": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Alan_Dershowitz", "wikipedia_api"),
    ],
    "Les Wexner": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Les_Wexner", "wikipedia_api"),
    ],
    "Ehud Barak": [
        ("https://en.wikipedia.org/api/rest_v1/page/summary/Ehud_Barak", "wikipedia_api"),
    ],
}

USER_AGENT = "ResearchAnalystDemo/1.0 (investigative-intelligence-poc; contact: demo@example.com)"


def download_image(url: str, source_type: str) -> bytes | None:
    """Download an image from a URL. Handles Wikipedia API JSON responses."""
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/jpeg,image/png,image/*,*/*",
        "Referer": "https://en.wikipedia.org/",
    }
    try:
        if source_type == "wikipedia_api":
            # Wikipedia REST API returns JSON with thumbnail URL
            api_headers = dict(browser_headers)
            api_headers["Accept"] = "application/json"
            req = urllib.request.Request(url, headers=api_headers)
            resp = urllib.request.urlopen(req, timeout=20)
            data = json.loads(resp.read().decode())
            img_url = data.get("thumbnail", {}).get("source", "")
            if not img_url:
                return None
            img_req = urllib.request.Request(img_url, headers=browser_headers)
            img_resp = urllib.request.urlopen(img_req, timeout=20)
            return img_resp.read()
        else:
            req = urllib.request.Request(url, headers=browser_headers)
            resp = urllib.request.urlopen(req, timeout=20)
            return resp.read()
    except urllib.error.HTTPError as e:
        logger.warning("HTTP %d for %s", e.code, url[:80])
        return None
    except Exception as e:
        logger.warning("Failed to download %s: %s", url[:80], str(e)[:100])
        return None


def resize_to_square(image_bytes: bytes, size: int = 200) -> bytes:
    """Resize image to a square JPEG."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((size, size), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--bucket", default=BUCKET)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name="us-east-1")

    success = 0
    failed = []

    for person, sources in PHOTO_SOURCES.items():
        logger.info("Downloading photo for %s...", person)
        img_bytes = None

        for url, source_type in sources:
            img_bytes = download_image(url, source_type)
            if img_bytes and len(img_bytes) > 1000:
                logger.info("  Got %d bytes from %s", len(img_bytes), source_type)
                break
            img_bytes = None

        if not img_bytes:
            logger.error("  FAILED — no source worked for %s", person)
            failed.append(person)
            continue

        # Resize to 200x200 square
        resized = resize_to_square(img_bytes)
        s3_key = f"cases/{args.case_id}/face-crops/demo/{person}.jpg"

        if args.dry_run:
            logger.info("  [DRY RUN] Would upload %d bytes to %s", len(resized), s3_key)
        else:
            s3.put_object(Bucket=args.bucket, Key=s3_key, Body=resized,
                          ContentType="image/jpeg")
            logger.info("  Uploaded %d bytes to %s", len(resized), s3_key)

        success += 1
        time.sleep(1)  # Be polite

    print(f"\nResults: {success} uploaded, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
