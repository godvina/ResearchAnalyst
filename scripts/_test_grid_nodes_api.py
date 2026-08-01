"""Test the grid nodes API with official Hagens data."""
import urllib.request
import json

url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/pattern-library/grid/nodes"
req = urllib.request.Request(url)
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read())

print("Grid Nodes API — Official Hagens Data")
print(f"  Source: {data.get('source', '?')[:80]}")
print(f"  Total nodes: {data.get('total_nodes')}")
print(f"  Stats: {json.dumps(data.get('stats', {}))}")
print(f"  Latitude bands: {data.get('latitude_bands')}")
print()

nodes = data.get("nodes", [])
print("First 5 nodes:")
for n in nodes[:5]:
    site = n.get("nearest_known_site", "NONE")
    dist = n.get("distance_to_nearest_km", "?")
    print(f"  Node {n['id']:>2} | {n['lat']:>7.2f}, {n['lng']:>8.2f} | {n['classification']} | {site} ({dist}km)")

print()
unexplored = [n for n in nodes if n["classification"] == "unexplored_land"]
print(f"Unexplored land nodes (investigation targets): {len(unexplored)}")
for n in unexplored[:10]:
    print(f"  Node {n['id']:>2} | {n['lat']:>7.2f}, {n['lng']:>8.2f} | {n.get('continent', '?')}")
