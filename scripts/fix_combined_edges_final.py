"""Connect key persons to location nodes using __.V() anonymous traversal."""
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
        Payload=json.dumps({
            "action": "gremlin_query",
            "case_id": CASE_ID,
            "query": query,
            "timeout": 120,
            "max_result_len": 2000,
        }),
    )
    d = json.loads(r["Payload"].read().decode())
    if "error" in d:
        return None, d["error"][:500]
    return d.get("result"), None

# Person vertex IDs (from earlier discovery)
PERSON_IDS = {
    "Jeffrey Epstein": "68cec485-03af-17f3-9951-dd1770956dce",
    "Ghislaine Maxwell": "62ce9fc2-5dd1-2dc0-de21-c661c76fda78",
    "Lesley Groff": "f0cea01d-2c9a-6c15-da7d-958f26cd5114",
}

# Location vertex IDs (from earlier discovery)
LOC_IDS = {
    "Marrakesh": "a5344fa1-8608-40e1-83ba-19e91266fb40",
    "Islip": "a2cea01d-222d-cf8b-1c22-7fbf9ee3e5d3",
    "Little St. James Island": "6ace9fc2-49d2-a5c8-b249-aa51befe1eea",
    "Palm Beach": "0ccea01d-2da3-7f54-d97f-e3a8aa6b9425",
    "London": "92cea01d-6597-5ecf-fe31-7fd60b814562",
    "Manhattan": "48ce9fc2-8929-4e7d-4eb9-97849e63c540",
    "Virgin Islands": "22ce9fc2-3bed-b023-a27a-7225191c5846",
    "U.S. Virgin Islands": "bcce9fc2-5a5d-4730-3de9-0c14c93d0ce1",
    "New Mexico": "dacea01d-3d53-8f99-8ec0-0e2a5c466873",
    "Santa Fe": "4ecea01d-57c4-2184-7b55-06e4ed2ddca6",
    "Ohio": "21bbc3ca-f927-4ea7-8f35-389e9346b9ea",
    "Paris": "cccec485-35bb-8e5f-6bdb-19cce38f2898",
    "New York": "50cec484-f564-9f4f-8491-b15dce970941",
    "PARIS": "facec485-34ff-a335-d70c-607a75d97ee7",
    "NY": "56cec488-cfc1-2cac-00d7-726a259e637e",
}

# Edges to create
EDGES = [
    ("Jeffrey Epstein", ["Marrakesh", "Islip", "Little St. James Island", "Palm Beach",
                         "London", "Manhattan", "Virgin Islands", "U.S. Virgin Islands",
                         "New Mexico", "Santa Fe", "Ohio"]),
    ("Ghislaine Maxwell", ["Marrakesh", "London", "Manhattan", "Little St. James Island",
                           "Palm Beach", "Virgin Islands", "Paris", "New York"]),
    ("Lesley Groff", ["Manhattan", "Palm Beach", "New York"]),
]

print(f"=== Adding person→location edges ===")
success = 0
failed = 0

for person, locs in EDGES:
    pid = PERSON_IDS.get(person)
    if not pid:
        print(f"  ⏭️  No ID for {person}")
        continue
    for loc in locs:
        lid = LOC_IDS.get(loc)
        if not lid:
            print(f"  ⏭️  No ID for {loc}")
            continue
        eid = str(uuid.uuid4())
        # Use __.V() for anonymous traversal in .to()
        q = (
            f"g.V('{pid}')"
            f".addE('RELATED_TO')"
            f".to(__.V('{lid}'))"
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

# Verify via patterns API
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
        
        # Person→location edges
        person_names = {n["name"] for n in nodes if n.get("type") == "person"}
        loc_names = {n["name"] for n in loc_nodes}
        p2l = [e for e in edges if (e["from"] in person_names and e["to"] in loc_names) or (e["to"] in person_names and e["from"] in loc_names)]
        print(f"\n  Person↔Location edges: {len(p2l)}")
        unique_pairs = set()
        for e in p2l:
            pair = f"{e['from']} → {e['to']}"
            if pair not in unique_pairs:
                unique_pairs.add(pair)
                print(f"    {pair}")
except Exception as e:
    print(f"  Error: {e}")
