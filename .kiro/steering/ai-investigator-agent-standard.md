---
inclusion: auto
---

# AI Investigator Agent — Progressive Execution Standard (MANDATORY)

## Rule: EVERY AI investigation panel MUST follow this progressive execution format. The agent runs steps sequentially, each step's output feeds the next, and the analyst watches it unfold in real-time.

## What This Is

The AI Investigator is the "Run" button on any case, voyage, entity, or lead. When the analyst clicks it, the system executes 3-5 investigation steps progressively — each step queries different data sources, produces a one-line finding, and that finding feeds context into the next step.

This is NOT a static panel. It is a LIVE execution sequence that demonstrates the AI's analytical reasoning in a way the analyst can follow, interrupt, or redirect.

---

## The Standard Components (use these, never reinvent)

### Pre-Built Shared Components

| Component | Path | Use When |
|-----------|------|----------|
| `InvestigationContextPanel` | `frontend/src/components/shared/InvestigationContextPanel.tsx` | BEFORE running — shows hypothesis, evidence gaps, planned steps |
| `AgentOrchestrator` | `frontend/src/components/shared/AgentOrchestrator.tsx` | AFTER running — shows findings, recommends next agents, approval gate |
| `AIInvestigatorPanel` (inline) | Built into page component | For simpler progressive execution within a detail panel (interdiction queue pattern) |

### When to Use Which

- **Full orchestration** (multi-agent, multi-loop): Use `InvestigationContextPanel` → API call → `AgentOrchestrator`
- **Inline progressive execution** (single panel, demo-friendly): Use the `AIInvestigatorPanel` pattern (built into the page)

---

## Progressive Execution Format (MANDATORY)

### Structure

```
┌─────────────────────────────────────────────────────────────┐
│ 🤖 AI Investigator — Recommended Next Steps    [2/5 complete]│
│                                                              │
│ [Run Investigation] button (top-right)                       │
├─────────────────────────────────────────────────────────────┤
│ HYPOTHESIS (ASSESSED — Moderate Confidence)                  │
│ "MV Raider operated as a drug logistics platform..."         │
├─────────────────────────────────────────────────────────────┤
│ Progress: ████████░░░░░░░░ 40%                               │
├─────────────────────────────────────────────────────────────┤
│ ✓ R1  Vessel Ownership Deep Trace                            │
│       Trace through Togo registry. ID beneficial owner...    │
│       → FOUND: "Pacifica Shipping LLC" (Belize). Nominee... │
│       [Equasis] [Togo Registry] [ICIJ] [IMO GISIS]          │
│                                                              │
│ ✓ R2  Crew Network Analysis                                  │
│       Run crew through Interpol, Five Eyes, travel records   │
│       → FOUND: Crew #3 linked to 2019 Sinaloa logistics...  │
│       [Interpol] [APIS/PNR] [TECS] [DOJ Corpus]             │
│                                                              │
│ ⟳ R3  Satellite Phone Intelligence                           │
│       Analyze satphone metadata from seized devices...       │
│       [Satellite provider] [SIGINT]                          │
│                                                              │
│ ○ R4  Upstream Supply Route  (pending)                       │
│ ○ R5  Financial Trace  (pending)                             │
└─────────────────────────────────────────────────────────────┘
```

### Rules for Each Step

1. **Action Title** — short name (2-4 words). Examples: "Vessel Ownership Deep Trace", "BOL Entity Cross-Reference", "Financial Trace"
2. **Description** — one paragraph explaining what this step does (written for a GS-14 analyst, not an engineer)
3. **Data Sources** — badges showing which databases are queried (e.g., [Equasis] [ICIJ] [OFAC])
4. **Output Line** — starts with `→ FOUND:` — one sentence stating what was discovered. This is the KEY DELIVERABLE of each step.
5. **Feed-Forward** — the output of step N must logically enable step N+1. Example: R1 finds the owner name → R2 runs that name through watchlists.

### Timing

- Each step takes **1.5 seconds** in demo mode (simulated)
- In production, each step is an actual API call (Bedrock + data sources)
- Steps execute SEQUENTIALLY — each waits for the prior to complete
- Progress bar updates after each step

---

## Context-Aware Step Generation (MANDATORY)

The investigation plan MUST adapt based on what's known about the case. Three patterns:

### Pattern A: Unknown Vessel (vessel not identified)
Use when: delivery vessel never entered port, dropped cargo offshore, not identified

| Step | Action | What It Does |
|------|--------|-------------|
| R1 | AIS Corridor Analysis | Query all vessels near seizure location in time window. Filter for speed/AIS anomalies. |
| R2 | Vessel Ownership Trace | For candidates from R1: trace IMO → owner → beneficial owner. Cross-ref ICIJ. |
| R3 | Port Call History | 12-month history for top candidates. Flag cocaine origin ports. |
| R4 | Financial Intelligence | Run owner entities through AUSTRAC/FinCEN. Check for filed SMRs. |

### Pattern B: BOL-Based (commercial cargo, container seizure)
Use when: drugs found in commercial container with legitimate BOL

| Step | Action | What It Does |
|------|--------|-------------|
| R1 | BOL Entity Cross-Reference | Run shipper + consignee against OFAC, ICIJ, DOJ roster. |
| R2 | Historical Shipment Pattern | Pull all BOLs from same shipper in 24 months. ID frequency/volume anomalies. |
| R3 | Consignee Network Expansion | Trace consignee to directors/shareholders. Expand 2 hops. Check drug addresses. |
| R4 | Financial Indicators | Check consignee banking for structured deposits, SMRs. AUSTRAC typology match. |
| R5 | Supply Chain Integrity | Coordinate with origin country: was shipper compromised (insider) or a front? |

### Pattern C: Mothership / Go-Fast (vessel identified, crew detained)
Use when: vessel seized, crew in custody, need to trace upstream

| Step | Action | What It Does |
|------|--------|-------------|
| R1 | Vessel Ownership Deep Trace | Registry → nominee directors → beneficial owner. ICIJ cross-ref. |
| R2 | Crew Network Analysis | Run crew IDs through Interpol, Five Eyes, travel records. ID recruiter. |
| R3 | Communications Intelligence | Analyze satellite phone / encrypted comms metadata. Map command structure. |
| R4 | Upstream Supply Route | AIS backtrack to loading point. Port records for departure logistics. |
| R5 | Financial Trace | Follow payments for vessel mods, crew wages, fuel, provisions. |

---

## Priority Scoring Algorithm (Configurable)

### Formula

```
PRIORITY = Base Risk Score × Impact Multiplier × Pattern Boost

Where:
  Base Risk Score (0-100) = weighted sum of 5 scoring categories
  Impact Multiplier (1.0-2.5x) = based on estimated volume/value
  Pattern Boost (1.0-1.3x) = based on Crime Pattern Library signature matches
```

### Impact Multiplier Tiers

| Estimated Volume | Multiplier | Rationale |
|-----------------|-----------|-----------|
| < 100 kg | 1.0x | Significant but not strategic |
| 100 kg – 1 tonne | 1.3x | Multi-million dollar operation |
| 1 – 5 tonnes | 1.8x | Major cartel-scale shipment |
| > 5 tonnes | 2.5x | Strategic-level interdiction target |

### Pattern Boost Tiers

| Signatures Matched | Boost | Rationale |
|-------------------|-------|-----------|
| 0 signatures | 1.0x | No known pattern match — still scored on other factors |
| 1-2 signatures | 1.1x | Matches known prosecution method |
| 3-4 signatures | 1.2x | Strong pattern convergence |
| 5+ signatures | 1.3x | Multi-method operation — highest prosecution viability |

### 5 Scoring Categories (weights configurable per agency)

| Category | Default Weight | Rules | Scores Against |
|----------|--------------|-------|----------------|
| Vessel Behavior (AIS) | 25% | 5 rules | Dark periods, speed, route deviation, STS, flag change |
| Cargo & Manifest (BOL) | 25% | 5 rules | No manifest, weight anomaly, origin port, reefer, transshipment |
| Entity & Network | 25% | 4 rules | OFAC match, ICIJ hit, DOJ connection, opaque ownership |
| Financial Intelligence | 15% | 4 rules | SMR match, mirror trading, cash business, IFTI risk |
| Crime Pattern Library (AI) | 10% | 2 rules | k-NN signature match (≥0.85), multi-sig convergence |

### Configuration

Weights are adjustable per agency priority:
- **AFP** may weight Financial Intelligence higher (Chinese ML focus)
- **USCG** may weight Vessel Behavior higher (maritime interdiction focus)
- **ABF** may weight Cargo & Manifest higher (port inspection focus)

Config location: `frontend/src/lib/pacific-interdiction-data.ts` → `SCORING_CATEGORIES`

---

## Transaction Types (What Feeds the Queue)

The interdiction queue is fed by 4 real-time transaction types:

| Transaction | Volume/Year | Source | Equivalent |
|-------------|-------------|--------|-----------|
| AIS Position Report | ~100M (Pacific) | Vessel transponder → satellite | Continuous sensor feed |
| AUSTRAC SMR | 452,951 (↑19%) | Banks/casinos/remitters → AUSTRAC | US FinCEN SAR |
| Cargo Manifest (BOL) | ~8M containers (AU) | Shipping lines → ABF | US CBP ACE/ABI |
| IFTI (Wire Transfer) | ~200M/year | Banks → AUSTRAC | US FinCEN CTR |

Each transaction passes through the 5-category scoring engine. Only transactions scoring above threshold (≥60 = HIGH) enter the analyst queue.

---

## Output Format Rules

### The `→ FOUND:` Line

Every step MUST produce exactly ONE output line starting with `→ FOUND:`. This line must:
- Name a SPECIFIC entity, amount, or connection discovered
- Be actionable (the analyst can verify or act on it)
- Feed context to the next step (the next step should logically use what was found)
- Not exceed 2 sentences

**Good examples:**
- `→ FOUND: Owner is "Pacifica Shipping LLC" (Belize). Nominee director: J. Hernandez, Tegucigalpa.`
- `→ FOUND: Same shipper sent 14 containers in 12 months (previously 3/year). Volume spike correlates with cocaine market.`
- `→ FOUND: $340K wire HK → Belize → vessel provisions. Same HK entity in ICIJ Panama Papers.`

**Bad examples:**
- ❌ `→ FOUND: Multiple entities identified.` (too vague)
- ❌ `→ FOUND: Investigation continues.` (no finding)
- ❌ `→ FOUND: Based on analysis of 47 data points across 3 systems...` (too verbose)

---

## NEVER Do This

- ❌ Show investigation steps as static text without a Run button
- ❌ Show all findings at once (must be progressive — step by step)
- ❌ Generate steps that don't logically chain (each output must feed the next)
- ❌ Use generic step names ("Step 1", "Step 2") — always use domain-specific action titles
- ❌ Skip the hypothesis (analyst needs to know WHAT the agent is testing)
- ❌ Show steps without data source badges (analyst needs to know WHERE data comes from)
- ❌ Make the investigation plan static — it MUST adapt based on case type

## ALWAYS Do This

- ✅ Show a "Run Investigation" button (analyst initiates, not auto-run)
- ✅ Execute steps progressively with visible timing (1.5s per step in demo)
- ✅ Produce exactly one `→ FOUND:` output per step
- ✅ Show data source badges on each step
- ✅ Adapt investigation plan based on case type (Pattern A/B/C above)
- ✅ Show progress bar updating in real-time
- ✅ Include the hypothesis (ASSESSED, with confidence level)
- ✅ Make the panel scrollable and always visible at bottom of case detail

---

## Reference Implementations

| Page | Path | Pattern Used |
|------|------|-------------|
| Pacific Interdiction Queue | `frontend/src/app/pacific/interdiction-queue/page.tsx` | Inline `AIInvestigatorPanel` with `getInvestigationPlan()` + `getStepOutputs()` + `getAssessment()` |
| Compass Investigation Agent | `frontend/src/app/compass/investigation-agent/page.tsx` | Full `InvestigationContextPanel` → API → `AgentOrchestrator` |
| MAF Investigation | `frontend/src/app/maf/investigate/page.tsx` | `CaseFile` with embedded investigation |

## The Full Investigation Loop (MANDATORY — complete cycle)

```
1. ANALYST clicks "Run Investigation"
2. HYPOTHESIS displayed (what the AI is testing)
3. STEPS execute progressively (1.5s each):
   - Each produces → FOUND: one-line output
   - Output feeds context to next step
   - Progress bar advances
4. ASSESSMENT phase (after all steps complete):
   a. VERDICT: MOVE FORWARD | DEVELOP | DECLINE
   b. CONFIDENCE: HIGH | MODERATE | LOW (with basis)
   c. REASONING: 2-3 sentences explaining verdict
   d. DIMINISHING RETURNS CHECK:
      - If saturation reached → "✓ No further AI search. Transfer to human."
      - If gaps remain → "⟳ Second pass recommended. [reason]"
         → "Run Second Pass" button available
   e. ACTION ITEMS: Numbered list for human investigator
      - Format: "TIMING: Action description"
      - Timings: IMMEDIATE | WITHIN 72H | WITHIN 7D | ONGOING
5. GEOSPATIAL VIEW: Route map showing AIS track with color-coded status
   - Cyan = normal transit
   - Red/dashed = AIS dark (lost signal)
   - Amber = anomaly (speed change, loitering)
```

### Verdict Criteria

| Verdict | When | Next Action |
|---------|------|-------------|
| **MOVE FORWARD** | All elements of offence provable. Financial trail confirmed. Prosecution package achievable. | Transfer to prosecutor. No more AI search needed. |
| **DEVELOP** | Promising but gaps remain. Identity of key player unknown, or evidence circumstantial. | Run second pass with sharper focus. |
| **DECLINE** | Investigation exhausted. No actionable intelligence despite full search. | Close. Document negative for future reference. |

### Diminishing Returns Logic

The AI decides whether to recommend a second pass based on:
- Did all steps produce actionable findings? (If yes → saturation)
- Are there unresolved IDENTITY questions? (If yes → run again)
- Is evidence circumstantial vs. direct? (If circumstantial → run again)
- Would a different data source potentially resolve the gap? (If yes → run again with different plan)

---

## Geospatial Route View (MANDATORY on every voyage/case)

Every investigation MUST include a geospatial visualization showing:
- **Vessel track** (from AIS data points in the voyage record)
- **Color coding**: normal (cyan), dark period (red dashed), anomaly (amber)
- **Key timestamps** at start and end points
- **Legend** explaining colors
- **Track point details** below the map (date, coordinates, speed, status)

For follow-the-money views, the same geospatial component shows:
- **Wire transfer route**: origin country → intermediary → destination
- **Nodes**: entities at each geographic point (banks, shell companies)
- **Amounts**: on the connecting lines

Use the SVG route map pattern (no SSR issues, works everywhere) or Leaflet (when full interactive zoom needed).

---

## Data File Reference

- Scoring categories: `frontend/src/lib/pacific-interdiction-data.ts` → `SCORING_CATEGORIES`
- Transaction types: `frontend/src/lib/pacific-interdiction-data.ts` → `TRANSACTION_TYPES`
- Step outputs per voyage: `getStepOutputs()` function in interdiction queue page
- Investigation plan logic: `getInvestigationPlan()` function in interdiction queue page
- Assessment/verdict logic: `getAssessment()` function in interdiction queue page
- Geospatial route: SVG route map in "Route Map" tab of detail panel
- FinCEN real SAR cases: `data/pacific/real-vessels/FinCEN-LEAP-Cases-Compilation.pdf`
