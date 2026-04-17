"""Check entity extraction status for both cases and EC2 instances."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
ec2 = boto3.client("ec2", region_name="us-east-1")

cases = [
    ("7f05e8d5-4492-4f19-8894-25367606db96", "Epstein Main"),
    ("ed0b6c27-3b6b-4255-b9d0-efe8f4383a99", "Epstein Combined"),
]

for cid, name in cases:
    r = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
                   InvocationType="RequestResponse",
                   Payload=json.dumps({"action": "backfill_entities_count", "case_id": cid}))
    d = json.loads(r["Payload"].read().decode())
    has = d.get("has_entities_count", 0)
    missing = d.get("missing_count", 0)
    print(f"{name}: {has:,} with entities, {missing:,} remaining")

instances = [
    ("i-06144ab22c4a90751", "Main EC2"),
    ("i-0655e73c4f1789a32", "Combined EC2"),
]
for iid, label in instances:
    try:
        r = ec2.describe_instances(InstanceIds=[iid])
        state = r["Reservations"][0]["Instances"][0]["State"]["Name"]
        print(f"{label} ({iid}): {state}")
    except Exception as e:
        print(f"{label}: {e}")
