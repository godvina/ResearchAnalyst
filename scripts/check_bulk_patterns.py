"""Check patterns for the bulk CSV loader test case."""
import urllib.request
import json

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "0c5c28f7-ab20-41c5-b452-16f8c58e78ec"

url = f"{API_URL}/case-files/{CASE_ID}/patterns"
req = urllib.request.Request(url, data=json.dumps({"graph": True}).encode(), method="POST",
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=45) as resp:
    data = json.loads(resp.read().decode())
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    print(f"Graph API: {len(nodes)} nodes, {len(edges)} edges")
    print(f"Total in Neptune: {data.get('total_nodes', '?')}")

    # Show entity type breakdown
    types = {}
    for n in nodes:
        t = n.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
    print(f"\nEntity types:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    # Show top 10 by degree
    top = sorted(nodes, key=lambda x: x.get("degree", 0), reverse=True)[:10]
    print(f"\nTop 10 by connections:")
    for n in top:
        print(f"  {n.get('name', '?')} ({n.get('type', '?')}) — {n.get('degree', 0)} connections")
