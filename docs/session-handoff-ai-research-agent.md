# Session Handoff: AI Research Agent — Next Phase

## What Was Built This Session

### Features Deployed (all live on Lambda + S3):
1. **AI Level Summaries** — Structured intelligence briefs at each Pattern Library level (ASSESSMENT → KEY INDICATORS → GAPS → RECOMMENDED ACTION)
2. **Geospatial Maps** — Leaflet.js + OpenStreetMap with AI-adaptive visualization (great circle lines, clusters, constellations)
3. **Becker-Hagens Grid** — Toggleable planetary icosahedral grid overlay with color-coded nodes (green=confirmed, red=unexplored)
4. **Research Recommendations** — AI-generated research hypotheses with Brave Search execution
5. **Grid Intersection Analysis** — Identifies unexplored grid nodes, generates research cards, computes Theory Verification Score
6. **Ley Line Ranking** — Top 3 strongest ley lines highlighted on map

### What Works Well:
- AI summaries in intelligence brief format
- Map with labeled sites + grid overlay
- Theory verification score + production pitch
- Research button executes Brave searches

### What Needs Improvement (Next Session Priority):

## THE CORE PROBLEM: Research Quality

The research briefs come back thin ("SITE UNKNOWN", "Investigation pending", generic website links). The root causes:

1. **Claude Haiku is too small** for complex multi-source synthesis. The OSINT report format requires reasoning that Haiku often can't deliver. Consider switching to Claude Sonnet for research execution only.

2. **Single-step research** — Currently does one (or three) Brave searches and summarizes. Real OSINT is multi-step: 
   - Step 1: Understand the CONCEPT deeply (ley lines globally)
   - Step 2: Identify priority targets from that understanding
   - Step 3: Deep-dive each target with multiple angles

3. **No auto-research on the concept** — When you land on "Ley Line Alignments", the system should FIRST research ley lines as a topic (academic papers, key researchers, known alignments), THEN come back with prioritized targets.

4. **No starting point for the analyst** — All 10 grid nodes show as equal "UNEXPLORED" cards. The system should rank them by research potential.

## Recommended Architecture for Next Session

### AI Research Agent (2-phase approach)

**Phase 1: Concept Research (runs automatically when you navigate to a pattern)**
- Input: Pattern name + description
- Action: Bedrock (Sonnet) + 5 Brave searches on the CONCEPT
- Output: 
  - Executive summary of the field
  - Key researchers and papers
  - Current state of evidence (what's proven, what's contested)
  - PRIORITIZED list of investigation targets with reasoning
  - "Here's where I'd start and why"

**Phase 2: Site Investigation (user clicks to drill into specific targets)**
- Input: Specific location + concept context from Phase 1
- Action: Multi-angle OSINT (3-5 Brave searches per site: geographic, archaeological, geological, anomaly, historical)
- Output: Full OSINT field report (the format already built but needs better content)

### Technical Changes Needed:
1. **Use Sonnet for research** (keep Haiku for summaries/coordinates to stay cheap)
2. **Increase max_tokens to 2000** for research synthesis
3. **Add a "concept research" cache layer** — research the topic ONCE, use it to inform all subsequent site investigations
4. **Priority scoring algorithm** — weight grid nodes by: proximity to known ley line, number of nearby geological anomalies, presence in academic literature
5. **Store findings in Aurora** with linkage back to taxonomy (so findings enrich the pattern library over time)

### UX Changes Needed:
1. **Research panel should show Phase 1 results FIRST** (concept overview + prioritized targets)
2. **Individual site cards should show AFTER** (as drill-downs from the priority list)
3. **Map dots should update color** as research completes (red → yellow → green)
4. **Red dot click → drill into research** (currently broken due to timing — research panel loads async)

## Files Modified This Session

### New Files Created:
- `src/lambdas/api/level_summary.py` — AI summary handler
- `src/lambdas/api/level_coordinates.py` — Geospatial coordinate handler
- `src/lambdas/api/level_research.py` — Research recommendations + search execution
- `src/services/summary_prompt_builder.py` — Intelligence brief prompts
- `src/services/summary_cache_manager.py` — Aurora cache CRUD
- `src/services/summary_rate_limiter.py` — 60/hour rate limiter
- `src/services/coordinate_prompt_builder.py` — Geospatial + visualization prompts
- `src/db/migrations/022_ai_level_summaries.sql` — Cache table

### Modified Files:
- `src/lambdas/api/case_files.py` — Added 3 route blocks (summary, coordinates, research)
- `src/frontend/pattern-library.html` — Major frontend additions (AI panel, map, grid, research)
- `scripts/index_pattern_library.py` — Cache invalidation integration

## API Endpoints (all live):
- `GET /pattern-library/summary/{level}/{context_key}` — AI intelligence brief
- `POST /pattern-library/summary/invalidate` — Clear cached summaries
- `GET /pattern-library/coordinates/{level}/{context_key}` — Geospatial + visualization
- `POST /pattern-library/coordinates/invalidate` — Clear cached coordinates
- `GET /pattern-library/research/{level}/{context_key}` — Research recommendations
- `POST /pattern-library/research/execute` — Execute Brave search + synthesize

## Rate Limiting
All Bedrock calls share ONE 60/hour clock-hour rate limiter. Summaries + coordinates + research all count toward it. On a demo, you'll hit it fast if clicking through many patterns. Consider raising to 120/hour for demo accounts.

## Key Insight for Next Session
The user's vision: "The AI should think like me. When I see the grid, I immediately think 'what's at the intersections?' — the system should think that way too, automatically, and come back with prioritized findings."

This is essentially an **agentic research loop** — the system needs to:
1. Observe the pattern
2. Form hypotheses (what would an investigator check?)
3. Execute research
4. Synthesize findings
5. Present priorities
6. Allow drill-down

The infrastructure is built. The quality of the research output is the next frontier.
