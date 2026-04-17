"""Test the entity-neighborhood API — the backend IS returning 50 nodes per logs."""
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
case_id = "7f05e8d5-4492-4f19-8894-25367606db96"
url = f"{API_URL}/case-files/{case_id}/entity-neighborhood?entity_name=Jeffrey%20Epstein&hops=1"
req = urllib.request.Request(url, headers={"Content-Type": "application/json"})

print("Querying...")
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = json.loads(resp.read().decode())
    nodes = body.get("nodes", [])
    edges = body.get("edges", [])
    print(f"Nodes: {len(nodes)}, Edges: {len(edges)}")
    for n in nodes[:5]:
        print(f"  {n}")
except urllib.error.HTTPError as e:
    err = e.read().decode()[:500] if hasattr(e, "read") else str(e)
    print(f"HTTP {e.code}: {err}")
except Exception as e:
    print(f"Error: {e}")
