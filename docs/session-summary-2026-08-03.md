# Session Summary — 2026-08-03

## Major Accomplishments

### 1. 3-Tier Data Processing Pipeline (Built + Proven)
- **Script:** `scripts/epstein_tiered_scan.py`
- Tier 1: Keyword/regex filter → 3,804 files → 225 passed (94% junk removed) — $0, 23 seconds
- Tier 2: Titan Embed on 225 files → 209 embedded — $0.02, 59 seconds
- Tier 3: Taxonomy scoring + Claude Haiku → 195 docs → 1,329 entities, 445 relationships, 278 red flags — $0.25
- **Total cost: $0.27** (vs $4.56 without tiering = 94% savings)
- Documented in steering, lessons learned, colleague handoff
- **Created global steering file** at `~/.kiro/steering/tiered-data-processing.md` (applies to ALL projects)

### 2. Rhowardstone Pre-Processed Epstein Data
- Downloaded: knowledge graph (606 entities, 2,302 relationships), persons registry (1,614), extracted entities (8,081)
- **Loaded into Neptune:** 605 nodes + 2,300 edges (Jeffrey Epstein network, typed relationships)
- **Loaded into OpenSearch:** 606 entity embeddings for k-NN search
- Coverage: ALL 12 DOJ datasets (1.39M documents) — far beyond our 3,804 Textract subset

### 3. Neptune Entity Recovery
- Accidentally deleted ~15K nodes with "non-standard" entity types
- **Lesson learned:** Don't delete by entity_type alone — types like "object", "identifier" were legitimate
- **Recovered 6,588 entities from Aurora** back into Neptune
- **Deep analysis:** 33% gold (DOJ refs, EFTA IDs, evidence exhibits), 6% silver (devices, flight numbers), 2% junk, 59% contextual

### 4. Irish Sacred Sites (13 sites, trip prep)
- Created full dataset with GPS coordinates, taxonomy scores, mysteries, field notes
- **Tier 2 deep research on ALL 13 sites** — acoustic measurements, dating controversies, academic sources
- Loaded into **Ancient Aliens Investigation** case in Neptune (13 nodes + 17 edges)
- Added `country=Ireland` and `region` tags for geographic filtering
- **Key discovery:** Sites form a distributed astronomical calendar across the landscape

### 5. Frontend: Country/Region Filter
- Added country + region dropdown filters to Map tab
- Updated Lambda patterns.py to return country/region properties
- Deployed to production Lambda
- **Spec created** for Geographic Explorer tab (`.kiro/specs/geographic-explorer/`)

## Costs This Session
- Tier 1-3 Epstein processing: ~$0.27
- Rhowardstone embeddings (OpenSearch): ~$0.06
- Irish sites taxonomy scoring: ~$0.10
- **Total session: ~$0.50**

## Infrastructure State
- **Neptune:** 966K+ nodes, 34.2M edges (clean after recovery)
- **Aurora:** 255K+ entities
- **OpenSearch:** 606 rhowardstone embeddings indexed
- **Lambda:** Deployed with country/region filter support

## Parked / Next Session
| Task | Priority | Notes |
|------|----------|-------|
| Geographic Explorer tab (frontend) | HIGH | Spec created, needed for Ireland trip |
| Full 1.38M corpus tiered processing | MEDIUM | $50-70, HuggingFace download |
| Selinko counterfeiting taxonomy | MEDIUM | Start in Fentanyl project |
| Fix Aurora entity inserts (Tier 3 + Irish) | LOW | UUID format issue |
| Score Epstein embeddings against full 6-deep crime taxonomy | MEDIUM | Enables cross-taxonomy search |

## Files Created/Modified
- `scripts/epstein_tiered_scan.py` — 3-tier pipeline
- `scripts/load_rhowardstone_data.py` — pre-processed data loader
- `src/data/conspiracy-seed/irish_sacred_sites/` — 3 JSON files (sites + deep research)
- `src/data/proof-engine-results-irish-sacred-sites.json` — taxonomy results
- `docs/lessons-learned-tiered-data-processing.md` — full write-up
- `.kiro/steering/data-processing-rules.md` — updated with tiered approach
- `~/.kiro/steering/tiered-data-processing.md` — global best practice
- `.kiro/specs/geographic-explorer/requirements.md` — new feature spec
- `src/lambdas/api/patterns.py` — added country/region to graph response
- `src/frontend/investigator.html` — added country/region filter dropdowns
