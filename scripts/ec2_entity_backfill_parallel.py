#!/usr/bin/env python3
"""EC2 entity extraction backfill — PARALLEL version with 20 threads."""
import json
import time
import boto3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
CASE_NAME = "Epstein Main"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
BATCH_SIZE = 20
NUM_THREADS = 20

# Thread-safe counters
lock = threading.Lock()
stats = {"processed": 0, "entities": 0, "errors": 0, "empty": 0}

def create_client():
    """Each thread gets its own boto3 client."""
    return boto3.client("lambda", region_name=REGION)

def process_batch(thread_id):
    """Process one batch of docs. Returns (processed, entities, error)."""
    lam = create_client()
    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "action": "backfill_entities_batch",
                "case_id": CASE_ID,
                "batch_size": BATCH_SIZE,
            }),
        )
        result = json.loads(resp["Payload"].read().decode())

        if "error" in result or resp.get("FunctionError"):
            return 0, 0, str(result)[:200]

        processed = result.get("processed", 0)
        entities = result.get("entities_extracted", 0)
        remaining = result.get("remaining", 0)
        return processed, entities, None

    except Exception as e:
        return 0, 0, str(e)[:200]

def worker(thread_id):
    """Worker thread — keeps processing batches until no more docs."""
    lam_check = create_client()
    consecutive_empty = 0

    while True:
        processed, entities, error = process_batch(thread_id)

        with lock:
            if error:
                stats["errors"] += 1
                if stats["errors"] % 20 == 0:
                    print(f"  Thread {thread_id}: error #{stats['errors']}: {error[:100]}")
                if stats["errors"] > 200:
                    print(f"  Thread {thread_id}: too many errors, stopping")
                    return
                time.sleep(2)
                continue

            if processed == 0:
                consecutive_empty += 1
                stats["empty"] += 1
                if consecutive_empty >= 3:
                    return  # No more docs for this thread
                time.sleep(1)
                continue

            consecutive_empty = 0
            stats["processed"] += processed
            stats["entities"] += entities

        time.sleep(0.2)  # Small delay between batches per thread

print(f"{'='*60}")
print(f"PARALLEL Entity Extraction: {CASE_NAME}")
print(f"Threads: {NUM_THREADS}, Batch size: {BATCH_SIZE}")
print(f"{'='*60}")

# Check initial count
lam = boto3.client("lambda", region_name=REGION)
resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
)
result = json.loads(resp["Payload"].read().decode())
has = result.get("has_entities_count", 0)
missing = result.get("missing_count", 0)
print(f"Starting: {has:,} with entities, {missing:,} remaining")

if missing == 0:
    print("All docs have entities. Nothing to do.")
    exit(0)

start = time.time()

# Progress reporter thread
def progress_reporter():
    while True:
        time.sleep(60)
        elapsed = time.time() - start
        with lock:
            rate = stats["processed"] / max(elapsed, 1) * 60
            print(f"  PROGRESS: {stats['processed']:,} docs, {stats['entities']:,} entities, "
                  f"{stats['errors']:,} errors, {rate:.0f} docs/min, {elapsed/60:.1f} min elapsed")
        # Check remaining
        try:
            r = create_client().invoke(
                FunctionName=LAMBDA_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
            )
            d = json.loads(r["Payload"].read().decode())
            remaining = d.get("missing_count", 0)
            has_now = d.get("has_entities_count", 0)
            print(f"  STATUS: {has_now:,} with entities, {remaining:,} remaining")
            if remaining == 0:
                return
        except Exception:
            pass

reporter = threading.Thread(target=progress_reporter, daemon=True)
reporter.start()

# Launch worker threads
print(f"\nLaunching {NUM_THREADS} worker threads...")
with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
    futures = [executor.submit(worker, i) for i in range(NUM_THREADS)]
    for f in as_completed(futures):
        try:
            f.result()
        except Exception as e:
            print(f"  Thread exception: {e}")

elapsed = time.time() - start

# Final count
resp = lam.invoke(
    FunctionName=LAMBDA_NAME,
    InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
)
result = json.loads(resp["Payload"].read().decode())

# Refresh stats
try:
    lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "refresh_case_stats", "case_id": CASE_ID}),
    )
except Exception:
    pass

print(f"\n{'='*60}")
print(f"PARALLEL Entity Extraction Complete")
print(f"  Processed: {stats['processed']:,}")
print(f"  Entities:  {stats['entities']:,}")
print(f"  Errors:    {stats['errors']:,}")
print(f"  Elapsed:   {elapsed/60:.1f} minutes")
print(f"  Rate:      {stats['processed']/max(elapsed,1)*60:.0f} docs/min")
print(f"  Final:     {result.get('has_entities_count', '?'):,} with entities, {result.get('missing_count', '?'):,} remaining")
print(f"{'='*60}")
