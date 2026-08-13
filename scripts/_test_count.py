"""Test what format counts come back in."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + CASE_ID

r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
    Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID,
        "query": "g.V().hasLabel('" + LABEL + "').hasNot('source').has('entity_type','person').count()",
        "timeout": 30}))
d = json.loads(r["Payload"].read().decode())

print("Full response keys:", list(d.keys()))
print("result type:", type(d.get("result")))
print("result value:", repr(d.get("result"))[:500])

# If it's a string, try to parse it
result = d.get("result")
if isinstance(result, str):
    print("\nIt's a STRING — need to parse")
    # Try to extract the number
    if "@value" in result:
        import re
        match = re.search(r"'@value': (\d+)", result)
        if match:
            print(f"  Extracted count: {match.group(1)}")
