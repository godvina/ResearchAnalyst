# Implementation Plan: Investigator AI-First

## Overview

Incremental implementation of the Investigator AI-First module — 1 new service (InvestigatorAIEngine), extensions to 3 existing services (ChatService, HypothesisTestingService, CaseAssessmentService), 1 new Lambda handler, 4 new Aurora tables, Pydantic models, and 5 new frontend tabs. Reuses DecisionWorkflowService and ai_decisions table from prosecutor-case-review. Python codebase with Hypothesis for property-based testing. Each task builds on previous steps, wiring components together progressively. Uses existing Aurora/Neptune/OpenSearch/Bedrock infrastructure.

## Tasks

- [x] 1. Create Aurora database schema and Pydantic models
  - [x] 1.1 Create Aurora migration script for investigator AI tables
    - Create `src/db/migrations/003_investigator_ai_first.sql` with 4 tables: `investigator_leads`, `evidence_triage_results`, `investigator_analysis_cache`, `investigator_sessions`
    - `investigator_leads`: UUID PK, case_id FK, entity_name, entity_type, lead_priority_score (CHECK 0-100), evidence_strength, connection_density, novelty, prosecution_readiness floats, ai_justification TEXT, recommended_actions JSONB, decision_id FK to ai_decisions, timestamps
    - `evidence_triage_results`: UUID PK, case_id FK, document_id, doc_type_classification CHECK IN 7 types, identified_entities JSONB, high_priority_findings JSONB, linked_leads JSONB, prosecution_readiness_impact CHECK IN (strengthens, weakens, neutral), decision_id FK
    - `investigator_analysis_cache`: UUID PK, case_id FK UNIQUE, analysis_result JSONB, evidence_count_at_analysis INT, status CHECK IN (processing, completed, failed), timestamps
    - `investigator_sessions`: UUID PK, case_id FK, user_id VARCHAR(255), last_session_at TIMESTAMP, UNIQUE(case_id, user_id)
    - Include all indexes per design: idx_investigator_leads_case, idx_investigator_leads_score DESC, idx_evidence_triage_case, idx_evidence_triage_doc_type, idx_analysis_cache_case, idx_investigator_sessions_case_user
    - _Requirements: 2.1, 2.4, 3.1, 6.4, 9.5, 12.5_

  - [x] 1.2 Implement Pydantic models in `src/models/investigator.py`
    - Create enums: `DocumentTypeClassification` (7 values), `ConfidenceLevel` (high/medium/low), `ProsecutionReadinessImpact` (strengthens/weakens/neutral), `DecisionState` (ai_proposed/human_confirmed/human_overridden)
    - Create models: `InvestigativeLead` (lead_priority_score Field ge=0 le=100, evidence_strength/connection_density/novelty/prosecution_readiness Field ge=0.0 le=1.0), `EvidenceTriageResult`, `InvestigativeHypothesis`, `SubpoenaRecommendation` (priority_rank Field ge=1), `CaseBriefing`, `SessionBriefing`, `CaseAnalysisResult`
    - All Optional fields and default values per design
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.3, 5.1, 5.2, 6.1, 6.4, 9.1, 9.2_

  - [ ]* 1.3 Write property tests for investigator model validation
    - **Property 1: Lead priority score domain** — for any valid InvestigativeLead, lead_priority_score in [0, 100] and all factor floats in [0.0, 1.0]
    - **Validates: Requirements 2.1, 2.2**
    - **Property 2: Document type classification domain** — for any valid EvidenceTriageResult, doc_type_classification is one of the 7 allowed values
    - **Validates: Requirements 3.2**
    - **Property 3: Decision state domain invariant** — for any model with decision_state, value is one of ai_proposed, human_confirmed, human_overridden; new instances default to ai_proposed
    - **Validates: Requirements 8.1, 8.2**
    - **Property 4: Subpoena recommendation priority ordering** — priority_rank >= 1 for all SubpoenaRecommendation instances
    - **Validates: Requirements 5.2**

- [x] 2. Checkpoint — Verify schema and models
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement InvestigatorAIEngine core service
  - [x] 3.1 Implement `src/services/investigator_ai_engine.py` — constructor and analyze method
    - Define `SENIOR_LEGAL_ANALYST_PERSONA` class constant with investigative analyst system prompt per design
    - Constructor with `aurora_cm`, `bedrock_client`, `case_assessment_svc`, `hypothesis_testing_svc`, `pattern_discovery_svc`, `decision_workflow_svc`, optional `neptune_endpoint`, `neptune_port`, `opensearch_endpoint` injection
    - Implement `analyze(case_id)` → `CaseAnalysisResult`: check cache in `investigator_analysis_cache`; if valid return cached; otherwise gather assessment via CaseAssessmentService, discover patterns via PatternDiscoveryService, generate hypotheses via HypothesisTestingService, compute Lead_Priority_Scores, generate subpoena recommendations, generate Case_Briefing narrative via Bedrock, create AI_Proposed decisions for each finding/lead/hypothesis/recommendation via DecisionWorkflowService, cache result in Aurora
    - Implement `get_cached_analysis(case_id)` → `Optional[CaseAnalysisResult]`: retrieve from `investigator_analysis_cache`, return None if stale or missing
    - Bedrock fallback: produce partial Case_Briefing with statistics and entity counts only, add warning message
    - Neptune fallback: return partial result with Aurora/OpenSearch-derived findings only, add warning
    - For cases with 100K+ documents, return initial response with status "processing" and complete asynchronously
    - Use paginated queries (batches of 1,000) for entity/document/relationship retrieval
    - Limit Bedrock context to 100,000 tokens by summarizing large evidence sets
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 3.2 Implement `compute_lead_priority_score` method
    - Compute weighted composite: evidence_strength (0.30) × min(doc_count/total_docs, 1.0) + connection_density (0.25) × degree_centrality + novelty (0.25) × (1.0 - previously_flagged_ratio) + prosecution_readiness (0.20) × prosecution_readiness
    - Return int 0-100
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Implement `triage_evidence` method
    - Classify document type via Bedrock with Senior_Legal_Analyst_Persona
    - Link entities to existing Neptune graph
    - Flag high-priority findings (admissions, financial irregularities, contradictions)
    - Match to existing investigative leads in Aurora
    - Assess prosecution readiness impact (strengthens/weakens/neutral)
    - Create AI_Proposed decisions for classification and each finding via DecisionWorkflowService
    - Store result in `evidence_triage_results` table
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [x] 3.4 Implement `generate_subpoena_recommendations` method
    - Generate recommendations from evidence gaps and active leads using Bedrock with Senior_Legal_Analyst_Persona
    - Each recommendation includes target, custodian, legal basis with evidence citations, expected evidentiary value, priority ranking
    - Create AI_Proposed decisions for each recommendation
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x] 3.5 Implement retrieval methods: `get_investigative_leads`, `get_evidence_triage_results`, `get_hypotheses`, `get_subpoena_recommendations`, `get_session_briefing`
    - `get_investigative_leads`: query `investigator_leads` table, join with `ai_decisions` for state, filter by min_score and state
    - `get_evidence_triage_results`: query `evidence_triage_results`, filter by doc_type and state
    - `get_hypotheses`: query `case_hypotheses` table extended with decision state, filter by confidence and state
    - `get_subpoena_recommendations`: query from cached analysis result, filter by priority and state
    - `get_session_briefing`: compute changes since last_session_at from Aurora, generate narrative via Bedrock
    - _Requirements: 6.4, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [ ]* 3.6 Write property tests for InvestigatorAIEngine
    - **Property 5: Lead priority score formula** — score equals round((0.30 × min(doc_count/total_docs, 1.0) + 0.25 × degree_centrality + 0.25 × (1.0 - previously_flagged_ratio) + 0.20 × prosecution_readiness) × 100), result in [0, 100]
    - **Validates: Requirements 2.1, 2.2**
    - **Property 6: Evidence triage classification domain** — triage_evidence always returns doc_type_classification in the 7 allowed values
    - **Validates: Requirements 3.2**
    - **Property 7: Analysis creates AI_Proposed decisions** — analyze() creates at least one AI_Proposed decision for each finding, lead, hypothesis, and recommendation
    - **Validates: Requirements 1.8, 8.1, 8.2**
    - **Property 8: Cache invalidation on new evidence** — if evidence_count_at_analysis < current document count, cached result is not returned
    - **Validates: Requirements 12.5**

  - [ ]* 3.7 Write unit tests for InvestigatorAIEngine
    - Create `tests/unit/test_investigator_ai_engine.py`
    - Test analyze returns CaseAnalysisResult with briefing, leads, hypotheses, subpoena_recommendations
    - Test Bedrock fallback returns partial briefing with statistics only and warning
    - Test Neptune fallback returns partial result with warning
    - Test cache hit returns cached result without re-analysis
    - Test cache miss triggers full analysis
    - Test compute_lead_priority_score with known inputs matches expected formula output
    - Test triage_evidence creates AI_Proposed decisions
    - _Requirements: 1.1, 1.9, 9.7, 12.5_

- [x] 4. Extend existing services
  - [x] 4.1 Extend `src/services/hypothesis_testing_service.py` with `generate_hypotheses` method
    - Add `generate_hypotheses(case_id, patterns)` → `list[dict]`: use Bedrock with Senior_Legal_Analyst_Persona to propose hypotheses from pattern data
    - Generate hypotheses for financial patterns (money laundering, shell companies, unusual transactions), communication patterns (frequency anomalies, timing correlations, network clustering), geographic patterns (co-location, travel), temporal patterns (event clustering, timeline anomalies)
    - Each hypothesis includes: hypothesis_text, supporting_evidence citations, confidence (High/Medium/Low), recommended_actions
    - Reuse existing `_decompose` and `_classify_evidence` internal methods where applicable
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 4.2 Extend `src/services/case_assessment_service.py` with narrative and session methods
    - Add `generate_strength_narrative(case_id, assessment)` → `str`: use Bedrock with Senior_Legal_Analyst_Persona to generate AI narrative explaining case strength score, citing specific evidence strengths and weaknesses
    - Add `get_session_changes(case_id, since)` → `dict`: query Aurora for new documents, new entities, updated scores, new findings since timestamp; return structured change summary
    - _Requirements: 6.1, 6.4, 6.6_

  - [x] 4.3 Extend `src/services/chat_service.py` with structured responses, action triggers, and network queries
    - Append new intent patterns to existing INTENT_PATTERNS: flag_entity, create_lead, generate_subpoena, co_location, shared_documents per design regex patterns
    - Add `_handle_flag_entity`: create AI_Proposed decision via DecisionWorkflowService, return structured response with decision_id and yellow state badge
    - Add `_handle_create_lead`: create AI_Proposed investigative_lead decision, return structured response
    - Add `_handle_generate_subpoena`: generate subpoena recommendations using InvestigatorAIEngine, return structured response with recommendations and decision_ids
    - Add `_handle_co_location`: query Neptune for co-location relationships filtered by location and date, return structured table
    - Add `_handle_shared_documents`: query OpenSearch for documents containing both entities, return structured table with relevance scores
    - Add `_format_structured_response`: format entity results as markdown table (entity name, type, doc count, connection count)
    - Maintain context-aware follow-ups by tracking current investigation focus (active entity, lead, hypothesis) in conversation context
    - Do not modify existing intent classification for non-enhanced queries
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [ ]* 4.4 Write unit tests for service extensions
    - Create `tests/unit/test_investigator_service_extensions.py`
    - Test generate_hypotheses returns list with hypothesis_text, confidence, supporting_evidence
    - Test generate_strength_narrative returns non-empty string
    - Test get_session_changes returns dict with new_documents, new_entities keys
    - Test ChatService flag_entity creates AI_Proposed decision and returns structured response
    - Test ChatService co_location returns structured table
    - Test ChatService shared_documents returns structured table with relevance scores
    - Test existing chat intents still work unchanged after extension
    - _Requirements: 4.1, 6.1, 6.4, 7.1, 7.2, 7.5, 7.6_

- [x] 5. Checkpoint — Verify InvestigatorAIEngine and service extensions
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Lambda handler and API routes
  - [x] 6.1 Implement `src/lambdas/api/investigator_analysis.py`
    - `dispatch_handler(event, context)` routing by HTTP method + resource path:
      - POST `/case-files/{id}/investigator-analysis` → `trigger_analysis`: build InvestigatorAIEngine, call analyze(case_id), return CaseAnalysisResult JSON
      - GET `/case-files/{id}/investigator-analysis` → `get_analysis`: return cached analysis result
      - GET `/case-files/{id}/investigative-leads` → `get_leads`: return ranked leads with optional min_score and state query params
      - GET `/case-files/{id}/evidence-triage` → `get_triage`: return triage results with optional doc_type and state filters
      - GET `/case-files/{id}/ai-hypotheses` → `get_hypotheses`: return hypotheses with optional confidence and state filters
      - GET `/case-files/{id}/subpoena-recommendations` → `get_subpoenas`: return recommendations with optional priority and state filters
      - GET `/case-files/{id}/session-briefing` → `get_session_briefing`: return session briefing computed from since query param
    - `_build_investigator_ai_engine()`: construct InvestigatorAIEngine with all dependencies from environment variables (AURORA_*, NEPTUNE_*, OPENSEARCH_*, BEDROCK_*)
    - CORS preflight via OPTIONS
    - Use `response_helper.success_response` / `error_response` for consistent responses
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [x] 6.2 Add API Gateway routes to `infra/api_gateway/api_definition.yaml`
    - Add paths: `/case-files/{id}/investigator-analysis` (POST + GET), `/case-files/{id}/investigative-leads` (GET), `/case-files/{id}/evidence-triage` (GET), `/case-files/{id}/ai-hypotheses` (GET), `/case-files/{id}/subpoena-recommendations` (GET), `/case-files/{id}/session-briefing` (GET)
    - Include Lambda integrations and CORS configuration
    - Query parameters: min_score (integer), state (string enum), doc_type (string), confidence (string enum), priority (string), since (date-time)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [ ]* 6.3 Write unit tests for Lambda handler
    - Create `tests/unit/test_investigator_analysis_handler.py`
    - Test dispatch routing for each HTTP method/resource combination (7 routes)
    - Test CORS preflight returns correct headers
    - Test 400 for missing case_id
    - Test POST trigger_analysis returns CaseAnalysisResult structure
    - Test GET get_leads with min_score filter
    - Test GET get_triage with doc_type filter
    - _Requirements: 10.1, 10.8_

- [x] 7. Checkpoint — Verify Lambda handler and API routes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement frontend AI tabs in investigator.html
  - [x] 8.1 Add AI Briefing tab to `src/frontend/investigator.html`
    - Add "AI Briefing" tab alongside existing tabs (Case Dashboard, Graph Explorer, Pipeline Monitor, Chatbot)
    - Display Case_Briefing on case load: statistics cards (total documents, entity counts by type, relationship count, persons of interest, financial patterns, communication networks, geographic clusters)
    - Key findings list ranked by significance with expandable AI reasoning sections
    - Top 3 investigative leads with AI justification
    - Evidence_Coverage_Map showing coverage status (covered/gap) for: people, organizations, financial connections, communication patterns, physical evidence, timeline, geographic scope
    - Recommended next steps as actionable items
    - Each finding and next step has Accept/Override buttons with Decision_Workflow state badges (yellow=AI_Proposed, green=Human_Confirmed, blue=Human_Overridden)
    - Auto-trigger POST `/case-files/{id}/investigator-analysis` on case load
    - Use green accent (#48bb78) for all new components
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 6.1, 6.2, 6.3, 8.5, 8.6, 11.1, 11.7, 11.8_

  - [x] 8.2 Add Leads tab to `src/frontend/investigator.html`
    - Ranked list of Investigative_Leads from GET `/case-files/{id}/investigative-leads`
    - Each lead card: entity name and type, Lead_Priority_Score as progress bar (0-100), expandable AI justification section, recommended investigative actions list
    - Accept/Override buttons with state badges per Decision_Workflow
    - Filter controls: minimum score slider, decision state dropdown (ai_proposed, human_confirmed, human_overridden)
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 8.5, 8.6, 11.2, 11.6_

  - [x] 8.3 Add Evidence Triage tab to `src/frontend/investigator.html`
    - List of Evidence_Triage_Results from GET `/case-files/{id}/evidence-triage`
    - Each card: document name, Document_Type_Classification badge, identified entities as tags, high-priority findings with passage citations, linked investigative threads, prosecution readiness impact indicator (strengthens/weakens/neutral)
    - Accept/Override buttons for classification and each finding
    - Filter controls: document type dropdown, decision state dropdown
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 8.5, 8.6, 11.3_

  - [x] 8.4 Add Hypotheses tab to `src/frontend/investigator.html`
    - Investigative_Hypothesis cards from GET `/case-files/{id}/ai-hypotheses`
    - Each card: hypothesis statement, confidence badge (High=green, Medium=yellow, Low=red), supporting evidence citations as clickable links, recommended investigative actions
    - Accept/Override buttons with state badges
    - Filter controls: confidence level dropdown, decision state dropdown
    - _Requirements: 4.1, 4.3, 4.5, 4.6, 4.7, 8.5, 8.6, 11.4_

  - [x] 8.5 Add Subpoenas tab to `src/frontend/investigator.html`
    - Subpoena_Recommendation list from GET `/case-files/{id}/subpoena-recommendations`
    - Each card: target (person/org/record type), custodian, legal basis with evidence citations, expected evidentiary value badge (High/Medium/Low), priority ranking
    - Accept/Override buttons with state badges
    - Confirmed recommendations show export button for structured subpoena request document
    - Filter controls: priority dropdown, decision state dropdown
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 8.5, 8.6, 11.5_

  - [x] 8.6 Add Session Briefing and Case Strength widgets
    - Session_Briefing panel from GET `/case-files/{id}/session-briefing`: new findings count, updated lead scores, new evidence count, recommended next actions, AI narrative
    - Case strength score display with AI-generated narrative explaining the score basis
    - Prosecution_Readiness_Score widget showing per-statute readiness scores and missing statutory elements (reuse from prosecutor-case-review)
    - Auto-generated timeline of key events from Neptune date/event entities, ordered chronologically with linked source documents
    - Evidence_Coverage_Map auto-refresh within 30 seconds when new evidence is added
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 9. Wire frontend to Streamlit app
  - [x] 9.1 Register investigator AI tabs in `src/frontend/app.py`
    - Wire API client calls for all investigator AI endpoints: investigator-analysis (POST/GET), investigative-leads, evidence-triage, ai-hypotheses, subpoena-recommendations, session-briefing
    - Ensure existing investigator.html tabs (Case Dashboard, Graph Explorer, Pipeline Monitor, Chatbot) remain functional
    - _Requirements: 11.7_

- [x] 10. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate model constraints and algorithmic invariants
- Unit tests validate specific examples and edge cases
- All services follow the existing Protocol/constructor-injection pattern
- Task order: schema → models → InvestigatorAIEngine → service extensions → Lambda handler → API routes → frontend tabs → integration
- Senior_Legal_Analyst_Persona (investigative focus) used in all Bedrock calls across InvestigatorAIEngine, HypothesisTestingService, CaseAssessmentService
- Three-state Decision Workflow (AI_Proposed → Human_Confirmed / Human_Overridden) reused from prosecutor-case-review for all AI recommendations
- DecisionWorkflowService and ai_decisions table reused without modification; new decision_type values added for investigator-specific decisions
