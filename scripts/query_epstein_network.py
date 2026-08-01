"""Get Epstein's network from Neptune — all connected persons ranked by connection strength."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

# Get all persons connected to Epstein
print("=== Persons Connected to Jeffrey Epstein (Neptune) ===")
q = (
    "g.V().hasLabel('Entity_" + CASE_ID + "')"
    ".has('canonical_name','Jeffrey Epstein')"
    ".both('RELATED_TO')"
    ".has('entity_type','person')"
    ".groupCount().by('canonical_name')"
)
r = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "case_id": CASE_ID,
        "query": q,
        "timeout": 60,
        "max_result_len": 8000,
    }),
)
d = json.loads(r["Payload"].read().decode())
result = d.get("result", "")
print(f"Raw: {result[:4000]}")

# Also get organizations connected to Epstein
print("\n=== Organizations Connected to Epstein ===")
q2 = (
    "g.V().hasLabel('Entity_" + CASE_ID + "')"
    ".has('canonical_name','Jeffrey Epstein')"
    ".both('RELATED_TO')"
    ".has('entity_type','organization')"
    ".groupCount().by('canonical_name')"
)
r2 = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "case_id": CASE_ID,
        "query": q2,
        "timeout": 60,
        "max_result_len": 4000,
    }),
)
d2 = json.loads(r2["Payload"].read().decode())
print(f"Raw: {d2.get('result', '')[:2000]}")

# Get locations
print("\n=== Locations Connected to Epstein ===")
q3 = (
    "g.V().hasLabel('Entity_" + CASE_ID + "')"
    ".has('canonical_name','Jeffrey Epstein')"
    ".both('RELATED_TO')"
    ".has('entity_type','location')"
    ".groupCount().by('canonical_name')"
)
r3 = lam.invoke(
    FunctionName=LAMBDA,
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "case_id": CASE_ID,
        "query": q3,
        "timeout": 60,
        "max_result_len": 4000,
    }),
)
d3 = json.loads(r3["Payload"].read().decode())
print(f"Raw: {d3.get('result', '')[:2000]}")
