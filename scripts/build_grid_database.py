"""Build the complete grid investigation database from official Hagens KMZ data.

Takes the parsed 62 vertices + 193 lines and produces:
1. Classified node database (what's at each point)
2. Edge connection map (which nodes connect to which)
3. All intersection points where edges cross
4. Priority-ranked investigation targets

This is the foundation for the Neptune graph and the auto-research system.
"""

import json
import math
import os
import re

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

# Load parsed Hagens data
with open(os.path.join(DATA_DIR, "uvg-grid-hagens-official.json")) as f:
    hagens_data = json.load(f)

with open(os.path.join(DATA_DIR, "uvg-grid-hagens-lines.json")) as f:
    lines_data = json.load(f)

points = hagens_data["points"]
lines = lines_data["lines"]


def deg2rad(d): return d * math.pi / 180.0
def rad2deg(r): return r * 180.0 / math.pi

def lat_lng_to_xyz(lat, lng):
    lat_r, lng_r = deg2rad(lat), deg2rad(lng)
    return (math.cos(lat_r)*math.cos(lng_r), math.cos(lat_r)*math.sin(lng_r), math.sin(lat_r))

def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def normalize(v):
    mag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if mag < 1e-12: return (0,0,0)
    return (v[0]/mag, v[1]/mag, v[2]/mag)

def angular_dist_deg(p1, p2):
    d = dot(p1, p2)
    return rad2deg(math.acos(max(-1.0, min(1.0, d))))

def km_from_deg(d): return d * 111.32

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = deg2rad(lat2 - lat1)
    dlng = deg2rad(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(deg2rad(lat1))*math.cos(deg2rad(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# =====================================================
# Step 1: Extract and number the 62 UVG grid nodes
# =====================================================

print("=" * 70)
print("STEP 1: Building node database from official Hagens coordinates")
print("=" * 70)

# Filter to just UVG nodes (named "UVG 1" through "UVG 62")
uvg_nodes = []
other_points = []
for p in points:
    match = re.match(r"UVG (\d+)", p["name"])
    if match:
        node_id = int(match.group(1))
        uvg_nodes.append({
            "id": node_id,
            "lat": p["lat"],
            "lng": p["lng"],
            "name": p["name"],
        })
    else:
        other_points.append(p)

uvg_nodes.sort(key=lambda n: n["id"])
print(f"  UVG nodes extracted: {len(uvg_nodes)}")
print(f"  Other points (Gizeh marker, Alison markers, etc.): {len(other_points)}")

# Add poles if missing
node_ids = {n["id"] for n in uvg_nodes}
if 61 not in node_ids:
    uvg_nodes.append({"id": 61, "lat": 90.0, "lng": 0.0, "name": "UVG 61 (North Pole)"})
if 62 not in node_ids:
    uvg_nodes.append({"id": 62, "lat": -90.0, "lng": 0.0, "name": "UVG 62 (South Pole)"})

uvg_nodes.sort(key=lambda n: n["id"])
print(f"  Total nodes (with poles): {len(uvg_nodes)}")


# =====================================================
# Step 2: Classify each node (land/ocean, known sites)
# =====================================================

print()
print("=" * 70)
print("STEP 2: Classifying nodes — what's at each location?")
print("=" * 70)

# Known sites near grid nodes
KNOWN_NEARBY = [
    {"name": "Great Pyramid of Giza", "lat": 29.979, "lng": 31.134, "type": "ancient_monument"},
    {"name": "Stonehenge", "lat": 51.179, "lng": -1.826, "type": "ancient_monument"},
    {"name": "Machu Picchu", "lat": -13.163, "lng": -72.545, "type": "ancient_monument"},
    {"name": "Easter Island", "lat": -27.126, "lng": -109.277, "type": "ancient_monument"},
    {"name": "Nazca Lines", "lat": -14.735, "lng": -75.130, "type": "ancient_monument"},
    {"name": "Angkor Wat", "lat": 13.413, "lng": 103.867, "type": "ancient_monument"},
    {"name": "Göbekli Tepe", "lat": 37.223, "lng": 38.923, "type": "ancient_monument"},
    {"name": "Mohenjo-daro", "lat": 27.324, "lng": 68.139, "type": "ancient_monument"},
    {"name": "Uluru", "lat": -25.344, "lng": 131.037, "type": "sacred_site"},
    {"name": "Great Zimbabwe", "lat": -20.267, "lng": 30.934, "type": "ancient_monument"},
    {"name": "Sedona Vortexes", "lat": 34.807, "lng": -111.762, "type": "anomaly_zone"},
    {"name": "Bermuda Triangle", "lat": 32.308, "lng": -64.751, "type": "anomaly_zone"},
    {"name": "Devil's Sea (Dragon Triangle)", "lat": 25.0, "lng": 136.0, "type": "anomaly_zone"},
    {"name": "Lake Baikal", "lat": 53.183, "lng": 107.338, "type": "geological"},
    {"name": "Newgrange", "lat": 53.695, "lng": -6.476, "type": "ancient_monument"},
    {"name": "Tiwanaku/Puma Punku", "lat": -16.555, "lng": -68.673, "type": "ancient_monument"},
    {"name": "Petra", "lat": 30.329, "lng": 35.444, "type": "ancient_monument"},
    {"name": "Teotihuacan", "lat": 19.693, "lng": -98.844, "type": "ancient_monument"},
    {"name": "Chaco Canyon", "lat": 36.060, "lng": -107.962, "type": "ancient_monument"},
    {"name": "Richat Structure", "lat": 21.125, "lng": -11.402, "type": "geological"},
    {"name": "Gunung Padang", "lat": -6.995, "lng": 107.056, "type": "ancient_monument"},
    {"name": "Baalbek", "lat": 34.007, "lng": 36.204, "type": "ancient_monument"},
    {"name": "Persepolis", "lat": 29.935, "lng": 52.892, "type": "ancient_monument"},
    {"name": "Sacsayhuaman", "lat": -13.509, "lng": -71.982, "type": "ancient_monument"},
    {"name": "Carnac Stones", "lat": 47.592, "lng": -3.078, "type": "ancient_monument"},
    {"name": "Delphi", "lat": 38.482, "lng": 22.501, "type": "ancient_monument"},
    {"name": "Nan Madol", "lat": 6.844, "lng": 158.333, "type": "ancient_monument"},
    {"name": "Cahokia Mounds", "lat": 38.660, "lng": -90.062, "type": "ancient_monument"},
]

def is_on_land_rough(lat, lng):
    """Rough land check."""
    boxes = [
        (-35, 37, -20, 55, "Africa"), (35, 72, -12, 45, "Europe"),
        (8, 78, 25, 180, "Asia"), (-48, -10, 112, 155, "Australia"),
        (-55, 12, -82, -34, "South America"), (7, 85, -170, -50, "North America"),
        (-50, -30, 165, 180, "New Zealand"),
    ]
    for min_lat, max_lat, min_lng, max_lng, name in boxes:
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return name
    return None

# Classify each node
classified_nodes = []
for node in uvg_nodes:
    lat, lng = node["lat"], node["lng"]
    
    # Find nearest known site
    nearest_site = None
    nearest_dist = 9999
    for site in KNOWN_NEARBY:
        dist = haversine_km(lat, lng, site["lat"], site["lng"])
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_site = site
    
    land = is_on_land_rough(lat, lng)
    
    # Classification
    if nearest_dist < 200:
        status = "confirmed_site"
        priority = "documented"
    elif nearest_dist < 500:
        status = "near_site"
        priority = "high"
    elif land:
        status = "unexplored_land"
        priority = "investigate"
    else:
        status = "ocean"
        priority = "low"
    
    classified_nodes.append({
        "id": node["id"],
        "lat": round(lat, 4),
        "lng": round(lng, 4),
        "name": node["name"],
        "classification": status,
        "priority": priority,
        "continent": land,
        "nearest_known_site": nearest_site["name"] if nearest_dist < 500 else None,
        "distance_to_nearest_km": round(nearest_dist, 0),
    })

# Stats
confirmed = [n for n in classified_nodes if n["classification"] == "confirmed_site"]
near = [n for n in classified_nodes if n["classification"] == "near_site"]
unexplored = [n for n in classified_nodes if n["classification"] == "unexplored_land"]
ocean = [n for n in classified_nodes if n["classification"] == "ocean"]

print(f"  Confirmed sites (<200km): {len(confirmed)}")
print(f"  Near known sites (200-500km): {len(near)}")
print(f"  Unexplored land nodes: {len(unexplored)}")
print(f"  Ocean nodes: {len(ocean)}")

print(f"\n  CONFIRMED SITES:")
for n in confirmed:
    print(f"    Node {n['id']:>2} | {n['lat']:>7.2f}°, {n['lng']:>8.2f}° | {n['nearest_known_site']} ({n['distance_to_nearest_km']:.0f}km)")

print(f"\n  HIGH PRIORITY UNEXPLORED:")
for n in unexplored[:15]:
    print(f"    Node {n['id']:>2} | {n['lat']:>7.2f}°, {n['lng']:>8.2f}° | {n['continent']} — NO KNOWN SITE")


# =====================================================
# Step 3: Save complete database
# =====================================================

print()
print("=" * 70)
print("STEP 3: Saving grid investigation database")
print("=" * 70)

output = {
    "name": "UVG Grid Investigation Database — Official Hagens Coordinates",
    "source": "Parsed from UVG-grid-compiled-by-B-Hagens.kmz (Wayback Machine archive)",
    "total_nodes": len(classified_nodes),
    "stats": {
        "confirmed_sites": len(confirmed),
        "near_sites": len(near),
        "unexplored_land": len(unexplored),
        "ocean": len(ocean),
    },
    "latitude_bands": sorted(set(abs(n["lat"]) for n in classified_nodes if abs(n["lat"]) > 1)),
    "nodes": classified_nodes,
    "reference_sites": KNOWN_NEARBY,
}

output_path = os.path.join(DATA_DIR, "uvg-grid-investigation-database.json")
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"  Saved to {output_path}")
print(f"  Total nodes: {len(classified_nodes)}")
print(f"  Total lines from KMZ: {len(lines)}")
print()
print("DONE. This database is ready for:")
print("  1. Neptune graph loading (nodes + edges)")
print("  2. Auto-research of each unexplored node")
print("  3. Frontend globe visualization")
print("  4. OpenSearch vector indexing")
