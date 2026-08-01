# Design Document: AI Research Agent Chain

## Overview

A multi-agent orchestration system that autonomously investigates research topics using a sequential chain of specialized AI agents. Each agent builds on the accumulated findings of all previous agents, producing compounding intelligence.

**Single execution result (2026-08-01):** 163.4 seconds, 7 signature matches, 38 new cross-site indicators, 25+ sites linked across 6 continents.

---

## Architecture

```
Research Question (string)
        │
        ▼
┌─ ORCHESTRATOR ──────────────────────────────────────────────┐
│  src/services/agent_orchestrator.py                         │
│  • Registers agents with priority levels (1-8)              │
│  • Manages InvestigationContext (accumulated findings)      │
│  • Auto-triggers follow-ups from suggested_follow_ups[]     │
│  • Max recursion depth: 5                                   │
│  • Error recovery: skip failed agents, continue chain       │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ AGENT 1: BROAD SCANNER ───────────────────────────────────┐
│  Priority: 1 | Time: ~83s                                   │
│  Input:  Research question string                           │
│  Model:  Claude Sonnet 4 (us.anthropic.claude-sonnet-4-6)   │
│  Output: {summary, key_facts[], anomalies[],                │
│           counter_arguments[], sites_identified[]}           │
│  Trigger: Always runs first                                 │
└─────────────────────────────────────────────────────────────┘
        │ passes accumulated_findings + signature_matches
        ▼
┌─ AGENT 2: TAXONOMY SCANNER ────────────────────────────────┐
│  Priority: 2 | Time: ~80s                                   │
│  Input:  Broad Scanner findings + taxonomy signatures       │
│  Model:  Claude Sonnet 4 + Tavily Web Search (Phase 2)      │
│  Output: {signature_matches[] with confidence + citations,  │
│           new_evidence, gaps_remaining[], strongest_signal}  │
│  Trigger: suggested_follow_ups from Agent 1                 │
└─────────────────────────────────────────────────────────────┘
        │ passes all accumulated findings
        ▼
┌─ AGENT 3: CROSS-PATTERN AGENT ─────────────────────────────┐
│  Priority: 3 | Time: ~80s                                   │
│  Input:  All previous findings + sites list                 │
│  Model:  Claude Sonnet 4 + Tavily (top 3 connections)       │
│  Output: {connections_found[], strongest_correlation,        │
│           documentary_hook, signature_matches[]}             │
│  Trigger: suggested_follow_ups from Agent 2                 │
│  Focus:  Sites >3000km apart sharing specific traits        │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ POST-PROCESSING ──────────────────────────────────────────┐
│  scripts/_merge_cross_pattern_results.py                    │
│  • Maps site names → node IDs (fuzzy match)                 │
│  • Extracts specific indicators from evidence text          │
│  • Filters generic indicators (pattern definitions)         │
│  • Upgrades confidence levels where warranted               │
│  • Creates cross-pattern signature IDs (am-gge-xpat-*)     │
│  • Saves to uvg-grid-scored-findings.json                   │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ FRONTEND VISUALIZATION ───────────────────────────────────┐
│  src/frontend/grid-globe.html                               │
│  • Reads scored-findings.json at startup                    │
│  • D3 force-directed network graph                          │
│  • Edges = SPECIFIC shared indicators only                  │
│  • Nodes = sites matching focused pattern                   │
│  • Documentary-style brief: Hook → Evidence → Connection    │
│  • 2-level drill-down with sidebar flash                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Handlers (registered but not all wired)

| # | Agent | Status | Handler |
|---|-------|--------|---------|
| 1 | Broad Scanner | ✅ Ready | `broad_scanner_handler()` |
| 2 | Taxonomy Scanner | ✅ Ready | `taxonomy_scanner_handler()` |
| 3 | Cross-Pattern Agent | ✅ Ready | `cross_pattern_agent_handler()` |
| 4 | Cultural Memory | ❌ No handler | Separate script: `_research_cultural_memory.py` |
| 4 | Geological Correlation | ❌ No handler | — |
| 5 | LiDAR Opportunity Finder | ❌ No handler | — |
| 6 | Auto-Query Generator | ❌ No handler | — |
| 8 | Production Brief | ❌ No handler | — |

---

## Key Design Decisions

### 1. Context Accumulation
Each agent receives ALL findings from previous agents via `InvestigationContext.accumulated_findings[]`. This enables compounding intelligence — Agent 3 can find connections between sites that Agent 1 surfaced but didn't recognize as significant.

### 2. Generic Indicator Filtering
The network graph filters out indicators that simply restate the pattern definition:
- "5+ ancient sites clustered" ← this IS the pattern, not a connection
- "Within 300km of node" ← same
- Only SPECIFIC traits (shared construction technique, astronomical alignment, etc.) create edges

### 3. Structured JSON Output
All agents are prompted to return valid JSON. A robust parser (`_parse_llm_json`) handles:
- Markdown code fences
- Truncated JSON (auto-repairs bracket/brace balance)
- Fallback to raw text in dict

### 4. Confidence Taxonomy
- **STRONG:** Peer-reviewed, independently measured, reproducible
- **MODERATE:** Cited by researchers but not independently replicated
- **WEAK:** Anecdotal, single-source, or contested

### 5. Counter-Arguments Required
Every finding includes the strongest skeptical argument. This builds credibility with researchers — the system is investigative, not advocacy.

### 6. Cost Control
- Tavily: max 20 calls per chain run
- Bedrock: 4096 max tokens per call, 120s timeout
- Estimated cost per full chain: ~$0.35

---

## Data Files

| File | Purpose |
|------|---------|
| `src/data/agent-chain-results.json` | Full chain execution output (all agents) |
| `src/data/uvg-grid-scored-findings.json` | 59 nodes × N signatures (frontend reads this) |
| `src/data/uvg-grid-research-all-nodes.json` | Per-node intelligence briefs |
| `src/data/emergent-patterns.json` | OpenSearch k-NN similarity pairs |
| `src/data/cultural-memory-results.json` | Indigenous tradition traits per site |

---

## Cross-Pattern Findings (2026-08-01 Run)

### Signatures Found

1. **am-gge-xpat-001** (Great Circle Alignment) — STRONG
   - Sites: Giza, Persepolis, Mohenjo-daro, Angkor, Easter Island
   - <1° deviation across 40,000km
   - Researcher: Jim Alison (2001)

2. **am-gge-xpat-002** (Orion Epoch Encoding) — STRONG
   - Sites: Giza, Angkor, Teotihuacan
   - Same precessional sky-date: 10,500 BCE
   - Researchers: Bauval (1994), Hancock (1998), Harleston (1974)

3. **am-gge-san-001** (Megalithic Construction) — STRONG
   - Sites: Giza, Stonehenge, Puma Punku, Nan Madol
   - 25-80 ton blocks, sub-mm precision
   - Researchers: Petrie (1883), Protzen & Nair (2000)

4. **am-gge-cnp-002** (Astronomical Encoding) — STRONG
   - Sites: Giza, Angkor, Teotihuacan, Stonehenge, Machu Picchu
   - Orion correlation + solar/lunar alignments
   - Researchers: Bauval (1994), Aveni (1980)

5. **am-gge-cnp-001** (Polygonal Masonry) — MODERATE
   - Sites: Sacsayhuaman, Mycenae, Malta (12,000km apart)
   - Similar fitting technique — convergent evolution unclear
   - Researchers: Protzen (1986), Shaw (2004)

6. **am-gge-cm-001** (Sacred Continuity / Axis Mundi) — STRONG
   - Sites: Delphi, Jerusalem, Cusco, Angkor, Mecca
   - 500+ years continuous sacred designation, all near grid nodes
   - Researchers: Eliade (1959), Fontenrose (1978)

7. **am-gge-ga-002** (Mathematical Encoding) — MODERATE
   - Sites: Giza (pi), Teotihuacan (12th-root-of-2), Angkor (lunar cycles)
   - Unit-of-measure circularity weakens some claims
   - Researchers: Taylor (1859), Harleston (1974), Mannikka (1996)

---

## Invocation

```powershell
# Full agent chain
python scripts/_run_agent_chain.py "cross_pattern_connections_between_uvg_grid_sites"

# Merge results into scored data
python scripts/_merge_cross_pattern_results.py

# Cultural memory (separate script)
python scripts/_research_cultural_memory.py
```

---

## Remaining Work

1. **Cultural Memory re-run** — Sedona (failed), zero-match nodes
2. **Emergent Pattern re-run** — k-NN with updated scored data
3. **Suggested by AI (from taxonomy_scanner):**
   - Monte Carlo null-hypothesis grid test
   - GPS verification of Alison alignment
   - Isotopic stone-sourcing across nodes
   - Precessional encoding test at 3 sites
   - Underwater survey compilation for marine nodes
