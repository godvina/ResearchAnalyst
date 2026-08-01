#!/usr/bin/env python3
"""Fast entity extraction — runs 10 parallel processes via multiprocessing."""
import json
import time
import os
import boto3
from multiprocessing import Process, Value

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
BATCH_SIZE = 20
NUM_WORKERS = 10

total_processed = Value('i', 0)
total_errors = Value('i', 0)

def worker(worker_id):
    """Each worker gets its own boto3 client and processes batches."""
    lam = boto3.client("lambda", region_name=REGION)
    consecutive_empty = 0
    local_processed = 0
    local_errors = 0

    while True:
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
                local_errors += 1
                with total_errors.get_lock():
                    total_errors.value += 1
                if local_errors > 30:
                    print(f"  Worker {worker_id}: too many errors, stopping")
                    return
                time.sleep(3)
                continue

            processed = result.get("processed", 0)
            if processed == 0:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    print(f"  Worker {worker_id}: no more docs, stopping")
                    return
                time.sleep(2)
                continue

            consecutive_empty = 0
            local_processed += processed
            with total_processed.get_lock():
                total_processed.value += processed

            time.sleep(0.5)

        except Exception as e:
            local_errors += 1
            with total_errors.get_lock():
                total_errors.value += 1
            time.sleep(5)

if __name__ == "__main__":
    lam = boto3.client("lambda", region_name=REGION)

    # Check initial count
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
    )
    result = json.loads(resp["Payload"].read().decode())
    has = result.get("has_entities_count", 0)
    missing = result.get("missing_count", 0)
    print(f"Starting: {has:,} with entities, {missing:,} remaining")
    print(f"Launching {NUM_WORKERS} workers...")

    start = time.time()
    workers = []
    for i in range(NUM_WORKERS):
        p = Process(target=worker, args=(i,))
        p.start()
        workers.append(p)
        time.sleep(0.5)  # Stagger starts

    # Monitor progress
    while any(p.is_alive() for p in workers):
        time.sleep(60)
        elapsed = time.time() - start
        rate = total_processed.value / max(elapsed, 1) * 60
        # Check actual count
        try:
            resp = lam.invoke(
                FunctionName=LAMBDA_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
            )
            r = json.loads(resp["Payload"].read().decode())
            actual_has = r.get("has_entities_count", 0)
            actual_missing = r.get("missing_count", 0)
            print(f"  PROGRESS: {actual_has:,} done, {actual_missing:,} remaining, "
                  f"{rate:.0f} docs/min, {total_errors.value} errors, {elapsed/60:.0f} min elapsed")
        except Exception:
            print(f"  PROGRESS: ~{total_processed.value} processed locally, {elapsed/60:.0f} min elapsed")

    for p in workers:
        p.join()

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

    print(f"\nDone: {result.get('has_entities_count', '?'):,} with entities, "
          f"{result.get('missing_count', '?'):,} remaining, "
          f"{total_errors.value} errors, {elapsed/60:.1f} min")
