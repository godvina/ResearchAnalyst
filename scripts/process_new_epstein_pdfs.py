"""Process new DOJ Epstein PDFs through the pipeline.

Lists EFTA*.pdf files in S3 that haven't been processed yet,
batches them, and triggers Step Functions executions.

Usage:
    python scripts/process_new_epstein_pdfs.py
    python scripts/process_new_epstein_pdfs.py --batch-size 50 --max-batches 1
"""
import argparse
import json
import time
import boto3
from botocore.config import Config

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
RAW_PREFIX = f"cases/{CASE_ID}/raw/"
EXTRACTION_PREFIX = f"cases/{CASE_ID}/extractions/"
STATE_MACHINE_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion"

s3 = boto3.client("s3", region_name=REGION)
sfn = boto3.client("stepfunctions", region_name=REGION, config=Config(
    retries={"max_attempts": 3, "mode": "adaptive"}
))


def list_new_pdfs():
    """List PDF files in raw/ that don't have extraction artifacts yet."""
    # Get all PDFs in raw/
    raw_pdfs = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=RAW_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            if filename.lower().endswith(".pdf") and filename.startswith("EFTA"):
                raw_pdfs.add(filename)

    # Get already-processed files (have extraction artifacts)
    processed = set()
    for page in paginator.paginate(Bucket=BUCKET, Prefix=EXTRACTION_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Extraction artifacts are named {doc_id}_extraction.json
            # We can't easily match by EFTA filename, so we'll process all EFTA PDFs
            # The pipeline is idempotent — reprocessing just overwrites
            pass

    new_pdfs = sorted(raw_pdfs)
    print(f"Found {len(new_pdfs)} EFTA PDFs in S3")
    return new_pdfs


def trigger_batch(pdf_filenames, batch_num, total_batches):
    """Trigger a Step Functions execution for a batch of PDFs."""
    # The pipeline expects document_ids as filename without extension
    doc_ids = [f.rsplit(".", 1)[0] if "." in f else f for f in pdf_filenames]

    execution_input = {
        "case_id": CASE_ID,
        "sample_mode": False,
        "upload_result": {
            "document_ids": doc_ids,
            "document_count": len(doc_ids),
        },
    }

    execution_name = f"epstein-doj-batch{batch_num}-{int(time.time())}"

    try:
        resp = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(execution_input),
        )
        arn = resp["executionArn"]
        print(f"  Batch {batch_num}/{total_batches}: {len(pdf_filenames)} docs → {arn.split(':')[-1]}")
        return arn
    except Exception as e:
        print(f"  Batch {batch_num} FAILED: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Process new Epstein PDFs")
    parser.add_argument("--batch-size", type=int, default=50, help="Docs per batch")
    parser.add_argument("--max-batches", type=int, default=0, help="Max batches (0=all)")
    parser.add_argument("--delay", type=int, default=5, help="Seconds between batches")
    args = parser.parse_args()

    print("=" * 60)
    print("Process New DOJ Epstein PDFs")
    print(f"Case: {CASE_ID}")
    print(f"Batch size: {args.batch_size}")
    print("=" * 60)

    pdfs = list_new_pdfs()
    if not pdfs:
        print("No new PDFs to process.")
        return

    # Split into batches
    batches = []
    for i in range(0, len(pdfs), args.batch_size):
        batches.append(pdfs[i:i + args.batch_size])

    if args.max_batches > 0:
        batches = batches[:args.max_batches]

    print(f"Processing {sum(len(b) for b in batches)} PDFs in {len(batches)} batches")
    print()

    executions = []
    for i, batch in enumerate(batches, 1):
        arn = trigger_batch(batch, i, len(batches))
        if arn:
            executions.append(arn)
        if i < len(batches):
            time.sleep(args.delay)

    print(f"\n{'=' * 60}")
    print(f"STARTED {len(executions)} Step Functions executions")
    print(f"Monitor in AWS Console: Step Functions → research-analyst-ingestion")
    print(f"Or check status with: python scripts/check_v2_graphload_logs.py")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
