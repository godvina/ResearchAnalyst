"""Check Neptune state for main case - verify vertices and edges exist."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
case_id = "7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e"
label = f"Entity_{case_id}"

def gremlin(query):
    event = {"action": "gremlin_query", "query": query}
    resp = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        Payload=json.dumps(event),
    )
    return json.loads(resp["Payload"].read())

# Count vertices
print("1. Vertex count...")
r = gremlin(f"g.V().hasLabel('{label}').count()")
print(f"   Result: {json.dumps(r)[:200]}")

# Count edges (total from these vertices)
print("2. Edge count (bothE from case vertices)...")
r = gremlin(f"g.V().hasLabel('{label}').bothE().count()")
print(f"   Result: {json.dumps(r)[:200]}")

# Sample 3 edges to see their structure
print("3. Sample edges...")
r = gremlin(f"g.V().hasLabel('{label}').outE().limit(3).project('label','src','tgt','type').by(label).by(outV().values('canonical_name')).by(inV().values('canonical_name')).by(coalesce(values('relationship_type'), label))")
print(f"   Result: {json.dumps(r)[:500]}")

# Check Aurora entities table
print("\n4. Aurora entities count...")
event2 = {"action": "query_aurora_entities", "case_id": case_id, "count_only": True}
resp2 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps(event2),
)
print(f"   Result: {json.loads(resp2['Payload'].read())}")

# Check Aurora relationships table
print("5. Aurora relationships count...")
event3 = {"action": "query_relationships", "case_id": case_id, "limit": 3}
resp3 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps(event3),
)
print(f"   Result: {json.loads(resp3['Payload'].read())}")
