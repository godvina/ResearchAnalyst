"""Verify the patterns API returns the new locations."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

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
    print(f"Nodes: {len(nodes)}, Edges: {len(edges)}, Locations: {len(loc_nodes)}")
    print("\nAll locations:")
    for ln in sorted(loc_nodes, key=lambda x: x.get("degree", 0), reverse=True):
        print(f"  {ln['name']} (degree: {ln.get('degree', '?')})")

    # Check for key locations
    loc_names = {n["name"] for n in loc_nodes}
    print("\nKey location check:")
    for key in ["Marrakesh", "Islip", "Palm Beach", "London", "Manhattan",
                "Little St. James Island", "Virgin Islands", "New Mexico", "Santa Fe"]:
        status = "✅" if key in loc_names else "❌"
        print(f"  {status} {key}")

    # Person→location edges
    person_names = {n["name"] for n in nodes if n.get("type") == "person"}
    p2l = [e for e in edges if (e["from"] in person_names and e["to"] in loc_names) or
           (e["to"] in person_names and e["from"] in loc_names)]
    print(f"\nPerson↔Location edges: {len(p2l)}")
    seen = set()
    for e in p2l:
        pair = f"{e['from']} → {e['to']}"
        if pair not in seen:
            seen.add(pair)
            print(f"  {pair}")
