"""Quick final check of Neptune + Aurora state after rhowardstone load."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

def gremlin(q, timeout=60):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q, "timeout": timeout}))
    d = json.loads(r["Payload"].read().decode())
    return d.get("result", d.get("error", ""))

def invoke(payload):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps(payload))
    return json.loads(r["Payload"].read().decode())

label = "Entity_" + CASE_ID

print("=== NEPTUNE ===")
q = "g.V().hasLabel('" + label + "').has('source','rhowardstone_kg').count()"
print("Rhowardstone nodes:", gremlin(q))
q = "g.E().has('source','rhowardstone_kg').count()"
print("Rhowardstone edges:", gremlin(q))

# Sample a relationship to verify it's correct
q = "g.V().hasLabel('" + label + "').has('source','rhowardstone_kg').has('canonical_name','Jeffrey Epstein').outE().limit(5).valueMap()"
print("\nEpstein outgoing edges:", gremlin(q))

# Total graph size
q = "g.V().hasLabel('" + label + "').count()"
print("\nTotal case nodes:", gremlin(q))
print("Total edges:", gremlin("g.E().count()"))

print("\n=== AURORA ===")
result = invoke({"action": "query_aurora_entities", "case_id": CASE_ID, "limit": 1, "offset": 0})
print("Total Aurora entities:", result.get("total", result.get("error", "?")))
