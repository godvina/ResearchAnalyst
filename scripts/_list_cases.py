"""List all cases to find Ancient Aliens case ID."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
r = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({"action": "list_cases"})
)
d = json.loads(r["Payload"].read().decode())
cases = d.get("cases", d.get("case_files", []))
for c in cases:
    name = c.get("topic_name", c.get("name", "?"))
    cid = c.get("case_id", "?")
    if "alien" in name.lower() or "ancient" in name.lower() or "irish" in name.lower():
        print(f"*** {cid} | {name}")
    else:
        print(f"    {cid} | {name}")
