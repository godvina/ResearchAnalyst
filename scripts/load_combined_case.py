"""Load combined Epstein case — DataSet 1-5 (3,800) + DataSet 11 (5,000) into a NEW case.

Creates a new case "Epstein Combined (DS1-5 + DS11)" via the API,
then loads both datasets into it. The original Epstein Main case is untouched.

Usage:
    python scripts/load_combined_case.py --confirm
    python scripts/load_combined_case.py --dry-run
"""
import argparse
import base64
import json
import sys
import time
import urllib.request

import boto3

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

# DataSet 1-5 pre-extracted text (source bucket)
DS15_PREFIXES = [f"textract-output/DataSet{i}/" for i in range(1, 6)]
# DataSet 11 pre-extracted text (main bucket)
DS11_PREFIX = "textract-output/DataSet11/"

BATCH_SIZE = 50
BLANK_THRESHOLD = 10

s3 = boto3.client("s3", region_name=REGION)


def create_case(name, description):
    """Create a new case via the API. Returns case_id."""
    url = f"{API_URL}/case-files"
    body = json.dumps({
        "topic_name": name,
        "description": description,
        "search_tier": "enterprise",
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
    case_id = result.get("case_id") or result.get("case_file", {}).get("case_id")
    print(f"Created case: {case_id}")
    print(f"  Name: {name}")
    return case_id


def list_ds15_files():
    """List all DataSet 1-5 text files from source bucket."""
    files = []
    for prefix in DS15_PREFIXES:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".json") and obj["Size"] > 50:
                    files.append(("source", obj["Key"]))
    return files


def list_ds11_files():
    """List all DataSet 11 text files from main bucket."""
    files = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=DS11_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json") and obj["Size"] > 50:
                files.append(("main", obj["Key"]))
    return files


def read_text(bucket_type, s3_key):
    """Read extracted text from a JSON file."""
    bucket = SOURCE_BUCKET if bucket_type == "source" else BUCKET
    obj = s3.get_object(Bucket=bucket, Key=s3_key)
    data = json.loads(obj["Body"].read().decode())
    text = data.get("extractedText", "")
    source = data.get("sourceFile", s3_key.split("/")[-1].replace(".json", ""))
    return text, source


def ingest_batch(case_id, batch_texts, batch_num, total_batches):
    """Send a batch to the ingest API."""
    files_payload = []
    for text, source_filename in batch_texts:
        if not text or len(text.strip()) < BLANK_THRESHOLD:
            continue
        filename = source_filename
        if not filename.endswith(".txt"):
            filename = filename.replace(".json", ".txt").replace(".pdf", ".txt")
        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        files_payload.append({"filename": filename, "content_base64": text_b64})

    if not files_payload:
        return None

    url = f"{API_URL}/case-files/{case_id}/ingest"
    body = json.dumps({"files": files_payload}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            arn = result.get("execution_arn", "?")
            docs = result.get("documents_uploaded", 0)
            short_arn = arn.split(":")[-1] if ":" in str(arn) else arn
            print(f"  Batch {batch_num}/{total_batches}: {docs} docs -> {short_arn}")
            return arn
    except Exception as e:
        print(f"  Batch {batch_num}/{total_batches}: ERROR - {str(e)[:200]}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("Load Combined Epstein Case")
    print("  DataSet 1-5 (source bucket) + DataSet 11 (main bucket)")
    print("=" * 60)

    # List all files
    print("\nListing DataSet 1-5 files...")
    ds15 = list_ds15_files()
    print(f"  Found {len(ds15)} files")

    print("Listing DataSet 11 files...")
    ds11 = list_ds11_files()
    print(f"  Found {len(ds11)} files")

    all_files = ds15 + ds11
    print(f"\nTotal files to load: {len(all_files)}")
    total_batches = (len(all_files) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Batches of {BATCH_SIZE}: {total_batches}")

    if args.dry_run:
        print("\n[DRY RUN] Would create new case and load all files.")
        print(f"Estimated pipeline cost: ~${len(all_files) * 0.005:.2f}")
        return

    if not args.confirm:
        print("\nRun with --confirm to proceed.")
        return

    # Create new case
    case_id = create_case(
        "Epstein Combined (DS1-5 + DS11)",
        "Combined dataset: DataSet 1-5 (~3,800 docs) + DataSet 11 (~3,500 non-blank docs). "
        "Enterprise search tier for keyword + semantic + hybrid search.",
    )

    # Read all texts
    print(f"\nReading {len(all_files)} text files...")
    valid_texts = []
    blank = 0
    for i, (btype, key) in enumerate(all_files):
        text, source = read_text(btype, key)
        if text and len(text.strip()) >= BLANK_THRESHOLD:
            valid_texts.append((text, source))
        else:
            blank += 1
        if (i + 1) % 500 == 0:
            print(f"  Read {i+1}/{len(all_files)}...")

    print(f"Valid docs: {len(valid_texts)}, Blank skipped: {blank}")

    # Batch and send
    print(f"\nSending {len(valid_texts)} docs in batches of {BATCH_SIZE}...")
    executions = []
    total = (len(valid_texts) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(valid_texts), BATCH_SIZE):
        batch = valid_texts[i:i + BATCH_SIZE]
        num = (i // BATCH_SIZE) + 1
        arn = ingest_batch(case_id, batch, num, total)
        if arn:
            executions.append(arn)
        time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"DONE — {len(executions)} Step Functions executions triggered")
    print(f"  Case ID: {case_id}")
    print(f"  Total docs sent: {len(valid_texts)}")
    print(f"  Blanks skipped: {blank}")
    print(f"  Monitor: AWS Console -> Step Functions")
    print(f"{'=' * 60}")

    log = {
        "case_id": case_id,
        "case_name": "Epstein Combined (DS1-5 + DS11)",
        "executions": executions,
        "total_docs": len(valid_texts),
        "blanks_skipped": blank,
        "ds15_files": len(ds15),
        "ds11_files": len(ds11),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open("scripts/combined_load_executions.json", "w") as f:
        json.dump(log, f, indent=2)
    print(f"Log saved to scripts/combined_load_executions.json")


if __name__ == "__main__":
    main()
