"""Check what location entities exist in Neptune for Epstein Combined."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")

# Check Neptune locations - get raw result
r = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "case_id": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
        "query": "g.V().has('entityType','location').values('name').limit(50)"
    }),
)
d = json.loads(r["Payload"].read().decode())
print("=== Neptune Location Names ===")
if "result" in d:
    result = d["result"]
    if isinstance(result, list):
        print(f"Found {len(result)} locations:")
        for name in result:
            print(f"  - {name}")
    else:
        print(f"Raw result type: {type(result)}")
        print(str(result)[:2000])
elif "error" in d:
    print(f"ERROR: {d['error'][:500]}")
else:
    print(json.dumps(d)[:2000])

# Check person->location edges
print("\n=== Person→Location Edges ===")
r2 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "case_id": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
        "query": "g.V().has('entityType','person').outE().inV().has('entityType','location').path().by('name').by(label).by('name').limit(30)"
    }),
)
d2 = json.loads(r2["Payload"].read().decode())
if "result" in d2:
    result = d2["result"]
    if isinstance(result, list):
        print(f"Found {len(result)} person→location paths:")
        for p in result[:30]:
            print(f"  {p}")
    else:
        print(str(result)[:2000])
elif "error" in d2:
    print(f"ERROR: {d2['error'][:500]}")

# Now check patterns API via HTTP-style event
print("\n=== Patterns API (via Lambda event) ===")
r3 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "resource": "/case-files/{id}/patterns",
        "httpMethod": "POST",
        "pathParameters": {"id": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"},
        "body": json.dumps({"graph": True}),
    }),
)
d3 = json.loads(r3["Payload"].read().decode())
if "statusCode" in d3:
    print(f"Status: {d3['statusCode']}")
    body = json.loads(d3.get("body", "{}"))
    nodes = body.get("nodes", [])
    edges = body.get("edges", [])
    print(f"Nodes: {len(nodes)}, Edges: {len(edges)}")
    if len(nodes) == 0:
        print("ZERO NODES - checking error/message in body:")
        print(json.dumps(body)[:1000])
    else:
        loc_nodes = [n for n in nodes if n.get("type") == "location"]
        print(f"Location nodes: {len(loc_nodes)}")
        for ln in loc_nodes[:20]:
            print(f"  - {ln['name']} (degree: {ln.get('degree', '?')})")
elif "error" in d3:
    print(f"ERROR: {d3['error'][:500]}")
else:
    print(f"Unexpected response: {json.dumps(d3)[:1000]}")
