"""Sync Neptune entities to Aurora for Ancient Aliens — async."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
payload = {
    "action": "sync_neptune_to_aurora",
    "case_id": "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7",
}

print("Invoking sync async for Ancient Aliens...")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="Event",
    Payload=json.dumps(payload),
)
print(f"Status: {resp['StatusCode']}")
