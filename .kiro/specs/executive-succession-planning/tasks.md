# Implementation Plan: Executive Succession Planning Module

## Overview

This plan implements an AI-driven Executive Succession Planning module deployed within the existing Research Analyst platform, sharing Neptune, OpenSearch, Aurora PostgreSQL, Amazon Bedrock, and the Tiered Pipeline. The module adds domain-specific scoring algorithms, cultural calibration, government/military overlays, scenario modeling, and a succession dashboard — all leveraging existing shared infrastructure. TypeScript/Node.js for Lambda services, React/Next.js for frontend, Python for data processing scripts, Jest + fast-check for property-based testing.

## Tasks

### Phase 1: Schema + Scoring Engine Core (the algorithm foundation)

- [ ] 1. Aurora schema creation (succession.* tables)
  - [ ] 1.1 Create migration script `migrations/succession_schema.sql`
    - Create schema `succession` with tables: `role_configurations`, `scoring_decisions`, `human_overrides`, `assessment_ingestions`, `consent_records`, `data_rights_requests`, `bias_reports`, `confirmation_pipeline`, `saved_scenarios`, `tenants`
    - All tables include `tenant_id UUID NOT NULL` column with RLS policy `tenant_id = current_setting('app.current_tenant')::uuid`
    - Add CHECK constraints: composite_score BETWEEN 0 AND 100, criterion scores BETWEEN 1 AND 10
    - Add indexes on tenant_id, candidate_id, role_config_id, created_at
    - _Requirements: R12.7, R13.3_

  - [ ] 1.2 Create `succession.role_configurations` table
    - Columns: id UUID PK, tenant_id, sector ENUM('PRIVATE','GOVERNMENT','MILITARY'), country VARCHAR(2) ISO 3166-1, role_type VARCHAR, context ENUM('baseline','crisis','growth'), universal_core JSONB, cultural_flex JSONB, sector_params JSONB, created_at, updated_at
    - Constraint: max 50 custom configs per tenant (enforced via trigger)
    - Index: UNIQUE(tenant_id, sector, country, role_type, context)
    - _Requirements: R2.1, R2.6_

  - [ ] 1.3 Create `succession.scoring_decisions` audit table
    - Columns: id UUID PK, tenant_id, candidate_id, role_config_id FK, composite_score NUMERIC(5,2), layer_breakdown JSONB, criterion_scores JSONB, master_variable_scores JSONB, threshold_violations JSONB, weights_applied JSONB, model_version VARCHAR, below_minimum BOOLEAN, created_at TIMESTAMPTZ
    - Retention policy: 5-year minimum (partitioned by created_at quarter)
    - RLS policy on tenant_id
    - _Requirements: R10.2, R10.6, R17.5_

  - [ ] 1.4 Create `succession.human_overrides` table
    - Columns: id UUID PK, tenant_id, scoring_decision_id FK, candidate_id, action ENUM('ADVANCE','ELIMINATE','HOLD','OVERRIDE_SCORE'), rationale TEXT NOT NULL, overridden_by UUID (Cognito user), authenticated_at TIMESTAMPTZ, created_at
    - EU AI Act Article 14 compliance: no auto-advance/auto-eliminate code paths
    - _Requirements: R10.7, R17.2_

  - [ ] 1.5 Create remaining succession tables
    - `succession.assessment_ingestions`: platform, scores JSONB, mapped_criteria JSONB, staleness_flag BOOLEAN, ingested_at, expires_at (24-month)
    - `succession.consent_records`: candidate_id, purpose, regulation, consent_given BOOLEAN, timestamp, withdrawn_at
    - `succession.data_rights_requests`: candidate_id, request_type ENUM('ERASURE','ACCESS','OPT_OUT'), regulation, received_at, deadline_at, completed_at, status
    - `succession.bias_reports`: report_id, tenant_id, generated_at, four_fifths_results JSONB, chi_squared_results JSONB, flagged BOOLEAN
    - `succession.confirmation_pipeline`: candidate_id, stage ENUM('FBI_CHECK','IRS_REVIEW','OGE_DISCLOSURE','COMMITTEE_HEARING','FLOOR_VOTE'), entered_at, days_elapsed INT
    - `succession.saved_scenarios`: tenant_id, name, weight_overrides JSONB, result_rankings JSONB, created_by, created_at
    - _Requirements: R7.3, R9.6, R10.3, R17.1, R17.4, R17.6_

- [ ] 2. Neptune node/edge type additions
  - [ ] 2.1 Add succession node types to existing Neptune instance
    - Node labels: `Executive`, `CompetencyScore`, `RoleConfig`, `Assessment`, `CulturalContext`, `DevelopmentPlan`
    - ID prefix convention: `succession:{tenant_id}:person:{uuid}`, `succession:{tenant_id}:role:{uuid}`
    - Properties: all nodes include `tenant_id`, `domain: "succession"`, `created_at`, `source_provenance` (JSONB)
    - _Requirements: R12.1, R12.4, R12.8_

  - [ ] 2.2 Add succession edge types to Neptune
    - `HELD_ROLE`: startDate, endDate, tenure_months, performanceRating (1-10), isRotational, isPnLResponsibility, isCrossFunctional
    - `DEMONSTRATES`: score (1-10), assessmentSource, assessedAt, confidence (0-1)
    - `CONNECTED_TO`: relationshipType ENUM, strength (0-1), recency, decayedWeight (half-life 3 years)
    - `ASSESSED_BY`: scores JSONB, mappedCriteria JSONB, assessmentDate
    - `SUCCEEDS`: readinessLevel ENUM('emergency','accelerated','planned'), readinessScore (0-100), assignedAt, lastEvaluated
    - `SCORED_FOR`: roleConfigId, compositeScore, timestamp
    - _Requirements: R12.2, R18.1_

  - [ ] 2.3 Create Neptune Gremlin query templates for succession traversals
    - 3-degree relationship path traversal (< 2s for 1M nodes)
    - Shared connections between candidate and target org leadership
    - Career trajectory path queries (Person → Position → Organization with timestamps)
    - Network centrality computation (degree + betweenness)
    - _Requirements: R12.3, R18.2, R18.4_

- [ ] 3. OpenSearch new indices
  - [ ] 3.1 Create `succession-candidates-{tenant_id}` index template
    - 1536-dim kNN vector field (HNSW engine, cosinesimil space type)
    - Metadata fields: candidate_id, name, current_title, current_org, sector, country, seniority_level, source_provenance
    - Tenant isolation: index-per-tenant pattern with IAM policies restricting cross-index access
    - _Requirements: R12.6, R13.3_

  - [ ] 3.2 Create `succession-role-signatures` index
    - 1536-dim kNN vector field for role competency requirement vectors
    - Fields: role_config_id, sector, country, role_type, signature_text, embedding
    - Used for passive candidate identification (cosine similarity ≥ 0.75 threshold)
    - _Requirements: R5.5, R12.6_

  - [ ] 3.3 Configure index settings and mappings
    - HNSW parameters: ef_construction=512, m=16 (matching existing Research Analyst config)
    - Refresh interval: 1s for real-time search
    - Replica count: 1 (matches existing cluster)
    - k-NN search: minimum threshold 0.70 for qualification, 0.75 for passive candidate identification
    - _Requirements: R5.5, R12.6_

- [ ] 4. Scoring Engine implementation
  - [ ] 4.1 Implement `ScoringEngine` Lambda handler (`src/succession/scoring-engine/handler.ts`)
    - Entry point for AppSync resolver: `computeScore`, `computeBatchScores`, `rankCandidates`
    - Load role configuration from Aurora `succession.role_configurations`
    - Retrieve candidate criterion scores from Neptune `DEMONSTRATES` edges
    - Return `ScoringResult` with compositeScore, layerBreakdown, criterionScores, thresholdViolations
    - _Requirements: R1.1, R1.4, R1.5_

  - [ ] 4.2 Implement three-layer weight computation
    - Layer 1 (Universal Core): Base weights from `role_configurations.universal_core` JSONB
    - Layer 2 (Cultural Flex): Adjustments from Cultural Calibration Module (Phase 2)
    - Layer 3 (Sector Parameters): Adjustments from `role_configurations.sector_params` JSONB
    - Combined weight: w_i = Layer1_weight + Layer2_adjustment + Layer3_adjustment
    - _Requirements: R1.1, R1.6, R1.8_

  - [ ] 4.3 Implement weight normalization
    - After combining all three layers: normalize so Σ(w_i) = 1.0 (±0.0001)
    - Each w_i must be > 0 after normalization
    - Formula: w_i_normalized = w_i / Σ(all_w)
    - _Requirements: R1.1 — Property 1: Weight Normalization_

  - [ ] 4.4 Implement threshold enforcement
    - Universal Core attributes: Strategic Vision, Integrity, Cognitive Ability, Resilience, Results Orientation
    - If any core attribute score < configured minimum → candidate flagged `below_minimum: true`, excluded from ranked output
    - Cultural/sector adjustments CANNOT lower a core attribute below its threshold floor
    - _Requirements: R1.2, R1.3 — Property 2: Threshold Enforcement, Property 3: Threshold Floor Protection_

  - [ ] 4.5 Implement composite score computation
    - Score = Σ(w_i × s_i) where s_i ∈ [1, 10] integer, composite normalized to [0, 100]
    - Normalization: composite = (raw_sum / max_possible_raw_sum) × 100
    - _Requirements: R1.1, R1.4, R1.5 — Property 4: Score Range_

  - [ ] 4.6 Implement ranked output with tiebreaker
    - Sort candidates descending by composite score
    - Tiebreaker: highest Universal Core attribute score
    - Exclude all candidates with `below_minimum: true`
    - _Requirements: R1.7 — Property 5: Ranked Output Ordering_

  - [ ] 4.7 Implement scoring audit trail persistence
    - Write every scoring decision to `succession.scoring_decisions` with full breakdown
    - Include: input data snapshot, weights applied, model version, timestamp
    - 5-year retention enforcement
    - _Requirements: R10.2, R10.6, R17.2_

- [ ] 5. Unit tests for scoring correctness properties (fast-check)
  - [ ]* 5.1 Property test: Weight Normalization (Property 1)
    - For any valid role configuration with random weights, verify Σ(w_i) = 1.0 (±0.0001) and all w_i > 0
    - Generator: random arrays of 15-25 positive floats for Layer 1/2/3 weights
    - Assert: Math.abs(sum - 1.0) < 0.0001 && weights.every(w => w > 0)
    - _Requirements: R1.1_

  - [ ]* 5.2 Property test: Threshold Enforcement (Property 2)
    - For any candidate with at least one Universal Core attribute below minimum, verify exclusion from ranked output
    - Generator: random candidate scores [1-10] × 25 criteria, random thresholds [3-8] for 5 core attributes
    - Assert: if any core score < threshold → candidate not in ranked list regardless of composite
    - _Requirements: R1.2, R2.3_

  - [ ]* 5.3 Property test: Threshold Floor Protection (Property 3)
    - For any Flex/Sector adjustment, no core attribute weight falls below configured minimum floor
    - Generator: random base weights, random cultural adjustments [-0.15, +0.15], random sector adjustments
    - Assert: adjusted core weights ≥ floor for all core attributes
    - _Requirements: R1.3, R6.5_

  - [ ]* 5.4 Property test: Score Range (Property 4)
    - For any candidate, criterion scores ∈ [1, 10] integers; composite ∈ [0, 100]
    - Generator: random integer arrays [1-10] length 25, random valid weight profiles
    - Assert: composite >= 0 && composite <= 100 && all criteria in [1, 10]
    - _Requirements: R1.4, R1.5_

  - [ ]* 5.5 Property test: Ranked Output Ordering (Property 5)
    - For any set of scored candidates, output strictly descending by composite; tiebreaker = highest Universal Core attribute
    - Generator: random array of 2-50 ScoringResults with random composites [0-100]
    - Assert: for all i, ranked[i].composite >= ranked[i+1].composite; ties broken by max core
    - _Requirements: R1.7_

  - [ ]* 5.6 Property test: Context Modifier Bounds (Property 6)
    - For any crisis/growth application, target variables increase ≥2 points capped at 10; all weights in [1, 10]
    - Generator: random baseline weights [1-10], random context ('crisis' | 'growth')
    - Assert: target vars increased by ≥2 (or capped at 10); all weights ∈ [1, 10]
    - _Requirements: R2.4, R2.5_

  - [ ]* 5.7 Property test: Tier 1 Filter Determinism (Property 7)
    - Same input always produces same pass/fail; rejects if missing ≥2 fields OR duplicate OR below director
    - Generator: random profile objects with optional missing fields, random seniority levels
    - Assert: tier1Filter(profile) === tier1Filter(profile) for same input; rejection rules hold
    - _Requirements: R5.3, R5.4_

  - [ ] 5.8 Unit tests for composite score calculation correctness
    - Known-value tests: hand-computed scores for specific weight/score combinations
    - Edge cases: all minimum scores (1), all maximum scores (10), single criterion
    - Boundary: weights summing to exactly 1.0 before normalization
    - _Requirements: R1.1, R1.4_

### Phase 2: Role Configuration + Cultural Calibration (parameter matrices)

- [ ] 6. Role Configuration Engine
  - [ ] 6.1 Implement `RoleConfigurationEngine` Lambda (`src/succession/role-config/handler.ts`)
    - `getConfiguration(sector, country, role)` → lookup from consolidated parameter matrix
    - `applyContextOverride(configId, 'crisis' | 'growth')` → apply predefined weight shifts
    - `saveCustomConfig(orgId, config)` → persist with max-50-per-tenant validation
    - `validateOverride(configId, overrides)` → reject if any Universal Core threshold would be violated
    - Auto-apply within 3 seconds of selection
    - _Requirements: R2.1, R2.3, R2.6, R2.7_

  - [ ] 6.2 Implement consolidated parameter matrix data store
    - 15 Master Variables × 3 Sectors × 16 Countries = weight lookup table
    - Store as `succession.parameter_matrix` or seed JSONB in `role_configurations`
    - Variables: Strategic Vision, Profit/Value Orientation, Political Savvy, Innovation Tolerance, Stakeholder Consensus, Relationship Networks, Hierarchical Respect, Physical Fitness, Exam/Test Rigor, Cultural/Faith Ethics, Resilience, Mission Execution, Chain of Command, Coalition Building, Emotional Intelligence
    - Each weight on 1-10 scale per context
    - _Requirements: R1.5, R2.1_

  - [ ] 6.3 Implement supported role types
    - Private: CEO, CFO, CIO, CTO, COO, CRO, Chief AI Officer
    - Government: Cabinet Secretary positions (15), SES positions
    - Military: Brigade Commander and above
    - Validation: reject unsupported sector-country-role combinations with error message
    - _Requirements: R2.2, R2.7_

  - [ ] 6.4 Implement crisis/growth context modifiers
    - Crisis: Resilience +2, Change Leadership +2, Mission Execution +2 (capped at 10)
    - Growth: Strategic Vision +2, Innovation Tolerance +2, Market Understanding +2 (capped at 10)
    - Baseline: no modifiers applied
    - Enforce: all resulting weights remain in [1, 10]
    - _Requirements: R2.4, R2.5 — Property 6: Context Modifier Bounds_

  - [ ] 6.5 Implement custom configuration persistence
    - Save up to 50 custom configs per organization
    - Retain until explicitly deleted
    - UPSERT logic: if same sector+country+role+context exists, update; else insert (check limit)
    - _Requirements: R2.6_

- [ ] 7. Cultural Calibration Module
  - [ ] 7.1 Implement `CulturalCalibrationModule` Lambda (`src/succession/cultural-calibration/handler.ts`)
    - `getGlobeCluster(country)` → map 16 countries to 10 GLOBE clusters
    - `computeFlexWeights(country, baseWeights)` → apply GLOBE + Hofstede adjustments
    - `getLoyaltyCompetenceRatio(searchId)` / `setLoyaltyCompetenceRatio(searchId, ratio)`
    - `computeCrossCulturalAgility(candidateId, targetClusters)` → score 0-100
    - `checkNationalizationCompliance(slate, country)` → compliance result
    - _Requirements: R6.1, R6.2, R6.4, R6.7, R6.8_

  - [ ] 7.2 Implement GLOBE cluster mapping and Flex_Weight calculation
    - 10 GLOBE clusters: Anglo, Latin Europe, Nordic Europe, Germanic Europe, Eastern Europe, Latin America, Sub-Saharan Africa, Middle East, Southern Asia, Confucian Asia
    - Flex_Weight adjustments range: [0.7, 1.3] relative to baseline 1.0
    - Middle Eastern contexts (SA, UAE, QA, EG): Relationship Networks, Power Distance, Faith/Ethics get 1.15-1.3
    - _Requirements: R6.1, R6.3 — Property 9: Cultural Flex Bounds_

  - [ ] 7.3 Implement Hofstede dimension modifiers
    - 6 dimensions: Power Distance, Individualism, Uncertainty Avoidance, Masculinity, Long-Term Orientation, Indulgence
    - Each dimension contributes modifier in [-0.15, +0.15] to applicable Layer 2 attribute weights
    - Lookup table: country → dimension scores → modifier computation
    - _Requirements: R6.2 — Property 9: Cultural Flex Bounds_

  - [ ] 7.4 Implement loyalty-competence ratio
    - Configurable per search, default 0.5 (equal weighting)
    - Range: [0.1, 0.9]
    - Display current ratio transparently before scoring begins
    - Affects relative weight between loyalty-related criteria and competence-related criteria
    - _Requirements: R6.4_

  - [ ] 7.5 Implement wasta scoring for Middle Eastern contexts
    - Integrate with Neptune relationship graph for tribal/family network strength
    - Score on 0.0-1.0 scale, feeds into Cultural Calibration adjustments
    - Only applied when target role context is Middle Eastern
    - _Requirements: R6.3, R18.3_

  - [ ] 7.6 Implement nationalization compliance tracking
    - Saudization percentage monitoring at C-suite tier
    - Emiratisation targets tracking
    - Flag slates that don't meet mandated national representation levels
    - Display compliance warning with shortfall percentage and applicable regulation
    - _Requirements: R6.7_

  - [ ] 7.7 Implement cross-cultural agility scoring
    - Score 0-100 based on: prior multi-cluster experience, language capabilities, demonstrated adaptability
    - Triggered when candidate considered for assignment spanning 2+ GLOBE clusters
    - Query Neptune for candidate's prior roles across different cluster countries
    - _Requirements: R6.8_

  - [ ]* 7.8 Property test: Cultural Flex Bounds (Property 9)
    - For any country, GLOBE adjustments ∈ [0.7, 1.3]; Hofstede modifiers ∈ [-0.15, +0.15]; loyalty-competence ratio ∈ [0.1, 0.9]
    - Generator: random country from supported list, random base weights [1-10]
    - Assert: all flex adjustments within bounds; ratio clamped to [0.1, 0.9]
    - _Requirements: R6.1, R6.2, R6.4_

  - [ ] 7.9 Implement Universal Core threshold preservation under cultural adjustment
    - When Flex_Weight would cause core attribute to drop below floor → cap adjustment
    - Include notification of which attributes were capped
    - _Requirements: R6.5, R6.6 — Property 3: Threshold Floor Protection_

### Phase 3: Pipeline Dashboard + Internal Candidates (the UI)

- [ ] 8. Pipeline Dashboard Service
  - [ ] 8.1 Implement `PipelineDashboardService` Lambda (`src/succession/pipeline-dashboard/handler.ts`)
    - `getHeatMap(orgId)` → succession heat map with color-coded strength per role
    - `getScenarioLists(roleId)` → three-scenario lists (emergency/accelerated/planned)
    - `getReadinessScore(candidateId, roleId)` → 9-box + algorithm composite → 0-100
    - `triggerReEvaluation(candidateId)` → re-score within 24h of data update
    - `getGapAnalysis(candidateId, roleId)` → competency gaps for target role
    - _Requirements: R3.4, R3.5, R3.6, R3.7, R19.1_

  - [ ] 8.2 Implement three-scenario list management
    - Emergency: ready within 48 hours (Ready Now)
    - Accelerated: developable in 6-12 months
    - Planned: multi-year development track
    - Minimum target: 1 candidate per scenario per critical role
    - Classification based on readiness score ranges and gap analysis
    - _Requirements: R3.5, R3.9_

  - [ ] 8.3 Implement readiness scoring (9-box + algorithm composite)
    - Combine traditional 9-box grid position with Scoring Engine composite score
    - Unified readiness score: 0-100 numeric scale
    - Display alongside scenario assignment
    - Weight formula: configurable blend of performance (9-box) and potential (algorithm)
    - _Requirements: R3.7_

  - [ ]* 8.4 Property test: Heat Map Categorization (Property 10)
    - For any critical role, categories are mutually exclusive: Strong (3+ Ready Now) | Adequate (1-2 Ready Now) | Weak (development only) | Empty (none)
    - Generator: random number of candidates [0-10] with random readiness levels
    - Assert: exactly one category per role; category logic matches candidate counts
    - _Requirements: R3.6, R19.1_

- [ ] 9. HRIS integration connectors
  - [ ] 9.1 Implement Workday connector (`src/succession/connectors/workday.ts`)
    - Ingest: performance reviews, tenure, role history, compensation, 9-box grid positions
    - Confirm sync: display timestamp of most recent completed ingestion
    - Error handling: retry 3x, log failure, mark incomplete
    - _Requirements: R3.1_

  - [ ] 9.2 Implement SAP SuccessFactors connector (`src/succession/connectors/sap-sf.ts`)
    - Same data scope as Workday: performance, tenure, role history, compensation, 9-box
    - OAuth2 authentication, paginated API retrieval
    - _Requirements: R3.1_

  - [ ] 9.3 Implement Oracle HCM connector (`src/succession/connectors/oracle-hcm.ts`)
    - Same data scope as above
    - REST API integration with Oracle HCM Cloud
    - _Requirements: R3.1_

  - [ ] 9.4 Implement 360° feedback data ingestion
    - Map behavioral indicators to 25 criteria (≥90% mapping coverage)
    - Support multiple feedback cycles; aggregate trend scores (min 3 cycles, 12 months)
    - _Requirements: R3.2, R9.4_

- [ ] 10. Heat map visualization and alerts
  - [ ] 10.1 Implement heat map data computation
    - Color-coded pipeline strength per critical role
    - Strong (green): 3+ Ready Now candidates
    - Adequate (amber): 1-2 Ready Now candidates
    - Weak (orange): candidates only in Accelerated/Planned
    - Empty (red): no candidates in any scenario
    - Drill-down: click cell → view three-scenario lists for that role
    - _Requirements: R3.6, R19.1, R19.2_

  - [ ] 10.2 Implement alert system for readiness threshold crossings
    - When candidate crosses configured readiness threshold → alert within 4 hours
    - When role drops from Strong/Adequate to Weak/Empty → alert within 24 hours
    - Alert to designated succession sponsor
    - Include: affected role, previous/new strength level, triggering event
    - _Requirements: R3.8, R3.9, R19.3_

  - [ ] 10.3 Implement aggregate organizational readiness metrics
    - Percentage of critical roles with at least one Ready Now candidate
    - Average pipeline depth (mean candidate count across all three scenarios)
    - Display on CEO dashboard landing page
    - Data reflects all changes through end of previous business day
    - _Requirements: R19.4, R19.5_

- [ ] 11. Development gap analysis and planning
  - [ ] 11.1 Implement gap analysis engine
    - For Accelerated/Planned candidates: identify every criterion below target role threshold
    - Display: candidate current score vs. required threshold per gap variable
    - Identify no false positives: criteria at or above threshold are NOT flagged
    - _Requirements: R14.1 — Property 19: Gap Analysis Accuracy_

  - [ ] 11.2 Implement development plan generation
    - 1-5 developmental experiences per gap (rotational assignments, stretch projects, mentoring, external programs)
    - Ranked by relevance using CAPER career pattern data
    - Re-score within 24h of milestone completion
    - _Requirements: R14.2, R14.3_

  - [ ] 11.3 Implement time-to-readiness estimation
    - Expressed in calendar months
    - Calculated from: total gap magnitude + median historical development velocity (same sector, 5-year lookback)
    - Low confidence flag if < 10 historical patterns match
    - _Requirements: R14.4, R14.5_

  - [ ] 11.4 Implement development plan progress tracking
    - Percentage: completed milestones / total assigned milestones
    - Update on each milestone status change
    - Trigger re-evaluation when milestone completed
    - _Requirements: R14.6_

  - [ ]* 11.5 Property test: Gap Analysis Accuracy (Property 19)
    - For any candidate on Accelerated/Planned list: identifies every criterion where score < threshold AND none where score ≥ threshold
    - Generator: random candidate scores [1-10] × 25 criteria, random thresholds [3-8]
    - Assert: gaps = {c | score[c] < threshold[c]}; no false positives or negatives
    - _Requirements: R14.1_

### Phase 4: External Sourcing + Tiered Pipeline Config

- [ ] 12. Market Intelligence Service
  - [ ] 12.1 Implement `MarketIntelligenceService` Lambda (`src/succession/market-intelligence/handler.ts`)
    - `sourceExternalCandidates(roleConfigId, countries)` → trigger sourcing job
    - `getPassiveCandidates(roleConfigId, threshold?)` → passive candidates above similarity threshold
    - `getMarketAlerts(orgId, since)` → market movement alerts
    - `getCompensationBenchmark(role, country, sector)` → comp data
    - `configureMonitoring(config)` → set up real-time monitoring rules
    - _Requirements: R5.1, R5.5, R5.6, R5.7, R16.1_

  - [ ] 12.2 Implement Tiered Pipeline configuration for succession domain
    - Tier 1 keywords: executive titles, board positions, C-suite, director+, sector terms
    - Tier 1 rejection rules: missing ≥2 required fields, duplicate (name+org match), below director seniority
    - Tier 2 signatures: leadership competency embeddings from role-signatures index
    - Tier 3 prompts: domain-specific entity extraction (competencies, relationships, career history)
    - Same Step Functions state machine, `domain: "succession"` input parameter
    - _Requirements: R5.3, R5.4 — Property 7: Tier 1 Filter Determinism_

  - [ ] 12.3 Implement Tier 1 filter Lambda for succession domain
    - Regex/keyword scan: $0 cost
    - Reject: missing name OR current_title OR current_org OR industry (if ≥2 missing → reject)
    - Reject: duplicate detection (name + organization match against existing index)
    - Reject: seniority below director (title parsing heuristic)
    - Target: 80%+ rejection rate at Tier 1
    - _Requirements: R5.3, R5.4_

- [ ] 13. LinkedIn Talent Insights API integration
  - [ ] 13.1 Implement LinkedIn connector (`src/succession/connectors/linkedin.ts`)
    - OAuth2 authentication with LinkedIn Talent Insights API
    - Query by: sector, country, role type, seniority level
    - Return: candidate profile objects with name, title, org, industry, skills
    - Rate limiting: respect API quotas, exponential backoff
    - _Requirements: R5.1_

  - [ ] 13.2 Implement passive candidate identification
    - Passive = cosine similarity ≥ 0.75 AND no profile update 90 days AND no open-to-work AND no recent applications
    - Embed candidate profile via shared Titan endpoint
    - Compare against role competency signature vector in OpenSearch
    - _Requirements: R5.5 — Property 8: Passive Candidate Classification_

  - [ ]* 13.3 Property test: Passive Candidate Classification (Property 8)
    - For any profile: passive = similarity ≥ 0.75 AND no update 90d AND no open-to-work AND no recent apps; else not passive
    - Generator: random similarity scores [0-1], random boolean flags, random days since update [0-365]
    - Assert: classification matches all four conditions simultaneously
    - _Requirements: R5.5_

- [ ] 14. Country-specific source connectors
  - [ ] 14.1 Implement US/UK connectors
    - BoardEx, Equilar (US/UK): board membership data
    - SEC EDGAR (US): executive compensation disclosures, insider filings
    - Companies House (UK): director appointments and resignations
    - _Requirements: R5.2_

  - [ ] 14.2 Implement European connectors
    - XING, Bundesanzeiger (Germany): professional profiles, company filings
    - Societe.com (France): company officer data
    - KvK (Netherlands): chamber of commerce records
    - Bolagsverket (Sweden): company registration office
    - _Requirements: R5.2_

  - [ ] 14.3 Implement Asia-Pacific connectors
    - ACRA BizFile (Singapore): company officers
    - EDINET, BizReach (Japan): financial filings, executive profiles
    - Maimai, Qichacha/Tianyancha (China): professional network, company data
    - DART (South Korea): corporate disclosure system
    - MCA, NSE/BSE filings (India): ministry of corporate affairs
    - _Requirements: R5.2_

  - [ ] 14.4 Implement Middle East connectors
    - GulfTalent (Saudi Arabia, UAE, Qatar): executive profiles
    - Tadawul (Saudi Arabia): stock exchange filings
    - IVC Research Center, TASE (Israel): company and market data
    - EGX filings (Egypt): stock exchange corporate data
    - IranTalent (Iran): professional profiles
    - _Requirements: R5.2_

  - [ ] 14.5 Implement source unavailability handling
    - Circuit breaker: 3 consecutive failures → OPEN → 300s cooldown → HALF_OPEN → probe
    - Log failure, skip source for current cycle
    - Indicate unavailable sources in results summary
    - _Requirements: R5.8, R16.3_

- [ ] 15. Compensation benchmarking and market monitoring
  - [ ] 15.1 Implement compensation benchmarking service
    - Data by: role type, geography (country), sector
    - Include: base salary range, total compensation range, equity/LTI indicators
    - Source from public filings and market data providers
    - _Requirements: R5.7_

  - [ ] 15.2 Implement real-time market monitoring and alerts
    - Scan configured sources: minimum daily for public filings, real-time for webhook-capable APIs
    - Process through Tiered Pipeline (Tier 1 keyword filter rejects irrelevant before paid processing)
    - Detect: executive movements, board appointments, role changes
    - Alert within 4 hours of published change (24 hours for general market movements)
    - _Requirements: R5.6, R16.1, R16.2_

  - [ ] 15.3 Implement competitor bench strength tracking
    - Monitor publicly available appointment/departure data
    - Track filled vs. vacant leadership positions (C-suite + direct reports)
    - Update within 24 hours of detected change
    - _Requirements: R16.4_

  - [ ] 15.4 Implement career trajectory-based transition prediction
    - Identify candidates likely to transition within 6-18 months
    - Based on: role tenure, promotion velocity, lateral move frequency (CAPER patterns)
    - Confidence threshold: ≥ 0.6 to surface prediction
    - _Requirements: R16.5_

  - [ ]* 15.5 Property test: Provenance Gate (Property 18)
    - For any record submission, rejected without all three tier-completion flags + source metadata
    - Generator: random records with random subsets of tier flags and metadata fields
    - Assert: record accepted only if all three tier flags TRUE and source metadata present
    - _Requirements: R12.4, R12.5_

### Phase 5: Government + Military Overlays

- [ ] 16. ECQ Overlay (US Federal Government)
  - [ ] 16.1 Implement `ECQOverlay` scoring module (`src/succession/gov-overlays/ecq.ts`)
    - 5 OPM Executive Core Qualifications (January 2025 update):
      - Leading Change, Leading People, Results Driven, Business Acumen, Building Coalitions
    - Score: 0-100 per category, 0-100 aggregate weighted score
    - Applied in addition to standard three-layer scoring for SES positions
    - _Requirements: R7.1, R7.6_

  - [ ] 16.2 Implement inter-agency multiplier
    - If target role = inter-agency coordination → Building Coalitions weighted at exactly 1.5x
    - All other four categories at 1.0x
    - All ECQ scores remain in [0, 100]
    - _Requirements: R7.2 — Property 22: ECQ Multiplier_

  - [ ]* 16.3 Property test: ECQ Multiplier (Property 22)
    - For any inter-agency role, Building Coalitions at exactly 1.5x; all ECQ scores ∈ [0, 100]
    - Generator: random ECQ scores [0-100] × 5 categories, random inter-agency boolean
    - Assert: if inter-agency → BC weight = 1.5x others; all scores in range
    - _Requirements: R7.1, R7.2_

  - [ ] 16.4 Implement Senate confirmation pipeline tracking
    - Stages: FBI background check → IRS tax review → OGE financial disclosure → Committee hearing → Floor vote
    - Display: current stage, date entered, days elapsed per stage
    - Advance candidate when cleared from one stage to next; record transition date
    - _Requirements: R7.3, R7.4_

  - [ ] 16.5 Implement Cabinet Secretary competency profiles
    - 15 Cabinet Secretary positions with configurable competency sets
    - Each: 3-10 domain expertise competencies + minimum required ECQ category scores
    - Validation: reject profiles with < 3 or > 10 competencies
    - _Requirements: R7.5_

- [ ] 17. CAP 10-point Assessment (Military)
  - [ ] 17.1 Implement `CAPAssessment` module (`src/succession/gov-overlays/cap.ts`)
    - 10 assessment points: cognitive testing, non-cognitive/personality, peer evaluation, physical fitness, writing samples, verbal communication, psychometric assessment, behavioral psychologist interview, senior officer panel interview, 360° feedback
    - Require score on ALL 10 points before composite scoring
    - If incomplete → display "assessment incomplete" with missing components listed
    - _Requirements: R8.1, R8.6_

  - [ ] 17.2 Implement physical fitness pass/fail gate
    - Physical fitness = pass/fail (not graded)
    - If fail → block composite score calculation, flag "ineligible for ranking"
    - Must record passing result before any ranking
    - _Requirements: R8.2 — Property 12: CAP Completeness Gate_

  - [ ]* 17.3 Property test: CAP Completeness Gate (Property 12)
    - For any military candidate: <10 assessment points OR physical fitness fail → excluded from ranked lists
    - Generator: random subsets of 10 assessment points (0-10 completed), random fitness pass/fail
    - Assert: excluded if count < 10 OR fitness = fail; included only if count = 10 AND fitness = pass
    - _Requirements: R8.1, R8.2, R8.6_

  - [ ] 17.4 Implement Goldwater-Nichols joint qualification tracking
    - Stages: JPME Phase I complete → JPME Phase II complete → Joint Duty Assignment in progress → Joint Qualified Officer
    - Display current stage + remaining requirements for general/flag grade promotion
    - _Requirements: R8.3_

  - [ ] 17.5 Implement MSAF subordinate ratings
    - Minimum 3 subordinate respondents
    - Feedback within preceding 12 months
    - Scored component within military candidate profile
    - _Requirements: R8.4_

  - [ ] 17.6 Implement military weight multipliers
    - Chain of Command adherence: ≥ 2x private sector weight
    - Mission Execution track record: ≥ 2x private sector weight
    - Combat Performance history: ≥ 2x private sector weight
    - Enforce minimum multiplier in role configuration validation
    - _Requirements: R8.5 — Property 13: Military Weight Multiplier_

  - [ ]* 17.7 Property test: Military Weight Multiplier (Property 13)
    - For any military config: Chain of Command, Mission Execution, Combat Performance each ≥ 2x their private sector weight
    - Generator: random private sector weights [1-10] for the 3 variables, random military multipliers [1-5]
    - Assert: military_weight >= 2 * private_weight for all three variables
    - _Requirements: R8.5_

- [ ] 18. International Government Frameworks
  - [ ] 18.1 Implement UK Success Profiles overlay
    - 5 elements: Ability, Behaviours, Experience, Strengths, Technical
    - Each scored independently on 1-10 scale
    - Applied as Layer 3 modifier for UK Civil Service senior appointments
    - _Requirements: R15.1, R15.5_

  - [ ] 18.2 Implement Singapore PSC pipeline modeling
    - Track through 3+ sequential evaluation stages
    - Psychometric assessment: ≥ 200 items aligned to ministerial potential criteria
    - Meritocratic ranking at each stage
    - _Requirements: R15.2_

  - [ ] 18.3 Implement France INSP/concours scoring
    - Competitive ranking against examination-based criteria
    - Concours score integration for senior public administration
    - _Requirements: R15.3_

  - [ ] 18.4 Implement Germany Staatssekretär qualification tracking
    - Formal qualification verification
    - Configurable coalition-alignment score (party-political fit)
    - _Requirements: R15.4_

  - [ ] 18.5 Implement international framework selection UI
    - Present list of supported frameworks during government sector search configuration
    - Identify each by country + framework name
    - Flag incomplete assessment data for national frameworks
    - _Requirements: R15.6, R15.7_

### Phase 6: Scenario Modeling + Explainability + Compliance

- [ ] 19. Scenario Model (what-if simulations)
  - [ ] 19.1 Implement `ScenarioModel` service (`src/succession/scenario-model/handler.ts`)
    - Weight modification → recalculate rankings within 3 seconds
    - Non-persisted: changes do not affect production configuration
    - Save named scenarios for later retrieval
    - Export shareable scenario reports
    - _Requirements: R11.1, R11.7_

  - [ ] 19.2 Implement crisis-vs-growth toggle
    - Apply predefined weight shifts for crisis context (Resilience, Change Leadership, Mission Execution ↑)
    - Apply predefined weight shifts for growth context (Strategic Vision, Innovation Tolerance, Market Understanding ↑)
    - Display side-by-side candidate rankings for each context
    - _Requirements: R11.2_

  - [ ] 19.3 Implement multi-successor comparison
    - Up to 5 candidates side-by-side
    - Score breakdowns across all 25 criteria
    - Visual diff: highlight where candidates diverge most
    - _Requirements: R11.3_

  - [ ] 19.4 Implement historical pattern matching
    - Compare current candidates against leaders who held similar roles (same sector/culture, 3+ years)
    - Similarity score: 0-100 per matched pattern
    - Query Neptune for historical career trajectories
    - _Requirements: R11.4_

  - [ ] 19.5 Implement ranking shift explanation
    - When top-3 changes vs. production → highlight specific weight changes causing shift
    - Order by magnitude of impact
    - Threshold warning: if override violates Universal Core → display warning, enforce constraint
    - _Requirements: R11.5, R11.6_

- [ ] 20. Explainability Engine
  - [ ] 20.1 Implement `ExplainabilityEngine` service (`src/succession/explainability/handler.ts`)
    - SHAP/LIME attribution for each scoring decision
    - Top 5 positive factors + top 5 negative factors (percentage contribution each)
    - Layer contribution breakdown: Universal Core %, Cultural Flex %, Sector Parameters %
    - Response within 5 seconds of request
    - _Requirements: R10.1, R10.5_

  - [ ] 20.2 Implement explanation consistency validation
    - Layer contributions must sum to composite score
    - Percentages must sum to 100%
    - Exactly 5 positive + 5 negative factors per explanation
    - _Requirements: R10.1, R10.5 — Property 15: Explanation Consistency_

  - [ ]* 20.3 Property test: Explanation Consistency (Property 15)
    - For any scoring result: layer contributions sum to composite; percentages sum to 100%; exactly 5+5 factors
    - Generator: random scoring results with random layer breakdowns
    - Assert: sum(layer_contributions) ≈ composite (±0.01); sum(percentages) = 100%; factor count = 10
    - _Requirements: R10.1, R10.5_

  - [ ] 20.4 Implement EU AI Act Article 12 record-keeping
    - Log: algorithmic scoring decisions, data inputs, model versions, transparency disclosures, human override actions
    - 10-year retention from date of each decision
    - Conformity assessment documentation maintenance
    - _Requirements: R10.6, R17.2_

- [ ] 21. Bias Detection Dashboard
  - [ ] 21.1 Implement `BiasDetectionDashboard` service (`src/succession/bias-detection/handler.ts`)
    - Monitor outcomes across: gender, age, nationality, ethnicity, educational background
    - Four-fifths rule: flag if any group's selection rate < 80% of highest group
    - Chi-squared test: flag if p-value < 0.05
    - Generate report within 30 seconds
    - _Requirements: R10.3, R10.4_

  - [ ] 21.2 Implement bias alert system
    - When disparity exceeds threshold → alert compliance officers within 24 hours
    - Report: slate composition % breakdowns vs. available talent pool demographics
    - Store in `succession.bias_reports`
    - _Requirements: R10.8_

  - [ ]* 21.3 Property test: Four-Fifths Rule (Property 14)
    - For any slate: flag when any protected group selection rate < 80% of highest group OR chi-squared p < 0.05
    - Generator: random slate compositions with random group sizes and selection counts
    - Assert: flag set correctly per four-fifths calculation; chi-squared computed correctly
    - _Requirements: R10.3_

  - [ ] 21.4 Implement human-in-the-loop gate
    - No code path auto-advances or auto-eliminates final-stage candidates
    - Require authenticated human confirmation (Cognito user) via explicit approval action
    - Record in `succession.human_overrides` with rationale
    - _Requirements: R10.7 — Property 16: Human-in-the-Loop Gate_

  - [ ]* 21.5 Property test: Human-in-the-Loop Gate (Property 16)
    - For any final-stage candidate: no code path auto-advances or auto-eliminates without authenticated human confirmation
    - Generator: random candidate states (final-stage true/false), random action attempts (advance/eliminate)
    - Assert: if final_stage AND no human_confirmation → action blocked
    - _Requirements: R10.7_

- [ ] 22. GDPR/CCPA consent management and compliance
  - [ ] 22.1 Implement consent-before-ingestion gate
    - Before any candidate data enters Neptune/OpenSearch/Aurora → verify consent record exists with earlier timestamp
    - Reject ingestion if consent not recorded; return consent-required error
    - Record: purpose, regulation, consent timestamp
    - _Requirements: R17.1 — Property 21: Consent-Before-Ingestion_

  - [ ]* 22.2 Property test: Consent-Before-Ingestion (Property 21)
    - For any candidate data in any store: consent record with earlier timestamp must exist
    - Generator: random candidate records with random consent timestamps (before/after/missing)
    - Assert: data accepted only if consent_timestamp < ingestion_timestamp; rejected otherwise
    - _Requirements: R17.1_

  - [ ] 22.3 Implement right to erasure (GDPR Article 17)
    - Remove all PII from Neptune, OpenSearch, and Aurora within 30 calendar days
    - Preserve anonymized aggregate data (< 5 quasi-identifiers cannot re-identify)
    - Log in compliance audit trail
    - _Requirements: R17.6_

  - [ ] 22.4 Implement CCPA consumer data rights
    - Right to know, right to delete, right to opt-out of automated decision-making
    - Fulfill verified requests within 45 calendar days
    - Track in `succession.data_rights_requests`
    - _Requirements: R17.4_

  - [ ] 22.5 Implement data residency enforcement
    - EU candidate data → EU region
    - Saudi data → per PDPL requirements
    - Singapore data → per PDPA requirements
    - Data routing based on candidate country + applicable regulation
    - _Requirements: R17.3_

  - [ ] 22.6 Implement SOX-compliant audit trails
    - All assessment scores, ranking decisions, access logs for publicly-traded company officers
    - 7-year retention from creation date
    - Immutable audit entries (append-only)
    - _Requirements: R17.5_

  - [ ] 22.7 Implement data rights request deadline tracking
    - If request cannot be fulfilled within regulatory timeframe → notify candidate within 3 business days
    - Provide estimated completion date
    - Log exception in compliance audit trail
    - Send confirmation within 3 business days of completion
    - _Requirements: R17.7, R17.8_

- [ ] 23. Assessment Integration Hub
  - [ ] 23.1 Implement `AssessmentHub` service (`src/succession/assessment-hub/handler.ts`)
    - Connect to: SHL, Hogan, Korn Ferry, DDI via API
    - Map ingested scores to 25-criteria framework (configurable mapping schema)
    - ≥ 90% mapping coverage for ingested dimensions
    - _Requirements: R9.1, R3.2, R3.3_

  - [ ] 23.2 Implement assessment API retry logic
    - Retry up to 3 times within 60 seconds on connection failure
    - Exponential backoff: 1s/2s/4s
    - If all retries fail → log failure, mark incomplete, notify specialist
    - _Requirements: R9.2_

  - [ ] 23.3 Implement CAP-style multi-modal assessment ingestion
    - Combine: cognitive ability, personality, peer evaluation, interview data
    - Require at least 2 of 4 modalities before producing composite score
    - _Requirements: R9.3_

  - [ ] 23.4 Implement assessment staleness detection
    - Flag data older than 24 months with visual indicator
    - Send notification recommending re-assessment
    - Configurable staleness threshold per assessment type
    - _Requirements: R9.6_

  - [ ] 23.5 Implement re-scoring trigger on new assessment
    - When new result ingested → re-score candidate for all roles where they appear in succession lists
    - Complete re-score within 30 seconds of ingestion
    - Trigger AppSync subscription for real-time dashboard update
    - _Requirements: R9.5_

  - [ ] 23.6 Implement unmapped score quarantine
    - If scores cannot map to any criterion → quarantine unmapped scores
    - Log mapping failure, notify system admin for schema review
    - _Requirements: R9.7_

- [ ] 24. Career Trajectory Predictor (CAPER model)
  - [ ] 24.1 Implement `CAPERModel` service (`src/succession/caper/handler.ts`)
    - Model ternary relationships: Person × Position × Organization with date-level timestamps
    - Store in Neptune as temporal edges with start/end dates
    - Predict future positions within 1-5 year horizon
    - Confidence score: 0-1 per prediction; only surface if ≥ configurable threshold (default 0.6)
    - _Requirements: R4.1, R4.2_

  - [ ] 24.2 Implement skill adjacency computation
    - Similarity score (0-1) between candidate competencies and target role requirements
    - Rank experience gaps by relevance to target role (descending)
    - Use OpenSearch k-NN for competency vector similarity
    - _Requirements: R4.3_

  - [ ] 24.3 Implement development recommendations
    - Prioritized list: max 10 experiences/competencies needed for target readiness level
    - Categorize: rotational assignments (6+ months), cross-functional projects (2+ business functions), P&L responsibility
    - Track as predictive indicators of executive readiness
    - _Requirements: R4.4, R4.5_

  - [ ]* 24.4 Property test: CAPER Confidence Gate (Property 11)
    - Below threshold (default 0.6) → not surfaced; < 2 career transitions → no predictions
    - Generator: random confidence scores [0-1], random transition counts [0-10]
    - Assert: if confidence < 0.6 → not surfaced; if transitions < 2 → no prediction generated
    - _Requirements: R4.2, R4.6_

- [ ] 25. Relationship Network Analysis
  - [ ] 25.1 Implement `RelationshipNetworkAnalyzer` (`src/succession/network-analysis/handler.ts`)
    - Model relationships with edge properties: type, strength (0-1), recency, decayed weight
    - Time decay: weight = strength × 0.5^(years_since_interaction / 3) (half-life 3 years)
    - Centrality score: degree + betweenness, normalized to [0, 1]
    - _Requirements: R18.1, R18.2_

  - [ ] 25.2 Implement relationship type support
    - Types: board co-service, alumni, former colleagues, mentor-mentee, tribal/family, military unit, wasta
    - Israel context: 8200/IDF officer corps as professional relationship category
    - Shared connections: count and list between candidate and target org leadership
    - _Requirements: R18.3, R18.4, R18.5_

  - [ ]* 25.3 Property test: Relationship Time Decay (Property 20)
    - Weight = strength × 0.5^(years/3); centrality ∈ [0, 1]; < 3 edges → low-confidence flag
    - Generator: random strength [0-1], random years [0-20], random edge counts [0-50]
    - Assert: decay formula correct; centrality bounded; low-confidence flagged when edges < 3
    - _Requirements: R18.1, R18.2, R18.6_

  - [ ] 25.4 Implement low-confidence network handling
    - If fewer than 3 verified relationship edges → flag low-confidence
    - Indicate insufficient relationship data in assessment output
    - Exclude from network scoring (do not penalize, just mark uncertain)
    - _Requirements: R18.6_

- [ ] 26. Authentication + Multi-tenancy
  - [ ] 26.1 Extend Cognito user pool with succession-specific roles
    - Roles: Platform Administrator, Organization Administrator, Succession Planner, Board Member (read-only), External Search Consultant (limited engagement access)
    - SAML 2.0 federation for enterprise SSO
    - Custom claims: `tenantId`, `successionRole`, `clearanceLevel`
    - _Requirements: R13.1, R13.2_

  - [ ] 26.2 Implement tenant isolation enforcement
    - Aurora: RLS policy on all succession.* tables
    - Neptune: Gremlin query scoping via `has('tenant_id', tenantId)` predicate
    - OpenSearch: index-per-tenant with IAM policies
    - AppSync: resolver-level auth extracting tenantId from Cognito JWT
    - _Requirements: R13.3, R13.4_

  - [ ]* 26.3 Property test: Tenant Isolation (Property 17)
    - For any request with Tenant A credentials: zero results from Tenant B across all data stores
    - Generator: random tenant IDs (A, B), random data distribution, random query patterns
    - Assert: all results have tenant_id === requesting_tenant; never cross-tenant data
    - _Requirements: R13.3, R13.4_

  - [ ] 26.4 Implement session management and security
    - Account lockout: 5 failed logins in 15 min → lock 30 min + notify org admin
    - Session timeout: 30 min inactivity → terminate, require re-auth
    - Clearance-level permission: restrict clearance-designated candidates to authorized users only
    - Cross-tenant access attempt: deny + log + security alert
    - _Requirements: R13.1, R13.5, R13.6_

- [ ] 27. Frontend (React/Next.js on Amplify)
  - [ ] 27.1 Set up succession module in existing Amplify app
    - Add succession routes/pages to existing React/Next.js application
    - Configure AppSync GraphQL schema additions for succession queries/mutations/subscriptions
    - Responsive: 768px - 2560px viewport support, no horizontal scrolling
    - WCAG 2.1 Level AA compliance
    - _Requirements: R20.1, R20.4, R20.5_

  - [ ] 27.2 Implement AppSync GraphQL schema for succession
    - Queries: getHeatMap, getScenarioLists, getReadinessScore, getRankedCandidates, getExplanation, getScenarioSimulation, getBiasReport, getCompensationBenchmark
    - Mutations: computeScore, saveScenario, applyOverride, triggerReEvaluation, recordHumanDecision
    - Subscriptions: onScoreUpdate, onAlertTriggered, onPipelineChange
    - Real-time updates within 3 seconds of server-side change
    - _Requirements: R20.2_

  - [ ] 27.3 Implement role-based landing pages
    - Succession Planner → heat map dashboard
    - Board Member → executive summary view (read-only)
    - Search Consultant → assigned engagement workspace
    - _Requirements: R20.3_

  - [ ] 27.4 Implement heat map dashboard UI component
    - Color-coded grid: green (Strong), amber (Adequate), orange (Weak), red (Empty)
    - Click-to-drill-down into three-scenario lists per role
    - Aggregate metrics: % roles with Ready Now, average pipeline depth
    - _Requirements: R3.6, R19.1, R19.2, R19.4_

  - [ ] 27.5 Implement candidate comparison and scenario UI
    - Multi-successor comparison: up to 5 candidates side-by-side, all 25 criteria
    - Crisis-vs-growth toggle with side-by-side rankings
    - Weight adjustment sliders with real-time recalculation (< 3s)
    - Explainability panel: top 5 positive/negative factors per candidate
    - _Requirements: R11.1, R11.2, R11.3, R10.1, R10.5_

  - [ ] 27.6 Implement real-time connection handling
    - WebSocket connection status indicator
    - On disconnect: retry 12× at 5-second intervals
    - Graceful degradation: show stale data with "connection lost" banner
    - _Requirements: R20.7_

  - [ ] 27.7 Implement performance targets
    - Largest Contentful Paint: < 3s on 10Mbps connection
    - Client-side navigation between modules: < 1s
    - Lighthouse CI integration for automated performance regression detection
    - _Requirements: R20.6_

## Notes

- Tasks marked with `*` are property-based tests (PBT) using fast-check for correctness validation
- Each task references specific requirements (R1-R20) for traceability to the requirements document
- Property tests validate the 22 correctness properties defined in the design document
- The module deploys within the existing Research Analyst platform — no new Neptune/OpenSearch/Aurora instances
- Shared infrastructure: same VPC, same Cognito user pool, same AppSync endpoint, same Amplify app
- Domain isolation via: Neptune node ID prefixes (`succession:`), separate OpenSearch indices, Aurora `succession.*` schema
- Tiered Pipeline reuse: same Step Functions state machine with `domain: "succession"` parameter for different keywords/signatures/prompts
- Phase ordering enforces dependencies: schema before scoring, scoring before dashboard, dashboard before external sourcing
- Cultural Calibration (Phase 2) feeds into Scoring Engine (Phase 1) — Phase 2 extends Phase 1's scoring with Flex weights
- Government overlays (Phase 5) are composable plugins that extend the base scoring engine
- Frontend (Phase 6 task 27) depends on all backend services being complete

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "3.1", "3.2", "3.3"] },
    { "id": 2, "tasks": ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7"] },
    { "id": 3, "tasks": ["5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8"] },
    { "id": 4, "tasks": ["6.1", "6.2", "6.3", "6.4", "6.5"] },
    { "id": 5, "tasks": ["7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8", "7.9"] },
    { "id": 6, "tasks": ["8.1", "8.2", "8.3", "8.4", "9.1", "9.2", "9.3", "9.4"] },
    { "id": 7, "tasks": ["10.1", "10.2", "10.3", "11.1", "11.2", "11.3", "11.4", "11.5"] },
    { "id": 8, "tasks": ["12.1", "12.2", "12.3", "13.1", "13.2", "13.3"] },
    { "id": 9, "tasks": ["14.1", "14.2", "14.3", "14.4", "14.5", "15.1", "15.2", "15.3", "15.4", "15.5"] },
    { "id": 10, "tasks": ["16.1", "16.2", "16.3", "16.4", "16.5"] },
    { "id": 11, "tasks": ["17.1", "17.2", "17.3", "17.4", "17.5", "17.6", "17.7", "18.1", "18.2", "18.3", "18.4", "18.5"] },
    { "id": 12, "tasks": ["19.1", "19.2", "19.3", "19.4", "19.5"] },
    { "id": 13, "tasks": ["20.1", "20.2", "20.3", "20.4", "21.1", "21.2", "21.3", "21.4", "21.5"] },
    { "id": 14, "tasks": ["22.1", "22.2", "22.3", "22.4", "22.5", "22.6", "22.7"] },
    { "id": 15, "tasks": ["23.1", "23.2", "23.3", "23.4", "23.5", "23.6", "24.1", "24.2", "24.3", "24.4"] },
    { "id": 16, "tasks": ["25.1", "25.2", "25.3", "25.4", "26.1", "26.2", "26.3", "26.4"] },
    { "id": 17, "tasks": ["27.1", "27.2", "27.3", "27.4", "27.5", "27.6", "27.7"] }
  ]
}
```
