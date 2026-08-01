# Session Summary — 2026-08-01: Interactive Investigation Dashboard

## What Was Built

### 1. Grid Globe Dashboard (Complete Rebuild)
- Clean layered approach: diamond vertices + faint triangle grid + site circles
- Focus mode: click pattern → everything dims → only matching nodes visible
- No connection lines on map (relationships shown in network graph below)
- Grid stays visible during focus (provides geometric context)
- Sidebar: 440px wide, pattern cards, known sites list, emergent patterns section

### 2. Network Graph (D3 Force-Directed)
- Appears below map when pattern is focused
- Nodes color-coded by continent, sized by evidence count
- Edges ONLY between nodes sharing specific non-generic indicators
- Intelligence brief panel on right side of graph (shows AI summary on hover/click)
- Intelligence summary in header: "11 sites on 5 continents — 15 share specific ceremonial traits"
- Max 15 edges cap to prevent spaghetti

### 3. Agent Chain (Working End-to-End)
- Broad Scanner → Taxonomy Scanner → Cross-Pattern Agent chain
- Runs on Bedrock only (no external search for Phase 1)
- Tavily integrated for Phase 2 deep dives (9 calls used, 991 remaining)
- 16 signature matches found across 3 agents in 220 seconds
- Fixed JSON parsing with robust `_parse_llm_json()` function

### 4. Interactive Documentary (Audio + Animation)
- 7 chapters generated via Bedrock narration + Amazon Polly (Matthew neural voice)
- 3.1MB total audio, stored in S3 with presigned URLs
- Cue sheet engine: 500ms polling, fires map animations synced to audio
- Chapter buttons for jumping, progress scrubber, ⏪/⏩ seek, speed control (0.75x-2x)
- CC captions with highlighted current word
- Picture-in-Picture: site photos appear when narrator mentions a location
- Live research triggers (Tavily search per chapter for new findings)

### 5. Emergent Patterns (OpenSearch k-NN)
- Ran cross-embedding similarity on all 62 nodes
- Found 128 unexpected similarity pairs
- Clickable: shows network graph + documentary brief for emergent clusters

### 6. Cultural Memory Deep-Dive Research
- 15 sacred sites researched for specific cultural traits
- Found: Spirit Dwelling (3 sites), Water Sacred (3), Forbidden Zone (2), Creation Myth (2)
- Merged into scored findings → network graph now shows meaningful edges

### 7. Research & Documentation
- `docs/PLATFORM-EVOLUTION-IDEAS.md` — living document for platform direction
- `docs/spec-interactive-documentary.md` — R1-R8 requirements + design
- `docs/best-practices-documentary-research-format.md` — 5-layer template
- `docs/best-practices-investigative-methodology-comparison.md` — Documentary vs Law Enforcement vs Intelligence
- `docs/data-gap-analysis-and-research-plan.md` — what's missing, what to scan next
- Deep scan: 8 key sites with documentary-quality evidence (Giza CONFIRMED, Angkor CONFIRMED, Easter Island PROBABLE)

---

## Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Brave eliminated → Tavily + Bedrock | Brave key expired; Tavily gives 1000 free/month; Bedrock alone sufficient for broad research |
| Inline cue sheet + script data | Fetching from S3 had CORS/path issues; inline eliminates all fetch dependencies |
| Network edges filtered by specific indicators | Generic indicators ("Indigenous oral tradition") create 45+ meaningless edges; specific traits create 8 meaningful ones |
| OpenSearch justified for emergent patterns | k-NN fuzzy similarity finds patterns human didn't search for — can't do this in Aurora at scale |
| Audio via Polly Neural | $0.08 per full briefing; professional quality; SSML for pacing |
| D3 force-directed graph | Better than geographic lines for showing relationship structure |

---

## What's NOT Working / Known Issues

1. **Some Unsplash photo URLs may not resolve** (Angkor was a plane, Mohenjo-daro was broken) — need verified URLs
2. **Audio-map sync timing is approximate** — based on chars-per-second, not word-level timestamps from Polly SpeechMarks
3. **Network graph brief is raw situation text** — should use documentary template format
4. **No 2-level drill-down** on network nodes yet — click shows same brief regardless of pattern context
5. **Sedona research failed** (JSON parsing error in cultural memory scan) — needs re-run
6. **GitHub push still running** (Contents API is slow — 1 file at a time)

---

## Next Session Priorities

1. **Documentary-style AI summaries** — Use Hook → Anomaly → Pattern → Implication template for ALL intelligence briefs
2. **2-level drill-down on network graph** — Click node → contextual brief about THIS node's role in THIS pattern (not generic brief)
3. **Labels on geo map** — Permanent labels above focused nodes
4. **Expand audio documentary** — Add sections for each pattern, site-specific chapters, emergent patterns chapter
5. **Fix photo URLs** — Verify all 10 site photos load correctly
6. **Run remaining research** — Cultural Memory on failed nodes, Cross-Pattern connections scan

---

## How to Resume

Tell the new session:
> "Continue from `docs/PLATFORM-EVOLUTION-IDEAS.md` and `docs/session-summary-2026-08-01-grid-dashboard.md`. Priorities: documentary-style AI summaries in network graph, 2-level drill-down, geo map labels, expand audio chapters."

Key files to reference:
- `src/frontend/grid-globe.html` — the dashboard
- `src/services/agent_orchestrator.py` — agent chain with handlers
- `src/data/uvg-grid-scored-findings.json` — scored data with cultural traits
- `src/data/agent-chain-results.json` — full research chain output
- `docs/best-practices-documentary-research-format.md` — template for summaries

---

## Tavily Budget

- Used: 9 calls (taxonomy scanner deep-dive on strong matches)
- Remaining: ~991 of 1000 monthly credits
- Key: `tvly-dev-1NS91G-...` (set as env var, never hardcode)

## Commits This Session

```
d109ecd Session end: update PLATFORM-EVOLUTION-IDEAS with next session priorities
7075ef6 Cultural Memory Deep-Dive: specific traits enable meaningful network edges
db1f6af Fix network spaghetti: exclude generic indicators, fix photo URLs
4231671 Fix Angkor photo, cap network edges at 15
a08f3b6 Network graph: intelligence brief panel next to graph
9a1a3f2 Add picture-in-picture: site photos synced to narration
80c8664 Fix network graph: intelligence summary, correct audio-map sync
18e2574 Fix cue engine: timing for individual vs full playback mode
53f698f Fix audio sync: inline cue sheet + script data
e09c2b8 Fix audio player data loading
177a483 Fix audio player: progress scrubber, chapter buttons, CC captions
0f23f14 Audio player: chapter navigation, seek controls, speed adjustment
1cb5e6c Interactive documentary dashboard (main commit)
```
