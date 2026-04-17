"""Check what the patterns endpoint returns for map data."""
import urllib.request
import json

cid = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
url = f"https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/{cid}/patterns"
data = json.dumps({"graph": True}).encode()
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as resp:
    d = json.loads(resp.read().decode())

nodes = d.get("nodes", [])
edges = d.get("edges", [])

persons = [n for n in nodes if n.get("type") == "person"]
locations = [n for n in nodes if n.get("type") == "location"]

print(f"Total nodes: {len(nodes)}")
print(f"Persons: {len(persons)}")
print(f"Locations: {len(locations)}")
print(f"Total edges: {len(edges)}")

# Find person→location edges
person_names = {n["name"] for n in persons}
location_names = {n["name"] for n in locations}

pl_edges = []
for e in edges:
    if (e.get("from") in person_names and e.get("to") in location_names) or \
       (e.get("to") in person_names and e.get("from") in location_names):
        pl_edges.append(e)

print(f"Person↔Location edges: {len(pl_edges)}")
for e in pl_edges[:10]:
    print(f"  {e.get('from')} → {e.get('to')}")

print(f"\nLocations: {[n['name'] for n in locations[:15]]}")
