"""End-to-end test: patterns API → geocode → verify map data is clean."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

# Step 1: Get patterns
print("=== Step 1: Patterns API ===")
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
    print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}, Locations: {len(loc_nodes)}")

# Step 2: Geocode the locations
print("\n=== Step 2: Geocode ===")
loc_names = [n["name"] for n in loc_nodes]
req2 = urllib.request.Request(
    f"{API}/case-files/{CASE_ID}/geocode",
    data=json.dumps({"locations": loc_names}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req2, timeout=30) as resp2:
    geo = json.loads(resp2.read().decode())
    geocoded = geo.get("geocoded", {})
    resolved = geo.get("resolved", 0)
    total = geo.get("total", 0)
    print(f"  Resolved: {resolved}/{total}")
    
    # Check for NaN values
    nan_count = 0
    valid_count = 0
    for name, coords in geocoded.items():
        lat = coords.get("lat")
        lng = coords.get("lng")
        if lat is None or lng is None:
            nan_count += 1
        else:
            try:
                float(lat)
                float(lng)
                valid_count += 1
            except (ValueError, TypeError):
                nan_count += 1
    
    print(f"  Valid coordinates: {valid_count}")
    print(f"  Invalid/NaN: {nan_count}")
    
    # Show resolved locations
    print(f"\n  Resolved locations:")
    for name in sorted(geocoded.keys()):
        coords = geocoded[name]
        print(f"    {name}: ({coords.get('lat', '?')}, {coords.get('lng', '?')})")

print("\n=== Map should work ✅ ===" if nan_count == 0 else f"\n=== WARNING: {nan_count} NaN coords ===")
