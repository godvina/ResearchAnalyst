"""Invoke Neptune-Aurora sync asynchronously."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
payload = {
    "action": "sync_neptune_to_aurora",
    "case_id": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
}

print("Invoking Lambda asynchronously...")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="Event",
    Payload=json.dumps(payload),
)
print(f"Status: {resp['StatusCode']}")
print("Lambda invoked async. Check CloudWatch for results.")
