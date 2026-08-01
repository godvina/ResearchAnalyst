"""Test grid investigation API."""
import urllib.request
import json

url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/pattern-library/grid/targets"
req = urllib.request.Request(url)
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read())

s = data.get("summary", {})
print("Grid Targets API working!")
print(f"  Confirmed sites: {s.get('confirmed', 0)}")
print(f"  Unexplored land targets: {s.get('unexplored_land', 0)}")
print(f"  Anomaly zones: {s.get('anomalies', 0)}")
print(f"  Probable sites: {s.get('probable', 0)}")
print(f"  Edge intersections on land: {s.get('edge_intersections', 0)}")
print()
print("CONFIRMED SITES:")
for t in data.get("confirmed_sites", []):
    print(f"  Node {t['id']:>2} | {t['lat']:>6.1f}, {t['lng']:>7.1f} | {t.get('known_site', '?')}")
print()
print("UNEXPLORED TARGETS (what's here?):")
for t in data.get("unexplored_targets", []):
    print(f"  Node {t['id']:>2} | {t['lat']:>6.1f}, {t['lng']:>7.1f} | {t.get('continent', '?')}")
