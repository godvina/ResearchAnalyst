"""Compute all intersection points of the Becker-Hagens UVG 120 grid.

Takes the 62 vertices and 120 edges, computes where every pair of
non-adjacent great circle edges cross each other on the sphere.
Outputs a database of intersection coordinates with metadata about
which lines cross there.

This is the foundation for the "what's at every intersection" research.
"""

import json
import math
import os

# Load the 62-point grid
GRID_FILE = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-62-points.json")

with open(GRID_FILE, "r") as f:
    grid_data = json.load(f)

vertices = grid_data["vertices"]
# Build a lookup by ID
vertex_by_id = {v["id"]: v for v in vertices}


def deg2rad(d):
    return d * math.pi / 180.0

def rad2deg(r):
    return r * 180.0 / math.pi

def lat_lng_to_xyz(lat, lng):
    """Convert lat/lng (degrees) to unit sphere XYZ."""
    lat_r = deg2rad(lat)
    lng_r = deg2rad(lng)
    x = math.cos(lat_r) * math.cos(lng_r)
    y = math.cos(lat_r) * math.sin(lng_r)
    z = math.sin(lat_r)
    return (x, y, z)

def xyz_to_lat_lng(x, y, z):
    """Convert unit sphere XYZ to lat/lng (degrees)."""
    lat = rad2deg(math.asin(max(-1, min(1, z))))
    lng = rad2deg(math.atan2(y, x))
    return (lat, lng)

def cross_product(a, b):
    """Cross product of two 3D vectors."""
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0]
    )

def normalize(v):
    """Normalize a 3D vector to unit length."""
    mag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if mag < 1e-10:
        return (0, 0, 0)
    return (v[0]/mag, v[1]/mag, v[2]/mag)

def dot_product(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def great_circle_intersection(p1, p2, p3, p4):
    """Find intersection points of two great circles.
    
    Great circle 1 passes through p1, p2 (unit sphere XYZ).
    Great circle 2 passes through p3, p4 (unit sphere XYZ).
    
    Returns two antipodal intersection points (lat, lng) or None if parallel.
    """
    # Normal to plane of great circle 1
    n1 = normalize(cross_product(p1, p2))
    # Normal to plane of great circle 2
    n2 = normalize(cross_product(p3, p4))
    
    if n1 == (0,0,0) or n2 == (0,0,0):
        return None
    
    # Intersection line direction = cross product of the two normals
    line = normalize(cross_product(n1, n2))
    
    if line == (0,0,0):
        return None  # Parallel great circles (same or opposite)
    
    # Two antipodal points
    pt1 = line
    pt2 = (-line[0], -line[1], -line[2])
    
    lat1, lng1 = xyz_to_lat_lng(*pt1)
    lat2, lng2 = xyz_to_lat_lng(*pt2)
    
    return [(lat1, lng1), (lat2, lng2)]

def point_on_arc(p, a, b, tolerance_deg=5.0):
    """Check if point p is 'between' a and b on the great circle arc (within tolerance).
    
    Uses angular distance: if dist(a,p) + dist(p,b) ≈ dist(a,b), p is on the arc.
    """
    def angular_dist(x, y):
        d = dot_product(x, y)
        d = max(-1, min(1, d))
        return math.acos(d)
    
    p_xyz = lat_lng_to_xyz(*p) if isinstance(p, tuple) and len(p) == 2 else p
    a_xyz = lat_lng_to_xyz(*a) if isinstance(a, tuple) and len(a) == 2 else a
    b_xyz = lat_lng_to_xyz(*b) if isinstance(b, tuple) and len(b) == 2 else b
    
    d_ap = angular_dist(a_xyz, p_xyz)
    d_pb = angular_dist(p_xyz, b_xyz)
    d_ab = angular_dist(a_xyz, b_xyz)
    
    # Point is on arc if the sum of partial distances equals the total (within tolerance)
    tolerance_rad = deg2rad(tolerance_deg)
    return abs(d_ap + d_pb - d_ab) < tolerance_rad


# Define all 120 edges of the UVG grid
# The UVG 120 polyhedron connects vertices based on the icosidodecahedron topology
# Edges connect: polar→dodeca(5), polar→icosa(5), dodeca→icosa(adjacent), 
# icosa→equatorial, dodeca→equatorial, equatorial ring

def build_edges():
    """Build the 120 edges of the UVG grid based on icosidodecahedron connectivity.
    
    The key insight: vertices at the same or adjacent latitude bands connect
    if their longitude difference matches the geometric spacing (36° or 72°).
    """
    edges = set()
    
    # Helper: vertex IDs by latitude band
    north_pole = [1]
    south_pole = [62]
    north_dodeca = [2, 3, 4, 5, 6, 52, 53, 54, 55, 56]  # lat 52.62
    north_icosa = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]  # lat 26.57
    equatorial = list(range(17, 37))  # lat 0
    south_icosa = [37, 38, 39, 40, 41, 42, 43, 44, 45, 46]  # lat -26.57
    south_dodeca = [47, 48, 49, 50, 51, 57, 58, 59, 60, 61]  # lat -52.62
    
    # North Pole connects to all north dodecahedron vertices
    for v in north_dodeca:
        edges.add((1, v))
    
    # South Pole connects to all south dodecahedron vertices
    for v in south_dodeca:
        edges.add((62, v))
    
    # North dodecahedron ring (connect adjacent by longitude)
    nd_sorted = sorted(north_dodeca, key=lambda v: vertex_by_id[v]["lng"])
    for i in range(len(nd_sorted)):
        edges.add((nd_sorted[i], nd_sorted[(i+1) % len(nd_sorted)]))
    
    # South dodecahedron ring
    sd_sorted = sorted(south_dodeca, key=lambda v: vertex_by_id[v]["lng"])
    for i in range(len(sd_sorted)):
        edges.add((sd_sorted[i], sd_sorted[(i+1) % len(sd_sorted)]))
    
    # North icosahedron ring
    ni_sorted = sorted(north_icosa, key=lambda v: vertex_by_id[v]["lng"])
    for i in range(len(ni_sorted)):
        edges.add((ni_sorted[i], ni_sorted[(i+1) % len(ni_sorted)]))
    
    # South icosahedron ring
    si_sorted = sorted(south_icosa, key=lambda v: vertex_by_id[v]["lng"])
    for i in range(len(si_sorted)):
        edges.add((si_sorted[i], si_sorted[(i+1) % len(si_sorted)]))
    
    # Equatorial ring
    eq_sorted = sorted(equatorial, key=lambda v: vertex_by_id[v]["lng"])
    for i in range(len(eq_sorted)):
        edges.add((eq_sorted[i], eq_sorted[(i+1) % len(eq_sorted)]))
    
    # Cross-band connections: dodeca to icosa (same longitude or ±36°)
    for d in north_dodeca:
        d_lng = vertex_by_id[d]["lng"]
        for ic in north_icosa:
            ic_lng = vertex_by_id[ic]["lng"]
            diff = abs(d_lng - ic_lng) % 360
            if diff < 1 or diff > 359 or abs(diff - 36) < 1 or abs(diff - 324) < 1:
                edges.add(tuple(sorted((d, ic))))
    
    for d in south_dodeca:
        d_lng = vertex_by_id[d]["lng"]
        for ic in south_icosa:
            ic_lng = vertex_by_id[ic]["lng"]
            diff = abs(d_lng - ic_lng) % 360
            if diff < 1 or diff > 359 or abs(diff - 36) < 1 or abs(diff - 324) < 1:
                edges.add(tuple(sorted((d, ic))))
    
    # Cross-band: icosa to equatorial (±18° longitude offset)
    for ic in north_icosa:
        ic_lng = vertex_by_id[ic]["lng"]
        for eq in equatorial:
            eq_lng = vertex_by_id[eq]["lng"]
            diff = abs(ic_lng - eq_lng) % 360
            if diff < 1 or diff > 359 or abs(diff - 18) < 1 or abs(diff - 342) < 1:
                edges.add(tuple(sorted((ic, eq))))
    
    for ic in south_icosa:
        ic_lng = vertex_by_id[ic]["lng"]
        for eq in equatorial:
            eq_lng = vertex_by_id[eq]["lng"]
            diff = abs(ic_lng - eq_lng) % 360
            if diff < 1 or diff > 359 or abs(diff - 18) < 1 or abs(diff - 342) < 1:
                edges.add(tuple(sorted((ic, eq))))
    
    return list(edges)


def is_on_land(lat, lng):
    """Very rough check if a coordinate is likely on land (not open ocean).
    Simplified bounding boxes for major landmasses.
    """
    # Major landmass rough bounds [min_lat, max_lat, min_lng, max_lng]
    landmasses = [
        (-35, 37, -20, 55, "Africa"),
        (35, 72, -12, 45, "Europe"),
        (8, 78, 25, 180, "Asia"),
        (-48, -10, 112, 155, "Australia"),
        (-55, 12, -82, -34, "South America"),
        (7, 85, -170, -50, "North America"),
        (-50, -30, 165, 180, "New Zealand"),
    ]
    for min_lat, max_lat, min_lng, max_lng, name in landmasses:
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return name
    return None


def compute_all_intersections(edges):
    """Compute intersections of all non-adjacent edge pairs."""
    intersections = []
    seen_coords = set()  # Deduplicate by rounded coords
    
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            e1 = edges[i]
            e2 = edges[j]
            
            # Skip if edges share a vertex (adjacent)
            if e1[0] in e2 or e1[1] in e2:
                continue
            
            # Get vertex coordinates
            v1a = vertex_by_id[e1[0]]
            v1b = vertex_by_id[e1[1]]
            v2a = vertex_by_id[e2[0]]
            v2b = vertex_by_id[e2[1]]
            
            # Convert to XYZ
            p1 = lat_lng_to_xyz(v1a["lat"], v1a["lng"])
            p2 = lat_lng_to_xyz(v1b["lat"], v1b["lng"])
            p3 = lat_lng_to_xyz(v2a["lat"], v2a["lng"])
            p4 = lat_lng_to_xyz(v2b["lat"], v2b["lng"])
            
            # Find great circle intersections
            result = great_circle_intersection(p1, p2, p3, p4)
            if result is None:
                continue
            
            # Check which intersection point(s) are actually on both arcs
            for pt_lat, pt_lng in result:
                # Deduplicate (round to 0.1 degree)
                key = (round(pt_lat, 1), round(pt_lng, 1))
                if key in seen_coords:
                    continue
                
                # Check if point is on both arcs (not just on the great circles)
                pt_xyz = lat_lng_to_xyz(pt_lat, pt_lng)
                on_arc1 = point_on_arc(pt_xyz, p1, p2)
                on_arc2 = point_on_arc(pt_xyz, p3, p4)
                
                if on_arc1 and on_arc2:
                    seen_coords.add(key)
                    land = is_on_land(pt_lat, pt_lng)
                    intersections.append({
                        "lat": round(pt_lat, 4),
                        "lng": round(pt_lng, 4),
                        "edge1": [e1[0], e1[1]],
                        "edge2": [e2[0], e2[1]],
                        "edge1_names": [v1a["name"], v1b["name"]],
                        "edge2_names": [v2a["name"], v2b["name"]],
                        "on_land": land,
                        "priority": "high" if land else "low",
                    })
    
    return intersections


def main():
    print("Building UVG grid edges...")
    edges = build_edges()
    print(f"  {len(edges)} edges defined")
    
    print("Computing great circle intersections...")
    intersections = compute_all_intersections(edges)
    print(f"  {len(intersections)} intersection points found")
    
    # Separate land vs ocean
    land_intersections = [p for p in intersections if p["on_land"]]
    ocean_intersections = [p for p in intersections if not p["on_land"]]
    print(f"  {len(land_intersections)} on land (HIGH PRIORITY)")
    print(f"  {len(ocean_intersections)} in ocean")
    
    # Sort land intersections by latitude for readability
    land_intersections.sort(key=lambda p: -p["lat"])
    
    # Assign IDs
    for i, pt in enumerate(intersections):
        pt["id"] = f"INT-{i+1:04d}"
    
    # Save output
    output = {
        "name": "UVG Grid Intersection Points",
        "description": "All points where UVG 120 grid edges cross each other. Each point is where two great circle lines intersect — these are investigation targets.",
        "total_intersections": len(intersections),
        "land_intersections": len(land_intersections),
        "ocean_intersections": len(ocean_intersections),
        "intersections": intersections,
    }
    
    output_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-intersections.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {output_path}")
    
    # Print top land intersections
    print(f"\n{'='*60}")
    print("TOP LAND-BASED INTERSECTION POINTS (Investigation Targets):")
    print(f"{'='*60}")
    for pt in land_intersections[:20]:
        print(f"  {pt.get('id','?')} | {pt['lat']:>7.2f}°, {pt['lng']:>8.2f}° | {pt['on_land']}")
        print(f"       Lines: {pt['edge1_names'][0][:30]} ↔ {pt['edge1_names'][1][:30]}")
        print(f"              {pt['edge2_names'][0][:30]} ↔ {pt['edge2_names'][1][:30]}")
        print()


if __name__ == "__main__":
    main()
