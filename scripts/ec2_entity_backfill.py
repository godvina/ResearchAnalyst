#!/usr/bin/env python3
"""EC2 entity extraction backfill — runs unattended, self-terminates when done."""
import json
import time
import boto3

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
CASE_IDS = [
    ("7f05e8d5-4492-4f19-8894-25367606db96", "Epstein Main"),
    ("ed0b6c27-3b6b-4255-b9d0-efe8f4383a99", "Epstein Combined"),
]
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
BATCH_SIZE = 10

lam = boto3.client("lambda", region_name=REGION)

# Get count
for CASE_ID, CASE_NAME in CASE_IDS:
    print(f"\n{'='*60}")
    print(f"Processing: {CASE_NAME} ({CASE_ID})")
    print(f"{'='*60}")

    resp = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
                      Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}))
    result = json.loads(resp["Payload"].read().decode())
    missing = result.get("missing_count", 0)
    has = result.get("has_entities_count", 0)
    print(f"Docs with entities: {has:,}")
    print(f"Docs missing entities: {missing:,}")

    if missing == 0:
        print("All docs have entities. Skipping.")
        continue

    total_processed = 0
    total_entities = 0
    total_errors = 0
    start = time.time()
    batch_num = 0

    print(f"Processing {missing:,} docs in batches of {BATCH_SIZE}...")

    while True:
        batch_num += 1
        try:
            resp = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
                              Payload=json.dumps({"action": "backfill_entities_batch", "case_id": CASE_ID, "batch_size": BATCH_SIZE}))
            result = json.loads(resp["Payload"].read().decode())
        except Exception as e:
            total_errors += 1
            print(f"Batch {batch_num} error: {e}")
            if total_errors > 20:
                print("Too many errors, stopping.")
                break
            time.sleep(10)
            continue

        if "error" in result:
            total_errors += 1
            print(f"Batch {batch_num} Lambda error: {str(result)[:200]}")
            if total_errors > 20:
                break
            time.sleep(5)
            continue

        processed = result.get("processed", 0)
        entities = result.get("entities_extracted", 0)
        remaining = result.get("remaining", 0)
        total_processed += processed
        total_entities += entities

        if batch_num % 50 == 0:
            elapsed = time.time() - start
            rate = total_processed / max(elapsed, 1) * 60
            print(f"Batch {batch_num}: {total_processed:,} docs, {total_entities:,} entities, "
                  f"{remaining:,} remaining, {rate:.0f} docs/min, {total_errors} errors")

        if processed == 0:
            print(f"No more docs to process at batch {batch_num}.")
            break

        time.sleep(1)

    elapsed = time.time() - start

    # Refresh stats
    try:
        resp = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
                          Payload=json.dumps({"action": "refresh_case_stats", "case_id": CASE_ID}))
        stats = json.loads(resp["Payload"].read().decode())
        print(f"Stats: docs={stats.get('document_count','?')}, entities={stats.get('entity_count','?')}")
    except Exception:
        pass

    print(f"\n{CASE_NAME} Complete: {total_processed:,} docs, {total_entities:,} entities, "
          f"{total_errors} errors, {elapsed/60:.1f} min")

print(f"\n{'='*60}")
print("All cases complete!")
print(f"{'='*60}")
