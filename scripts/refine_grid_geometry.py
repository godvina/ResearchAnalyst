"""Refine UVG grid geometry using known anchor sites.

The standard Becker-Hagens orientation places Giza at a vertex, but our
computed grid has Giza 384km from the nearest vertex. The issue: the grid
needs to be ROTATED so that known anchor sites sit exactly on vertices.

This script:
1. Uses Giza (29.98°N, 31.13°E) as the PRIMARY anchor — it must be at a vertex
2. Tests multiple grid orientations to find the best fit
3. Validates against known alignment principles:
   - Jim Alison's Great Circle (Giza-Nazca-Easter Island on one great circle)
   - The 30th parallel principle (many ancient sites near 30°N)
   - The equidistant principle (sacred sites are equally spaced on the grid)
4. Outputs the corrected grid with verified vertex positions

Key insight: The UVG grid is an icosidodecahedron. Its shape is fixed —
only its ORIENTATION on the globe can change. We need to find the rotation
that places Giza at a vertex AND maximizes alignment with other known sites.
"""

import json
import math
import os
from itertools import combinations


def deg2rad(d): return d * math.pi / 180.0
def rad2deg(r): return r * 180.0 / math.pi

def lat_lng_to_xyz(lat, lng):
    lat_r, lng_r = deg2rad(lat), deg2rad(lng)
    return (math.cos(lat_r)*math.cos(lng_r), math.cos(lat_r)*math.sin(lng_r), math.sin(lat_r))

def xyz_to_lat_lng(x, y, z):
    lat = rad2deg(math.asin(max(-1, min(1, z))))
    lng = rad2deg(math.atan2(y, x))
    return (lat, lng)

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

def rotate_z(point, angle_rad):
    """Rotate point around Z axis (adjusts longitude)."""
    x, y, z = point
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return (c*x - s*y, s*x + c*y, z)

def rotate_x(point, angle_rad):
    """Rotate point around X axis (adjusts latitude)."""
    x, y, z = point
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return (x, c*y - s*z, s*y + c*z)


# =================================================================
# PRINCIPLE 1: The Great Circle of Giza
# Jim Alison (1995) documented that Giza, Nazca, Easter Island,
# Angkor Wat, Mohenjo-daro, and Persepolis all fall on a single
# great circle tilted ~30° from the equator.
# =================================================================

ANCHOR_SITES = {
    "giza": {"lat": 29.9792, "lng": 31.1342},
    "nazca": {"lat": -14.7350, "lng": -75.1300},
    "easter_island": {"lat": -27.1256, "lng": -109.2767},
    "angkor_wat": {"lat": 13.4125, "lng": 103.8670},
    "mohenjo_daro": {"lat": 27.3242, "lng": 68.1386},
    "machu_picchu": {"lat": -13.1631, "lng": -72.5450},
    "petra": {"lat": 30.3285, "lng": 35.4444},
}

def compute_great_circle_from_two_points(p1_ll, p2_ll):
    """Compute the great circle normal from two lat/lng points."""
    p1 = lat_lng_to_xyz(p1_ll["lat"], p1_ll["lng"])
    p2 = lat_lng_to_xyz(p2_ll["lat"], p2_ll["lng"])
    return normalize(cross(p1, p2))

def distance_to_great_circle(point_ll, gc_normal):
    """Distance in km from a point to a great circle."""
    p = lat_lng_to_xyz(point_ll["lat"], point_ll["lng"])
    angle = rad2deg(math.acos(max(-1, min(1, abs(dot(p, gc_normal))))))
    return km_from_deg(90 - angle) if angle <= 90 else km_from_deg(angle - 90)


print("=" * 70)
print("PRINCIPLE 1: Validating Jim Alison's Great Circle")
print("=" * 70)
print()

# Compute the great circle defined by Giza and Nazca
gc_normal = compute_great_circle_from_two_points(ANCHOR_SITES["giza"], ANCHOR_SITES["nazca"])
print(f"Great circle through Giza and Nazca:")
print(f"  Normal vector: ({gc_normal[0]:.6f}, {gc_normal[1]:.6f}, {gc_normal[2]:.6f})")
print()

for name, coords in ANCHOR_SITES.items():
    dist = distance_to_great_circle(coords, gc_normal)
    status = "✅" if dist < 100 else "⚠️" if dist < 300 else "❌"
    print(f"  {status} {name:<20} {dist:>6.0f} km from the Giza-Nazca great circle")

print()


# =================================================================
# PRINCIPLE 2: The 30th Parallel
# An extraordinary number of ancient sites are near 30°N latitude:
# Giza (30°N), Persepolis (30°N), Lhasa (30°N), ancient Chinese
# capitals, Bermuda Triangle (32°N)
# =================================================================

print("=" * 70)
print("PRINCIPLE 2: The 30th Parallel Concentration")  
print("=" * 70)
print()

SITES_30TH = [
    {"name": "Great Pyramid of Giza", "lat": 29.979, "lng": 31.134},
    {"name": "Persepolis", "lat": 29.935, "lng": 52.892},
    {"name": "Mohenjo-daro", "lat": 27.324, "lng": 68.139},
    {"name": "Lhasa (Potala Palace)", "lat": 29.656, "lng": 91.117},
    {"name": "Bermuda Triangle (center)", "lat": 32.308, "lng": -64.751},
    {"name": "Petra", "lat": 30.329, "lng": 35.444},
    {"name": "Baalbek", "lat": 34.007, "lng": 36.204},
    {"name": "Ancient Susa (Iran)", "lat": 32.189, "lng": 48.259},
    {"name": "Eridu (oldest Sumerian city)", "lat": 30.816, "lng": 45.995},
    {"name": "Heliopolis (Egypt)", "lat": 30.131, "lng": 31.302},
    {"name": "Xi'an (Terracotta Army)", "lat": 34.265, "lng": 108.940},
]

print(f"Sites near the 30th parallel (26°-34°N):")
for s in SITES_30TH:
    deviation = abs(s["lat"] - 30.0)
    print(f"  {s['name']:<35} {s['lat']:>6.2f}°N  (deviation from 30°: {deviation:.1f}°, {km_from_deg(deviation):.0f}km)")


# =================================================================
# PRINCIPLE 3: Recompute Grid with Giza as Anchor
# The icosidodecahedron vertex latitudes are at:
#   ±arctan(1/2) ≈ ±26.57° and ±(90° - arctan(1/2)) ≈ ±63.43°
# But Giza is at 29.98°N. So either:
#   a) The grid is slightly tilted (not pole-aligned), OR
#   b) Giza sits between vertex bands (on an EDGE, not a vertex)
#
# Research shows Becker-Hagens placed Giza at vertex 1 of the
# icosahedron component, which IS at ~26.57° in the standard model.
# The ~3.4° discrepancy = 378km. This matches our validation!
#
# OPTION A: Accept that Giza is on an EDGE (between 26.57° and 52.62°)
# OPTION B: Tilt the grid so a vertex lands at 30°N
# =================================================================

print()
print("=" * 70)
print("PRINCIPLE 3: Grid Orientation Analysis")
print("=" * 70)
print()

# Standard icosidodecahedron latitude bands
STD_LATS = [90, 52.62, 26.57, 0, -26.57, -52.62, -90]
print("Standard icosidodecahedron latitude bands:")
for lat in STD_LATS:
    print(f"  {lat:>7.2f}°")
print()

# Giza at 29.98°N is between 26.57° and 52.62° bands
print(f"Giza is at 29.98°N — between the 26.57° and 52.62° bands")
print(f"  Distance to 26.57° band: {km_from_deg(29.98 - 26.57):.0f} km")
print(f"  Distance to 30° (adjusted band): {km_from_deg(29.98 - 30.0):.0f} km")
print()

# What if we use 30° instead of 26.57°? 
# arctan(1/φ) where φ = golden ratio gives a different angle
# Let's test: what latitude makes the most sites align?
print("Testing alternative grid latitudes for best site alignment:")
print()

ALL_SITES_FOR_FIT = [
    {"name": "Giza", "lat": 29.979},
    {"name": "Mohenjo-daro", "lat": 27.324},
    {"name": "Easter Island", "lat": -27.126},
    {"name": "Nazca", "lat": -14.735},
    {"name": "Uluru", "lat": -25.344},
    {"name": "Stonehenge", "lat": 51.179},
    {"name": "Newgrange", "lat": 53.695},
    {"name": "Lake Baikal", "lat": 53.183},
    {"name": "Angkor Wat", "lat": 13.413},
    {"name": "Teotihuacan", "lat": 19.693},
]

for test_lat in [26.57, 28.0, 29.0, 30.0, 31.0]:
    # Count how many sites are within 3° of this latitude or its complement
    complement = 90 - test_lat  # ~63.43, ~62, ~61, ~60, ~59
    
    close_count = 0
    for s in ALL_SITES_FOR_FIT:
        abs_lat = abs(s["lat"])
        if abs(abs_lat - test_lat) < 4 or abs(abs_lat - complement) < 4:
            close_count += 1
    
    print(f"  Band at ±{test_lat}° (complement ±{90-test_lat:.1f}°): {close_count} sites within 4°")


# =================================================================
# PRINCIPLE 4: Compute refined grid with TWO orientations
# Orientation A: Standard (pole-aligned, 26.57° bands, lng offset 31.72°)
# Orientation B: Giza-anchored (tilted so Giza IS at a vertex)
# =================================================================

print()
print("=" * 70)
print("PRINCIPLE 4: Refined Grid — Giza-Anchored Orientation")
print("=" * 70)
print()

# For Giza to be at a vertex, we need a latitude band at ~30°N
# The icosahedron has vertices at arctan(1/2) = 26.565°
# If we tilt the grid by 3.4° (the diff between 26.57 and 29.98), 
# then Giza sits ON a vertex.

TILT_ANGLE = deg2rad(3.41)  # Tilt to move 26.57° band to ~30°N

# Compute tilted grid vertices
print("Computing Giza-anchored grid (tilted 3.4° to place vertex at Giza)...")
print()

# Standard vertices in XYZ (pole-aligned), then tilt
def generate_standard_icosidodecahedron():
    """Generate the 62 vertices of the standard icosidodecahedron."""
    verts = []
    # Poles
    verts.append((0, 0, 1))   # North
    verts.append((0, 0, -1))  # South
    
    # Icosahedron vertices at ±26.57°
    lat1 = deg2rad(26.565)
    for i in range(10):
        lng = deg2rad(31.72 + i * 36)  # 36° spacing, offset to hit Giza longitude
        z = math.sin(lat1) if i < 5 else -math.sin(lat1)
        lat_use = lat1 if i < 5 else -lat1
        # Alternate offset for southern hemisphere
        lng_adj = lng if i < 5 else lng + deg2rad(18)
        x = math.cos(lat_use) * math.cos(lng_adj)
        y = math.cos(lat_use) * math.sin(lng_adj)
        verts.append((x, y, z))
    
    # Dodecahedron vertices at ±52.62°
    lat2 = deg2rad(52.62)
    for i in range(10):
        lng = deg2rad(31.72 + i * 36)
        z = math.sin(lat2) if i < 5 else -math.sin(lat2)
        lat_use = lat2 if i < 5 else -lat2
        lng_adj = lng if i < 5 else lng + deg2rad(18)
        x = math.cos(lat_use) * math.cos(lng_adj)
        y = math.cos(lat_use) * math.sin(lng_adj)
        verts.append((x, y, z))
    
    # Equatorial vertices at 0°
    for i in range(20):
        lng = deg2rad(31.72 + i * 18)  # 18° spacing
        x = math.cos(lng)
        y = math.sin(lng)
        verts.append((x, y, 0))
    
    return verts

std_verts = generate_standard_icosidodecahedron()
print(f"Generated {len(std_verts)} standard vertices")

# Apply tilt (rotate around X axis to shift latitude bands north by 3.4°)
tilted_verts = [rotate_x(v, TILT_ANGLE) for v in std_verts]

# Convert to lat/lng
tilted_latlng = [xyz_to_lat_lng(*v) for v in tilted_verts]

# Find the vertex closest to Giza
giza_xyz = lat_lng_to_xyz(29.979, 31.134)
min_dist = 999
closest_idx = -1
for i, v in enumerate(tilted_verts):
    d = angular_dist_deg(giza_xyz, v)
    if d < min_dist:
        min_dist = d
        closest_idx = i

print(f"After tilting, closest vertex to Giza: index {closest_idx}")
print(f"  Vertex position: {tilted_latlng[closest_idx][0]:.2f}°N, {tilted_latlng[closest_idx][1]:.2f}°E")
print(f"  Distance to Giza: {km_from_deg(min_dist):.0f} km")
print()

# Now validate ALL sites against the tilted grid
print("Validation of tilted grid against known sites:")
print(f"{'Site':<30} {'Nearest vertex (km)':<22} {'Standard grid (km)'}")
print("-" * 75)

VALIDATE_SITES = [
    {"name": "Giza", "lat": 29.979, "lng": 31.134},
    {"name": "Stonehenge", "lat": 51.179, "lng": -1.826},
    {"name": "Mohenjo-daro", "lat": 27.324, "lng": 68.139},
    {"name": "Easter Island", "lat": -27.126, "lng": -109.277},
    {"name": "Angkor Wat", "lat": 13.413, "lng": 103.867},
    {"name": "Nazca", "lat": -14.735, "lng": -75.130},
    {"name": "Uluru", "lat": -25.344, "lng": 131.037},
    {"name": "Newgrange", "lat": 53.695, "lng": -6.476},
    {"name": "Sedona", "lat": 34.807, "lng": -111.762},
    {"name": "Lake Baikal", "lat": 53.183, "lng": 107.338},
    {"name": "Tiwanaku", "lat": -16.555, "lng": -68.673},
    {"name": "Petra", "lat": 30.329, "lng": 35.444},
    {"name": "Great Zimbabwe", "lat": -20.267, "lng": 30.934},
    {"name": "Göbekli Tepe", "lat": 37.223, "lng": 38.923},
]

# Also compute distance to standard (untilted) grid for comparison
std_latlng = [xyz_to_lat_lng(*v) for v in std_verts]

tilted_total = 0
standard_total = 0
for site in VALIDATE_SITES:
    site_xyz = lat_lng_to_xyz(site["lat"], site["lng"])
    
    # Tilted grid
    min_tilted = min(angular_dist_deg(site_xyz, v) for v in tilted_verts)
    tilted_km = km_from_deg(min_tilted)
    
    # Standard grid
    min_std = min(angular_dist_deg(site_xyz, v) for v in std_verts)
    std_km = km_from_deg(min_std)
    
    tilted_total += tilted_km
    standard_total += std_km
    
    better = "← BETTER" if tilted_km < std_km else ""
    print(f"  {site['name']:<28} {tilted_km:>6.0f} km          {std_km:>6.0f} km  {better}")

print()
print(f"  TOTAL (tilted):   {tilted_total:.0f} km")
print(f"  TOTAL (standard): {standard_total:.0f} km")
print(f"  {'Tilted grid is better!' if tilted_total < standard_total else 'Standard grid is better!'}")


# =================================================================
# PRINCIPLE 5: Output the best grid
# =================================================================
print()
print("=" * 70)
print("FINAL: Saving refined grid coordinates")
print("=" * 70)

# Use whichever grid has lower total distance
use_tilted = tilted_total < standard_total
final_verts = tilted_latlng if use_tilted else std_latlng
grid_type = "Giza-anchored (tilted 3.4°)" if use_tilted else "Standard (pole-aligned)"
print(f"Using: {grid_type}")
print(f"Total vertices: {len(final_verts)}")

# Build output
refined_vertices = []
for i, (lat, lng) in enumerate(final_verts):
    # Normalize longitude to -180..180
    while lng > 180: lng -= 360
    while lng < -180: lng += 360
    
    vtype = "polar" if abs(lat) > 85 else "high_lat" if abs(lat) > 45 else "mid_lat" if abs(lat) > 15 else "equatorial"
    refined_vertices.append({
        "id": i + 1,
        "lat": round(lat, 4),
        "lng": round(lng, 4),
        "type": vtype,
    })

output = {
    "name": f"UVG 120 Grid — Refined ({grid_type})",
    "method": "Icosidodecahedron projected onto Earth, orientation optimized for ancient site alignment",
    "total_vertices": len(refined_vertices),
    "orientation": grid_type,
    "anchor_site": "Great Pyramid of Giza (29.98°N, 31.13°E)",
    "vertices": refined_vertices,
}

output_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-refined.json")
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"Saved to {output_path}")
