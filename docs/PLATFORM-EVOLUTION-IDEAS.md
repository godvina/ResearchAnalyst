# PLATFORM EVOLUTION IDEAS — Living Document

> **This document is the single source of truth for platform direction.**
> Every time a relevant idea, lesson, or architectural decision emerges, it gets logged here.
> Kiro will remind you when this document is updated.

Last updated: 2026-08-01

---

## The Vision: Investigation-Type-Aware Intelligence Platform

A platform that doesn't just investigate, but **knows HOW to investigate** based on what it's looking at. When a lead comes in, the AI classifies it into an investigation type and activates the correct methodology, agents, views, and evidence standards automatically.

---

## Investigation Types (the taxonomy of investigations)

### Type 1: Documentary / Historical
- **Trigger**: Theory, curiosity, anomaly detection
- **Methodology**: Hook → Facts → Anomaly → Pattern → Implication
- **Agents**: Broad Scanner → Taxonomy Scanner → Cross-Pattern → Production Brief
- **Views**: Geographic layers (clean → focused), alignment visualization, site comparison
- **Evidence standard**: Credible sources + measurement + counter-argument addressed
- **Output**: Episode pitch, narrative arc, visual plan
- **Current examples**: Ley lines, UVG grid, ancient mysteries

### Type 2: Criminal Network
- **Trigger**: Crime report, suspicious activity, tipoff
- **Methodology**: Network mapping → Evidence chain → Timeline → Prosecution
- **Agents**: Entity Extractor → Network Builder → Financial Tracer → Case Assembler
- **Views**: Network graph (entities + relationships), movement map, financial flows, timeline
- **Evidence standard**: Legally obtainable, chain of custody, admissible in court
- **Output**: Prosecution brief, arrest warrant support, sentencing memo
- **Current examples**: Epstein network, fentanyl trafficking

### Type 3: Strategic Intelligence
- **Trigger**: Signal detection, indicator match, emerging trend
- **Methodology**: Hypothesis generation → Collection → Assessment → Dissemination
- **Agents**: Signal Scanner → Hypothesis Generator → Evidence Weigher → Assessment Writer
- **Views**: Heat map, competing hypotheses matrix, trend lines, confidence dashboard
- **Evidence standard**: Explicit confidence levels, alternative hypotheses maintained
- **Output**: Intelligence assessment with confidence ratings for decision-makers
- **Current examples**: (not yet built — future)

### Type 4: Financial / Fraud
- **Trigger**: Anomalous transaction, whistleblower, pattern detection
- **Methodology**: Follow the money → Entity resolution → Prove intent
- **Agents**: Transaction Tracer → Entity Resolver → Pattern Matcher → Fraud Assessor
- **Views**: Sankey diagrams, transaction timeline, entity resolution graph, shell company tree
- **Evidence standard**: Auditable trail, transaction records, beneficial ownership
- **Output**: Suspicious Activity Report, regulatory filing, fraud case brief
- **Current examples**: Antitrust pattern recognition lens (partially built)

### Type 5: Missing / Cold Case
- **Trigger**: Unsolved case, new evidence, new technology
- **Methodology**: Review → Re-interview → Apply new tech → Geographic profile
- **Agents**: Case Reviewer → Evidence Re-analyzer → Geographic Profiler → Connection Finder
- **Views**: Last-known timeline, geographic profile heat map, behavioral analysis
- **Evidence standard**: Law enforcement standards + new analytical methods
- **Output**: Investigative lead package, person of interest profile
- **Current examples**: (not yet built — future)

---

## Shared Infrastructure (works across all 5 types)

| Component | What it does | Status |
|-----------|-------------|--------|
| Brave Search + Bedrock synthesis | Research any topic | ✅ Working |
| Pattern Library (taxonomy + signatures) | Define what to look for | ✅ Working |
| OpenSearch + embeddings | Semantic search across all findings | ✅ Working |
| Neptune graph | Entity relationships, network visualization | ✅ Working |
| Aurora PostgreSQL | Structured data, case management | ✅ Working |
| Agent Orchestrator | Chain agents based on triggers | ⚠️ Built but unexecuted |
| S3 data lake | Raw storage for everything | ✅ Working |
| API Gateway + Lambda | Serve frontend, run agents | ✅ Working |
| Frontend (HTML/JS) | Visualization, user interaction | ⚠️ Working but per-use-case |

---

## Architecture Decisions — Validated

1. **Taxonomy-driven investigation works.** Define signatures → scan → score → visualize. Proven with 18 grid signatures across 62 nodes.
2. **AI synthesis + web search = viable research.** Brave + Sonnet produces documentary-quality research briefs with specific citations.
3. **Layered visualization beats everything-at-once.** Clean base → progressive disclosure → focus mode. Proven today with grid globe.
4. **Agent chaining via triggers is the right model.** One agent's output triggers the next. The orchestrator pattern is correct.
5. **Local JSON + S3 + API is the right data flow.** Research locally → upload to S3 → serve via API → render in frontend.

## Architecture Decisions — Failed / Avoid

1. **Don't draw all connections at once.** Network graphs become hairballs. ALWAYS filter by evidence strength.
2. **Don't use coordinate-only queries for named sites.** "Megalithic near 31.72 31.2" finds nothing. "Great Pyramid of Giza alignment" finds everything.
3. **Don't show raw taxonomy scores as network connections.** "Both matched the same broad signature" ≠ meaningful connection. Need SPECIFIC shared indicators.
4. **API Gateway 29-second timeout kills long research.** Run research via direct Bedrock calls locally, not through the API.
5. **Generic indicators are noise.** "Within 100km of node" matches everything. Only SPECIFIC traits (named ceremonies, measured precisions, dated artifacts) create meaningful connections.

---

## Ideas Backlog (add new ideas here)

### 2026-08-01: Investigation Type Classification Layer
- When a new lead/idea arrives, AI evaluates it and classifies into one of 5 types
- This triggers the correct: methodology, agents, views, evidence standards, output format
- Single entry point → divergent execution paths → type-specific output
- **Priority: HIGH** — this is the unifying architecture for the whole platform

### 2026-08-01: Rebuild Consideration
- Everything built so far (Research Analyst + Fentanyl Finding) is prototype-quality
- Lessons learned are now documented
- Rebuild would start with investigation-type layer, proper data models per type, unified UI that adapts
- **Decision: Not yet.** Finish Documentary type end-to-end first. Use as template for rebuild.
- **When to rebuild**: When we have 2+ investigation types proven and want to productionize

### 2026-08-01: Documentary Template Enhancement
- Add intelligence-style confidence levels to every claim
- Add "What would disprove this?" section (Analysis of Competing Hypotheses)
- Add network visualization of site connections (from DEA methodology)
- Require counter-argument in every research brief

### 2026-08-01: Agent Handler Wiring
- The orchestrator has 8 agent definitions but no execution handlers
- Need to wire Brave + Sonnet into each agent's handler function
- Then `orchestrator.investigate("topic")` auto-chains the full pipeline
- **Priority: NOW** — this is what makes the scan automated

### 2026-08-01: Geospatial Views per Investigation Type
- Documentary: Clean grid + layered patterns + focus mode (built today)
- Criminal Network: Entity placement on map + movement tracks + surveillance zones
- Intelligence: Heat maps + threat vectors + signal density
- Financial: Geographic flow map (where money moves between jurisdictions)
- Cold Case: Last-known location + radius search + behavioral geographic profile

### 2026-08-01: Evidence Standard Enforcement
- Each investigation type has different "what counts as confirmed"
- The scoring engine should be parameterized by type
- Documentary: credible source + measurement = confirmed
- Law Enforcement: legally obtained + corroborated + chain of custody = confirmed
- Intelligence: multiple independent sources + analyst consensus = high confidence

---

## When to Rebuild (checklist)

- [ ] Documentary type proven end-to-end (ley lines demo complete)
- [ ] Criminal Network type proven end-to-end (Epstein/fentanyl demo complete)
- [ ] Shared infrastructure stable (no more breaking changes to APIs)
- [ ] Data models documented for all 5 types
- [ ] User feedback from demo audiences incorporated
- [ ] Clear separation between prototype code and production code

When 4+ of these are checked, it's time to rebuild with proper architecture.

---

## Running Notes

_Add timestamped notes here as ideas emerge during sessions:_

**2026-08-01 (Session: Grid Globe Dashboard)**
- The "focus mode" UX pattern (click pattern → dim everything → spotlight matches) is the killer feature. This should be the standard interaction for ALL investigation types.
- Documentary research needs site-NAME-based queries, not coordinate-only. Obvious in hindsight.
- 5 investigation types identified. Each needs its own methodology, agents, views, and evidence standards.
- Agent orchestrator is architecturally ready but needs handler functions wired up.
- Consider whether a full rebuild is needed vs. evolving what we have. Decision: evolve for now, rebuild when 2 types are proven.

**2026-08-01 (Session: Agent Wiring + TALOS Vision)**
- The 5-layer taxonomy (Domain → Typology → Method → Signature → Precedent Case) from the crime work is the SAME structure we're using for ancient mysteries. This validates: one universal taxonomy structure, domain-agnostic.
- TALOS AS MULTI-TENANT RESEARCH PLATFORM idea (see below)
- Agent handlers now wired: Broad Scanner, Taxonomy Scanner, Cross-Pattern. Ready to run chains.
- Deep scan merged: 46/59 nodes now have signature matches (up from 41).
- Brave API eliminated — Tavily (1000 free/month) replaces it. Bedrock for Phase 1, Tavily for Phase 2.
- Full agent chain successful: 16 signature matches in 220s across 3 agents.
- ARCHITECTURE DECISION: Cache ALL AI-generated summaries in Aurora. Generate once, serve from cache, refresh on demand. Eliminates redundant Bedrock calls, enables SQL queryability across all research findings, and prevents hallucination drift between sessions.
- Network graph (D3 force-directed) added as separate view from geographic map.
- OpenSearch justified for emergent pattern detection (k-NN fuzzy similarity) — Aurora can't do this efficiently at scale.

---

## FUTURE PLATFORM: TALOS Multi-Tenant Research Platform

### The Vision
TALOS becomes an open research backend where:
- Multiple research communities (UFO, ancient mysteries, crime, climate, health) each have their own TENANT
- Each tenant uploads research data, and TALOS analyzes it against the global typology template
- The taxonomy layers (Domain → Typology → Method → Signature → Case) are universal
- Communities contribute findings that, once validated, flow into the shared knowledge base
- Like Wikipedia meets intelligence analysis — collaborative, structured, quality-controlled

### How It Would Work
```
RESEARCHER uploads data (papers, images, coordinates, observations)
    → TALOS classifies: "This is a Documentary/Historical investigation"
    → TALOS activates the correct agent chain for that type
    → Agents analyze against the tenant's taxonomy
    → Findings scored and indexed
    → Cross-tenant pattern detection: "UFO sightings cluster at same grid nodes as ancient sites"
    → Validated findings promote to shared knowledge base
```

### Multi-Tenancy Architecture
- Each tenant gets: their own S3 prefix, their own taxonomy, their own agent config
- Shared infrastructure: Bedrock, OpenSearch, Neptune, Agent Orchestrator
- Data isolation: tenants can't see each other's raw data
- Cross-pollination layer: ONLY validated findings (above threshold) visible across tenants
- Quality control: peer review before findings promote to global

### Use Cases
1. **UFO Research Community** — Upload sighting data, TALOS correlates with electromagnetic anomalies, flight paths, military activity
2. **Ancient Mysteries** — Upload site surveys, TALOS scores against taxonomy, finds cross-continental patterns
3. **Cold Case Network** — Upload case files, TALOS identifies behavioral patterns, geographic clusters
4. **Environmental Crime** — Upload satellite imagery, TALOS detects deforestation patterns, correlates with shipping data
5. **Pandemic Intelligence** — Upload epidemiological data, TALOS identifies outbreak patterns before official detection

### How to Make It Better
- **Reputation system**: Researchers earn credibility scores based on validated findings
- **Peer review pipeline**: Before findings promote to global, N other researchers must verify
- **Citation graph**: Track which research builds on which (like academic papers)
- **Anomaly detection across tenants**: The REAL power — when UFO data and geological data independently point to the same locations
- **API for external tools**: Let researchers use their own frontends, just tap into TALOS analysis

### Risks & Mitigations
- **Data quality**: Garbage in = garbage out → Require minimum evidence standards per tenant type
- **Conspiracy amplification**: Bad research validated by echo chamber → Cross-tenant validation required for promotion
- **Privacy/legal**: Some research (crime) has legal constraints → Per-tenant access controls + audit trail
- **Cost**: Bedrock/OpenSearch costs scale with tenants → Tiered pricing model

### Action Items (Future)
- [ ] Design multi-tenant data model (S3 prefix strategy, tenant metadata)
- [ ] Design cross-tenant pattern detection (what triggers, what promotes)
- [ ] Design quality control / peer review workflow
- [ ] Prototype with 2 tenants (Ancient Mysteries + Crime) sharing Neptune graph
- [ ] Cost model for N tenants with M researchers each
