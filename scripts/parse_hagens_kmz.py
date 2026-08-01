"""Parse the official Bethe Hagens UVG KMZ file to extract all 62 grid vertices.

Extracts Placemark points with their coordinates and names from the KML data.
This gives us the authoritative, Hagens-verified coordinates for the grid.
"""

import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET

KMZ_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "data", "UVG-grid-compiled-by-B-Hagens.kmz")

# Extract KML from KMZ
with zipfile.ZipFile(KMZ_PATH, "r") as z:
    kml_content = z.read("doc.kml").decode("utf-8", errors="replace")

# Parse XML (KML namespace)
# Remove namespace for easier parsing
kml_clean = re.sub(r' xmlns="[^"]*"', '', kml_content)
root = ET.fromstring(kml_clean)

# Find all Placemarks
placemarks = root.findall(".//{0}Placemark".format("")) or root.findall(".//Placemark")

print(f"Total Placemarks found: {len(placemarks)}")

# Extract points (vertices) vs lines (edges)
points = []
lines = []
folders = root.findall(".//Folder")
print(f"Folders: {len(folders)}")
for folder in folders:
    folder_name = folder.findtext("name", "")
    print(f"  Folder: {folder_name}")

# Get all placemarks with Point geometry (these are the vertices)
all_placemarks = root.iter("Placemark")
for pm in all_placemarks:
    name = pm.findtext("name", "").strip()
    point = pm.find(".//Point")
    linestring = pm.find(".//LineString")
    
    if point is not None:
        coords_text = point.findtext("coordinates", "").strip()
        if coords_text:
            parts = coords_text.split(",")
            if len(parts) >= 2:
                lng = float(parts[0])
                lat = float(parts[1])
                alt = float(parts[2]) if len(parts) > 2 else 0
                points.append({
                    "name": name,
                    "lat": lat,
                    "lng": lng,
                    "alt": alt,
                })
    
    elif linestring is not None:
        coords_text = linestring.findtext("coordinates", "").strip()
        if coords_text:
            line_coords = []
            for coord_str in coords_text.split():
                parts = coord_str.split(",")
                if len(parts) >= 2:
                    line_coords.append({
                        "lng": float(parts[0]),
                        "lat": float(parts[1]),
                    })
            if line_coords:
                lines.append({
                    "name": name,
                    "coordinates": line_coords,
                })

print(f"\nExtracted: {len(points)} points, {len(lines)} lines")
print()

# Show the points (grid vertices)
print("=" * 70)
print("GRID VERTICES (from Bethe Hagens KMZ):")
print("=" * 70)

# Sort by name to find numbered nodes
points_sorted = sorted(points, key=lambda p: p["name"])
for i, p in enumerate(points_sorted[:62]):
    print(f"  {p['name']:<40} {p['lat']:>8.4f}°, {p['lng']:>9.4f}°")

# Save to JSON
output = {
    "name": "Becker-Hagens UVG Grid — Official Coordinates (from B. Hagens KMZ)",
    "source": "UVG-grid-compiled-by-B-Hagens.kmz via Wayback Machine (original from vortexmaps.com)",
    "total_points": len(points),
    "total_lines": len(lines),
    "points": points,
    "lines": [{"name": l["name"], "point_count": len(l["coordinates"])} for l in lines],
}

output_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-hagens-official.json")
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"\nSaved to {output_path}")

# Also save full line data
lines_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "uvg-grid-hagens-lines.json")
with open(lines_path, "w") as f:
    json.dump({"lines": lines}, f, indent=2)
print(f"Lines saved to {lines_path}")
