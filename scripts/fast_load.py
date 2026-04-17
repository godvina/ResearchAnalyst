"""Fast batch loader — caches S3 file list, fires parallel Step Functions.

Usage:
    python scripts/fast_load.py --count 100          # load 100 docs
    python scripts/fast_load.py --count 10000        # load 10K docs
    python scripts/fast_load.py --count 10000 --parallel 20  # 20 parallel SFNs
    python scripts/fast_load.py --status             # check running SFNs
    python scripts/fast_load.py --entity-resolution  # run ER only
"""
import argparse, boto3, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
SOURCE_BUCKET = "research-analyst-data-lake-974220725866"
SOURCE_PREFIX = f"cases/{CASE_ID}/raw/"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CACHE_FILE = Path("scripts/s3_file_cache.json")
PROGRESS_FILE = Path("scripts/fast_load_progress.json")
SUB_BATCH = 50  # docs per SFN execution

def list_s3_files():
    """List all files under prefix, with local cache."""
    if CACHE_FILE.exists():
        data = json.loads(CACHE_FILE.read_text())
        print(f"  Using cached file list: {len(data)} files")
        return data

    print(f"  Scanning S3 {SOURCE_BUCKET}/{SOURCE_PREFIX} ...")
    s3 = boto3.client("s3")
    files = []
    token = None
    while True:
        kw = {"Bucket": SOURCE_BUCKET, "Prefix": SOURCE_PREFIX, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith((".pdf", ".txt", ".png", ".jpg", ".jpeg", ".tiff")):
                files.append(key)
        if not resp.get("IsTruncated"):
            break
        token = resp["NextContinuationToken"]
        if len(files) % 10000 == 0:
            print(f"    ...{len(files)} files found so far")

    CACHE_FILE.write_text(json.dumps(files))
    print(f"  Cached {len(files)} files to {CACHE_FILE}")
    return files


def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"processed": 0, "cursor": 0}

def save_progress(prog):
    PROGRESS_FILE.write_text(json.dumps(prog, indent=2))

def submit_batch(s3_keys):
    """Submit a sub-batch directly to Step Functions, bypassing the API.

    The ingest API expects base64-encoded file content, but we already have
    files in S3. So we trigger the Step Functions pipeline directly with
    document_ids derived from the S3 keys.
    """
    sfn = boto3.client("stepfunctions", region_name="us-east-1")
    # Extract document_ids from S3 keys (filename without extension)
    doc_ids = []
    for key in s3_keys:
        filename = key.split("/")[-1]
        doc_id = filename.rsplit(".", 1)[0] if "." in filename else filename
        doc_ids.append(doc_id)

    sfn_input = {
        "case_id": CASE_ID,
        "sample_mode": False,
        "upload_result": {
            "document_ids": doc_ids,
            "document_count": len(doc_ids),
        },
    }

    try:
        import time as _t
        execution_name = f"fast-{CASE_ID[:8]}-{int(_t.time())}-{hash(s3_keys[0]) % 10000}"
        resp = sfn.start_execution(
            stateMachineArn="arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion",
            name=execution_name,
            input=json.dumps(sfn_input),
        )
        return resp.get("executionArn", "submitted")
    except Exception as e:
        return f"ERROR: {e}"

def run_load(count, parallel):
    files = list_s3_files()
    prog = load_progress()
    cursor = prog["cursor"]

    remaining = files[cursor:cursor + count]
    if not remaining:
        print(f"No more files to process (cursor at {cursor}/{len(files)})")
        return

    print(f"\n  Loading {len(remaining)} docs (cursor {cursor}, parallel {parallel})")
    print(f"  Sub-batches of {SUB_BATCH} = {(len(remaining) + SUB_BATCH - 1) // SUB_BATCH} SFN executions\n")

    batches = [remaining[i:i+SUB_BATCH] for i in range(0, len(remaining), SUB_BATCH)]
    arns = []
    active = 0

    for i, batch in enumerate(batches):
        arn = submit_batch(batch)
        arns.append(arn)
        active += 1
        status = "✓" if not arn.startswith("ERROR") else "✗"
        print(f"  [{i+1}/{len(batches)}] {status} Submitted {len(batch)} docs — {arn[:60]}...")

        # Throttle to stay within parallel limit
        if active >= parallel and i < len(batches) - 1:
            print(f"    Waiting 5s (parallel limit {parallel})...")
            time.sleep(5)
            active = max(0, active - 2)  # Assume some finished

    # Update progress
    prog["cursor"] = cursor + len(remaining)
    prog["processed"] = prog.get("processed", 0) + len(remaining)
    prog["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    prog["sfn_count"] = len(arns)
    save_progress(prog)

    errors = [a for a in arns if a.startswith("ERROR")]
    print(f"\n  Done! Submitted {len(arns)} SFN executions ({len(errors)} errors)")
    print(f"  Progress: {prog['processed']} total docs, cursor at {prog['cursor']}/{len(files)}")
    print(f"  SFNs are processing in background — check with: python scripts/fast_load.py --status")
    if errors:
        for e in errors[:5]:
            print(f"    {e}")

def check_status():
    """Check Step Function execution status."""
    sfn = boto3.client("stepfunctions")
    # List recent executions
    try:
        resp = sfn.list_executions(
            stateMachineArn="arn:aws:states:us-east-1:974220725866:stateMachine:ResearchAnalystStack-IngestionPipeline",
            maxResults=20,
        )
        running = sum(1 for e in resp["executions"] if e["status"] == "RUNNING")
        succeeded = sum(1 for e in resp["executions"] if e["status"] == "SUCCEEDED")
        failed = sum(1 for e in resp["executions"] if e["status"] == "FAILED")
        print(f"  Recent SFN executions: {running} running, {succeeded} succeeded, {failed} failed (last 20)")
    except Exception as e:
        print(f"  Could not check SFN status: {e}")
        print("  Try checking in the AWS Console: Step Functions > State Machines")

def run_entity_resolution():
    print("  Running entity resolution...")
    url = f"{API_URL}/case-files/{CASE_ID}/entity-resolution"
    body = json.dumps({"mode": "no-llm"}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            print(f"  Result: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"  Entity resolution failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fast batch loader")
    parser.add_argument("--count", type=int, default=100, help="Number of docs to load")
    parser.add_argument("--parallel", type=int, default=10, help="Max parallel SFN executions")
    parser.add_argument("--status", action="store_true", help="Check SFN execution status")
    parser.add_argument("--entity-resolution", action="store_true", help="Run entity resolution")
    parser.add_argument("--clear-cache", action="store_true", help="Clear S3 file cache")
    args = parser.parse_args()

    if args.clear_cache:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            print("Cache cleared.")
        sys.exit(0)

    if args.status:
        check_status()
        prog = load_progress()
        print(f"  Local progress: {prog}")
        sys.exit(0)

    if args.entity_resolution:
        run_entity_resolution()
        sys.exit(0)

    run_load(args.count, args.parallel)
