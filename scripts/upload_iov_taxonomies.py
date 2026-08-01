"""Upload IoV taxonomy JSON configs to S3.

Validates each file before upload, then uploads to:
  s3://{bucket}/config/iov_taxonomies/{case_type}.json

Uploads 6 small JSON files (<5KB each). No bulk processing, no EC2, no Bedrock.

Usage:
    python scripts/upload_iov_taxonomies.py
"""

import json
import os
import sys

import boto3

BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
LOCAL_DIR = os.path.join(os.path.dirname(__file__), "..", "config", "iov_taxonomies")
S3_PREFIX = "config/iov_taxonomies"

CASE_TYPES = [
    "monopolization",
    "price_fixing",
    "criminal_cartel",
    "procurement_collusion",
    "market_allocation",
    "merger_review",
]


def validate_hierarchy(data: dict) -> tuple:
    """Validate hierarchy structure. Returns (is_valid, error_message)."""
    if not data.get("case_type"):
        return False, "Missing case_type"
    if not data.get("version"):
        return False, "Missing version"
    categories = data.get("categories")
    if not categories or not isinstance(categories, list):
        return False, "Missing or empty categories"
    for i, cat in enumerate(categories):
        if not cat.get("name"):
            return False, f"Category {i} missing name"
        if not cat.get("indicators") or not isinstance(cat["indicators"], list):
            return False, f"Category '{cat.get('name', i)}' missing indicators"
    return True, ""


def main():
    s3 = boto3.client("s3", region_name=REGION)
    local_dir = os.path.abspath(LOCAL_DIR)

    print(f"Uploading IoV taxonomies from: {local_dir}")
    print(f"Target: s3://{BUCKET}/{S3_PREFIX}/")
    print()

    success = 0
    failed = 0

    for case_type in CASE_TYPES:
        filename = f"{case_type}.json"
        filepath = os.path.join(local_dir, filename)

        if not os.path.exists(filepath):
            print(f"  ❌ {filename} — FILE NOT FOUND")
            failed += 1
            continue

        # Validate
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  ❌ {filename} — INVALID JSON: {e}")
                failed += 1
                continue

        is_valid, error = validate_hierarchy(data)
        if not is_valid:
            print(f"  ❌ {filename} — VALIDATION FAILED: {error}")
            failed += 1
            continue

        # Count indicators
        indicator_count = 0
        for cat in data["categories"]:
            indicator_count += len(cat.get("indicators", []))
            for sub in cat.get("sub_categories", []):
                indicator_count += len(sub.get("indicators", []))

        # Upload
        s3_key = f"{S3_PREFIX}/{filename}"
        try:
            s3.put_object(
                Bucket=BUCKET,
                Key=s3_key,
                Body=json.dumps(data, indent=2),
                ContentType="application/json",
            )
            print(f"  ✅ {filename} — uploaded ({len(data['categories'])} categories, {indicator_count} indicators)")
            success += 1
        except Exception as e:
            print(f"  ❌ {filename} — UPLOAD FAILED: {e}")
            failed += 1

    print()
    print(f"Done: {success} uploaded, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
