# Design: Geographic Explorer Tab

## Architecture Overview

The Geographic Explorer is a new standalone HTML page (`src/frontend/geographic-explorer.html`) following the same component-based architecture as the existing views (theory-investigation.html, grid-globe.html). It uses the established dark-theme design system, Leaflet for maps, and D3.js for network visualization.

This is NOT a passive data browser — it's an **AI-driven investigation experience**. When you select a site, the system generates an intelligence brief explaining what's significant, draws connections to sites worldwide, scores theories as proven/unproven/insufficient, and tells you what to investigate next. Think History Channel documentary meets intelligence platform.

## Data Flow

```
src/data/conspiracy-seed/irish_sacred_sites/
  ├── irish_ancient_sites.json         (15 sites — coordinates, taxonomy scores, field notes)
  ├── irish_ancient_sites_continued.json (additional sites)
  └── tier2_deep_research.json         (deep analysis — acoustic, construction, dating)
                │
                ▼
geographic-explorer-data.js (inline JSON load)
                │
                ├── Country List Panel     (grouped by country property)
                ├── Region Accordion       (grouped by county/region)
                ├── Site Cards             (scores, connections, GPS)
                ├── Detail Panel           (deep research, field notes, cross-domain)
                ├── AI Investigation Panel (Bedrock-generated intelligence briefs)
                ├── Theory Verdict Cards   (proven/insufficient/unproven per mystery)
                ├── Research Missions      (AI-generated field tasks)
                └── Documentary Mode       (narrated scrollable story per region)
```

## Two Modes: Data View ↔ Documentary View

A toggle at the top of the main area switches between:

1. **Data View** (default) — Map/Cards/Timeline with site selection and detail panel. The working investigation interface.
2. **Documentary View** — Pre-generated narrated story per region. Reads like a History Channel documentary script. Scrollable, cinematic typography, chapter-based.

Both modes share the same sidebar navigator.

## Component Structure

### Layout: Two-Column (Sidebar + Main)

```
┌──────────────────────────────────────────────────────────────┐
│ Header: 🗺️ Geographic Explorer  [nav links: Home, Globe, etc]│
├──────────────┬───────────────────────────────────────────────┤
│              │                                               │
│  SIDEBAR     │  MAIN AREA                                   │
│  (320px)     │                                               │
│              │  [Map View]  — Leaflet map with site pins     │
│  Country     │  ─────────────────────────────────────────── │
│  └ Region    │  [Site Detail / Cards Grid]                  │
│    └ Sites   │  - Drill-down investigation view             │
│              │  - Cross-domain connections                    │
│              │  - Field notes for trip planning               │
│              │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

### Sidebar: Hierarchical Navigator

- **Level 0: All Countries** — List of countries with site counts
- **Level 1: Regions within Country** — Collapsible accordion (Boyne Valley, Sligo, etc.)
- **Level 2: Sites within Region** — Clickable site names with mini-score badge

Sidebar state persists as user drills down. Breadcrumb at top of main area mirrors location.

### Main Area: Multi-View

Three view modes toggled by tabs above the content area:

1. **Map View** (default) — Leaflet map centered on selected country/region. Custom markers colored by taxonomy score (gold = cross-domain, green = high score, grey = standard). Click marker → populates Site Detail below.

2. **Cards View** — Grid of site cards (same pattern as theory-investigation.html card-grid). Each card shows: name, category badge, age, top 3 taxonomy scores as bar charts, connection count, GPS link.

3. **Timeline View** — Horizontal timeline of sites ordered by date_built (3500 BC → present). Color-coded by category. Shows construction sequence pattern.

## Site Detail Panel

Expands below map/cards when a site is selected. Contains:

| Section | Source Field | Visual |
|---------|-------------|--------|
| AI Intelligence Brief | Bedrock-generated (cached) | Blue-bordered panel with 🤖 header, narrative text, loading skeleton |
| Overview | name, category, age, coordinates | Header with category badge |
| Theory Verdict Cards | mysteries[] scored via proof engine | Grid of proven/insufficient/unproven cards |
| Taxonomy Scores | taxonomy_matches | Horizontal bar chart (0-1 scale) |
| Research Missions | AI-generated from theory gaps | Amber checklist: "what would advance this score" |
| Deep Research | tier2_deep_research[site_id] | Tabbed sections: Acoustic, Construction, Dating, Suppression |
| Cross-Domain | cross_domain_connections[] | Purple-bordered panel with narrated edge explanations |
| Field Notes | field_notes | Amber-bordered callout box |
| Narrated Network | (computed from cross_site_patterns) | D3 force graph with AI-explained edges |

### AI Intelligence Brief Panel

Same architecture as `ai-level-summaries` spec:
- On site selection, fetch cached brief or generate via Bedrock
- Prompt includes: site data, taxonomy scores, global connections, deep research findings
- Output: 3-paragraph narrative (hook → evidence → implication)
- Cached in local JSON (frontend-only, no Aurora needed for demo)
- Loading skeleton while generating
- Refresh button to regenerate

Example output:
> **🤖 Intelligence Brief — Newgrange**
>
> This 5,200-year-old chamber shares a 110Hz acoustic resonance with the Hal Saflieni Hypogeum in Malta and Chavín de Huántar in Peru — three sites on three continents, all engineered to the same frequency that EEG studies show suppresses language processing. The probability of convergence by chance is vanishingly low.
>
> Combined with waterproofing technology that has no modern equivalent without synthetic materials, and construction predating Giza by 500 years, this site scores 0.95 astronomical correlation — the highest in your dataset. The roofbox mechanism (1m × 0.25m aperture aligned to solar azimuth 134.5°) maintains accuracy within 1° across 5 millennia.
>
> The suppression pattern is notable: Martin Brennan's 1983 astronomical interpretations were dismissed as "fringe" by establishment archaeology, yet his equinox/solstice predictions were subsequently verified. This matches the taxonomy signature for information_asymmetry and expert_divergence.

### Theory Verdict Cards

Each site's mysteries are scored and displayed as verdict cards (reusing theory-investigation.html styling):

| Mystery/Theory | Verdict | Score | Color |
|----------------|---------|-------|-------|
| Solar alignment precision | PROVEN | 0.95 | green border-top |
| Acoustic engineering (110Hz) | PROVEN | 0.92 | green |
| Pre-Celtic astronomical culture | INSUFFICIENT | 0.68 | yellow |
| Global acoustic network | ACTIVE INVESTIGATION | 0.55 | blue |
| Consciousness alteration intent | UNPROVEN | 0.35 | red |

Verdict thresholds:
- **PROVEN** (≥0.80): Strong evidence, multiple independent sources confirm
- **INSUFFICIENT** (0.40-0.79): Suggestive evidence, needs more data
- **UNPROVEN** (<0.40): Speculative, weak or no supporting evidence
- **ACTIVE INVESTIGATION**: Score rising (delta > 0 from last assessment)

### Research Missions Panel

For each theory scored INSUFFICIENT or ACTIVE INVESTIGATION, the AI generates specific field tasks:

> **To advance "Global 110Hz Network" from 0.55 → 0.75:**
> - [ ] Measure resonant frequency in Carrowkeel Cairn G (predicted: 95-120Hz)
> - [ ] Compare with published data from Chavín de Huántar (Dr. Miriam Kolar, Stanford)
> - [ ] Record ambient sound in Knowth's dual passages at dawn
> - [ ] Check if Dowth's south chamber shows same resonance pattern
>
> **To advance "Pre-Celtic Astronomical Culture" from 0.68 → 0.85:**
> - [ ] Photograph Kerbstone K52 lunar encoding at Knowth (verify Metonic cycle interpretation)
> - [ ] Document Loughcrew equinox beam movement across backstone (50-minute sequence)
> - [ ] Compare spiral counting patterns across Boyne Valley sites

### Narrated Connection Graph

The D3 network graph includes AI-generated edge labels explaining WHY sites are connected:

- Node: Newgrange (center)
- Edge → Hypogeum (Malta): "Same 110Hz resonance — both engineered as acoustic instruments"
- Edge → Karnak (Egypt): "Solstice alignment precision within 1° — shared astronomical knowledge?"
- Edge → Knowth (2km): "Part of 500-year construction sequence, complementary calendar (solstice vs equinox)"
- Edge → Loughcrew (40km): "Prototype? 300 years older, same technique refined"

Each edge is clickable — shows the full narrated explanation.

### Cross-Domain Badge

Sites matching 2+ taxonomy domains get a gold badge: `⚡ Cross-Domain (3 matches)`. The badge uses the existing `.cross-domain` CSS class pattern from theory-investigation.html.

## Documentary View (History Channel Mode)

When toggled, the main area replaces Map/Cards with a scrollable, cinematic narrative:

```
┌──────────────────────────────────────────────────────────────┐
│ SIDEBAR (same)  │  DOCUMENTARY VIEW                          │
│                 │                                             │
│                 │  # Chapter 1: The Boyne Valley Complex      │
│                 │  *A 500-year construction program that      │
│                 │  encoded the entire solar calendar          │
│                 │  into stone*                                │
│                 │                                             │
│                 │  In 3500 BC, on the hills of Meath,        │
│                 │  someone began building...                  │
│                 │                                             │
│                 │  [Inline map: Loughcrew → Newgrange path]   │
│                 │  [Score card: 0.95 astronomical]            │
│                 │                                             │
│                 │  ## The Acoustic Mystery                    │
│                 │  Every chamber resonates at exactly 110Hz...│
│                 │                                             │
│                 │  [Network graph: global 110Hz sites]        │
│                 │                                             │
│                 │  # Chapter 2: The Signal Network            │
│                 │  ...                                        │
└──────────────────────────────────────────────────────────────┘
```

Documentary content is:
- Pre-generated per region using Bedrock (Nova Pro or Claude Haiku)
- Cached as static JSON (`geographic-explorer-narratives.js`)
- Includes inline visualizations (mini maps, score cards, network fragments)
- Chapter structure: one chapter per region, sections per major discovery
- Tone: investigative documentary — present evidence, highlight anomalies, leave questions open

Prompt template for narrative generation:
```
You are writing an investigative documentary script for a History Channel / Discovery Channel program about ancient mysteries. Write a chapter about {region_name} that covers these sites: {sites}. 

Structure: Hook (dramatic opening question) → Evidence (specific measurements, dates, comparisons) → Anomaly (what doesn't fit conventional explanations) → Pattern (connections to other sites globally) → Research Mission (what a field researcher should look for).

Use specific numbers, academic sources, and concrete details from this data: {deep_research_json}

Tone: Authoritative but open-minded. Present mainstream archaeology AND alternative interpretations fairly. Never dismiss — investigate.
```

## Integration Points

### Map Tab ↔ Geographic Explorer
- "Show on Map" button in site detail → navigates to `grid-globe.html?lat=X&lng=Y&zoom=14`
- URL params on geographic-explorer.html: `?site=irl-001` pre-selects a site

### Graph View ↔ Geographic Explorer  
- "Show Network" button → renders narrated D3 force graph in the connection panel (inline)
- Nodes = this site + connected sites from `cross_site_patterns` + global connections
- Edges = shared patterns (acoustic, alignment, construction sequence) with AI-narrated labels
- Edge click → shows full narrated explanation of the connection

### AI Investigator
- "Investigate" button → navigates to `chatbot.html?topic=<site_name>&domain=ancient_mysteries`
- Chat pre-seeded with the AI intelligence brief for context

### Theory Investigation ↔ Geographic Explorer
- Sites with INSUFFICIENT/ACTIVE theories link to theory-investigation.html filtered to that theory
- Theory cards in Geographic Explorer use same CSS classes as theory-investigation.html

## Data Loading Strategy

The site data is small (<50KB total across 3 files). Load inline via `<script>` tags pointing to generated JS data files:

```javascript
// geographic-explorer-data.js (generated from JSON sources)
const GEO_SITES = [...];  // merged from all irish_ancient_sites files
const GEO_DEEP_RESEARCH = {...};  // from tier2_deep_research.json
const GEO_CROSS_PATTERNS = {...}; // from cross_site_patterns section
```

```javascript
// geographic-explorer-narratives.js (AI-generated, cached)
const GEO_INTELLIGENCE_BRIEFS = {
  "irl-001": { brief: "...", theories: [...], missions: [...] },
  ...
};
const GEO_DOCUMENTARY_CHAPTERS = {
  "boyne_valley": { title: "...", content: "...", sections: [...] },
  ...
};
const GEO_CONNECTION_NARRATIVES = {
  "irl-001→hypogeum": "Same 110Hz resonance — both engineered as acoustic instruments...",
  ...
};
```

This matches the existing pattern (theory-registry-data.js for theory-investigation.html).

### AI Content Generation (Build Step)

A Python script generates the narratives file:
- `scripts/generate_geographic_narratives.py`
- Reads all site data + deep research
- Calls Bedrock (Nova Pro) to generate:
  - Intelligence brief per site (15 calls)
  - Theory verdicts per site (scored from data, no LLM needed)
  - Research missions per insufficient theory (1 call per site with gaps)
  - Documentary chapters per region (5-6 calls)
  - Connection narratives (1 call per unique global connection)
- Total estimated cost: ~$0.15-0.25 (Nova Pro at $0.001/doc × ~50 calls)
- Output: `src/frontend/geographic-explorer-narratives.js`
- Run once, cached. Regenerate when data changes.

## Styling

Reuse the existing design tokens from `common.css`:
- Background: `#0a0f19`
- Card background: `rgba(26,35,50,0.9)`
- Border: `rgba(255,255,255,0.08)`
- Primary accent: `#63b3ed`
- Success/high score: `#48bb78`
- Warning/moderate: `#ecc94b`
- Cross-domain: `#b794f4`
- Field notes: `#ed8936`

Score bars use gradient fills: red (0-0.3) → yellow (0.3-0.7) → green (0.7-1.0).

## Region Grouping Logic

Sites are grouped by `county` field. The mapping from county → region:

| County | Region Name |
|--------|------------|
| Meath | Boyne Valley |
| Sligo | Sligo / Carrowmore |
| Cork | West Cork |
| Kerry | Kerry Coast |
| Galway | Connemara |
| Westmeath | Irish Midlands |
| Clare | The Burren |
| Offaly | (standalone) |

If a county has only 1 site, it appears ungrouped under the country.

## Navigation Entry Point

Add to the nav-bar in `index.html`:
```html
<a href="geographic-explorer.html" class="nav-link">🗺️ Explorer</a>
```

Add to nav-links sections in existing pages (grid-globe.html, theory-investigation.html).

## File Deliverables

| File | Purpose |
|------|---------|
| `src/frontend/geographic-explorer.html` | Main page (HTML + CSS + JS) |
| `src/frontend/geographic-explorer-data.js` | Pre-built site data for inline loading |
| `src/frontend/geographic-explorer-narratives.js` | AI-generated intelligence briefs, verdicts, missions, documentary chapters |
| `scripts/generate_geographic_narratives.py` | Bedrock script that generates the narratives file |
| `src/frontend/index.html` | Updated nav-bar with Explorer link |
| `src/frontend/grid-globe.html` | Updated nav-links with Explorer link |

## Performance Considerations

- All data is static JSON (<50KB) — no API calls needed for initial load
- AI narratives are pre-generated and cached as static JS (~100KB) — no live Bedrock calls in the browser
- Leaflet tiles from OpenStreetMap (free, no key required)
- D3 force graph only renders when "Show Network" is clicked (lazy)
- Documentary chapters lazy-load per region (only the selected region's content renders)
- No build step for the frontend — plain HTML/CSS/JS matching existing architecture
- The narrative generation script is a one-time build step (re-run when data changes)

## Ancient Alien Theories Integration

Each site already has connections to global ancient mysteries via:
- `cross_domain_connections[]` in irish_ancient_sites.json
- `global_connections` in tier2_deep_research.json (110Hz sites, solstice alignments, etc.)
- `ancient_aliens_episode` field (Season/Episode references where applicable)

The AI intelligence briefs synthesize these into the narrative. The connection graph visualizes them spatially. The documentary chapters weave them into the larger story of "what if these ancient builders knew something we've forgotten?"

This is what makes it an investigation platform, not a travel guide — the AI draws connections across the dataset that a human would miss, and then tells you exactly what evidence to collect to prove or disprove the theory.
