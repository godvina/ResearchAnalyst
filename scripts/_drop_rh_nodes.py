"""Drop rhowardstone nodes that were loaded with old ID format."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

def gremlin(q, timeout=120):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q, "timeout": timeout}))
    return json.loads(r["Payload"].read().decode())

label = f"Entity_{CASE_ID}"

# Count nodes with source=rhowardstone_kg
r = gremlin(f"g.V().hasLabel('{label}').has('source','rhowardstone_kg').count()")
print(f"Rhowardstone nodes to drop: {r.get('result', r.get('error',''))}")

# Drop them in batches
r = gremlin(f"g.V().hasLabel('{label}').has('source','rhowardstone_kg').drop()", timeout=300)
print(f"Drop result: {r.get('result', r.get('error',''))}")

# Verify
r = gremlin(f"g.V().hasLabel('{label}').has('source','rhowardstone_kg').count()")
print(f"Remaining: {r.get('result', r.get('error',''))}")
