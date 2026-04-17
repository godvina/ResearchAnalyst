"""Check what location entities exist in Neptune for Epstein Combined."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")

# Check Neptune locations
r = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query",
        "case_id": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
        "query": "g.V().has('entityType','location').valueMap('name').limit(100)"
    }),
)
d = json.loads(r["Payload"].read().decode())
if "result" in d:
    locs = d["result"]
    print(f"Found {len(locs)} location nodes in Neptune:")
    for item in locs:
        if isinstance(item, dict):
            name = item.get("name", ["?"])
            if isinstance(name, list):
                name = name[0]
        elif isinstance(item, str):
            name = item
        else:
            name = str(item)
        print(f"  - {name}")
elif "error" in d:
    print(f"ERROR: {d['error'][:500]}")
else:
    print(json.dumps(d)[:1000])

# Also check what the patterns API returns for locations
print("\n--- Patterns API location nodes ---")
r2 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "resource": "/case-files/{id}/patterns",
        "httpMethod": "POST",
        "pathParameters": {"id": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"},
        "body": json.dumps({"graph": True}),
    }),
)
d2 = json.loads(r2["Payload"].read().decode())
if "statusCode" in d2:
    body = json.loads(d2.get("body", "{}"))
    nodes = body.get("nodes", [])
    edges = body.get("edges", [])
    loc_nodes = [n for n in nodes if n.get("type") == "location"]
    person_nodes = [n for n in nodes if n.get("type") == "person"]
    print(f"Total nodes: {len(nodes)}, Edges: {len(edges)}")
    print(f"Location nodes: {len(loc_nodes)}")
    for ln in loc_nodes:
        print(f"  - {ln['name']} (degree: {ln.get('degree', '?')})")
    print(f"Person nodes: {len(person_nodes)}")
    for pn in person_nodes[:10]:
        print(f"  - {pn['name']} (degree: {pn.get('degree', '?')})")
    
    # Check person->location edges
    loc_names = {n["name"] for n in loc_nodes}
    person_names = {n["name"] for n in person_nodes}
    p2l_edges = [e for e in edges if (e["from"] in person_names and e["to"] in loc_names) or (e["to"] in person_names and e["from"] in loc_names)]
    print(f"\nPerson↔Location edges: {len(p2l_edges)}")
    for e in p2l_edges[:20]:
        print(f"  {e['from']} → {e['to']} ({e.get('label', '?')})")
else:
    print(f"Unexpected: {json.dumps(d2)[:500]}")
