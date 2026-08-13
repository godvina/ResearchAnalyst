"""Get raw entity types from Neptune to understand response format."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + CASE_ID

def gremlin(q, timeout=300):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q, "timeout": timeout, "max_result_len": 50000}))
    return json.loads(r["Payload"].read().decode())

# Get a small sample of entity types to understand the format
result = gremlin("g.V().hasLabel('" + LABEL + "').hasNot('source').values('entity_type').dedup().limit(30)")
print("RAW RESULT:")
print(json.dumps(result, indent=2)[:3000])

print("\n\n--- Sample counts for specific types ---")
for t in ["person", "email", "address", "horse", "food", "object"]:
    r = gremlin("g.V().hasLabel('" + LABEL + "').hasNot('source').has('entity_type','" + t + "').count()")
    val = r.get("result", {})
    if isinstance(val, dict) and "@value" in val:
        count = val["@value"][0]["@value"] if val["@value"] else 0
    else:
        count = val
    print(f"  {t}: {count}")
