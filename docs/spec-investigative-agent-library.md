# Investigative Intelligence Agent Library — Specification

## The Core Insight

Just like a cyber security SOC has specialized agents (malware analysis, network forensics, threat intel), an investigative intelligence platform needs specialized research agents that auto-trigger based on what findings emerge.

The pattern we proved in this session:
1. Broad scan finds something interesting (ley lines)
2. Human says "dig deeper" → builds taxonomy + targeted research
3. Findings suggest the NEXT investigation ("15 nodes are indigenous sacred sites — why?")

**The agent should do step 3 automatically.** When it finds a pattern, it should spawn a follow-up investigation without waiting for the human.

---

## Agent Architecture

### What is an Investigative Agent?

An agent is a reusable research pipeline with:
- **Trigger condition**: What activates this agent (finding a specific signature, human request, or another agent's output)
- **Research strategy**: What queries to run, what data to gather
- **Taxonomy scope**: What signatures to look for in findings
- **Output format**: Structured findings that feed into the next pipeline step
- **Follow-up logic**: What agent(s) to trigger next based on results

### Agent Lifecycle
```
TRIGGER → RESEARCH → SCORE → DECIDE → [FOLLOW-UP or COMPLETE]
                                   ↓
                              Store findings in:
                              - S3 (raw)
                              - OpenSearch (vectors)
                              - Neptune (graph)
                              - Aurora (structured)
```

---

## Agent Library — Defined Types

### 1. Broad Scanner Agent
**Purpose**: Initial sweep of a new topic/domain/location
**Trigger**: Human selects a new taxonomy node or enters a concept
**Research strategy**: 3-5 diverse queries covering academic, geographic, cultural, skeptic angles
**Taxonomy scope**: ALL signatures (looking for anything)
**Output**: Prioritized list of findings + recommended follow-up agents
**Follow-up**: Triggers specific agents based on what was found

**We built this**: `batch_research_direct.py` + `concept_research_agent.py`

---

### 2. Taxonomy-Guided Scanner Agent
**Purpose**: Second pass with targeted signature-specific queries
**Trigger**: After Broad Scanner completes
**Research strategy**: One query per signature indicator (e.g., "megalithic >10 ton stones at [coords]")
**Taxonomy scope**: All 18 grid investigation signatures
**Output**: Signature match scores per node (MATCH/POSSIBLE/NO_MATCH)
**Follow-up**: Triggers Cross-Pattern Agent if cnp-* signatures match

**We built this**: `batch_research_taxonomy_guided.py`

---

### 3. Cross-Pattern Correlation Agent
**Purpose**: Finds connections between DISTANT sites that share the same signature
**Trigger**: When 3+ nodes match the same cnp-* (cross-node pattern) signature
**Research strategy**: 
  - "What do [Site A] and [Site B] have in common?"
  - "Same construction technique at [distance]km apart?"
  - "Shared astronomical encoding?"
**Taxonomy scope**: cnp-001 through cnp-004 specifically
**Output**: Validated cross-site connections with evidence
**Follow-up**: Triggers Documentary Production Agent with the strongest connections

**Status**: DEFINED — not yet built

---

### 4. Cultural Memory Deep-Dive Agent
**Purpose**: When cm-001 fires (indigenous sacred designation), investigate WHY
**Trigger**: cm-001 matches at 3+ nodes in same region
**Research strategy**:
  - "What specific traditions mark [location] as sacred?"
  - "What rituals are performed here and for how long?"
  - "Do these traditions describe the location's PROPERTIES (energy, healing, danger)?"
  - "Is there a creation myth associated?"
**Taxonomy scope**: cm-001, cm-002, cm-003
**Output**: Cultural evidence database — what indigenous peoples say about grid nodes
**Follow-up**: Triggers Geological Correlation Agent (do cultural claims match physical measurements?)

**Status**: DEFINED — not yet built

---

### 5. Geological Correlation Agent
**Purpose**: When ga-* signatures fire, get HARD DATA (measurements, surveys, satellite)
**Trigger**: ga-001 (geomagnetic) or ga-002 (geometric formation) match
**Research strategy**:
  - Search for published geomagnetic survey data at coordinates
  - Look for USGS/geological survey measurements
  - Find satellite imagery anomalies (Google Earth historical)
  - Cross-reference with tectonic/seismic databases
**Taxonomy scope**: ga-001, ga-002, ga-003
**Output**: Quantified geological evidence (actual measurements, not just descriptions)
**Follow-up**: If confirmed anomaly → triggers Field Recommendation Agent

**Status**: DEFINED — not yet built

---

### 6. Submerged Evidence Agent
**Purpose**: For ocean nodes — find what's underwater
**Trigger**: Node classified as "ocean" OR se-* signatures match
**Research strategy**:
  - Bathymetric databases (GEBCO, NOAA)
  - Sunken civilization mythology cross-referenced with coordinates
  - Maritime disappearance databases
  - Ice age sea level reconstruction (what was land 12,000 years ago?)
  - Underwater archaeology publications
**Taxonomy scope**: se-001 through se-004
**Output**: Underwater evidence database with depth profiles + mythology matches
**Follow-up**: If submerged plateau found → triggers "Was This Land?" Agent

**Status**: PARTIALLY BUILT — ocean queries in batch_research_direct.py

---

### 7. LiDAR Opportunity Agent
**Purpose**: Identify locations where LiDAR HASN'T been used but SHOULD be
**Trigger**: Finding mentions "unexplored", "dense vegetation", "unexcavated"
**Research strategy**:
  - Has LiDAR been used within 200km of this node?
  - What did LiDAR reveal in SIMILAR terrain elsewhere?
  - What vegetation cover exists (satellite check)?
  - Are there access/permission requirements?
**Taxonomy scope**: san-001 through san-004 (looking for hidden structures)
**Output**: LiDAR target priority list with logistics
**Follow-up**: Feeds into Documentary Production Agent

**Status**: DEFINED — not yet built

---

### 8. Documentary Production Agent
**Purpose**: For confirmed high-priority findings, prepare a production brief
**Trigger**: Investigation_status = CONFIRMED or PROBABLE with high production_value
**Research strategy**:
  - What's the visual appeal? (aerial potential, dramatic landscape)
  - Access logistics (permits, seasons, local contacts)
  - What story does this tell? (narrative arc)
  - What counter-arguments exist? (balanced journalism)
  - Who are the expert talking heads? (researchers to interview)
**Taxonomy scope**: N/A — meta-agent, works on findings not raw data
**Output**: Production brief for documentary team
**Follow-up**: TERMINAL — this is the final output for content creation

**Status**: DEFINED — not yet built

---

### 9. Auto-Query Generation Agent
**Purpose**: When any agent completes, generate the NEXT BEST queries automatically
**Trigger**: Any agent completion event
**Research strategy**:
  - Analyze what was found vs what's still unknown
  - Identify gaps in evidence (what signatures have NO matches?)
  - Generate 3-5 follow-up queries that would fill those gaps
  - Rank queries by likelihood of yielding results
**Taxonomy scope**: ALL — looks at unfired signatures as "gaps to fill"
**Output**: Ranked list of next-best queries to run
**Follow-up**: Triggers the appropriate specialized agent

**This is the "threat hunter query writer" you described.** It automates the "ok what should I search for next?" decision.

**Status**: DEFINED — highest priority to build next

---

### 10. Pattern Emergence Agent
**Purpose**: Periodically re-analyze ALL accumulated findings to detect NEW patterns
**Trigger**: Scheduled (after N new findings added) or manual
**Research strategy**:
  - Run k-NN similarity across all indexed nodes
  - Identify clusters that weren't obvious before
  - Check if any NEW cross-node patterns have emerged
  - Compare against known patterns to find anomalies
**Taxonomy scope**: cnp-* signatures specifically, but may GENERATE new signatures
**Output**: New pattern hypotheses to investigate
**Follow-up**: May ADD new signatures to the taxonomy, then triggers Broad Scanner on those

**This is the agent that GROWS the taxonomy.** It discovers patterns we didn't know to look for.

**Status**: DEFINED — game-changer when built

---

## Agent Orchestration

### Trigger Chain Example (what we just did, automated)

```
Human clicks "Ancient Mysteries" domain
  → Broad Scanner Agent fires
    → Finds: "ley lines are interesting, 15 nodes have indigenous sacred sites"
      → Auto-Query Agent fires
        → Generates: "investigate why indigenous peoples cluster at grid nodes"
          → Cultural Memory Deep-Dive Agent fires
            → Finds: "Tohono O'odham, Aboriginal, Shamanic traditions all mark these as power places"
              → Cross-Pattern Agent fires
                → Finds: "3 cultures on 3 continents describe same 'buzzing energy' at grid nodes"
                  → Documentary Production Agent fires
                    → Output: "Episode pitch: Three unrelated cultures feel the same thing at the same geometric points"
```

That entire chain should run WITHOUT human intervention once triggered. The human reviews the final output and decides what to produce.

---

## Implementation Priority

1. **Auto-Query Generation Agent** (highest value — automates the "what next?" decision)
2. **Cross-Pattern Correlation Agent** (finds the smoking guns)
3. **Pattern Emergence Agent** (grows the taxonomy automatically)
4. **Cultural Memory Deep-Dive Agent** (15 nodes already flagged — ready to go)
5. **LiDAR Opportunity Agent** (actionable field recommendations)
6. **Documentary Production Agent** (final output for content teams)

---

## How This Relates to the Existing System

Each agent maps to existing infrastructure:
- **Research**: Brave Search + Sonnet (already working)
- **Scoring**: Signature Matching Engine (already built)
- **Storage**: S3 → OpenSearch → Aurora → Neptune (pipeline working)
- **Taxonomy**: Extensible JSON signatures (already structured)

What's new is the **orchestration layer** — the logic that decides WHICH agent to run WHEN, and passes context between them. This could be implemented as:
- A Step Functions state machine (AWS native)
- A simple Python orchestrator with agent registry
- An event-driven system (agent completion → SNS → trigger next)

The simplest MVP: a Python class `AgentOrchestrator` that holds the trigger rules and runs agents sequentially. Graduate to Step Functions when we need parallelism and error handling.

---

## Is This a One-Off or Repeatable?

**100% repeatable.** The same agent library works for:
- Any new taxonomy domain (crime, fraud, ancient mysteries, biotech, etc.)
- Any geographic investigation (grid nodes, trade routes, migration paths)
- Any network analysis (connections between entities, organizations, sites)

The agents are DOMAIN-AGNOSTIC — they operate on the same pattern:
`trigger → research → score against taxonomy → decide next step`

What changes per domain is only the TAXONOMY (the signatures to look for). The agents themselves are reusable infrastructure.
