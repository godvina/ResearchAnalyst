# Implementation Plan: Prosecutor Case Review

## Overview

Incremental implementation of the Prosecutor Case Review module — 5 backend services, 9 Aurora tables, 5 Lambda handlers, 24 correctness properties. Covers AI-first case analysis with Senior Legal Analyst Persona, three-state human-in-the-loop decision workflow, element-by-element evidence mapping, case weakness detection, and precedent analysis. Python codebase with Hypothesis for property-based testing. Each task builds on previous steps, wiring components together progressively. Uses existing Aurora/Neptune/OpenSearch/Bedrock infrastructure.

## Tasks

- [x] 1. Create Aurora database schema and Pydantic models
  - [x] 1.1 Create Aurora migration script for all 9 prosecutor tables
    - Create `src/db/migrations/002_prosecutor_case_review.sql` with all 9 tables: `statutes`, `statutory_elements`, `case_statutes`, `element_assessments`, `charging_decisions`, `case_weaknesses`, `precedent_cases`, `ai_decisions`, `ai_decision_audit_log`
    - Include all CHECK constraints, UNIQUE constraints, foreign keys, and indexes per design
    - `ai_decisions.state` CHECK IN ('ai_proposed', 'human_confirmed', 'human_overridden')
    - `ai_decisions.confidence` CHECK IN ('high', 'medium', 'low')
    - `ai_decisions.decision_type` for 'statute_recommendation', 'element_rating', 'charging_recommendation', 'evidence_mapping'
    - `ai_decision_audit_log` references `ai_decisions(decision_id)` ON DELETE CASCADE
    - _Requirements: 1.1, 1.4, 2.1, 3.1, 4.6, 5.1, 12.1, 12.4_

  - [x] 1.2 Implement Pydantic models in `src/models/prosecutor.py`
    - Create enums: `SupportRating`, `ConfidenceLevel`, `DecisionState`, `WeaknessSeverity`, `WeaknessType`, `RulingOutcome`
    - Create models: `Statute`, `StatutoryElement`, `ElementRating`, `EvidenceMatrix`, `ReadinessScore`, `CaseWeakness`, `PrecedentMatch`, `RulingDistribution`, `SentencingAdvisory`, `AlternativeCharge`, `ChargingMemo`, `StatuteRecommendation`, `ElementMapping`, `ChargingRecommendation`, `AIDecision`, `DecisionAuditEntry`, `CaseAnalysisResult`
    - All Field constraints (ge, le) and Optional fields per design
    - `ElementRating` includes `legal_justification`, `decision_id`, `decision_state` fields
    - `AIDecision` includes full state tracking fields (confirmed_at/by, overridden_at/by, override_rationale)
    - _Requirements: 1.1, 1.4, 2.3, 2.6, 3.5, 4.6, 5.3, 5.4, 11.1, 11.5, 12.1_

  - [ ]* 1.3 Write property tests for prosecutor model validation
    - **Property 3: Element assessment output domain** — for any valid input triple, rating must be in {green, yellow, red}, confidence in [0, 100], reasoning non-empty
    - **Validates: Requirements 2.3, 8.1**
    - **Property 9: Weakness severity and linkage invariant** — severity in {critical, warning, info}, at least one affected element or evidence
    - **Validates: Requirements 4.6, 4.7**
    - **Property 11: Critical weakness requires remediation** — if severity=critical, remediation must be non-empty
    - **Validates: Requirements 10.5**
    - **Property 18: AI recommendation confidence domain** — confidence in {high, medium, low}, non-empty legal_reasoning or justification
    - **Validates: Requirements 11.5, 2.7**
    - **Property 19: Decision state domain invariant** — state in {ai_proposed, human_confirmed, human_overridden}, new decisions start as ai_proposed
    - **Validates: Requirements 12.1, 2.8, 3.7**

- [x] 2. Implement statute library seed data and retrieval
  - [x] 2.1 Create statute seed data script
    - Create `src/db/seeds/seed_statutes.py` with the 6 required statutes and their statutory elements: 18 U.S.C. § 1591, § 1341, § 1343, § 2241, § 1951, § 846
    - Each statute includes ordered elements with display_name and description of what must be proven
    - _Requirements: 1.2, 1.3_

  - [ ]* 2.2 Write property test for statute storage round-trip
    - **Property 1: Statute storage round-trip** — storing a statute with N elements and retrieving by statute_id returns same citation, title, and exactly N elements
    - **Validates: Requirements 1.1, 1.3, 1.4**

- [x] 3. Implement DecisionWorkflowService
  - [x] 3.1 Implement `src/services/decision_workflow_service.py`
    - Constructor with `aurora_cm` injection (no Bedrock dependency — purely Aurora CRUD)
    - Implement `create_decision(case_id, decision_type, recommendation_text, legal_reasoning, confidence, source_service)` → `AIDecision`: INSERT into `ai_decisions` with state=ai_proposed, INSERT initial audit log entry with actor='system'
    - Implement `confirm_decision(decision_id, attorney_id)` → `AIDecision`: UPDATE state to human_confirmed, set confirmed_at/confirmed_by, INSERT audit log entry
    - Implement `override_decision(decision_id, attorney_id, override_rationale)` → `AIDecision`: validate non-empty override_rationale, UPDATE state to human_overridden, set overridden_at/overridden_by/override_rationale, INSERT audit log entry
    - Implement `get_decision(decision_id)` → `AIDecision`: single decision retrieval
    - Implement `get_case_decisions(case_id, decision_type=None, state=None)` → `list[AIDecision]`: filtered listing
    - Implement `get_decision_history(decision_id)` → `list[DecisionAuditEntry]`: chronological audit trail ordered by created_at ASC
    - Handle conflict: return 409 if decision already confirmed/overridden
    - Handle validation: return 400 if override_rationale is empty on override
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.7_

  - [ ]* 3.2 Write property tests for DecisionWorkflowService
    - **Property 20: Decision confirmation and override invariants** — confirmed has non-null timestamp+attorney; overridden has non-null timestamp+attorney+rationale
    - **Validates: Requirements 12.2, 12.3**
    - **Property 21: Decision audit trail round-trip** — store and retrieve returns same recommendation_text, legal_reasoning, state, timestamps, attorney identities
    - **Validates: Requirements 12.4**
    - **Property 22: Decision history chronological ordering** — audit entries in ascending created_at order, count = state transitions + 1
    - **Validates: Requirements 12.7**

  - [ ]* 3.3 Write unit tests for DecisionWorkflowService
    - Create `tests/unit/test_decision_workflow_service.py`
    - Test confirm workflow: create AI_Proposed → confirm → verify state=human_confirmed with timestamp and attorney
    - Test override requires rationale: attempt override with empty rationale → 400 error
    - Test override workflow: create AI_Proposed → override with rationale → verify state=human_overridden
    - Test already confirmed: attempt to confirm already-confirmed decision → 409 conflict
    - Test decision history completeness: create → confirm → verify 2 audit entries in order
    - _Requirements: 12.2, 12.3, 12.7_

- [x] 4. Checkpoint — Verify schema, models, and decision workflow
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement ElementAssessmentService
  - [x] 5.1 Implement `src/services/element_assessment_service.py`
    - Define `SENIOR_LEGAL_ANALYST_PERSONA` class constant with AUSA system prompt per design
    - Constructor with `aurora_cm`, `neptune_cm`, `bedrock_client`, optional `search_fn` injection
    - Implement `assess_elements(case_id, statute_id)` → `EvidenceMatrix`: fetch statutory elements from Aurora, fetch case evidence from Aurora+Neptune, call Bedrock with Senior_Legal_Analyst_Persona for each element-evidence pair, each rating includes legal_justification and starts as AI_Proposed via DecisionWorkflowService
    - Implement `assess_single(case_id, element_id, evidence_id)` → `ElementRating`: single pair assessment via Bedrock with legal reasoning
    - Implement `compute_readiness_score(case_id, statute_id)` → `ReadinessScore`: calculate `round((green + yellow) / total_elements * 100)`, return covered count, missing element names, formatted citation
    - Implement `suggest_alternative_charges(case_id, statute_id)` → `list[AlternativeCharge]`: when primary charge has red elements, use Bedrock to suggest up to 5 alternatives sorted by estimated_conviction_likelihood descending
    - Implement `recommend_statutes(case_id)` → `list[StatuteRecommendation]`: auto-recommend applicable statutes ranked by evidence match strength, include justification and rejected_alternatives explaining why other statutes were not recommended
    - Implement `auto_categorize_evidence(case_id, evidence_id, statute_id)` → `list[ElementMapping]`: auto-map new evidence to most relevant statutory elements with justification citing evidentiary basis and confidence level
    - Implement `draft_charging_recommendation(case_id, statute_id)` → `ChargingRecommendation`: draft initial charging recommendation with full legal reasoning, precedent citations, and sentencing guideline references when readiness ≥ 70%
    - Reuse claim decomposition pattern from `hypothesis_testing_service.py` — each statutory element as a testable claim
    - Bedrock fallback: return `rating=yellow, confidence=0, reasoning="AI analysis unavailable"` when Bedrock is down; auto-analysis skips statute recommendations and returns empty results with warning
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 2.8, 3.3, 3.6, 8.1, 8.2, 8.3, 8.4, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [ ]* 5.2 Write property tests for ElementAssessmentService
    - **Property 2: Evidence matrix dimensions** — for E elements and D evidence items, matrix has E×D rating cells
    - **Validates: Requirements 2.1**
    - **Property 4: Readiness score formula** — score equals round((G+Y)/T × 100)
    - **Validates: Requirements 2.6**
    - **Property 5: Manual evidence link updates assessment** — after adding a link, matrix contains new (element_id, evidence_id) pair
    - **Validates: Requirements 2.5**
    - **Property 7: Alternative charges bounded and sorted** — at most 5 items, sorted by likelihood descending
    - **Validates: Requirements 3.3**
    - **Property 14: Readiness message format** — message matches "You have N/M elements covered for § C. Missing: [elem1], [elem2]" with exactly (M-N) missing names
    - **Validates: Requirements 6.3**
    - **Property 15: Auto-statute recommendation ranking and justification** — non-empty list sorted by match_strength descending, each has justification, confidence, and rejected_alternatives
    - **Validates: Requirements 11.1, 11.6**
    - **Property 16: Auto-evidence categorization produces valid mappings** — at least one ElementMapping with valid element_id, non-empty justification, confidence in {high, medium, low}
    - **Validates: Requirements 11.2**
    - **Property 17: Charging recommendation threshold trigger** — when readiness ≥ 70%, returns ChargingRecommendation with non-empty recommendation_text, legal_reasoning, and at least one sentencing_guideline_refs entry
    - **Validates: Requirements 3.6, 11.3**

  - [ ]* 5.3 Write unit tests for ElementAssessmentService
    - Create `tests/unit/test_element_assessment_service.py`
    - Test Bedrock fallback returns yellow/0/unavailable
    - Test empty case returns all-red matrix
    - Test manual evidence link triggers re-assessment
    - Test Senior Legal Analyst Persona system prompt is included in Bedrock calls
    - Test auto-analysis on case load returns statute recommendations with AI_Proposed decisions
    - _Requirements: 8.4, 2.5, 11.1, 11.4_

- [x] 6. Implement CaseWeaknessService
  - [x] 6.1 Implement `src/services/case_weakness_service.py`
    - Constructor with `aurora_cm`, `neptune_cm`, `bedrock_client` injection
    - Implement `analyze_weaknesses(case_id, statute_id)` → `list[CaseWeakness]`: orchestrates all four detection methods
    - Implement `detect_conflicting_statements(case_id)`: query Aurora documents and Neptune entity relationships for same-witness contradictions, cite Crawford v. Washington for confrontation clause implications
    - Implement `detect_missing_corroboration(case_id, statute_id)`: query element_assessments for elements with only one green/yellow evidence source
    - Implement `detect_suppression_risks(case_id)`: use Bedrock to flag Fourth Amendment issues, cite Mapp v. Ohio and exclusionary rule precedent
    - Implement `detect_brady_material(case_id)`: use Bedrock to scan for exculpatory evidence, cite Brady v. Maryland and Giglio v. United States
    - Each weakness includes `legal_reasoning` with case law citations appropriate to weakness_type
    - Assign severity (critical/warning/info) and link to affected elements and evidence
    - Critical weaknesses must include remediation text
    - Bedrock fallback: skip suppression_risk and brady_material checks, return only deterministic weaknesses; legal reasoning citations omitted
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 6.2 Write property tests for CaseWeaknessService
    - **Property 10: Missing corroboration detection** — element with exactly one green/yellow source flagged as missing_corroboration
    - **Validates: Requirements 4.3, 10.2**
    - **Property 23: Weakness legal citations present** — legal_reasoning non-empty and contains at least one case law citation appropriate to weakness_type (Brady v. Maryland, Mapp v. Ohio, or Crawford v. Washington)
    - **Validates: Requirements 4.8**

  - [ ]* 6.3 Write unit tests for CaseWeaknessService
    - Create `tests/unit/test_case_weakness_service.py`
    - Test conflicting statement detection with two contradictory documents for same witness
    - Test Bedrock fallback skips AI-dependent checks
    - Test critical weakness includes remediation
    - Test Brady material weakness contains "Brady v. Maryland" in legal_reasoning
    - Test suppression risk weakness contains "Mapp v. Ohio" in legal_reasoning
    - _Requirements: 4.2, 4.8, 10.1, 10.5_

- [x] 7. Implement PrecedentAnalysisService
  - [x] 7.1 Implement `src/services/precedent_analysis_service.py`
    - Constructor with `aurora_cm`, `neptune_cm`, `bedrock_client`, optional `opensearch_client` injection
    - Implement `find_precedents(case_id, charge_type, top_k=10)` → `list[PrecedentMatch]`: combine Neptune entity similarity (0.3), OpenSearch semantic similarity (0.3), charge type match (0.2), defendant profile match (0.2) into composite score
    - Extend `cross_case_service.py` entity matching with charge type matching via `case_statutes` table
    - OpenSearch fallback: use Neptune-only similarity when OpenSearch unavailable
    - _Requirements: 5.1, 5.2, 5.3, 9.1, 9.2_

  - [x] 7.2 Implement `compute_ruling_distribution(matches)` → `RulingDistribution`
    - Compute outcome percentages across matched precedents, summing to 100
    - _Requirements: 5.4_

  - [x] 7.3 Implement `generate_sentencing_advisory(case_id, matches)` → `SentencingAdvisory`
    - Use Bedrock with Senior_Legal_Analyst_Persona to generate likely sentence, fine/penalty, supervised release
    - Advisory must cite specific precedent cases by name and reference federal sentencing guideline sections (e.g., USSG §2B1.1)
    - Include disclaimer when fewer than 3 matches above similarity 50
    - _Requirements: 5.5, 9.3, 9.4_

  - [ ]* 7.4 Write property tests for PrecedentAnalysisService
    - **Property 12: Precedent search result bounds and score range** — at most 10 matches, each similarity_score in [0, 100]
    - **Validates: Requirements 5.1, 5.3**
    - **Property 13: Ruling distribution sums to 100** — percentages sum to 100 (±1 tolerance)
    - **Validates: Requirements 5.4**
    - **Property 24: Sentencing advisory cites precedent and guidelines** — advisory text contains at least one precedent case name and at least one "USSG §" or "U.S.S.G. §" reference
    - **Validates: Requirements 5.5**

  - [ ]* 7.5 Write unit tests for PrecedentAnalysisService
    - Create `tests/unit/test_precedent_analysis_service.py`
    - Test limited precedent disclaimer when < 3 matches above 50
    - Test OpenSearch fallback to Neptune-only similarity
    - Test sentencing advisory with 5 precedent matches contains at least one case_reference and "USSG §"
    - _Requirements: 9.4, 5.5_

- [x] 8. Checkpoint — Verify all four services
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement AIFirstAnalysisEngine
  - [x] 9.1 Implement `src/services/ai_first_analysis_engine.py`
    - Constructor with `element_assessment_svc`, `case_weakness_svc`, `decision_workflow_svc`, `bedrock_client` injection
    - Implement `auto_analyze(case_id)` → `CaseAnalysisResult`: orchestrate full auto-analysis on case load:
      1. Call `element_assessment_svc.recommend_statutes(case_id)` for ranked statute recommendations
      2. For each top recommended statute, call `element_assessment_svc.assess_elements(case_id, statute_id)` to auto-map evidence to elements
      3. Call `case_weakness_svc.analyze_weaknesses(case_id)` for weakness detection
      4. If readiness ≥ 70% for any statute, call `element_assessment_svc.draft_charging_recommendation(case_id, statute_id)`
      5. Each recommendation creates an AI_Proposed decision via `decision_workflow_svc.create_decision()`
    - Implement `on_evidence_added(case_id, evidence_id)` → `list[ElementMapping]`: auto-categorize new evidence against selected statutes, create AI_Proposed decisions for each new mapping
    - Bedrock fallback: fall back to deterministic-only analysis (no statute recommendations, no charging drafts), return partial results with `warnings` field
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 12.1_

  - [ ]* 9.2 Write unit tests for AIFirstAnalysisEngine
    - Create `tests/unit/test_ai_first_analysis_engine.py`
    - Test auto_analyze returns statute recommendations and element mappings with AI_Proposed decisions
    - Test on_evidence_added creates AI_Proposed decisions for new mappings
    - Test Bedrock fallback returns partial results with warnings
    - _Requirements: 11.1, 11.2_

- [x] 10. Implement Lambda handlers
  - [x] 10.1 Implement `src/lambdas/api/element_assessment.py`
    - `dispatch_handler(event, context)` routing GET and POST for `/case-files/{id}/element-assessment`
    - GET: return existing evidence matrix for case+statute (statute_id as query param)
    - POST: trigger new element assessment for case+statute
    - `_build_element_assessment_service()` with dependency injection
    - CORS preflight via OPTIONS
    - Use `response_helper.success_response` / `error_response`
    - _Requirements: 8.5, 2.1_

  - [x] 10.2 Implement `src/lambdas/api/precedent_analysis.py`
    - `dispatch_handler(event, context)` routing POST for `/case-files/{id}/precedent-analysis`
    - POST: run precedent analysis with charge_type from request body
    - _Requirements: 9.5_

  - [x] 10.3 Implement `src/lambdas/api/case_weakness.py`
    - `dispatch_handler(event, context)` routing GET for `/case-files/{id}/case-weaknesses`
    - GET: return weakness analysis for case, optional statute_id query param
    - _Requirements: 10.6_

  - [x] 10.4 Implement `src/lambdas/api/statutes.py`
    - `dispatch_handler(event, context)` routing GET for `/statutes` and `/statutes/{id}`
    - GET /statutes: list all statutes
    - GET /statutes/{id}: get statute with elements
    - Direct Aurora queries (no service layer needed)
    - _Requirements: 1.1, 1.3_

  - [x] 10.5 Implement `src/lambdas/api/decision_workflow.py`
    - `dispatch_handler(event, context)` routing for decision workflow routes:
      - POST `/decisions/{id}/confirm`: confirm an AI_Proposed decision (requires attorney_id in body)
      - POST `/decisions/{id}/override`: override an AI_Proposed decision (requires attorney_id and override_rationale in body)
      - GET `/case-files/{id}/decisions`: list all decisions for a case (optional decision_type and state query params)
    - `_build_decision_workflow_service()` with dependency injection
    - CORS preflight via OPTIONS
    - _Requirements: 12.1, 12.2, 12.3, 12.7_

  - [ ]* 10.6 Write unit tests for Lambda handlers
    - Create `tests/unit/test_prosecutor_handlers.py`
    - Test dispatch routing for each HTTP method/resource combination across all 5 handlers
    - Test CORS preflight returns correct headers
    - Test 400 for missing case_id, 404 for case/statute not found
    - Test decision_workflow handler: 400 for override without rationale, 409 for already-confirmed decision
    - _Requirements: 8.5, 12.3_

- [x] 11. Add API Gateway route definitions
  - [x] 11.1 Add routes to `infra/api_gateway/api_definition.yaml`
    - Add paths: `/statutes`, `/statutes/{id}`, `/case-files/{id}/element-assessment`, `/case-files/{id}/precedent-analysis`, `/case-files/{id}/case-weaknesses`, `/case-files/{id}/charging-memo`, `/decisions/{id}/confirm`, `/decisions/{id}/override`, `/case-files/{id}/decisions`
    - Include Lambda integrations and CORS configuration
    - Decision routes: `/decisions/{id}/confirm` (POST), `/decisions/{id}/override` (POST with required override_rationale), `/case-files/{id}/decisions` (GET with optional decision_type and state query params)
    - _Requirements: 8.5, 9.5, 10.6, 12.1_

- [x] 12. Implement charging decision and memo features
  - [x] 12.1 Add charging decision CRUD and memo generation
    - Add POST `/case-files/{id}/charging-memo` to element_assessment handler: generate charging memo via Bedrock with Senior_Legal_Analyst_Persona
    - Store/retrieve charging decisions in Aurora `charging_decisions` table
    - AI-drafted charging recommendations appear as AI_Proposed decisions with Accept/Override workflow
    - _Requirements: 3.1, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 12.2 Write property tests for charging features
    - **Property 6: Charging decision round-trip** — store and retrieve returns same charge, rationale, approving attorney, notes
    - **Validates: Requirements 3.1, 3.4**
    - **Property 8: Charging memo contains all required sections** — non-empty case_summary, selected_charges, evidence_mapping_summary, risk_assessment, rationale, approving_attorney
    - **Validates: Requirements 3.5**

- [x] 13. Checkpoint — Verify all handlers and API routes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Implement prosecutor frontend page
  - [x] 14.1 Create `src/frontend/prosecutor.html`
    - Case sidebar listing cases via `/case-files` API
    - Tabbed navigation: Evidence Matrix | Charging Decisions | Case Weaknesses | Precedent Analysis
    - Evidence Matrix tab: grid with element rows, evidence columns, color-coded cells (green/yellow/red), readiness score bar, expandable "Legal Reasoning" section per rating, color-coded decision state badges (yellow=AI_Proposed, green=Human_Confirmed, blue=Human_Overridden), Accept and Override buttons per rating
    - Charging Decisions tab: charge annotations, risk flags (Brady, suppression), alternative charge suggestions, memo export button, AI-drafted charging recommendations as AI_Proposed cards with Accept/Override workflow, expandable Legal Reasoning sections citing precedent and sentencing guidelines
    - Case Weaknesses tab: weakness cards with severity badges (Critical/Warning/Info), linked evidence and elements, "Legal Basis" section citing relevant case law per weakness
    - Precedent Analysis tab: precedent cards with similarity scores, ruling distribution bars, sentencing advisory panel citing specific precedent cases and USSG sections (reuse `doj-case-analysis.html` layout)
    - Orange accent color (#f6ad55) to distinguish from investigator (green #48bb78)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 2.4, 2.7, 2.8, 3.2, 3.7, 5.6, 12.5, 12.6_

  - [x] 14.2 Add Investigator Readiness Widget to `src/frontend/investigator.html`
    - Collapsible panel showing per-statute readiness score (percentage bar)
    - Element coverage message: "You have N/M elements covered for § XXXX. Missing: [element1], [element2]"
    - Auto-refresh polling every 30 seconds via `/case-files/{id}/element-assessment` API
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 15. Implement Streamlit app routing for prosecutor page
  - [x] 15.1 Register prosecutor page in `src/frontend/app.py`
    - Add prosecutor.html to the Streamlit navigation/sidebar
    - Wire API client calls for all prosecutor endpoints including decision workflow routes
    - _Requirements: 7.1_

- [x] 16. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate all 24 universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All services follow the existing Protocol/constructor-injection pattern
- Task order: schema → models → DecisionWorkflowService → ElementAssessmentService → CaseWeaknessService → PrecedentAnalysisService → AIFirstAnalysisEngine → Lambda handlers → API routes → frontend → integration
- Senior_Legal_Analyst_Persona system prompt used in all Bedrock calls across ElementAssessmentService, CaseWeaknessService, PrecedentAnalysisService, and AIFirstAnalysisEngine
- Three-state decision workflow (AI_Proposed → Human_Confirmed / Human_Overridden) applies to statute recommendations, element ratings, evidence mappings, and charging recommendations
