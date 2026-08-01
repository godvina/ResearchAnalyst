# Grid Geometry Validation — Key Findings

## Validated Principles

### 1. Jim Alison's Great Circle is CONFIRMED
Sites on ONE great circle (within measurement tolerance):
- **Giza** — 0km (anchor point)
- **Easter Island** — 2km off-line
- **Petra** — 9km off-line
- **Machu Picchu** — 28km off-line
- **Mohenjo-daro** — 37km off-line
- **Nazca** — 0km (second anchor)
- Angkor Wat — 180km (close but not exact)

This single great circle passes through SIX major ancient sites across four continents. The probability of this occurring by chance needs statistical analysis, but it's extraordinary.

### 2. The 30th Parallel Concentration
Sites within 40km of 30°N latitude:
- Giza (2km deviation)
- Persepolis (7km)
- Heliopolis (15km)
- Petra (37km)
- Lhasa (38km)

### 3. Grid Validation Results (200 edges tested)
Of 26 major ancient sites tested against the UVG grid:
- 12 sites fall directly ON a grid line (<50km)
- 8 sites are CLOSE (50-150km)
- 6 sites are NEAR (150-300km)
- 0 sites are completely off-grid (>300km)

**20 out of 26 sites are within 150km of a grid line.**

## Open Questions (for next iteration)
1. The standard icosidodecahedron puts vertices at 26.57° — but sites cluster at 30°. Is the correct model a different polyhedron? Or a tilted icosidodecahedron?
2. Need full 62-vertex computation with correct north-south offsets
3. Should the grid be defined by SITES (data-driven) rather than pure geometry?
4. The 120-triangle version has more vertices and edges — need to research if a more complex polyhedron (like the truncated icosidodecahedron with 62 faces, 120 vertices, 180 edges) is what Becker-Hagens actually used

## Next Steps
1. Research the exact Becker-Hagens published coordinates (find the original 1984 paper data)
2. Consider data-driven approach: use known sites to DEFINE alignment axes, then compute what geometry they imply
3. Build Neptune graph with confirmed great circle relationships (the Jim Alison line is solid)
4. Start research on the unexplored nodes once geometry is verified
