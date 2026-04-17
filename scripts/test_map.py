"""Test map/patterns endpoint for Epstein Combined."""
import urllib.request
import json

url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/patterns"
data = json.dumps({"graph": True}).encode()
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as resp:
    d = json.loads(resp.read().decode())

nodes = d.get("nodes", [])
locations = [n for n in nodes if n.get("type") == "location"]
print(f"Total nodes: {len(nodes)}")
print(f"Location nodes: {len(locations)}")
for loc in locations[:10]:
    print(f"  {loc['name']} (degree: {loc.get('degree', 0)})")
