#!/usr/bin/env python3
"""EC2 entity extraction for Epstein Combined only."""
import json
import time
import boto3

CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
BATCH_SIZE = 10

lam = boto3.client("lambda", region_name=REGION)

resp = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
                  Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}))
result = json.loads(resp["Payload"].read().decode())
missing = result.get("missing_count", 0)
print(f"Epstein Combined: {missing} docs need entities")

if missing == 0:
    print("Done.")
    exit(0)

total_processed = 0
total_entities = 0
errors = 0
start = time.time()
batch = 0

while True:
    batch += 1
    try:
        resp = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
                          Payload=json.dumps({"action": "backfill_entities_batch", "case_id": CASE_ID, "batch_size": BATCH_SIZE}))
        r = json.loads(resp["Payload"].read().decode())
    except Exception as e:
        errors += 1
        if errors > 20: break
        time.sleep(10)
        continue

    if "error" in r:
        errors += 1
        if errors > 20: break
        time.sleep(5)
        continue

    p = r.get("processed", 0)
    total_processed += p
    total_entities += r.get("entities_extracted", 0)

    if batch % 20 == 0:
        elapsed = time.time() - start
        rate = total_processed / max(elapsed, 1) * 60
        print(f"Batch {batch}: {total_processed} docs, {total_entities} entities, {r.get('remaining',0)} left, {rate:.0f}/min")

    if p == 0: break
    time.sleep(1)

# Refresh
lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
           Payload=json.dumps({"action": "refresh_case_stats", "case_id": CASE_ID}))

print(f"Done: {total_processed} docs, {total_entities} entities, {errors} errors, {(time.time()-start)/60:.0f} min")
