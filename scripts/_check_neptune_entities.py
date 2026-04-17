"""Check what entities exist in Neptune for the main case."""
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
case_id = "7f05e8d5-4492-4f19-8894-25367606db96"

# Query patterns endpoint to see what entities exist in Neptune
url = f"{API_URL}/case-files/{case_id}/patterns"
payload = json.dumps({"graph": True}).encode()
req = urllib.request.Request(url, data=payload, method="POST",
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=60) as resp:
    body = json.loads(resp.read().decode())

nodes = body.get("nodes", [])
total = body.get("total_nodes", len(nodes))
edges = body.get("total_edges_sampled", 0)
print(f"Total nodes in Neptune: {total}")
print(f"Edges sampled: {edges}")
print(f"Nodes returned: {len(nodes)}")

print("\nTop 20 entities by degree:")
for n in nodes[:20]:
    name = n.get("name", "?")
    etype = n.get("type", "?")
    degree = n.get("degree", 0)
    print(f"  {name} ({etype}) degree={degree}")

# Search for epstein
epstein_nodes = [n for n in nodes if "epstein" in (n.get("name", "") or "").lower()]
print(f"\nEpstein-related nodes: {len(epstein_nodes)}")
for n in epstein_nodes:
    print(f"  {n.get('name', '?')} ({n.get('type', '?')}) degree={n.get('degree', 0)}")

# Search for jeffrey
jeffrey_nodes = [n for n in nodes if "jeffrey" in (n.get("name", "") or "").lower()]
print(f"\nJeffrey-related nodes: {len(jeffrey_nodes)}")
for n in jeffrey_nodes:
    print(f"  {n.get('name', '?')} ({n.get('type', '?')}) degree={n.get('degree', 0)}")

# Show all person entities
person_nodes = [n for n in nodes if n.get("type", "").lower() == "person"]
print(f"\nPerson entities: {len(person_nodes)}")
for n in person_nodes[:30]:
    print(f"  {n.get('name', '?')} degree={n.get('degree', 0)}")
