# Implementation Plan: Executive Compensation Intelligence

## Overview
This plan implements the compensation intelligence, risk analysis, readiness scoring, and process stage tracking module for the Executive Succession Planning system. Tasks are ordered by dependency — data layer first, then backend services, then API server, then dashboard integration, then tests.

## Tasks

- [x] 1. Create compensation lookup data tables
  - Create `src/frontend/succession-comp-data.js` with COMP_LOOKUP, COST_OF_LIVING_INDEX, NOTICE_PERIODS, and NON_COMPETE_ENFORCEABILITY data
  - Include entries for all countries in the cultural profiles (US, GB, IR, AE, SA, SG, CN, DE, BR, FR, JP, IN, QA)
  - Include sector variants: PRIVATE, GOVERNMENT, MILITARY × seniority levels: VP, C_SUITE, DIRECTOR
  - Include allowances (hardship, housing, schooling, security) for Middle East countries
  - Load file in succession-dashboard.html via script tag

- [x] 2. Build CompensationEngine service
  - Create `src/succession/compensation_engine.py` with CompEstimate, MarketRange, CompGap dataclasses
  - Implement `compute_total_comp()` — lookup by sector_country_seniority key, sum components, handle allowances
  - Implement `compute_market_range()` — return P25/P50/P75 for target role config
  - Implement `compute_comp_gap()` — compute gap amount, percentage, label (BELOW_MARKET/PREMIUM_REQUIRED), cost_prohibitive flag
  - Implement `_nearest_fallback()` — find nearest seniority match when exact key missing, flag LOW confidence
  - Verify Property 1 (total = sum of parts) and Property 2 (gap sign matches label)

- [x] 3. Build RiskAnalyzer service
  - Create `src/succession/risk_analyzer.py` with RiskScore, CulturalRisk, ComplianceRisk, NoticePeriod dataclasses
  - Implement `compute_flight_risk()` — weighted formula: tenure(30) + org_stability(25) + comp_trend(20) + progression(25), clamp [0,100]
  - Implement `compute_poachability()` — weighted formula: comp_gap(30) + career_stage(20) + mobility(25) + org_instability(25), clamp [0,100]
  - Implement `compute_cultural_risk()` — Euclidean Hofstede distance across 6 dimensions, classify LOW/MEDIUM/HIGH/CRITICAL
  - Implement `compute_compliance_risk()` — check signals for sanctions/controversy keywords, classify severity
  - Implement `estimate_notice_period()` — lookup country+seniority from data tables
  - Verify Property 3 (score bounds) and Property 4 (cultural distance symmetry)

- [x] 4. Build ReadinessAnalyzer service
  - Create `src/succession/readiness_analyzer.py` with GapCell, ReadinessEstimate, ROIEstimate dataclasses
  - Implement `compute_gap_heatmap()` — for each of 25 criteria, classify EXCEEDS/MEETS/DEVELOPMENT_NEEDED/CRITICAL_GAP
  - Implement `compute_time_to_readiness()` — sum gap closure using VELOCITY dict, apply 0.6 concurrency factor, cap 36 months
  - Implement `compute_development_cost()` — map gaps to cost assumptions (coaching, rotation, upskilling, board program)
  - Implement `compute_roi()` — (annual_value - acquisition - dev) / (acquisition + dev) × 100
  - Verify Property 5 (TTR non-negative) and Property 6 (TTR monotonicity)

- [x] 5. Build ProcessTracker service
  - Create `src/succession/process_tracker.py` with STAGE_ORDER, DEFAULT_SLA, StageTransition, SLAStatus
  - Implement `advance_stage()` — validate ordering (reject backward moves), record transition
  - Implement `get_current_stage()` and `check_sla()` — compute days_in_stage, detect breach
  - Implement `get_timeline()` — return all transitions for a transaction
  - Use localStorage-based state for demo; Aurora schema ready for production
  - Verify Property 7 (stage ordering) and Property 8 (SLA breach correctness)

- [x] 6. Build HTTP API server
  - Create `scripts/succession_comp_risk_server.py` — port 8090, CORS enabled
  - Implement POST `/analyze-all` — batch analysis for all candidates against target role
  - Implement individual endpoints for comp, risk, readiness, and process operations
  - Load lookup data and cultural profiles; wire to backend services
  - Add request validation and error handling per design

- [x] 7. Add Compensation & Risk dashboard tab
  - Add "💰 Comp & Risk" nav tab to succession-dashboard.html
  - Create compRiskSection with: Market Range card, Candidate Comparison Table, Gap Heatmap area, Process Timeline area
  - Implement `renderCompRiskTab()` — call `/analyze-all`, populate comparison table
  - Style with existing boardroom theme; show skeleton loading; fallback if API unavailable

- [x] 8. Build D3.js Gap Heatmap visualization
  - Implement `renderGapHeatmap(candidateId, gaps)` — 25-cell grid, colored by gap category
  - Show criterion name, score, requirement in each cell
  - Add fit percentage badge and readiness category label
  - Responsive within boardroom theme

- [x] 9. Build D3.js Process Timeline (Gantt) visualization
  - Implement `renderProcessTimeline(timelineData)` — horizontal bars per candidate
  - Color code: completed (navy), current (gold), SLA breach (red)
  - Show benchmark average line, stage labels, date scale
  - Support filtering by stage, SLA status, candidate name

- [x] 10. Create Aurora schema migration
  - Create `migrations/succession_comp_schema.sql` with compensation_estimates and process_stages tables
  - Add RLS policies, indexes, CHECK constraints per design
  - Schema-only for demo (state lives in localStorage)

- [x] 11. Write property-based tests
  - Create `tests/test_compensation_intelligence_properties.py`
  - Test Properties 1-8 using Hypothesis for randomized inputs
  - Test cultural distance symmetry with all country pair permutations
  - Test stage ordering enforcement and SLA boundary cases

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": [1, 5, 10], "description": "Data layer + independent services" },
    { "wave": 2, "tasks": [2, 3, 4], "description": "Backend engines (depend on data tables)" },
    { "wave": 3, "tasks": [6, 11], "description": "HTTP API server + property tests" },
    { "wave": 4, "tasks": [7], "description": "Dashboard Comp & Risk tab" },
    { "wave": 5, "tasks": [8, 9], "description": "D3.js visualizations" }
  ],
  "dependencies": {
    "2": [1],
    "3": [1],
    "4": [],
    "5": [],
    "6": [2, 3, 4, 5],
    "7": [6],
    "8": [7],
    "9": [7],
    "10": [],
    "11": [2, 3, 4, 5]
  }
}
```

## Notes
- The compensation lookup data uses publicly available benchmark ranges (Glassdoor, Levels.fyi, Radford survey summaries). In production, this would integrate with paid compensation data providers (Mercer, Radford, McLagan).
- The ProcessTracker uses localStorage for the demo to avoid requiring an active Aurora connection. The schema design (Task 10) is ready for production deployment.
- All risk scores are deterministic (no AI calls) for speed and auditability. AI enrichment (Req 15) is triggered only when lookup confidence is LOW.
