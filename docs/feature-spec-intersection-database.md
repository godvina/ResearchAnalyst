# Feature Spec: Global Grid Intersection Database

## Vision
Build a complete database of all intersection points where ley lines / Earth grid lines cross each other globally. For each intersection, auto-research what exists there and prioritize sites for field investigation.

## Source Data
- **Becker-Hagens UVG 120 Polyhedron**: 62 vertices, 120 edges (great circle segments), producing hundreds of intersection points
- **Documented ley lines**: St Michael's Line, Great Alignment, Apollo-St Michael Axis, etc.
- **Cross-reference**: Where do documented ley lines cross the UVG grid? These are HIGH priority.

## Architecture

### Step 1: Compute Intersection Points
- Take all 120 UVG edges (great circles between 62 vertices)
- Compute where each pair of non-adjacent great circles cross
- Also compute where documented ley lines cross UVG edges
- Store as coordinates in database with metadata (which lines cross here)

### Step 2: Auto-Research Each Intersection
For each intersection coordinate, run a research agent:
- What's within 50km? (known ruins, monuments, geological features)
- Any folklore about this location? (buried cities, sacred mountains, anomalies)
- Satellite imagery anomalies? (geometric patterns, unexplained structures)
- Academic surveys? (archaeological, geological, geomagnetic)
- Has LiDAR been used here? If not → PRIORITY

### Step 3: Build Priority Database
Each intersection gets a score:
- **Known site present** → CONFIRMED (green on map)
- **Folklore/legends** → HIGH PRIORITY (investigate with LiDAR)
- **Unexplored but accessible** → MEDIUM PRIORITY (send scout team)
- **Ocean/ice** → LOW PRIORITY (noted but not actionable)
- **Nothing found** → UNKNOWN (monitor for new research)

### Step 4: Interactive Map
- Show ALL intersection points on the globe
- Color-coded by priority/evidence
- Click any point → see what's there + research summary
- "Investigate" button → deep AI research on that specific coordinate
- Export list for field team planning

## The Discovery Channel Angle
A researcher looks at this and says:
> "Hey, Grid Node 7 is at Giza (known). But look — the line from Giza to Node 40 (Uluru) crosses a point in the Indian Ocean where there's a submerged plateau. And this OTHER line from Node 14 (Bermuda) crosses at the same point. Two independent grid lines crossing at a geological anomaly nobody's investigated. Let's get a ship with side-scan sonar."

THAT is what makes this a show. Not "here's a math grid" — but "the math predicted something should be here, and when we looked... there WAS something."

## Implementation Phases
1. **Compute all intersection coordinates** (math — can do offline)
2. **Store in database** with metadata (which lines, classification)
3. **Batch research** all accessible land intersections (AI + Brave)
4. **Priority ranking** algorithm
5. **Map visualization** with the full grid + color-coded intersections
6. **Individual investigation** drill-down from any intersection point

## Priority
HIGH — this is the core product differentiator. The grid + intersections + auto-research is what makes this system valuable beyond a static map.
