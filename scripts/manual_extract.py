"""Manually run entity extraction batches to verify and push progress."""
import boto3
import json
import time

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

for i in range(10):
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "backfill_entities_batch",
            "case_id": CASE_ID,
            "batch_size": 20,
        }),
    )
    d = json.loads(r["Payload"].read().decode())
    processed = d.get("processed", 0)
    entities = d.get("entities_extracted", 0)
    remaining = d.get("remaining", 0)
    print(f"Batch {i+1}: +{processed} docs, +{entities} entities, {remaining} remaining")
    if processed == 0:
        print("No more docs to process")
        break
    time.sleep(1)

print("Done with manual batches")
