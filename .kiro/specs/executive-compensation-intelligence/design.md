# Design Document: Executive Compensation Intelligence

## Overview

This design extends the Executive Succession Planning module with compensation intelligence, risk analysis, fit/readiness scoring, and process stage tracking. It adds four backend services (Compensation_Engine, Risk_Analyzer, Readiness_Analyzer, Process_Tracker), a compensation lookup data layer, two new Aurora tables, and a new dashboard tab — all integrated with the existing three-layer scoring engine and cultural calibration system.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    succession-dashboard.html                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Pipeline │ │Candidates│ │ Comp &   │ │ Process  │ │ What-If │ │
│  │ Overview │ │  & Score │ │   Risk   │ │ Timeline │ │Simulator│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘ │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ fetch JSON
┌─────────────────────────────▼───────────────────────────────────────┐
│              succession_comp_risk_server.py (port 8090)              │
│  ┌───────────────────┐  ┌───────────────────┐  ┌────────────────┐ │
│  │Compensation_Engine│  │  Risk_Analyzer     │  │Process_Tracker │ │
│  │                   │  │                    │  │                │ │
│  │ • total_comp()    │  │ • flight_risk()    │  │ • advance()    │ │
│  │ • market_range()  │  │ • poachability()   │  │ • get_stage()  │ │
│  │ • comp_gap()      │  │ • cultural_risk()  │  │ • sla_check()  │ │
│  │ • enrich()        │  │ • compliance()     │  │ • timeline()   │ │
│  └────────┬──────────┘  │ • non_compete()    │  └────────────────┘ │
│           │              └────────┬───────────┘                     │
│  ┌────────▼──────────┐  ┌────────▼───────────┐  ┌────────────────┐│
│  │  Lookup Tables    │  │ Cultural Profiles  │  │Readiness Engine││
│  │  (comp_data.json) │  │ (GLOBE/Hofstede)   │  │ • gap_heatmap()││
│  └───────────────────┘  └────────────────────┘  │ • ttr()        ││
│                                                  │ • dev_cost()   ││
│                                                  │ • roi()        ││
│                                                  └────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│  Brave Search   │         │  Bedrock Haiku  │
│  (enrichment)   │         │  (extraction)   │
└─────────────────┘         └─────────────────┘
```

## Data Models

### Compensation Lookup Table (`src/frontend/succession-comp-data.js`)

```javascript
const COMP_LOOKUP = {
  // Key: "{sector}_{country}_{seniority}"
  "PRIVATE_US_VP": {
    base: { p25: 280000, p50: 350000, p75: 450000 },
    bonus_pct: { p25: 30, p50: 50, p75: 80 },
    equity: { p25: 300000, p50: 600000, p75: 1200000 },
    benefits: 45000,
    total: { p25: 950000, p50: 1400000, p75: 2100000 }
  },
  "PRIVATE_IR_VP": {
    base: { p25: 180000, p50: 250000, p75: 350000 },
    bonus_pct: { p25: 20, p50: 35, p75: 50 },
    equity: { p25: 0, p50: 50000, p75: 150000 },
    benefits: 80000, // housing + hardship
    total: { p25: 380000, p50: 520000, p75: 750000 },
    allowances: {
      hardship: 50000,
      housing: 60000,
      schooling: 30000,
      security: 20000
    }
  },
  // ... per sector/country/seniority
};

const COST_OF_LIVING_INDEX = {
  US: 1.00, GB: 0.95, IR: 0.45, AE: 0.85, SA: 0.75,
  SG: 0.90, CN: 0.55, DE: 0.88, BR: 0.40, FR: 0.92,
  // ...
};

const NOTICE_PERIODS = {
  US: { VP: 0, C_SUITE: 0 }, // at-will
  GB: { VP: 6, C_SUITE: 12 }, // months
  DE: { VP: 6, C_SUITE: 6 },
  SG: { VP: 3, C_SUITE: 6 },
  IR: { VP: 1, C_SUITE: 3 },
  // ...
};

const NON_COMPETE_ENFORCEABILITY = {
  US_CA: "unenforceable", US_NY: "enforceable",
  GB: "enforceable", DE: "enforceable",
  SG: "enforceable", IR: "limited",
  IN: "unenforceable",
  // ...
};
```

### Risk Scoring Formulas

```python
# Flight Risk Score (0-100)
flight_risk = (
    tenure_factor * 30 +        # 0-30: longer tenure = lower risk (inverse)
    org_stability_factor * 25 +  # 0-25: reorg/layoffs = higher risk
    comp_trend_factor * 20 +     # 0-20: below-market comp = higher risk
    progression_factor * 25      # 0-25: stalled career = higher risk
)

# Poachability Score (0-100)
poachability = (
    comp_gap_factor * 30 +       # 0-30: larger gap below market = more poachable
    career_stage_factor * 20 +   # 0-20: mid-career peak = most poachable
    mobility_factor * 25 +       # 0-25: history of moves = more poachable
    org_instability_factor * 25  # 0-25: troubled org = more poachable
)

# Cultural Adaptation Risk (Euclidean distance)
hofstede_distance = sqrt(
    (pdi_a - pdi_b)² + (idv_a - idv_b)² + (mas_a - mas_b)² +
    (uai_a - uai_b)² + (lto_a - lto_b)² + (ivr_a - ivr_b)²
)
# LOW: <30, MEDIUM: 30-60, HIGH: 60-90, CRITICAL: >90
```

### Aurora Schema Extensions

```sql
-- Compensation estimates (append-only audit trail)
CREATE TABLE IF NOT EXISTS succession.compensation_estimates (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    candidate_id      UUID NOT NULL,
    transaction_id    VARCHAR(100),
    base_salary       NUMERIC(12,2),
    bonus_amount      NUMERIC(12,2),
    equity_value      NUMERIC(12,2),
    benefits_value    NUMERIC(12,2),
    total_comp        NUMERIC(12,2) NOT NULL,
    currency          VARCHAR(3) DEFAULT 'USD',
    confidence        VARCHAR(10) CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    lookup_version    VARCHAR(20),
    source            VARCHAR(50), -- 'lookup_table', 'ai_enriched', 'manual'
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Process stage transitions
CREATE TABLE IF NOT EXISTS succession.process_stages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    candidate_id      UUID NOT NULL,
    transaction_id    VARCHAR(100),
    stage             VARCHAR(20) NOT NULL CHECK (stage IN (
        'LONG_LIST','SHORT_LIST','APPROACH','SCREEN',
        'ASSESS','OFFER','CLOSE','ONBOARD'
    )),
    entered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exited_at         TIMESTAMPTZ,
    advanced_by       VARCHAR(100),
    notes             TEXT,
    sla_days          INT,
    is_breach         BOOLEAN DEFAULT false
);
```

## Component Design

### 1. Compensation_Engine (`src/succession/compensation_engine.py`)

```python
class CompensationEngine:
    def compute_total_comp(self, candidate: dict, lookup: dict) -> CompEstimate:
        """Compute total compensation from lookup tables."""
        key = f"{candidate['sector']}_{candidate['country']}_{candidate['seniority']}"
        entry = lookup.get(key, self._nearest_fallback(candidate, lookup))
        
        base = entry['base']['p50']
        bonus = base * (entry['bonus_pct']['p50'] / 100)
        equity = entry['equity']['p50']
        benefits = entry['benefits']
        allowances = sum(entry.get('allowances', {}).values())
        
        return CompEstimate(
            base=base, bonus=bonus, equity=equity,
            benefits=benefits, allowances=allowances,
            total=base + bonus + equity + benefits + allowances,
            confidence=entry.get('confidence', 'MEDIUM')
        )

    def compute_market_range(self, role: dict, lookup: dict) -> MarketRange:
        """P25/P50/P75 for target role."""
        ...

    def compute_comp_gap(self, candidate_comp: float, role_p50: float) -> CompGap:
        """Gap between candidate current comp and target role P50."""
        gap = candidate_comp - role_p50
        pct = (gap / role_p50) * 100 if role_p50 > 0 else 0
        label = "PREMIUM_REQUIRED" if gap > 0 else "BELOW_MARKET"
        prohibitive = abs(pct) > 40 and gap > 0
        return CompGap(amount=gap, percentage=pct, label=label, cost_prohibitive=prohibitive)
```

### 2. Risk_Analyzer (`src/succession/risk_analyzer.py`)

```python
class RiskAnalyzer:
    def compute_flight_risk(self, candidate: dict) -> RiskScore:
        """0-100 flight risk based on tenure, org stability, comp trends, progression."""
        ...

    def compute_poachability(self, candidate: dict, comp_gap: CompGap) -> RiskScore:
        """0-100 poachability based on comp gap, career stage, mobility history."""
        ...

    def compute_cultural_risk(self, candidate_country: str, target_country: str,
                               profiles: dict) -> CulturalRisk:
        """Euclidean Hofstede distance → LOW/MEDIUM/HIGH/CRITICAL."""
        ...

    def compute_compliance_risk(self, candidate: dict, signals: list) -> ComplianceRisk:
        """Sanctions, political, controversy, regulatory checks."""
        ...

    def estimate_notice_period(self, country: str, seniority: str) -> NoticePeriod:
        """Country + seniority → notice months + non-compete months."""
        ...
```

### 3. Readiness_Analyzer (`src/succession/readiness_analyzer.py`)

```python
# Development velocity (months per score point to close gap)
VELOCITY = {
    'skills': 3,      # functional_excellence, financial_acumen, digital_fluency
    'behavioral': 6,  # emotional_intelligence, adaptability, self_awareness
    'experience': 12  # board_governance, crisis_leadership
}

class ReadinessAnalyzer:
    def compute_gap_heatmap(self, candidate_scores: dict, role_requirements: dict) -> list[GapCell]:
        """25-cell heatmap: EXCEEDS, MEETS, DEVELOPMENT_NEEDED, CRITICAL_GAP."""
        ...

    def compute_time_to_readiness(self, gaps: list[GapCell]) -> int:
        """Months to close all gaps (with 0.6 concurrency factor)."""
        ...

    def compute_development_cost(self, gaps: list[GapCell], ttr: int) -> float:
        """USD estimate for coaching, rotation, upskilling."""
        ...

    def compute_roi(self, role_value: float, acquisition_cost: float,
                    dev_cost: float) -> float:
        """(value - acquisition - dev) / (acquisition + dev) * 100."""
        ...
```

### 4. Process_Tracker (`src/succession/process_tracker.py`)

```python
STAGE_ORDER = ['LONG_LIST','SHORT_LIST','APPROACH','SCREEN','ASSESS','OFFER','CLOSE','ONBOARD']
DEFAULT_SLA = {'LONG_LIST':14,'SHORT_LIST':7,'APPROACH':10,'SCREEN':14,'ASSESS':21,'OFFER':7,'CLOSE':14,'ONBOARD':30}

class ProcessTracker:
    def advance_stage(self, candidate_id: str, new_stage: str, user: str, note: str = "") -> dict:
        """Move candidate to next stage, record transition."""
        ...

    def check_sla(self, candidate_id: str) -> dict:
        """Check if current stage exceeds SLA days."""
        ...

    def get_timeline(self, transaction_id: str) -> list[dict]:
        """Get all stage transitions for Gantt visualization."""
        ...
```

### 5. HTTP Server (`scripts/succession_comp_risk_server.py`)

Runs on port 8090, called by the dashboard. Endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | /comp/estimate | Compute total comp for a candidate |
| POST | /comp/market-range | Get market range for target role |
| POST | /comp/gap | Compute comp gap |
| POST | /risk/flight | Flight risk score |
| POST | /risk/poachability | Poachability score |
| POST | /risk/cultural | Cultural adaptation risk |
| POST | /risk/compliance | Compliance/reputational risk |
| POST | /risk/notice | Notice period + non-compete |
| POST | /readiness/gap | Gap heatmap |
| POST | /readiness/ttr | Time-to-readiness |
| POST | /readiness/cost | Development cost + ROI |
| POST | /process/advance | Advance candidate stage |
| GET | /process/timeline?txn_id=X | Get stage timeline |
| POST | /analyze-all | Run all analyses for a candidate batch |

### 6. Dashboard Tab (`succession-dashboard.html` — "Compensation & Risk" tab)

Layout for the new tab:

```
┌─────────────────────────────────────────────────────────────────┐
│ Target Role Compensation Range                                   │
│ ┌─── P25 ───┬─── P50 ───┬─── P75 ───┐  Sector: PRIVATE        │
│ │  $950K    │  $1.4M    │  $2.1M    │  Country: US             │
│ └───────────┴───────────┴───────────┘  Role: VP WWPS           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Candidate Comparison Table                                       │
│ ┌──────────┬────────┬────────┬───────┬───────┬───────┬────────┐│
│ │Candidate │Tot Comp│Gap     │Flight │Poach  │Culture│Stage   ││
│ ├──────────┼────────┼────────┼───────┼───────┼───────┼────────┤│
│ │S.Michel  │$1.2M   │-$200K  │  42   │  65   │ MED   │SCREEN  ││
│ │W.Sheta   │$890K   │-$510K  │  61   │  72   │ LOW   │APPROACH││
│ └──────────┴────────┴────────┴───────┴───────┴───────┴────────┘│
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐ ┌────────────────────────────────┐
│ Gap Heatmap (D3.js)          │ │ Process Timeline (D3 Gantt)    │
│ 25-cell colored grid         │ │ Horizontal stage bars          │
│ per candidate                │ │ SLA breach = red               │
└──────────────────────────────┘ └────────────────────────────────┘
```

## File Structure

```
src/
  succession/
    scoring_engine.py          (existing)
    compensation_engine.py     (NEW — Req 1,2,3)
    risk_analyzer.py           (NEW — Req 4,5,6,7,8)
    readiness_analyzer.py      (NEW — Req 9,10,11)
    process_tracker.py         (NEW — Req 12)
  frontend/
    succession-dashboard.html  (MODIFY — add Comp & Risk tab, Req 16)
    succession-cultural-profiles.js (existing)
    succession-comp-data.js    (NEW — lookup tables, Req 1,2)

scripts/
    succession_comp_risk_server.py  (NEW — HTTP API, port 8090)
    succession_live_research.py     (MODIFY — add comp enrichment, Req 15)

migrations/
    succession_comp_schema.sql      (NEW — tables for Req 14)
```

## Key Design Decisions

1. **Lookup tables as static JSON** — For the demo, comp data is pre-computed from public benchmarks (Radford, Glassdoor, Levels.fyi aggregates). In production, this would be a paid data feed from Mercer/Radford/McLagan.

2. **Separate HTTP server (port 8090)** — Keeps comp/risk analysis decoupled from the research agent (port 8089). The dashboard calls both.

3. **Append-only compensation history** — Every estimate is stored as a new row (never overwritten), enabling trend analysis and audit compliance.

4. **Cultural risk uses existing CULTURAL_PROFILES** — No new data source needed; we compute Euclidean Hofstede distance from the already-loaded profiles.

5. **Process tracker is client-side first** — For the demo, stage state lives in localStorage (like transactions). The Aurora table design is ready for when we connect to the live database.

6. **All risk scores are deterministic** — No AI calls for risk scoring (pure formula-based from inputs). AI is only used for enrichment (Req 15) when lookup confidence is LOW.

## Traceability

| Requirement | Component | File |
|-------------|-----------|------|
| R1, R2, R3 | Compensation_Engine | compensation_engine.py, succession-comp-data.js |
| R4, R5 | Risk_Analyzer.flight/poach | risk_analyzer.py |
| R6 | Risk_Analyzer.cultural | risk_analyzer.py, succession-cultural-profiles.js |
| R7 | Risk_Analyzer.compliance | risk_analyzer.py, succession_live_research.py |
| R8 | Risk_Analyzer.notice | risk_analyzer.py, succession-comp-data.js |
| R9, R10, R11 | Readiness_Analyzer | readiness_analyzer.py |
| R12, R13 | Process_Tracker | process_tracker.py, succession-dashboard.html |
| R14 | Aurora persistence | succession_comp_schema.sql |
| R15 | AI enrichment | succession_live_research.py |
| R16 | Dashboard integration | succession-dashboard.html |


## Components and Interfaces

### CompensationEngine Interface

```python
class CompensationEngine:
    def compute_total_comp(self, candidate: dict, lookup: dict) -> CompEstimate
    def compute_market_range(self, role: dict, lookup: dict) -> MarketRange
    def compute_comp_gap(self, candidate_comp: float, role_p50: float) -> CompGap
    def enrich_from_web(self, candidate: dict, search_client, bedrock_client) -> CompEstimate
```

**CompEstimate** dataclass: `base, bonus, equity, benefits, allowances, total, currency, confidence, source`
**MarketRange** dataclass: `p25, p50, p75, sector, country, role_type`
**CompGap** dataclass: `amount, percentage, label, cost_prohibitive`

### RiskAnalyzer Interface

```python
class RiskAnalyzer:
    def compute_flight_risk(self, candidate: dict) -> RiskScore
    def compute_poachability(self, candidate: dict, comp_gap: CompGap) -> RiskScore
    def compute_cultural_risk(self, origin_country: str, target_country: str, profiles: dict) -> CulturalRisk
    def compute_compliance_risk(self, candidate: dict, signals: list) -> ComplianceRisk
    def estimate_notice_period(self, country: str, seniority: str) -> NoticePeriod
```

**RiskScore** dataclass: `score (0-100), tier (LOW/MEDIUM/HIGH), factors: list[str]`
**CulturalRisk** dataclass: `level (LOW/MEDIUM/HIGH/CRITICAL), distance: float, dimension_gaps: list[str]`
**ComplianceRisk** dataclass: `sanctions (CLEAR-CRITICAL), reputational (CLEAR-CRITICAL), sources: list[str]`
**NoticePeriod** dataclass: `notice_months, non_compete_months, earliest_available_months, enforceable: bool, confidence`

### ReadinessAnalyzer Interface

```python
class ReadinessAnalyzer:
    def compute_gap_heatmap(self, candidate_scores: dict, role_requirements: dict) -> list[GapCell]
    def compute_time_to_readiness(self, gaps: list[GapCell]) -> ReadinessEstimate
    def compute_development_cost(self, gaps: list[GapCell], ttr_months: int) -> float
    def compute_roi(self, role_annual_value: float, acquisition_cost: float, dev_cost: float) -> ROIEstimate
```

**GapCell** dataclass: `criterion_id, candidate_score, requirement, gap, category (EXCEEDS/MEETS/DEVELOPMENT_NEEDED/CRITICAL_GAP)`
**ReadinessEstimate** dataclass: `months, category (READY_NOW/NEAR_READY/DEVELOPING/LONG_TERM/BEYOND_HORIZON)`
**ROIEstimate** dataclass: `percentage, breakeven_months, is_negative`

### ProcessTracker Interface

```python
class ProcessTracker:
    def advance_stage(self, candidate_id: str, new_stage: str, user: str, note: str) -> StageTransition
    def get_current_stage(self, candidate_id: str) -> StageInfo
    def check_sla(self, candidate_id: str) -> SLAStatus
    def get_timeline(self, transaction_id: str) -> list[StageTransition]
```

**StageTransition** dataclass: `candidate_id, stage, entered_at, exited_at, user, note`
**SLAStatus** dataclass: `stage, days_in_stage, sla_days, is_breach`

### HTTP API (port 8090) Interface

All endpoints accept JSON POST body and return JSON response. CORS headers included for dashboard access.

Request/Response pattern:
```json
// POST /analyze-all
// Request:
{
  "candidates": [...],
  "target_role": { "sector": "PRIVATE", "country": "IR", "role_type": "VP", "seniority": "VP" },
  "transaction_id": "txn-12345"
}
// Response:
{
  "results": [
    {
      "candidate_id": "...",
      "compensation": { "total": 1200000, "gap": -200000, "gap_pct": -14.3, "label": "BELOW_MARKET" },
      "risk": { "flight": 42, "poachability": 65, "cultural": "MEDIUM", "compliance": "CLEAR" },
      "readiness": { "fit_pct": 76, "ttr_months": 6, "category": "NEAR_READY", "dev_cost": 75000 },
      "process": { "stage": "SCREEN", "days_in_stage": 5, "sla_breach": false }
    }
  ]
}
```

## Correctness Properties

### Property 1: Comp total equals sum of parts
Total_Compensation MUST equal base + bonus + equity + benefits + allowances (±$1 rounding).
**Validates: Requirement 1.1**

### Property 2: Gap sign matches label
Comp_Gap sign MUST match label: positive → PREMIUM_REQUIRED, negative → BELOW_MARKET.
**Validates: Requirement 3.2, 3.3**

### Property 3: Risk score bounds
All risk scores (flight_risk, poachability) MUST be in [0, 100] inclusive.
**Validates: Requirement 4.1, 5.1**

### Property 4: Cultural distance symmetry
Hofstede distance(A→B) MUST equal distance(B→A).
**Validates: Requirement 6.2**

### Property 5: TTR non-negative
Time-to-readiness MUST be ≥ 0 months.
**Validates: Requirement 10.1**

### Property 6: TTR monotonicity
More gaps or larger gaps MUST produce equal or higher TTR.
**Validates: Requirement 10.2**

### Property 7: Stage ordering enforcement
Process stages MUST advance in defined order; backward transitions are not permitted.
**Validates: Requirement 12.1**

### Property 8: SLA breach correctness
is_breach MUST be true if and only if days_in_stage > sla_days for that stage.
**Validates: Requirement 12.4**

### Property 9: Append-only history
Compensation estimates are never overwritten; new estimates append with incremented timestamps.
**Validates: Requirement 14.3**

### Property 10: Confidence degradation
Fallback estimates MUST have lower confidence than direct-match estimates.
**Validates: Requirement 1.5**

## Error Handling

| Scenario | Handler | Recovery |
|----------|---------|----------|
| Lookup table miss (no sector/country/seniority match) | CompensationEngine._nearest_fallback() | Find nearest seniority match in same country; flag confidence=LOW |
| Brave Search API failure during enrichment | Research_Agent retry with exponential backoff (max 2 retries) | Return original LOW-confidence estimate |
| Bedrock invocation timeout | 60s timeout, catch exception | Skip enrichment, log warning, retain existing estimate |
| Invalid candidate scores (out of 1-10 range) | Clamp to [1, 10] before gap computation | Log warning with candidate_id |
| Hofstede data missing for country | Default to nearest GLOBE cluster average | Flag cultural_risk confidence=LOW |
| Process stage advance to invalid/backward stage | Reject with 400 error, log attempt | Return error message explaining valid next stages |
| SLA computation with missing entered_at | Use current timestamp as fallback | Flag stage entry as "RECONSTRUCTED" |
| Division by zero in comp gap (role P50 = 0) | Return gap=0, pct=0, label="NO_MARKET_DATA" | Log warning |

## Testing Strategy

### Unit Tests (pytest)

1. **CompensationEngine tests** — Verify total comp calculation for known lookup entries; verify fallback behavior; verify gap labels and percentages.
2. **RiskAnalyzer tests** — Verify flight risk formula with known inputs; verify cultural distance computation (Anglo↔Middle_East ≈ 75); verify non-compete lookup for US-CA vs US-NY.
3. **ReadinessAnalyzer tests** — Verify gap categorization (score 10 vs requirement 7 → EXCEEDS); verify TTR with concurrency factor; verify development cost sums.
4. **ProcessTracker tests** — Verify stage ordering enforcement; verify SLA breach detection at boundary (day 14 for LONG_LIST); verify backward transition rejection.

### Integration Tests

1. **End-to-end analyze-all** — Submit 3 mock candidates + role config to /analyze-all, verify all fields populated.
2. **Dashboard rendering** — Load succession-dashboard.html, switch to Comp & Risk tab, verify D3.js renders gap heatmap with correct colors.
3. **Cultural risk with real profiles** — Compute Anglo_US → Middle_East_IR distance using actual Hofstede values from succession-cultural-profiles.js.

### Property-Based Tests (Hypothesis)

1. **Comp total consistency** — For any random base/bonus/equity/benefits, total == sum.
2. **Risk score bounds** — For any random candidate inputs, 0 ≤ score ≤ 100.
3. **Gap categorization exhaustiveness** — Every gap value maps to exactly one category.
4. **TTR concurrency** — TTR with concurrency factor ≤ TTR without (factor reduces total).
