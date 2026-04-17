"""Phase 2: Load DataSet 11 (~3,466 non-blank docs) into the existing Epstein Combined case.

Reads the case_id from scripts/epstein_combined_case.json (created by Phase 1).
Loads DS11 pre-extracted text JSONs from the main bucket into the same case.

Usage:
    python scripts/phase2_load_ds11.py --dry-run   # see file counts and cost estimate
    python scripts/phase2_load_ds11.py --confirm    # actually run it
"""
import argparse
import base64
import json
import os
import time
import urllib.request

import boto3

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

DS11_PREFIX = "textract-output/DataSet11/"

BATCH_SIZE = 50
BLANK_THRESHOLD = 10
CASE_FILE = "scripts/epstein_combined_case.json"

s3 = boto3.client("s3", region_name=REGION)


def load_case_id():
    if not os.path.exists(CASE_FILE):
        print(f"ERROR: {CASE_FILE} not found. Run Phase 1 first:")
        print(f"  python scripts/phase1_load_ds15.py --confirm")
        return None
    with open(CASE_FILE) as f:
        data = json.load(f)
    return data.get("case_id")


def list_ds11_files():
    files = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=DS11_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json") and obj["Size"] > 50:
                files.append(obj["Key"])
    return files


def read_text(s3_key):
    obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
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
    parser = argparse.ArgumentParser(description="Phase 2: Load DS11 into Epstein Combined case")
    parser.add_argument("--confirm", action="store_true", help="Actually load DS11")
    parser.add_argument("--dry-run", action="store_true", help="Just show file counts")
    args = parser.parse_args()

    print("=" * 60)
    print("PHASE 2: Load DataSet 11 into Epstein Combined")
    print("  Source: pre-extracted text JSONs from main bucket")
    print("  ~3,466 non-blank docs (of 5,000 total)")
    print("=" * 60)

    case_id = load_case_id()
    if not case_id:
        return
    print(f"\nUsing existing case: {case_id}")

    print("\nListing DataSet 11 files...")
    ds11 = list_ds11_files()
    print(f"  Found {len(ds11)} files")

    if args.dry_run:
        print(f"\n[DRY RUN] Would load {len(ds11)} files into case {case_id}.")
        print(f"  Estimated Bedrock cost: ~${len(ds11) * 0.003:.2f}")
        print(f"  Batches of {BATCH_SIZE}: {(len(ds11) + BATCH_SIZE - 1) // BATCH_SIZE}")
        print(f"  ~1,534 blank files will be skipped automatically")
        print(f"\nAfter Phase 2 completes:")
        print(f"  - Case will have ~7,200 total docs (DS1-5 + DS11)")
        print(f"  - Compare graph to Epstein Main (7f05e8d5)")
        print(f"  - Then clean up: python scripts/cleanup_v2_cases.py")
        return

    if not args.confirm:
        print("\nRun with --confirm to proceed, or --dry-run to preview.")
        return

    # Read all DS11 texts
    print(f"\nReading {len(ds11)} text files from S3...")
    valid_texts = []
    blank = 0
    for i, key in enumerate(ds11):
        text, source = read_text(key)
        if text and len(text.strip()) >= BLANK_THRESHOLD:
            valid_texts.append((text, source))
        else:
            blank += 1
        if (i + 1) % 500 == 0:
            print(f"  Read {i+1}/{len(ds11)}...")

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

    # Update case file
    with open(CASE_FILE) as f:
        case_info = json.load(f)
    case_info["phase2_status"] = "triggered"
    case_info["phase2_executions"] = len(executions)
    case_info["phase2_docs_sent"] = len(valid_texts)
    case_info["phase2_blanks_skipped"] = blank
    case_info["phase2_completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(CASE_FILE, "w") as f:
        json.dump(case_info, f, indent=2)

    # Record in ingestion ledger
    try:
        from ledger import record_load
        record_load(case_id, {
            "load_id": "phase2_ds11",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "DS11 pre-extracted text JSONs",
            "source_bucket": BUCKET,
            "source_prefix": DS11_PREFIX,
            "source_files_total": len(ds11),
            "blanks_skipped": blank,
            "docs_sent_to_pipeline": len(valid_texts),
            "sfn_executions": len(executions),
            "sfn_succeeded": "pending",
            "sfn_failed": "pending",
            "s3_docs_after": len(valid_texts),
            "notes": f"Phase 2. {blank} blanks skipped from {len(ds11)} source files.",
        })
        print("  Ledger updated: scripts/ingestion_ledger.json")
    except Exception as e:
        print(f"  Ledger update failed: {e}")

    print(f"\n{'=' * 60}")
    print(f"PHASE 2 COMPLETE — {len(executions)} Step Functions executions triggered")
    print(f"  Case ID: {case_id}")
    print(f"  DS11 docs sent: {len(valid_texts)}")
    print(f"  Blanks skipped: {blank}")
    print(f"  Monitor: AWS Console -> Step Functions")
    print(f"\nNEXT STEPS:")
    print(f"  1. Wait for Step Functions to finish processing")
    print(f"  2. Compare Epstein Combined (~7,200 docs) vs Epstein Main in the UI")
    print(f"  3. Clean up: python scripts/cleanup_v2_cases.py")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
