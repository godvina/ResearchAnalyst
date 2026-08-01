"""Validate UVG grid geometry — verify known sites fall on grid lines.

This script:
1. Computes the exact geometry of the UVG 120 polyhedron
2. For each known ancient site, calculates distance to nearest grid LINE (not just vertex)
3. Reports which sites are confirmed on-grid vs not
4. Validates the grid orientation (Giza should be very close to a vertex)

The key question: are these sites actually on the lines, or is it coincidence?
"""

import json
import math
import os

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

def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def normalize(v):
    mag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if mag < 1e-12: return (0,0,0)
    return (v[0]/mag, v[1]/mag, v[2]/mag)

def angular_distance_deg(p1, p2):
    """Angular distance in degrees between two points on unit sphere (XYZ)."""
    d = dot(p1, p2)
    d = max(-1.0, min(1.0, d))
    return rad2deg(math.acos(d))

def distance_point_to_great_circle_deg(point_xyz, gc_normal):
    """Angular distance from a point to a great circle defined by its normal vector.
    
    The great circle is the set of all points perpendicular to gc_normal.
    Distance from point to great circle = |90° - angle between point and normal|.
    """
    angle_to_normal = angular_distance_deg(point_xyz, gc_normal)
    return abs(90.0 - angle_to_normal)

def km_from_degrees(degrees):
    """Convert angular degrees to km on Earth's surface."""
    return degrees * 111.32  # 1 degree ≈ 111.32 km

# Known ancient sites with precise coordinates
KNOWN_SITES = [
    {"name": "Great Pyramid of Giza", "lat": 29.9792, "lng": 31.1342},
    {"name": "Stonehenge", "lat": 51.1789, "lng": -1.8262},
    {"name": "Machu Picchu", "lat": -13.1631, "lng": -72.5450},
    {"name": "Easter Island (Ahu Tongariki)", "lat": -27.1256, "lng": -109.2767},
    {"name": "Nazca Lines", "lat": -14.7350, "lng": -75.1300},
    {"name": "Angkor Wat", "lat": 13.4125, "lng": 103.8670},
    {"name": "Göbekli Tepe", "lat": 37.2233, "lng": 38.9225},
    {"name": "Mohenjo-daro", "lat": 27.3242, "lng": 68.1386},
    {"name": "Chaco Canyon", "lat": 36.0604, "lng": -107.9615},
    {"name": "Uluru", "lat": -25.3444, "lng": 131.0369},
    {"name": "Great Zimbabwe", "lat": -20.2674, "lng": 30.9338},
    {"name": "Teotihuacan", "lat": 19.6925, "lng": -98.8438},
    {"name": "Newgrange", "lat": 53.6947, "lng": -6.4756},
    {"name": "Avebury", "lat": 51.4288, "lng": -1.8544},
    {"name": "Sedona (Bell Rock)", "lat": 34.8069, "lng": -111.7624},
    {"name": "Lake Baikal (Olkhon Island)", "lat": 53.1828, "lng": 107.3383},
    {"name": "Bermuda (center)", "lat": 32.3078, "lng": -64.7505},
    {"name": "Devil's Sea (center)", "lat": 25.0000, "lng": 136.0000},
    {"name": "Richat Structure (Eye of Sahara)", "lat": 21.1246, "lng": -11.4018},
    {"name": "Gunung Padang", "lat": -6.9946, "lng": 107.0564},
    {"name": "Baalbek", "lat": 34.0069, "lng": 36.2039},
    {"name": "Tiwanaku", "lat": -16.5546, "lng": -68.6732},
    {"name": "Puma Punku", "lat": -16.5617, "lng": -68.6803},
    {"name": "Sacsayhuaman", "lat": -13.5092, "lng": -71.9822},
    {"name": "Petra", "lat": 30.3285, "lng": 35.4444},
    {"name": "Persepolis", "lat": 29.9352, "lng": 52.8916},
]


def load_grid():
    grid_file = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-62-points.json")
    with open(grid_file) as f:
        return json.load(f)


def build_all_edges(vertices):
    """Build edges connecting vertices based on the UVG icosidodecahedron topology.
    
    Every edge is a great circle segment. We need the FULL set to test if sites
    fall on ANY grid line.
    """
    v_by_id = {v["id"]: v for v in vertices}
    edges = []
    
    # For the full UVG 120, every pair of vertices at adjacent latitude bands
    # with appropriate longitude spacing are connected.
    # Adjacent bands: polar↔dodeca, dodeca↔icosa, icosa↔equatorial
    
    bands = {
        "n_pole": [v for v in vertices if v["lat"] == 90],
        "n_dodeca": [v for v in vertices if 50 < v["lat"] < 55],
        "n_icosa": [v for v in vertices if 25 < v["lat"] < 28],
        "equatorial": [v for v in vertices if v["lat"] == 0],
        "s_icosa": [v for v in vertices if -28 < v["lat"] < -25],
        "s_dodeca": [v for v in vertices if -55 < v["lat"] < -50],
        "s_pole": [v for v in vertices if v["lat"] == -90],
    }
    
    def lng_diff(a, b):
        d = abs(a - b) % 360
        return min(d, 360 - d)
    
    # Polar to dodecahedron (all connections)
    for p in bands["n_pole"]:
        for d in bands["n_dodeca"]:
            edges.append((p, d))
    for p in bands["s_pole"]:
        for d in bands["s_dodeca"]:
            edges.append((p, d))
    
    # Same-band ring connections
    for band_name in ["n_dodeca", "n_icosa", "equatorial", "s_icosa", "s_dodeca"]:
        band = sorted(bands[band_name], key=lambda v: v["lng"])
        for i in range(len(band)):
            next_v = band[(i+1) % len(band)]
            if lng_diff(band[i]["lng"], next_v["lng"]) < 40:  # Adjacent in ring
                edges.append((band[i], next_v))
    
    # Cross-band connections (dodeca ↔ icosa, icosa ↔ equatorial)
    for d in bands["n_dodeca"]:
        for ic in bands["n_icosa"]:
            if lng_diff(d["lng"], ic["lng"]) <= 37:
                edges.append((d, ic))
    for d in bands["s_dodeca"]:
        for ic in bands["s_icosa"]:
            if lng_diff(d["lng"], ic["lng"]) <= 37:
                edges.append((d, ic))
    for ic in bands["n_icosa"]:
        for eq in bands["equatorial"]:
            if lng_diff(ic["lng"], eq["lng"]) <= 19:
                edges.append((ic, eq))
    for ic in bands["s_icosa"]:
        for eq in bands["equatorial"]:
            if lng_diff(ic["lng"], eq["lng"]) <= 19:
                edges.append((ic, eq))
    
    return edges


def main():
    grid = load_grid()
    vertices = grid["vertices"]
    edges = build_all_edges(vertices)
    
    print(f"UVG Grid: {len(vertices)} vertices, {len(edges)} edges")
    print()
    
    # For each edge, compute the great circle normal
    gc_normals = []
    for e in edges:
        p1 = lat_lng_to_xyz(e[0]["lat"], e[0]["lng"])
        p2 = lat_lng_to_xyz(e[1]["lat"], e[1]["lng"])
        normal = normalize(cross(p1, p2))
        if normal != (0, 0, 0):
            gc_normals.append({
                "normal": normal,
                "from": e[0]["name"],
                "to": e[1]["name"],
            })
    
    print(f"Computed {len(gc_normals)} great circle normals")
    print()
    
    # For each known site, find distance to nearest grid line AND nearest vertex
    print(f"{'Site':<35} {'Nearest Line (km)':<20} {'Nearest Vertex (km)':<22} {'Status'}")
    print("=" * 100)
    
    results = []
    for site in KNOWN_SITES:
        site_xyz = lat_lng_to_xyz(site["lat"], site["lng"])
        
        # Distance to nearest great circle line
        min_line_dist_deg = 999
        nearest_line = ""
        for gc in gc_normals:
            dist = distance_point_to_great_circle_deg(site_xyz, gc["normal"])
            if dist < min_line_dist_deg:
                min_line_dist_deg = dist
                nearest_line = f"{gc['from'][:20]} → {gc['to'][:20]}"
        
        min_line_dist_km = km_from_degrees(min_line_dist_deg)
        
        # Distance to nearest vertex
        min_vertex_dist_deg = 999
        nearest_vertex = ""
        for v in vertices:
            v_xyz = lat_lng_to_xyz(v["lat"], v["lng"])
            dist = angular_distance_deg(site_xyz, v_xyz)
            if dist < min_vertex_dist_deg:
                min_vertex_dist_deg = dist
                nearest_vertex = v["name"][:30]
        
        min_vertex_dist_km = km_from_degrees(min_vertex_dist_deg)
        
        # Classification
        if min_line_dist_km < 50:
            status = "✅ ON GRID LINE"
        elif min_line_dist_km < 150:
            status = "⚠️  CLOSE"
        elif min_line_dist_km < 300:
            status = "🔶 NEAR"
        else:
            status = "❌ NOT ON GRID"
        
        print(f"{site['name']:<35} {min_line_dist_km:>8.0f} km        {min_vertex_dist_km:>8.0f} km          {status}")
        
        results.append({
            "name": site["name"],
            "lat": site["lat"],
            "lng": site["lng"],
            "nearest_line_km": round(min_line_dist_km, 1),
            "nearest_vertex_km": round(min_vertex_dist_km, 1),
            "nearest_line": nearest_line,
            "nearest_vertex": nearest_vertex,
            "on_grid": min_line_dist_km < 150,
        })
    
    print()
    on_grid = [r for r in results if r["on_grid"]]
    print(f"\nSUMMARY: {len(on_grid)}/{len(results)} known sites fall within 150km of a grid line")
    print(f"  On grid (<50km): {len([r for r in results if r['nearest_line_km'] < 50])}")
    print(f"  Close (50-150km): {len([r for r in results if 50 <= r['nearest_line_km'] < 150])}")
    print(f"  Near (150-300km): {len([r for r in results if 150 <= r['nearest_line_km'] < 300])}")
    print(f"  Not on grid (>300km): {len([r for r in results if r['nearest_line_km'] >= 300])}")
    
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "grid-validation-results.json")
    with open(output_path, "w") as f:
        json.dump({"sites": results, "summary": {
            "total_sites_tested": len(results),
            "on_grid_count": len(on_grid),
            "grid_vertices": len(vertices),
            "grid_edges": len(edges),
        }}, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
