"""Debug the geospatial map — test patterns + geocode endpoints."""
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

print("=" * 60)
print("Step 1: Call /patterns to get location nodes")
print("=" * 60)

try:
    url = f"{API_URL}/case-files/{CASE_ID}/patterns"
    payload = json.dumps({"graph": True}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())

    nodes = body.get("nodes", [])
    edges = body.get("edges", [])
    locations = [n for n in nodes if n.get("type") == "location"]
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Total edges: {len(edges)}")
    print(f"  Location nodes: {len(locations)}")
    if locations:
        print(f"  First 10 locations:")
        for loc in locations[:10]:
            print(f"    - {loc.get('name')} (degree: {loc.get('degree', 0)})")
    else:
        print("  ** NO LOCATION NODES — this is why the map is empty **")
        print("  The /patterns endpoint returns nodes from Neptune.")
        print("  If there are 0 location nodes, there's nothing to geocode.")
except Exception as e:
    print(f"  ERROR: {e}")

print()
print("=" * 60)
print("Step 2: Call /geocode with test locations")
print("=" * 60)

test_locations = ["New York", "Palm Beach", "Paris", "Virgin Islands"]
try:
    url = f"{API_URL}/case-files/{CASE_ID}/geocode"
    payload = json.dumps({"locations": test_locations}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = resp.status
        body = json.loads(resp.read().decode())
    print(f"  Status: {status}")
    print(f"  Resolved: {body.get('resolved', 0)}/{body.get('total', 0)}")
    print(f"  Geocoded: {json.dumps(body.get('geocoded', {}), indent=2)[:500]}")
    if body.get("unresolved"):
        print(f"  Unresolved: {body['unresolved']}")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

print()
print("=" * 60)
print("Step 3: Test geocode with actual location names from patterns")
print("=" * 60)

if locations:
    loc_names = [loc["name"] for loc in locations[:20]]
    try:
        url = f"{API_URL}/case-files/{CASE_ID}/geocode"
        payload = json.dumps({"locations": loc_names}).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        print(f"  Resolved: {body.get('resolved', 0)}/{body.get('total', 0)}")
        for name, coords in list(body.get("geocoded", {}).items())[:10]:
            print(f"    {name}: ({coords['lat']}, {coords['lng']})")
        if body.get("unresolved"):
            print(f"  Unresolved: {body['unresolved'][:10]}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"  ERROR: {e}")
else:
    print("  Skipped — no location nodes from Step 1")
