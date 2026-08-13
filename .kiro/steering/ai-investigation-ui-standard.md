---
inclusion: auto
---

# AI Investigation UI Standard

## Rule: Every new frontend module MUST include an AI Investigation Layer.

No flat reports. No charts without interpretation. No data tables without "so what."

When we build a new module/tab/view, the AI interprets the data and narrates the significance. The user sees insight first, data second. This is the difference between a dashboard and an investigative intelligence platform.

---

## Geospatial Data Standard (MANDATORY for all datasets)

Every dataset loaded into the platform MUST include geographic metadata. This enables the Geographic Explorer, globe views, map overlays, and cross-case location analysis.

### Required Fields on Every Entity/Record

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `country` | string | YES | "Ireland" |
| `region` | string | YES (computed if not explicit) | "Boyne Valley" |
| `coordinates` | `{lat, lon}` | YES if location-based | `{lat: 53.6947, lon: -6.4754}` |
| `county` / `state` / `province` | string | YES | "Meath" |

### Rules

1. **Every new dataset must have a county/state-to-region mapping** — Define it at ingest time. If unsure of regions, group by geographic proximity (within 50km).
2. **Always include coordinates** — Use the GeocodingService for named locations, or add to its CURATED_LOCATIONS if missing. Never leave entities without lat/lon if they represent a physical place.
3. **Build a GEO_REGIONS lookup for every dataset** — Hierarchical: Country → Region → Site IDs. This powers the sidebar navigator across all geospatial views.
4. **Country is always top-level** — Even for single-country datasets (like Irish sites), wrap in a country key. This keeps the data model consistent when multi-country data arrives later.
5. **Tag every record with source provenance** — `{source: "irish_ancient_sites.json", loaded: "2026-08-03"}` for traceability.

### Adding New Geographic Data

When a new dataset arrives:

```python
# 1. Define the region mapping
REGION_MAP = {
    "Meath": "Boyne Valley",
    "Sligo": "Sligo / Carrowmore",
    "Clare": "The Burren",
    # ...
}

# 2. Compute region for each record
for record in dataset:
    record['region'] = REGION_MAP.get(record['county'], record['county'])

# 3. Build GEO_REGIONS lookup
geo_regions = {"Country": {}}
for record in dataset:
    region = record['region']
    if region not in geo_regions["Country"]:
        geo_regions["Country"][region] = []
    geo_regions["Country"][region].append(record['id'])

# 4. Resolve coordinates
from src.services.geocoding_service import GeocodingService
geo = GeocodingService()
unresolved = [r for r in dataset if not r.get('coordinates')]
if unresolved:
    results = geo.geocode([r['name'] for r in unresolved])
    # Add missing coords to CURATED_LOCATIONS if needed
```

### Why This Matters

- Geographic views are the PRIMARY exploration interface for field researchers
- Cross-case location overlap reveals connections invisible in text-only analysis
- The globe view (grid-globe.html) renders any dataset that has coordinates + regions
- Neptune graph queries filter by location — no coords means invisible in graph
- Future multi-country analysis depends on consistent country → region → site hierarchy

### GeocodingService Updates

When adding new geographic areas, update `src/services/geocoding_service.py` CURATED_LOCATIONS with:
- All site coordinates from the new dataset
- Region center points (for zoom-to-region behavior)
- Country center point (if new country)

---

## The AI Investigation Layer (MANDATORY for all new modules)

Every new frontend module includes these five components:

### 1. AI Intelligence Brief (🤖 panel)

- Blue-bordered panel at the top of any detail/drill-down view
- 3-paragraph narrative: **Hook** (dramatic finding) → **Evidence** (specific data) → **Implication** (what it means)
- Pre-generated via Bedrock and cached as static JS (no live API calls in the browser)
- Loading skeleton while content renders
- Refresh button (triggers regeneration via build script)
- Falls back gracefully: "Brief pending — run generate script" if not yet generated

### 2. Theory Verdict Cards

- Every data point gets scored against relevant patterns/theories
- Verdicts: **PROVEN** (≥0.80, green), **INSUFFICIENT** (0.40-0.79, yellow), **UNPROVEN** (<0.40, red), **ACTIVE INVESTIGATION** (rising score, blue)
- Displayed as small cards with verdict badge (top-right), score bar, 1-line evidence summary
- Uses the `.card` CSS pattern from theory-investigation.html with `border-top` color coding
- Sorted by score descending (strongest evidence first)

### 3. Research Missions

- For every INSUFFICIENT or ACTIVE theory, show what would advance the score
- Amber-bordered section with checkbox tasks
- Each task: specific, actionable, measurable (not vague)
- Checkboxes persist to localStorage (user tracks progress)
- Format: "To advance {theory} from {current} → {target}: [specific task]"

### 4. Narrated Network Graph

- D3 force-directed graph showing connections
- Edges have AI-narrated labels explaining WHY things connect (not just "connected")
- Edge click → shows full narrated explanation
- Nodes colored by type/domain
- Central node = currently selected item (larger, highlighted)
- The graph answers: "Did you know this connects to X? Here's why that matters."

### 5. Documentary View Toggle

- Every module has a toggle: **📊 Data View** ↔ **🎬 Documentary View**
- Documentary View = scrollable narrated story, not data grid
- Cinematic typography: large serif headers, generous line-height (1.8), max-width 720px centered
- Chapter-based structure per logical grouping (region, case, time period)
- Inline visualizations within narrative (mini maps, score cards, mini graphs)
- Pre-generated per grouping, cached as static JS

---

## UI Design System (MANDATORY — no deviations)

All modules use these design tokens. Do NOT create module-specific color schemes or layouts.

### Color Palette

```css
/* Backgrounds */
--bg-primary: #0a0f19;
--bg-card: rgba(26, 35, 50, 0.9);
--bg-card-hover: rgba(26, 35, 50, 1.0);

/* Borders */
--border-default: rgba(255, 255, 255, 0.08);
--border-hover: rgba(99, 179, 237, 0.3);

/* Accent Colors */
--accent-primary: #63b3ed;    /* Blue — default, links, active states */
--accent-success: #48bb78;    /* Green — proven, high scores, healthy */
--accent-warning: #ecc94b;    /* Yellow — insufficient, moderate, needs attention */
--accent-danger: #f56565;     /* Red — unproven, errors, critical */
--accent-purple: #b794f4;     /* Purple — cross-domain, connections, patterns */
--accent-amber: #ed8936;      /* Amber — field notes, research missions, action items */
--accent-gold: #f6ad55;       /* Gold — cross-domain badge, high-value items */

/* Text */
--text-primary: #e2e8f0;
--text-secondary: #a0aec0;
--text-muted: #718096;
```

### Layout Patterns

| Pattern | When to Use | Structure |
|---------|-------------|-----------|
| Two-column (sidebar + main) | Browse/drill-down modules | 320px fixed sidebar, fluid main |
| Card grid | Multiple items to compare | `grid-template-columns: repeat(auto-fill, minmax(380px, 1fr))` |
| Detail panel (expandable) | Single item deep-dive | Full-width below main content, slides in |
| Header + nav bar + content | Every page | Use `common.css` header/nav classes |

### Component Patterns (reuse, don't reinvent)

| Component | Source File | CSS Class |
|-----------|-------------|-----------|
| Score bar (horizontal) | theory-investigation.html | `.score-row`, `.score-bar`, `.score-fill` |
| Verdict badge | theory-investigation.html | `.card-badge.proven`, `.card-badge.insufficient`, `.card-badge.unproven` |
| Domain tabs | theory-investigation.html | `.domain-tab`, `.domain-tab.active` |
| Cross-domain panel | theory-investigation.html | `.cross-domain`, `.cross-domain .tag` |
| Investigation sections | theory-investigation.html | `.inv-section`, `.inv-hook`, `.inv-facts`, etc. |
| Network graph panel | grid-globe.html | `.network-panel`, `#networkSvg` |
| Card with border-top | theory-investigation.html | `.card`, `.card.proven`, `.card.insufficient` |
| Nav bar | common.css / index.html | `.nav-bar`, `.nav-link`, `.nav-link.active` |
| Loading skeleton | pattern-library.html | `.skeleton-line`, `.skeleton-pulse` |

### Typography

- Body: `"Segoe UI", system-ui, sans-serif`
- Code/data: `"Cascadia Code", "Fira Code", monospace`
- Documentary mode headers: `Georgia, "Times New Roman", serif` (cinematic feel)
- Base size: 0.78rem for body, 0.68rem for metadata, 1.0-1.3rem for headings

### Shared Dependencies (CDN)

Every module loads these — never bundle or self-host:
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://d3js.org/d3.v7.min.js"></script>
```

And these local files:
```html
<link rel="stylesheet" href="common.css">
<script src="config.js"></script>
```

---

## AI Content Generation Pattern (for build scripts)

Every module that needs AI narratives follows this pattern:

### Script Structure: `scripts/generate_{module}_narratives.py`

```python
"""Generate AI narratives for {module_name}.
Run once to build static narrative JS file. Re-run when data changes.
Estimated cost: $X.XX for ~N Bedrock calls.
"""
import json
import boto3

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# 1. Load source data
data = json.load(open('src/data/...'))

# 2. Generate intelligence briefs (1 per entity)
briefs = {}
for item in data:
    prompt = build_brief_prompt(item)  # hook → evidence → implication
    response = invoke_bedrock(prompt)
    briefs[item['id']] = response

# 3. Generate research missions (1 per item with gaps)
missions = {}
for item in data:
    gaps = [t for t in item['theories'] if t['score'] < 0.80]
    if gaps:
        prompt = build_missions_prompt(item, gaps)
        missions[item['id']] = invoke_bedrock(prompt)

# 4. Generate documentary chapters (1 per logical grouping)
chapters = {}
for group_id, group_items in groupby(data):
    prompt = build_documentary_prompt(group_items)
    chapters[group_id] = invoke_bedrock(prompt)

# 5. Generate connection narratives (1 per unique edge)
connections = {}
for edge in unique_edges:
    prompt = build_connection_prompt(edge)
    connections[edge_key] = invoke_bedrock(prompt)

# 6. Write output
output = f"""// Auto-generated by generate_{module}_narratives.py
// Cost: ${total_cost:.4f} | Calls: {call_count} | Generated: {datetime.now()}
const {MODULE}_BRIEFS = {json.dumps(briefs, indent=2)};
const {MODULE}_MISSIONS = {json.dumps(missions, indent=2)};
const {MODULE}_CHAPTERS = {json.dumps(chapters, indent=2)};
const {MODULE}_CONNECTIONS = {json.dumps(connections, indent=2)};
"""
with open(f'src/frontend/{module}-narratives.js', 'w') as f:
    f.write(output)
```

### Prompt Templates

**Intelligence Brief prompt:**
```
You are an investigative intelligence analyst writing a brief for a field researcher.
Given this data about {entity_name}: {data_json}

Write exactly 3 paragraphs:
1. HOOK: The single most striking finding — lead with the anomaly or connection
2. EVIDENCE: Specific measurements, dates, academic sources that support the finding
3. IMPLICATION: What this means for the broader investigation, and what remains unproven

Use specific numbers. Cite sources. Be authoritative but open-minded. Never dismiss alternative interpretations — investigate them.
Max 200 words total.
```

**Documentary Chapter prompt:**
```
You are writing an investigative documentary script for a History Channel / Discovery Channel program.
Write a chapter about {group_name} covering these items: {items_json}

Structure:
- Hook: dramatic opening question that grabs attention
- Evidence: specific measurements, dates, comparisons
- Anomaly: what doesn't fit conventional explanations
- Pattern: connections to other sites/cases globally
- Research Mission: what a field researcher should investigate next

Tone: Authoritative but open-minded. Present mainstream explanations AND alternative interpretations fairly. Never dismiss — investigate. Use specific numbers and academic sources.
500-800 words.
```

**Connection Narrative prompt:**
```
Explain in 1-2 sentences why {entity_A} connects to {entity_B}.
Connection type: {pattern_type}
Shared data: {shared_evidence}
Be specific — use numbers, dates, measurements. Not vague ("similar") — precise ("both resonate at 110Hz").
```

---

## Module Checklist (MANDATORY before starting implementation)

When building a new module, verify ALL of these are planned:

### Geospatial Requirements
- [ ] Dataset has `country`, `region`, `coordinates` fields on every location entity
- [ ] County/state-to-region mapping defined
- [ ] `GEO_REGIONS` hierarchical lookup built (Country → Region → IDs)
- [ ] GeocodingService CURATED_LOCATIONS updated with new sites + region centers
- [ ] Data-layer JS file includes the GEO_REGIONS constant for sidebar nav

### AI Investigation Layer
- [ ] Uses `common.css` + design tokens above (no custom color schemes)
- [ ] Has AI Intelligence Brief panel (blue-bordered, 🤖 header)
- [ ] Has Theory Verdict Cards (proven/insufficient/unproven)
- [ ] Has Research Missions panel (amber, checkboxes, localStorage)
- [ ] Has narrated network graph (D3 force, AI edge labels)
- [ ] Has Documentary View toggle
- [ ] Has `scripts/generate_{module}_narratives.py` for AI content
- [ ] Outputs static `{module}-narratives.js` (no live Bedrock calls in browser)

### UI Consistency
- [ ] Reuses existing CSS components (score bars, verdict badges, cards)
- [ ] Follows two-column or card-grid layout pattern
- [ ] Added to nav-bar in index.html
- [ ] Added to nav-links in related pages
- [ ] Supports URL params for deep-linking (?item=X, ?mode=documentary)
- [ ] Loading skeletons for AI content
- [ ] Graceful fallback when narratives not yet generated

---

## Why This Pattern (for future reference)

### The Problem It Solves
Every AWS dashboard/report project drifts toward "flat data with charts." Users look at a bar chart and think "okay, but so what?" The AI Investigation Layer answers "so what" automatically. It's the difference between a report and an analyst.

### How Top AWS Builders Keep UI Consistent
1. **Design tokens, not ad-hoc colors** — Every color, spacing, and font decision is a token reference, not a hex code in the CSS. When you want to change the accent color, change it once.
2. **Component library via copy-paste** — Without React/Vue (this project is vanilla JS), consistency comes from copying existing component patterns (score bars, cards, panels) verbatim and only changing the data. Never redesign a card.
3. **Layout templates** — Only 3 layouts exist: two-column, card-grid, detail-panel. Pick one. Don't invent a fourth.
4. **Static generation over live APIs** — For AI content, pre-generate and cache as JS files. This means: instant load, works offline, no CORS issues, no Lambda cold starts, no rate limiting in the UI. Regenerate on data change.
5. **Shared CSS file** — `common.css` defines the header, nav, page layout, and base typography. Every page imports it. Module-specific CSS is in `<style>` in the page, but only for module-specific components — never override the base.
6. **Narrative-first, data-second** — The AI brief is the FIRST thing you see when you drill into anything. Data tables and charts are below, for verification. This trains users to start with insight, not raw numbers.

### Anti-Patterns (DON'T)
- ❌ New color scheme per module ("let's make this one teal")
- ❌ Charts without AI interpretation ("here's a bar chart, figure it out")
- ❌ Custom card/panel designs when existing ones work
- ❌ Live Bedrock calls in the frontend (latency, cost, offline-hostile)
- ❌ Framework churn (no React, no Vue, no Svelte — vanilla JS matches existing codebase)
- ❌ Self-hosted CDN assets (Leaflet, D3 from CDN — simpler, cacheable)
- ❌ Separate styling per page (use common.css + design tokens)
