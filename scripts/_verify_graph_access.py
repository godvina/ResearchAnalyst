"""Verify Neptune graph access with the correct case ID. Read-only diagnostic."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")

def gremlin(query):
    event = {"action": "gremlin_query", "query": query}
    resp = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        Payload=json.dumps(event),
    )
    return json.loads(resp["Payload"].read())

neptune_case = "7f05e8d5-4492-4f19-8894-25367606db96"

# Verify vertices exist with correct label
print(f"Vertices with label Entity_{neptune_case}:")
r = gremlin(f"g.V().hasLabel('Entity_{neptune_case}').count()")
print(f"  {r}")

# Get top 5 entities by degree
print(f"\nTop 5 entities by connections:")
r = gremlin(f"g.V().hasLabel('Entity_{neptune_case}').has('entity_type', within('person','organization')).project('n','t').by('canonical_name').by('entity_type').order().by('n').limit(5)")
print(f"  {json.dumps(r)[:500]}")

# Check if parent_case_id column exists and is set
print(f"\nVerifying parent_case_id in Aurora...")
sql = "SELECT case_id, parent_case_id FROM case_files WHERE case_id = '7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e'"
event2 = {"httpMethod": "POST", "path": "/admin/run-migration", "body": json.dumps({"sql": sql}), "headers": {}, "pathParameters": {}, "queryStringParameters": None}
resp2 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq", Payload=json.dumps(event2))
result2 = json.loads(resp2["Payload"].read())
body2 = json.loads(result2.get("body", "{}"))
print(f"  {body2}")
