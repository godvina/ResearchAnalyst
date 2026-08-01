"""Test if the entity backfill fix works — count should decrease after a batch."""
import boto3
import json
import time

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# Check count before
r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}))
before = json.loads(r["Payload"].read().decode())
print(f"BEFORE: has={before.get('has_entities_count')}, missing={before.get('missing_count')}")

# Run one batch
time.sleep(2)  # Wait for Lambda update
r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_batch", "case_id": CASE_ID, "batch_size": 5}))
batch = json.loads(r["Payload"].read().decode())
print(f"BATCH: processed={batch.get('processed')}, entities={batch.get('entities_extracted')}, remaining={batch.get('remaining')}, errors={batch.get('errors')}")
if "error" in batch:
    print(f"ERROR: {batch['error']}")

# Check count after
r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}))
after = json.loads(r["Payload"].read().decode())
print(f"AFTER: has={after.get('has_entities_count')}, missing={after.get('missing_count')}")

# Did it change?
before_missing = before.get("missing_count", 0)
after_missing = after.get("missing_count", 0)
if after_missing < before_missing:
    print(f"\n✅ FIX WORKS! Missing decreased by {before_missing - after_missing}")
else:
    print(f"\n❌ STILL BROKEN — missing didn't change ({before_missing} → {after_missing})")
