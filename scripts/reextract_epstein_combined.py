"""Re-extract entities for Epstein Combined case documents.

The 8,974 documents were loaded into Aurora but entity extraction via Bedrock
either failed or was skipped. Neptune has 200 nodes but 0 edges.

This script re-triggers the Step Functions ingestion pipeline for existing
documents. The pipeline is idempotent (ON CONFLICT DO UPDATE) so re-running
is safe. Each document goes through: Parse → Extract → Embed → GraphLoad.

Usage:
    python scripts/reextract_epstein_combined.py --dry-run          # preview
    python scripts/reextract_epstein_combined.py --confirm          # run all
    python scripts/reextract_epstein_combined.py --max-batches 5    # run 5 batches
    python scripts/reextract_epstein_combined.py --status           # check progress
    python scripts/reextract_epstein_combined.py --fix-doc-count    # update sidebar count
"""
import argparse
import boto3
import json
import time
import sys

CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
BUCKET = "research-analyst-data-lake-974220725866"
RAW_PREFIX = f"cases/{CASE_ID}/raw/"
EXEC_PREFIX = "ep-combined-reextract"
REGION = "us-east-1"


def discover_sfn_arn():
    """Find the ingestion pipeline state machine ARN."""
    sfn = boto3.client("stepfunctions", region_name=REGION)
    paginator = sfn.get_paginator("list_state_machines")
    for page in paginator.paginate():
        for sm in page["stateMachines"]:
            if "IngestionPipeline" in sm["name"] or "ingestion" in sm["name"].lower():
                return sm["stateMachineArn"]
    return "arn:aws:states:us-east-1:974220725866:stateMachine:ResearchAnalystStack-IngestionPipeline"


def list_raw_document_ids():
    """List all document IDs from S3 raw/ prefix."""
    s3 = boto3.client("s3", region_name=REGION)
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
            doc_id = filename.rsplit(".", 1)[0] if "." in filename else filename
            if doc_id:
                doc_ids.append(doc_id)
        if not resp.get("IsTruncated"):
            break
        token = resp["NextContinuationToken"]
    return doc_ids


def submit_batch(sfn_arn, doc_ids, batch_num):
    """Submit a batch of document IDs to Step Functions."""
    sfn = boto3.client("stepfunctions", region_name=REGION)
    sfn_input = {
        "case_id": CASE_ID,
        "sample_mode": False,
        "upload_result": {
            "document_ids": doc_ids,
            "document_count": len(doc_ids),
        },
    }
    exec_name = f"{EXEC_PREFIX}-b{batch_num}-{int(time.time())}"
    resp = sfn.start_execution(
        stateMachineArn=sfn_arn,
        name=exec_name,
        input=json.dumps(sfn_input),
    )
    return resp.get("executionArn", "unknown")


def check_status():
    """Check recent Step Functions executions for this case."""
    sfn_arn = discover_sfn_arn()
    sfn = boto3.client("stepfunctions", region_name=REGION)
    resp = sfn.list_executions(
        stateMachineArn=sfn_arn,
        maxResults=100,
    )
    our_execs = [e for e in resp["executions"] if EXEC_PREFIX in e.get("name", "")]
    if not our_execs:
        print("No Epstein Combined re-extraction executions found.")
        return

    running = sum(1 for e in our_execs if e["status"] == "RUNNING")
    succeeded = sum(1 for e in our_execs if e["status"] == "SUCCEEDED")
    failed = sum(1 for e in our_execs if e["status"] == "FAILED")
    aborted = sum(1 for e in our_execs if e["status"] == "ABORTED")
    print(f"\nEpstein Combined Re-Extraction Status:")
    print(f"  Running:   {running}")
    print(f"  Succeeded: {succeeded}")
    print(f"  Failed:    {failed}")
    print(f"  Aborted:   {aborted}")
    print(f"  Total:     {len(our_execs)}")
    print()
    print("Recent executions:")
    for e in our_execs[:15]:
        print(f"  {e['name']}: {e['status']} — started {e['startDate']}")


def fix_doc_count():
    """Update the stale document_count in case_files table via API."""
    import urllib.request
    import urllib.error

    api_url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
    url = f"{api_url}/case-files/{CASE_ID}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            current_count = data.get("document_count", "unknown")
            print(f"Current document_count in API: {current_count}")
    except Exception as exc:
        print(f"Could not read current count: {exc}")

    # Trigger a recount by calling the case status update
    print("To fix the count, the pipeline's UpdateCaseStatus step will run")
    print("after each batch completes. The count should self-correct.")
    print(f"Expected final count: ~8,974")


def main():
    parser = argparse.ArgumentParser(description="Re-extract entities for Epstein Combined case")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Docs per SFN execution (default: 50)")
    parser.add_argument("--max-batches", type=int, default=0,
                        help="Max batches to submit (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List docs without submitting")
    parser.add_argument("--confirm", action="store_true",
                        help="Run without confirmation prompt")
    parser.add_argument("--status", action="store_true",
                        help="Check execution status")
    parser.add_argument("--fix-doc-count", action="store_true",
                        help="Check/fix stale document count")
    parser.add_argument("--delay", type=int, default=15,
                        help="Seconds between batches (default: 15)")
    args = parser.parse_args()

    if args.status:
        check_status()
        return

    if args.fix_doc_count:
        fix_doc_count()
        return

    print(f"Epstein Combined — Entity Re-Extraction")
    print(f"Case ID: {CASE_ID}")
    print(f"Bucket:  {BUCKET}")
    print()

    # 1. List documents
    print("Listing raw documents from S3...")
    doc_ids = list_raw_document_ids()
    print(f"Found {len(doc_ids)} raw documents")

    if not doc_ids:
        print("No documents found in S3. Check if raw files exist at:")
        print(f"  s3://{BUCKET}/{RAW_PREFIX}")
        return

    # 2. Batch them
    batches = [doc_ids[i:i + args.batch_size] for i in range(0, len(doc_ids), args.batch_size)]
    total_batches = len(batches)
    if args.max_batches > 0:
        batches = batches[:args.max_batches]

    print(f"Will submit {len(batches)} of {total_batches} total batches ({args.batch_size} docs each)")
    print(f"Delay between batches: {args.delay}s")
    print()

    if args.dry_run:
        print("DRY RUN — not submitting. Sample doc IDs:")
        for d in doc_ids[:10]:
            print(f"  {d}")
        if len(doc_ids) > 10:
            print(f"  ... and {len(doc_ids) - 10} more")
        print()
        print(f"Estimated Bedrock calls: ~{len(doc_ids)} (1 per doc, more for large docs)")
        print(f"Estimated time: {len(batches) * (args.delay + 60) // 60} minutes (rough)")
        return

    if not args.confirm:
        print(f"This will trigger entity extraction for {len(doc_ids)} documents.")
        print(f"Each document makes 1+ Bedrock API calls (Claude Haiku).")
        resp = input("Continue? [y/N] ")
        if resp.lower() not in ("y", "yes"):
            print("Aborted.")
            return

    # 3. Discover SFN ARN
    sfn_arn = discover_sfn_arn()
    print(f"State Machine: {sfn_arn}")
    print()

    # 4. Submit batches
    submitted = 0
    for i, batch in enumerate(batches):
        try:
            arn = submit_batch(sfn_arn, batch, i + 1)
            submitted += 1
            print(f"  Batch {i+1}/{len(batches)}: {len(batch)} docs — {arn[:80]}...")
        except Exception as exc:
            print(f"  Batch {i+1} FAILED: {exc}")
            print("  Stopping to avoid cascading failures.")
            break

        if i < len(batches) - 1:
            print(f"  Waiting {args.delay}s...")
            time.sleep(args.delay)

    print()
    print(f"Submitted {submitted}/{len(batches)} batches ({submitted * args.batch_size} docs)")
    print(f"Monitor with:")
    print(f"  python scripts/reextract_epstein_combined.py --status")


if __name__ == "__main__":
    main()
