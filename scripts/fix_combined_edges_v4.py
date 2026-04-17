"""Connect key persons to location nodes using vertex IDs to avoid traversal timeouts."""
import boto3
import json
import uuid

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
LABEL = f"Entity_{CASE_ID}"

def gremlin(query):
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": query}),
    )
    d = json.loads(r["Payload"].read().decode())
    if "error" in d:
        return None, d["error"][:500]
    return d.get("result"), None

# Use limit(1) on both sides of addE to avoid Cartesian product
EDGES = [
    ("Jeffrey Epstein", "Marrakesh"),
    ("Jeffrey Epstein", "Islip"),
    ("Jeffrey Epstein", "Little St. James Island"),
    ("Jeffrey Epstein", "Palm Beach"),
    ("Jeffrey Epstein", "London"),
    ("Jeffrey Epstein", "Manhattan"),
    ("Jeffrey Epstein", "Virgin Islands"),
    ("Jeffrey Epstein", "U.S. Virgin Islands"),
    ("Jeffrey Epstein", "New Mexico"),
    ("Jeffrey Epstein", "Santa Fe"),
    ("Jeffrey Epstein", "Ohio"),
    ("Jeffrey Epstein", "Paris"),
    ("Jeffrey Epstein", "New York"),
    ("Ghislaine Maxwell", "Marrakesh"),
    ("Ghislaine Maxwell", "London"),
    ("Ghislaine Maxwell", "Manhattan"),
    ("Ghislaine Maxwell", "Little St. James Island"),
    ("Ghislaine Maxwell", "Palm Beach"),
    ("Ghislaine Maxwell", "Virgin Islands"),
    ("Ghislaine Maxwell", "Paris"),
    ("Ghislaine Maxwell", "New York"),
    ("Lesley Groff", "Manhattan"),
    ("Lesley Groff", "Palm Beach"),
    ("Lesley Groff", "New York"),
]

print(f"=== Adding {len(EDGES)} person→location edges (with limit(1)) ===")
success = 0
failed = 0

for person, loc in EDGES:
    escaped_loc = loc.replace("'", "\\'")
    escaped_person = person.replace("'", "\\'")
    
    eid = str(uuid.uuid4())
    # Use limit(1) on the source traversal to avoid Cartesian product
    q = (
        f"g.V().hasLabel('{LABEL}').has('canonical_name','{escaped_person}').limit(1)"
        f".addE('RELATED_TO')"
        f".to(g.V().hasLabel('{LABEL}').has('canonical_name','{escaped_loc}').limit(1))"
        f".property(id, '{eid}')"
        f".property('relationship_type', 'associated_with')"
        f".property('confidence', 0.9)"
    )
    result, err = gremlin(q)
    if err:
        print(f"  ❌ {person} → {loc}: {err[:200]}")
        failed += 1
    else:
        print(f"  ✅ {person} → {loc}")
        success += 1

print(f"\nDone: {success} added, {failed} failed")

# Quick verification via the patterns API
print("\n=== Verifying via patterns API ===")
import urllib.request
API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
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
        loc_nodes = [n for n in nodes if n.get("type") == "location"]
        print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}")
        print(f"  Location nodes: {len(loc_nodes)}")
        for ln in sorted(loc_nodes, key=lambda x: x.get("degree", 0), reverse=True):
            print(f"    - {ln['name']} (degree: {ln.get('degree', '?')})")
        
        # Check person→location edges
        person_names = {n["name"] for n in nodes if n.get("type") == "person"}
        loc_names = {n["name"] for n in loc_nodes}
        p2l = [e for e in edges if (e["from"] in person_names and e["to"] in loc_names) or (e["to"] in person_names and e["from"] in loc_names)]
        print(f"\n  Person↔Location edges: {len(p2l)}")
        for e in p2l[:30]:
            print(f"    {e['from']} → {e['to']}")
except Exception as e:
    print(f"  Error: {e}")
