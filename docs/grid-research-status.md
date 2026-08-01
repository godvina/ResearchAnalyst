# Grid Research Status — Sourcing Becker-Hagens Coordinates

## What We've Confirmed (from Bethe Hagens herself)

Source: https://gearthhacks.com/downloads/VortexMaps/ (written by Prof. Bethe Hagens)

1. The shape is a **hexakis icosahedron** (not a simple icosidodecahedron)
   - 62 vertices, 120 triangular faces, 180 edges
   - Composed of 15 great circles creating 120 identical right triangles
   - The 62 vertices = 12 icosahedron vertices + 20 dodecahedron vertices + 30 edge-midpoints

2. **Point 1 is near the Great Pyramid** (her exact words: "Pt. 1 being so close to the Great Pyramid")
   - Note: "close to" — not exactly AT Giza

3. **Orientation**: The dodecahedron component aligns with the mid-Atlantic ridge
   - This was the Russian team's (Goncharov/Morozov/Makarov) starting orientation
   - Archaeological alignments became visible AFTER the geometric orientation was set

4. The **15 great circles** tie it to Lakota creation mythology (15 hoops)

5. The authoritative data file is: `UVG-grid-compiled-by-B-Hagens.kmz`
   - Available at http://www.vortexmaps.com/hagens-grid-google.php
   - Server blocks automated downloads (406 error) — needs manual download
   - This KMZ file contains the exact coordinates used by Becker-Hagens

## Math Validation — Jim Alison's Great Circle

CONFIRMED: These sites are on ONE great circle (within measurement tolerance):
- Giza — 0km (anchor)
- Easter Island — 2km
- Petra — 9km
- Machu Picchu — 28km  
- Mohenjo-daro — 37km
- Nazca — 0km (second anchor)

This is the strongest validated ley line alignment in the dataset.

## How to Get Definitive Coordinates

### Option A: Manual KMZ Download (Recommended)
1. User goes to http://www.vortexmaps.com/hagens-grid-google.php
2. Downloads `UVG-grid-compiled-by-B-Hagens.kmz`
3. Opens in Google Earth Pro (free) → File → Save Place As → KML
4. We parse the KML/XML for all placemark coordinates

### Option B: Compute from Hexakis Icosahedron Math
The hexakis icosahedron vertices are:
- 12 icosahedron vertices: 2 poles + 10 at ±arctan(1/2) = ±26.565°
- 20 dodecahedron vertices (face-centers of icosahedron): 10 at ±52.622° + 10 at ±10.812°
- 30 edge-midpoints: at 0° and ±31.717° latitudes

Orientation: rotate so that the mid-Atlantic ridge (~-30° longitude) aligns with a dodecahedron edge, and vertex closest to Giza becomes Node 1.

### Option C: Data-Driven from Confirmed Alignments
Use Jim Alison's great circle + 30th parallel + known sites to DEFINE alignment axes, then compute grid geometry that best fits.

## Current Math Results (200-edge grid, 62 vertices)
- 20/26 sites within 150km of a grid line
- 12/26 within 50km (essentially ON the grid)
- 0/26 more than 300km off
- Tilted grid (3.4° to align with Giza) scores slightly better than standard

## Next Steps
1. Try Option A (manual KMZ download) — ask user
2. If unavailable, proceed with Option B (hexakis icosahedron math with corrected latitude bands)
3. Once coordinates verified, load into Neptune graph + begin auto-research of each node
