"""Check Neptune graph state and patterns API for Epstein Combined."""
import boto3
import json
import urllib.request

lam = boto3.client("lambda", region_name="us-east-1")
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

# 1. Check total vertex count in Neptune
print("=== Neptune Graph Stats ===")
for q, label in [
    ("g.V().count()", "Total vertices"),
    ("g.E().count()", "Total edges"),
    ("g.V().has('entityType','location').count()", "Location vertices"),
    ("g.V().has('entityType','person').count()", "Person vertices"),
    ("g.V().has('entityType','organization').count()", "Org vertices"),
    ("g.V().groupCount().by('entityType')", "By entity type"),
]:
    r = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q}),
    )
    d = json.loads(r["Payload"].read().decode())
    result = d.get("result", d.get("error", "?"))
    print(f"  {label}: {result}")

# 2. Check if Neptune has case-specific graph (graph_case_id)
print("\n=== Check graph_case_id property ===")
r = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query", "case_id": CASE_ID,
        "query": "g.V().has('case_id','" + CASE_ID + "').count()"
    }),
)
d = json.loads(r["Payload"].read().decode())
print(f"  Vertices with case_id={CASE_ID}: {d.get('result', d.get('error', '?'))}")

# Also check parent case
r = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    InvocationType="RequestResponse",
    Payload=json.dumps({
        "action": "gremlin_query", "case_id": CASE_ID,
        "query": "g.V().limit(5).valueMap(true)"
    }),
)
d = json.loads(r["Payload"].read().decode())
print(f"\n  Sample vertices (first 5):")
result = d.get("result", "")
if isinstance(result, str):
    print(f"  {result[:2000]}")
else:
    for v in (result if isinstance(result, list) else [])[:5]:
        print(f"  {v}")

# 3. Test patterns API via HTTP
print("\n=== Patterns API via HTTP ===")
try:
    req = urllib.request.Request(
        f"{API}/case-files/{CASE_ID}/patterns",
        data=json.dumps({"graph": True}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
        nodes = body.get("nodes", [])
        edges = body.get("edges", [])
        print(f"  Status: {resp.status}")
        print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}")
        loc_nodes = [n for n in nodes if n.get("type") == "location"]
        print(f"  Location nodes: {len(loc_nodes)}")
        for ln in loc_nodes[:20]:
            print(f"    - {ln['name']} (degree: {ln.get('degree', '?')})")
except Exception as e:
    print(f"  Error: {e}")
