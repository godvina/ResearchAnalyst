"""Verify Irish sites in Neptune — check nodes, edges, coordinates."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + CASE_ID

def gremlin(q):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q, "timeout": 30}))
    return json.loads(r["Payload"].read().decode()).get("result", "")

# Count Irish nodes
print("Irish sacred sites in Neptune:")
print("  Nodes:", gremlin("g.V().has('source','irish_sacred_sites').count()"))
print("  Edges:", gremlin("g.E().has('source','irish_sacred_sites').count()"))

# Show all sites with coordinates
print("\n  Sites with coordinates:")
result = gremlin("g.V().has('source','irish_sacred_sites').valueMap('canonical_name','latitude','longitude','category')")
print(f"  {result[:2000]}")

# Show relationships
print("\n  Network connections:")
result = gremlin("g.V().has('source','irish_sacred_sites').outE().valueMap('relationship_type','description').limit(10)")
print(f"  {result[:2000]}")
