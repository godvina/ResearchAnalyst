"""Phase 1: Create "Epstein Combined" case and load DataSet 1-5 (~3,800 docs).

Creates a new case, loads DS1-5 pre-extracted text JSONs from the source bucket.
Saves the case_id to scripts/epstein_combined_case.json for Phase 2 to reuse.

The existing "Epstein Main" (7f05e8d5) is NOT touched.

Usage:
    python scripts/phase1_load_ds15.py --dry-run   # see file counts and cost estimate
    python scripts/phase1_load_ds15.py --confirm    # actually run it
"""
import argparse
import base64
import json
import time
import urllib.request

import boto3

REGION = "us-east-1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

DS15_PREFIXES = [f"textract-output/DataSet{i}/" for i in range(1, 6)]

BATCH_SIZE = 50
BLANK_THRESHOLD = 10
CASE_FILE = "scripts/epstein_combined_case.json"

s3 = boto3.client("s3", region_name=REGION)


def create_case(name, description):
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
    return case_id


def list_ds15_files():
    files = []
    for prefix in DS15_PREFIXES:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".json") and obj["Size"] > 50:
                    files.append(obj["Key"])
    return files


def read_text(s3_key):
    obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=s3_key)
    data = json.loads(obj["Body"].read().decode())
    text = data.get("extractedText", "")
    source = data.get("sourceFile", s3_key.split("/")[-1].replace(".json", ""))
    return text, source


def ingest_batch(case_id, batch_texts, batch_num, total_batches):
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
    parser = argparse.ArgumentParser(description="Phase 1: Load DS1-5 into new Epstein Combined case")
    parser.add_argument("--confirm", action="store_true", help="Actually create case and load")
    parser.add_argument("--dry-run", action="store_true", help="Just show file counts")
    args = parser.parse_args()

    print("=" * 60)
    print("PHASE 1: Create Epstein Combined + Load DataSet 1-5")
    print("  Source: pre-extracted text JSONs from source bucket")
    print("  Epstein Main (7f05e8d5) is NOT touched")
    print("=" * 60)

    print("\nListing DataSet 1-5 files...")
    ds15 = list_ds15_files()
    print(f"  Found {len(ds15)} files across DataSet 1-5")

    if args.dry_run:
        print(f"\n[DRY RUN] Would create new case and load {len(ds15)} files.")
        print(f"  Estimated Bedrock cost: ~${len(ds15) * 0.004:.2f}")
        print(f"  Batches of {BATCH_SIZE}: {(len(ds15) + BATCH_SIZE - 1) // BATCH_SIZE}")
        print(f"\nAfter Phase 1 completes:")
        print(f"  - Compare Epstein Combined graph vs Epstein Main (7f05e8d5)")
        print(f"  - Then run Phase 2: python scripts/phase2_load_ds11.py --confirm")
        return

    if not args.confirm:
        print("\nRun with --confirm to proceed, or --dry-run to preview.")
        return

    # Create the new case
    case_id = create_case(
        "Epstein Combined",
        "Combined Epstein dataset. Phase 1: DataSet 1-5 (~3,800 docs). "
        "Phase 2 will add DataSet 11 (~3,466 docs). Enterprise search tier.",
    )
    print(f"\nCreated case: {case_id}")
    print(f"  Name: Epstein Combined")

    # Save case_id for Phase 2
    case_info = {
        "case_id": case_id,
        "case_name": "Epstein Combined",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "phase1_status": "in_progress",
    }
    with open(CASE_FILE, "w") as f:
        json.dump(case_info, f, indent=2)
    print(f"  Case ID saved to {CASE_FILE} (Phase 2 will read this)")

    # Read all DS1-5 texts
    print(f"\nReading {len(ds15)} text files from S3...")
    valid_texts = []
    blank = 0
    for i, key in enumerate(ds15):
        text, source = read_text(key)
        if text and len(text.strip()) >= BLANK_THRESHOLD:
            valid_texts.append((text, source))
        else:
            blank += 1
        if (i + 1) % 500 == 0:
            print(f"  Read {i+1}/{len(ds15)}...")

    print(f"  Valid docs: {len(valid_texts)}, Blank skipped: {blank}")

    # Batch and send
    total_batches = (len(valid_texts) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\nSending {len(valid_texts)} docs in {total_batches} batches...")
    executions = []
    for i in range(0, len(valid_texts), BATCH_SIZE):
        batch = valid_texts[i:i + BATCH_SIZE]
        num = (i // BATCH_SIZE) + 1
        arn = ingest_batch(case_id, batch, num, total_batches)
        if arn:
            executions.append(arn)
        time.sleep(2)

    # Update case file with results
    case_info["phase1_status"] = "triggered"
    case_info["phase1_executions"] = len(executions)
    case_info["phase1_docs_sent"] = len(valid_texts)
    case_info["phase1_blanks_skipped"] = blank
    case_info["phase1_completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(CASE_FILE, "w") as f:
        json.dump(case_info, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"PHASE 1 COMPLETE — {len(executions)} Step Functions executions triggered")
    print(f"  Case ID: {case_id}")
    print(f"  Docs sent: {len(valid_texts)}")
    print(f"  Blanks skipped: {blank}")
    print(f"  Monitor: AWS Console -> Step Functions")
    print(f"\nNEXT STEPS:")
    print(f"  1. Wait for Step Functions to finish processing")
    print(f"  2. Compare Epstein Combined vs Epstein Main in the UI")
    print(f"  3. When ready: python scripts/phase2_load_ds11.py --confirm")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
