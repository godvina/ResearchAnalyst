# Architecture: Grid Intelligence System

## The Core Insight
The Becker-Hagens UVG grid defines geometric relationships between points on Earth. Some of those points have documented ancient sites. The investigative question is: **what do sites connected by the same grid line have in common, and what's at the points we haven't investigated yet?**

This isn't just a map — it's a **knowledge graph with geometric edges and AI-researched nodes.**

## Data Pipeline

```
[Grid Geometry]  →  [Site Research]  →  [S3 Raw]  →  [OpenSearch Vectors]  →  [Aurora Structured]  →  [Neptune Graph]  →  [Frontend]
     Math              AI + Brave          Store         Similarity Search        Relational            Relationships        Visualization
```

### Stage 1: Geometry Validation
- Compute exact UVG 120 polyhedron vertices (62 points)
- Validate by checking: do known sites (Giza, Stonehenge, etc.) actually fall ON a grid line?
- Calculate great circle distance from each known site to nearest grid line
- If distance < 50km → confirmed on-line. If 50-200km → close. If >200km → not on grid.
- Output: validated set of vertices + edges with confidence scores

### Stage 2: Site Research (AI + Brave)
For each grid node (land-based):
- What's physically there? (archaeological surveys, satellite imagery)
- Any ancient/sacred sites within 100km?
- Folklore or legends about this location?
- Geological anomalies? (magnetic, seismic, geothermal)
- Is there existing academic literature?
- Has LiDAR been used here?

Research output follows the TAXONOMY PATTERN:
- Domain: Grid & Earth Energy
- Typology: [Node type — icosahedron/dodecahedron/equatorial]
- Method: [Investigation method — archaeological/geological/folklore/satellite]
- Signature: [Specific finding — "stone circle at coordinates X" or "magnetic anomaly detected"]

### Stage 3: Store in S3 (Raw Findings)
- Each node gets a research document (JSON)
- Contains: raw search results, AI synthesis, sources, confidence levels
- Versioned — re-research updates the document without losing history

### Stage 4: OpenSearch Vectors
- Embed each node's research text using Titan Embed
- Index into `grid-node-research` index with:
  - node_id, lat, lng, research_text_embedding, known_sites, evidence_score
- Enables: "Find nodes similar to Giza" → returns nodes with similar characteristics
- Enables: "What do Node 7 and Node 44 have in common?" → vector comparison

### Stage 5: Aurora Structured Data
- `grid_nodes` table: id, lat, lng, type, classification, known_site, evidence_score, last_researched
- `grid_edges` table: from_node, to_node, great_circle_distance_km, sites_on_line_count
- `grid_findings` table: node_id, finding_type, evidence_status, finding_data, created_at
- Enables: SQL queries like "give me all nodes with evidence_score > 50 that haven't been researched in 30 days"

### Stage 6: Neptune Graph
- Vertices: grid nodes + known ancient sites
- Edges: 
  - `CONNECTED_BY_GRID_LINE` (geometric relationship)
  - `SIMILAR_TO` (vector similarity > 0.8)
  - `SHARES_CHARACTERISTIC` (same typology/method)
  - `ON_SAME_ALIGNMENT` (multiple sites on one great circle)
- Enables: 
  - "What connects Giza to Easter Island?" → traverse graph
  - "Find all sites that share 'precision stone cutting' with Giza" → SHARES_CHARACTERISTIC
  - "What's between Node 7 and Node 44 on their connecting line?" → graph + geometry

### Stage 7: Frontend Visualization
- Full globe with 62 nodes, 120 edges, color-coded by evidence
- Click any node → research summary + investigation panel
- Graph view showing connections between similar sites
- "What's in common?" comparison tool (pick 2+ sites, see shared attributes)
- Priority board: ranked list of where to send a team next

## The Discovery Channel Moment
A researcher uses this system and asks: 
> "Show me all grid nodes that have precision megalithic stone construction."

The system returns: Giza, Machu Picchu, Easter Island, Baalbek, Puma Punku.

Then they ask:
> "Are they connected by grid lines?"

Neptune graph traversal shows: Yes — Giza and Easter Island are connected via the equatorial great circle. Machu Picchu and Nazca are on the same node.

Then:
> "What's BETWEEN Giza and Easter Island on that line that we haven't investigated?"

The system computes intermediate points along the great circle and shows:
- Point at 0°N, 31.72°E: Lake Victoria (geological anomaly zone — East African Rift)
- Point at -26.57°S, -4.28°W: Gulf of Guinea (underwater plateau — unexplored)

**"Let's get a boat and side-scan sonar to that underwater plateau."**

That's the show.

## Implementation Priority
1. Validate geometry (verify known sites are actually on grid lines)
2. Build Neptune graph with basic edges
3. Research each land node (batch AI research)
4. Embed and index into OpenSearch
5. Build comparison/similarity queries
6. Frontend globe + investigation panel

## What Makes This Better Than a Static Map
- It's a LIVING system — research accumulates over time
- It finds connections humans might miss (vector similarity across 62 nodes)
- It can answer "what's in common?" across the entire planet
- It prioritizes where to look next based on evidence, not guesswork
- The taxonomy structure means findings are categorized and searchable
- Neptune graph means relationships are first-class queryable entities
