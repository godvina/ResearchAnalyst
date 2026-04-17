"""Re-ingest Ancient Aliens case transcripts through Step Functions pipeline.

The 240 raw .txt files exist in S3 and the graph is populated in Neptune,
but the Aurora documents table is empty (pipeline failed previously due to
Lambda VPC timeouts — Issue 18/19 from lessons-learned).

This script:
1. Lists all raw document IDs from S3
2. Triggers Step Functions in batches of 40 docs (MaxConcurrency=5 in pipeline)
3. Waits between batches to avoid throttling

Usage:
    python scripts/reingest_ancient_aliens.py
    python scripts/reingest_ancient_aliens.py --batch-size 20 --dry-run
    python scripts/reingest_ancient_aliens.py --status
"""
import argparse
import boto3
import json
import time
import sys

CASE_ID = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"
BUCKET = "research-analyst-data-lake-974220725866"
RAW_PREFIX = f"cases/{CASE_ID}/raw/"
SFN_ARN = None  # Will be discovered


def discover_sfn_arn():
    """Find the ingestion pipeline state machine ARN."""
    sfn = boto3.client("stepfunctions", region_name="us-east-1")
    paginator = sfn.get_paginator("list_state_machines")
    for page in paginator.paginate():
        for sm in page["stateMachines"]:
            if "IngestionPipeline" in sm["name"] or "ingestion" in sm["name"].lower():
                return sm["stateMachineArn"]
    # Fallback — try the known ARN pattern
    return "arn:aws:states:us-east-1:974220725866:stateMachine:ResearchAnalystStack-IngestionPipeline"


def list_raw_document_ids():
    """List all document IDs from S3 raw/ prefix."""
    s3 = boto3.client("s3", region_name="us-east-1")
    doc_ids = []
    token = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": RAW_PREFIX, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            # Strip extension to get document_id
            doc_id = filename.rsplit(".", 1)[0] if "." in filename else filename
            if doc_id:
                doc_ids.append(doc_id)
        if not resp.get("IsTruncated"):
            break
        token = resp["NextContinuationToken"]
    return doc_ids


def submit_batch(sfn_arn, doc_ids, batch_num):
    """Submit a batch of document IDs to Step Functions."""
    sfn = boto3.client("stepfunctions", region_name="us-east-1")
    sfn_input = {
        "case_id": CASE_ID,
        "sample_mode": False,
        "upload_result": {
            "document_ids": doc_ids,
            "document_count": len(doc_ids),
        },
    }
    exec_name = f"aa-reingest-b{batch_num}-{int(time.time())}"
    resp = sfn.start_execution(
        stateMachineArn=sfn_arn,
        name=exec_name,
        input=json.dumps(sfn_input),
    )
    return resp.get("executionArn", "unknown")


def check_status():
    """Check recent Step Functions executions for this case."""
    sfn_arn = discover_sfn_arn()
    sfn = boto3.client("stepfunctions", region_name="us-east-1")
    resp = sfn.list_executions(
        stateMachineArn=sfn_arn,
        maxResults=30,
    )
    aa_execs = [e for e in resp["executions"] if "aa-reingest" in e.get("name", "")]
    if not aa_execs:
        print("No Ancient Aliens re-ingestion executions found.")
        return

    running = sum(1 for e in aa_execs if e["status"] == "RUNNING")
    succeeded = sum(1 for e in aa_execs if e["status"] == "SUCCEEDED")
    failed = sum(1 for e in aa_execs if e["status"] == "FAILED")
    print(f"Ancient Aliens re-ingestion: {running} running, {succeeded} succeeded, {failed} failed (of {len(aa_execs)} total)")
    for e in aa_execs[:10]:
        print(f"  {e['name']}: {e['status']} — started {e['startDate']}")


def main():
    parser = argparse.ArgumentParser(description="Re-ingest Ancient Aliens case")
    parser.add_argument("--batch-size", type=int, default=40, help="Docs per SFN execution")
    parser.add_argument("--dry-run", action="store_true", help="List docs without submitting")
    parser.add_argument("--status", action="store_true", help="Check execution status")
    parser.add_argument("--delay", type=int, default=10, help="Seconds between batches")
    args = parser.parse_args()

    if args.status:
        check_status()
        return

    print(f"Ancient Aliens Case Re-Ingestion")
    print(f"Case ID: {CASE_ID}")
    print(f"Bucket:  {BUCKET}")
    print()

    # 1. List documents
    print("Listing raw documents from S3...")
    doc_ids = list_raw_document_ids()
    print(f"Found {len(doc_ids)} raw documents")

    if not doc_ids:
        print("No documents found. Exiting.")
        return

    # 2. Batch them
    batches = [doc_ids[i:i + args.batch_size] for i in range(0, len(doc_ids), args.batch_size)]
    print(f"Will submit {len(batches)} batches of ~{args.batch_size} docs each")
    print()

    if args.dry_run:
        print("DRY RUN — not submitting. First 5 doc IDs:")
        for d in doc_ids[:5]:
            print(f"  {d}")
        return

    # 3. Discover SFN ARN
    sfn_arn = discover_sfn_arn()
    print(f"State Machine: {sfn_arn}")
    print()

    # 4. Submit batches
    for i, batch in enumerate(batches):
        arn = submit_batch(sfn_arn, batch, i + 1)
        print(f"  Batch {i+1}/{len(batches)}: {len(batch)} docs — {arn[:80]}...")
        if i < len(batches) - 1:
            print(f"  Waiting {args.delay}s before next batch...")
            time.sleep(args.delay)

    print()
    print(f"All {len(batches)} batches submitted. Monitor with:")
    print(f"  python scripts/reingest_ancient_aliens.py --status")


if __name__ == "__main__":
    main()
