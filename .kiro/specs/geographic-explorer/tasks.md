# Tasks: Geographic Explorer Tab

## Task 1: Create the data layer (geographic-explorer-data.js)
- [ ] Read `src/data/conspiracy-seed/irish_sacred_sites/irish_ancient_sites.json` and `irish_ancient_sites_continued.json`
- [ ] Read `src/data/conspiracy-seed/irish_sacred_sites/tier2_deep_research.json`
- [ ] Merge into a single `GEO_SITES` array with: id, name, category, county, region, coordinates, age_years, date_built, unesco, mysteries, taxonomy_matches, cross_domain_connections, field_notes, ancient_aliens_episode
- [ ] Build `GEO_DEEP_RESEARCH` object keyed by site id with acoustic, construction, dating, suppression fields
- [ ] Build `GEO_CROSS_PATTERNS` object from the cross_site_patterns and global_connections sections
- [ ] Add county-to-region mapping (Meath→Boyne Valley, Sligo→Sligo/Carrowmore, Cork→West Cork, Kerry→Kerry Coast, Clare→The Burren, Galway→Connemara)
- [ ] Write output to `src/frontend/geographic-explorer-data.js`

## Task 2: Build the HTML page structure and CSS
- [ ] Create `src/frontend/geographic-explorer.html` with header, nav-links, two-column layout (sidebar 320px + main area)
- [ ] Implement dark theme using existing design tokens from common.css (background #0a0f19, cards rgba(26,35,50,0.9), borders rgba(255,255,255,0.08))
- [ ] Add header with title "🗺️ Geographic Explorer" and nav links to Home, Globe, Pattern Library, Theory Investigation
- [ ] Add sidebar container with country/region/site hierarchy placeholder
- [ ] Add main area with mode toggle (Data View ↔ Documentary View) and view tabs (Map, Cards, Timeline) for Data View
- [ ] Add site detail panel container (hidden by default, expands on site selection)
- [ ] Add AI Intelligence Brief panel with loading skeleton CSS
- [ ] Add Theory Verdict Cards grid section with proven/insufficient/unproven border-top colors (green/yellow/red)
- [ ] Add Research Missions panel with amber border and checkbox styling
- [ ] Add Documentary View container (hidden by default, scrollable narrative area with cinematic typography)
- [ ] Include Leaflet CSS/JS, D3.js CDN links, geographic-explorer-data.js, geographic-explorer-narratives.js

## Task 3: Implement the sidebar hierarchical navigator
- [ ] Render country list from GEO_SITES grouped by country (show site count per country)
- [ ] On country click: expand to show regions (grouped by county→region mapping)
- [ ] On region click: show site list within that region with mini taxonomy score badge (colored dot)
- [ ] On site click: select site — update main area, highlight in sidebar
- [ ] Add breadcrumb above main area showing current drill path (Ireland → Boyne Valley → Newgrange)
- [ ] Persist sidebar expand/collapse state during session

## Task 4: Implement the Map View
- [ ] Initialize Leaflet map centered on Ireland (53.14, -7.69) at zoom 7
- [ ] Place markers for all sites using coordinates from GEO_SITES
- [ ] Color markers by status: gold (#f6ad55) for cross-domain (2+ taxonomy domains ≥0.7), green (#48bb78) for high score (max ≥0.8), standard blue (#63b3ed) otherwise
- [ ] Marker popups showing: site name, category, top score, "Select" button
- [ ] On marker click or "Select": populate site detail panel below map
- [ ] When sidebar region is selected: zoom map to fit all sites in that region
- [ ] When sidebar site is selected: zoom to that site at level 14, open popup

## Task 5: Implement the Cards View
- [ ] Grid layout (auto-fill, minmax(380px, 1fr)) matching theory-investigation card pattern
- [ ] Each card shows: name, category badge, age/date_built, county
- [ ] Taxonomy score bars (top 3 scores): horizontal bars with gradient fill (red→yellow→green)
- [ ] Connection count (number of entries in cross_domain_connections)
- [ ] GPS coordinates (clickable — switches to Map view, zooms to site)
- [ ] Cross-domain badge (gold ⚡) if site matches 2+ domains at ≥0.7
- [ ] Theory verdict mini-summary: e.g. "3 PROVEN · 2 INSUFFICIENT · 1 ACTIVE"
- [ ] Sort options: by name, by top score (desc), by age (oldest first), by connections
- [ ] Card click → selects site, opens detail panel

## Task 6: Implement the Timeline View
- [ ] Horizontal timeline showing sites ordered by date_built (oldest left → newest right)
- [ ] Each site as a node on the timeline with name label and category color
- [ ] Hover shows tooltip with: name, date, top mystery, verdict summary
- [ ] Click selects site (same as sidebar/card click)
- [ ] Visual grouping indicator for sites built in same era (±200 years)
- [ ] Show the "sequential building" pattern arrow (Loughcrew 3500 BC → Newgrange 3200 BC → Tara 3000 BC)

## Task 7: Implement the AI Intelligence Brief panel
- [ ] When site is selected, look up `GEO_INTELLIGENCE_BRIEFS[site_id]` from narratives data
- [ ] Display blue-bordered panel with 🤖 header: "AI Intelligence Brief — {site_name}"
- [ ] Show 3-paragraph narrative (hook → evidence → implication)
- [ ] Add loading skeleton animation while content renders
- [ ] Add "Refresh" button (placeholder — regeneration requires running the build script)
- [ ] Highlight key statistics in the narrative with bold/accent color
- [ ] If no brief available for a site, show "Brief pending — run generate_geographic_narratives.py"

## Task 8: Implement Theory Verdict Cards
- [ ] For each site, compute verdict from taxonomy_matches and mysteries data
- [ ] Verdict logic: score ≥0.80 = PROVEN (green), 0.40-0.79 = INSUFFICIENT (yellow), <0.40 = UNPROVEN (red)
- [ ] Add ACTIVE INVESTIGATION status if a theory has cross-domain connections supporting it
- [ ] Display as grid of small cards (same CSS pattern as theory-investigation.html .card class)
- [ ] Each card: theory name, verdict badge (top-right), score bar, 1-line evidence summary
- [ ] Cards sorted by score descending (proven first)
- [ ] Card click → expands to show full evidence list and sources from deep research data

## Task 9: Implement Research Missions panel
- [ ] For each theory scored INSUFFICIENT or ACTIVE INVESTIGATION, show mission block
- [ ] Pull missions from `GEO_INTELLIGENCE_BRIEFS[site_id].missions` in narratives data
- [ ] Display as amber-bordered section with header: "🎯 Research Missions — What Would Advance These Scores"
- [ ] Each mission: checkbox, task description, target score improvement (e.g., "0.55 → 0.75")
- [ ] Group missions by theory they support
- [ ] Checkboxes are interactive (state saved to localStorage for trip tracking)
- [ ] If no missions data, compute basic missions from mysteries that lack sufficient evidence

## Task 10: Implement the narrated network graph (D3 force layout)
- [ ] Renders in a panel below site detail when "Show Network" is clicked
- [ ] Central node = selected site (larger, highlighted)
- [ ] Connected nodes = sites from cross_site_patterns + global_connections (worldwide sites like Giza, Hypogeum, Karnak)
- [ ] Edge labels = shared pattern type (acoustic, alignment, construction sequence, intervisibility)
- [ ] Pull narrated edge descriptions from `GEO_CONNECTION_NARRATIVES` in narratives data
- [ ] Edge click → shows full narrated explanation popup (e.g., "Same 110Hz resonance — both engineered as acoustic instruments")
- [ ] Node color: Irish sites = blue, international sites = purple
- [ ] Force-directed layout using D3 (same pattern as grid-globe.html network panel)
- [ ] Node click on Irish site → selects that site (updates sidebar, detail panel, map)
- [ ] Node click on international site → shows info tooltip with name, location, connection type
- [ ] Close button to dismiss graph panel

## Task 11: Implement Documentary View (History Channel mode)
- [ ] Toggle button at top of main area: "📊 Data View" ↔ "🎬 Documentary View"
- [ ] When Documentary active: hide Map/Cards/Timeline, show scrollable narrative container
- [ ] Load chapter content from `GEO_DOCUMENTARY_CHAPTERS[region_id]` in narratives data
- [ ] Render with cinematic typography: large serif headers, generous line-height (1.8), max-width 720px centered
- [ ] Chapter structure: Title, subtitle (italic), narrative paragraphs
- [ ] Inline visualizations within narrative: mini Leaflet maps (showing site locations mentioned), score cards, mini network fragments
- [ ] Chapter navigation: sidebar region click loads that region's chapter
- [ ] Smooth scroll to chapter start on navigation
- [ ] If no documentary chapter exists for a region, show placeholder: "Chapter pending — run generate_geographic_narratives.py"

## Task 12: Build the AI narrative generation script
- [ ] Create `scripts/generate_geographic_narratives.py`
- [ ] Load all site data from irish_ancient_sites.json + tier2_deep_research.json
- [ ] Generate intelligence briefs per site using Bedrock (Nova Pro): prompt includes site data, taxonomy scores, global connections, deep research. Output: 3-paragraph narrative (hook → evidence → implication)
- [ ] Generate research missions per site: for each INSUFFICIENT/ACTIVE theory, generate 3-5 specific field tasks with target score improvements
- [ ] Generate documentary chapters per region: prompt includes all sites in region, cross-site patterns, sequential building data. Output: 500-1000 word investigative narrative
- [ ] Generate connection narratives: for each unique edge in cross_site_patterns + global_connections, generate 1-2 sentence explanation of why the connection matters
- [ ] Compute theory verdicts from taxonomy_matches scores (no LLM needed — pure logic)
- [ ] Write all output to `src/frontend/geographic-explorer-narratives.js` as exported const objects
- [ ] Include cost tracking: log token counts and estimated cost per call
- [ ] Total estimated cost: ~$0.15-0.25 for ~50 Bedrock calls

## Task 13: Add navigation integration
- [ ] Add `<a href="geographic-explorer.html" class="nav-link">🗺️ Explorer</a>` to nav-bar in `src/frontend/index.html`
- [ ] Add Explorer link to nav-links in `src/frontend/grid-globe.html`
- [ ] Add Explorer link to nav-links in `src/frontend/theory-investigation.html`
- [ ] Support URL parameter `?site=irl-001` to pre-select a site on page load
- [ ] Support URL parameters `?lat=X&lng=Y&zoom=Z` to center map on load
- [ ] Support URL parameter `?mode=documentary` to open in Documentary View
- [ ] "Show on Map" button generates link to grid-globe.html with lat/lng/zoom params

## Task 14: Polish and test
- [ ] Verify all 15 sites render correctly in all three Data views (Map, Cards, Timeline)
- [ ] Verify AI Intelligence Brief panel displays for sites with narrative data
- [ ] Verify Theory Verdict Cards show correct verdicts based on scores
- [ ] Verify Research Missions populate for INSUFFICIENT theories
- [ ] Verify network graph shows global connections (Giza, Malta, Peru, etc.) with narrated edges
- [ ] Verify Documentary View loads chapter content for Boyne Valley region
- [ ] Verify sidebar drill-down: Ireland → Boyne Valley → Newgrange flow works
- [ ] Verify map markers match sidebar selection state
- [ ] Test URL param navigation (?site=irl-001 loads Newgrange, ?mode=documentary opens narrative)
- [ ] Verify nav links work from index.html, grid-globe.html, and theory-investigation.html
- [ ] Check responsive behavior at 1200px and 1600px widths
- [ ] Verify localStorage persistence for Research Mission checkboxes
