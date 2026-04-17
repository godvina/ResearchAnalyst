# Implementation Plan: Conspiracy Network Discovery

## Overview

Implement the AI-powered network analysis module following the order: Aurora schema → Pydantic models → NetworkDiscoveryService → PatternDiscoveryService extensions → CrossCaseService extensions → ChatService extensions → Lambda handler → API Gateway routes → frontend page → integration checkpoints. All code is Python (backend) and HTML/JS (frontend).

## Tasks

- [x] 1. Create Aurora schema migration and Pydantic models
  - [x] 1.1 Create database migration `003_conspiracy_network_discovery.sql`
    - Create the four new tables: `network_analyses`, `conspirator_profiles`, `network_patterns`, `sub_case_proposals`
    - Add all CHECK constraints, JSONB defaults, foreign key references to `case_files` and `ai_decisions`
    - Add all indexes (case_id, analysis_id, risk_level, involvement_score DESC, pattern_type, status)
    - _Requirements: 8.5, 9.3_

  - [x] 1.2 Create Pydantic models in `src/models/network.py`
    - Implement all enums: `RiskLevel`, `PatternType`, `AnalysisStatus`
    - Implement all models: `InvolvementScore`, `CentralityScores`, `CommunityCluster`, `EvidenceReference`, `RelationshipEntry`, `CoConspiratorProfile`, `NetworkPattern`, `CaseInitiationBrief`, `SubCaseProposal`, `NetworkAnalysisResult`
    - Add Field constraints (ge, le) matching the design spec
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 4.1_

  - [ ]* 1.3 Write property tests for Pydantic model validation
    - **Property 1: Involvement Score formula** — verify `round(connections * 0.25 + co_occurrence * 0.25 + financial * 0.20 + communication * 0.15 + geographic * 0.15)` equals total, and total is in [0, 100]
    - **Validates: Requirements 1.5**
    - **Property 4: Co-conspirator profile structural completeness** — verify non-empty entity_name, entity_type, score ranges, evidence_summary and relationship_map entry structure
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    - **Property 5: Detected pattern structural completeness** — verify pattern_type in valid set, confidence_score in [0, 100], non-empty entities_involved, evidence_documents, ai_reasoning
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
    - **Property 12: Case Initiation Brief structural completeness** — verify non-empty proposed_charges with statute_citation/charge_description, non-empty evidence_summary, non-empty investigative_steps with step_number/description/priority, non-empty full_brief
    - **Validates: Requirements 3.3**

- [x] 2. Checkpoint — Ensure schema and models are correct
  - Ensure all tests pass, ask the user if questions arise.


- [x] 3. Implement NetworkDiscoveryService core
  - [x] 3.1 Create `src/services/network_discovery_service.py` with constructor and constants
    - Implement `__init__` with constructor-injection for neptune_endpoint, neptune_port, aurora_cm, bedrock_client, opensearch_endpoint, decision_workflow_svc, cross_case_svc, pattern_discovery_svc
    - Define `SENIOR_LEGAL_ANALYST_PERSONA` and `INVOLVEMENT_WEIGHTS` class constants
    - _Requirements: 8.1, 8.3, 8.4, 8.5_

  - [x] 3.2 Implement community detection and centrality scoring internals
    - Implement `_run_community_detection(case_id)` with batched BFS (10K node pages) and approximate mode for >50K nodes
    - Implement `_run_centrality_scoring(case_id)` computing betweenness, degree, PageRank with approximate sampling for >50K nodes
    - Implement `_run_anomaly_detection(case_id, centrality)` flagging entities >2 std deviations from mean degree
    - _Requirements: 1.1, 1.2, 1.3, 1.8, 9.1, 9.2_

  - [ ]* 3.3 Write property tests for graph algorithm internals
    - **Property 16: Centrality scoring produces three measures per entity** — verify betweenness >= 0.0, degree >= 0, pagerank >= 0.0 for every entity
    - **Validates: Requirements 1.2**
    - **Property 17: Anomaly detection flags statistical outliers** — verify flagged entities have degree > mean + 2 * std_dev
    - **Validates: Requirements 1.3**

  - [x] 3.4 Implement involvement scoring and risk classification
    - Implement `_compute_involvement_score(case_id, entity_name, primary_subject)` with weighted composite formula (connections 0.25, co_occurrence 0.25, financial 0.20, communication 0.15, geographic 0.15)
    - Implement `_classify_risk_level(profile)` with High/Medium/Low rules per design
    - _Requirements: 1.5, 2.2, 2.6_

  - [ ]* 3.5 Write property tests for scoring and classification
    - **Property 1: Involvement Score formula** — verify weighted formula and [0, 100] range
    - **Validates: Requirements 1.5**
    - **Property 3: Risk Level classification** — verify High when doc_type_count >= 3 AND connection_strength > 70, Medium when doc_type_count == 2 OR 40 <= connection_strength <= 70, Low when doc_type_count <= 1 AND connection_strength < 40
    - **Validates: Requirements 2.6**

  - [x] 3.6 Implement AI reasoning and profile generation
    - Implement `_generate_legal_reasoning(profile)` invoking Bedrock with Senior_Legal_Analyst_Persona
    - Implement `_generate_case_initiation_brief(case_id, profile)` invoking Bedrock for proposed charges, evidence summary, investigative steps
    - _Requirements: 1.6, 2.5, 2.7, 3.3_

  - [x] 3.7 Implement main `analyze_network(case_id)` orchestration method
    - Count subgraph nodes; return `{analysis_status: "processing"}` if >50K
    - Orchestrate community detection → centrality → anomaly detection → co-occurrence → scoring → profile generation → legal reasoning → decision creation → Aurora caching
    - Create AI_Proposed decisions for each person of interest via DecisionWorkflowService
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 7.1, 9.4_

  - [ ]* 3.8 Write property tests for analysis orchestration
    - **Property 2: Persons of interest sorted by Involvement Score** — verify descending order of involvement_score.total
    - **Validates: Requirements 1.4**
    - **Property 6: Every finding creates an AI_Proposed decision with correct type** — verify non-null decision_id with correct decision_type for persons, patterns, and sub-case proposals
    - **Validates: Requirements 1.7, 4.6, 7.1**
    - **Property 7: Every AI_Proposed decision has non-empty legal reasoning** — verify non-empty legal_reasoning for all decision types
    - **Validates: Requirements 1.6, 2.7, 7.5**
    - **Property 13: Large subgraph triggers approximate algorithms and async** — verify analysis_status = "processing" and approximate = true for >50K nodes
    - **Validates: Requirements 9.2, 9.4**

  - [x] 3.9 Implement query and update methods
    - Implement `get_analysis(case_id)` to retrieve cached results from Aurora
    - Implement `get_persons_of_interest(case_id, risk_level, min_score)` with optional filters
    - Implement `get_person_profile(case_id, person_id)` for full profile retrieval
    - Implement `get_network_patterns(case_id, pattern_type)` with optional filter
    - Implement `update_analysis(case_id, new_evidence_ids)` for incremental updates
    - _Requirements: 8.2, 8.8, 10.2, 10.3, 10.4, 10.6_

  - [ ]* 3.10 Write property tests for query and filtering
    - **Property 14: Analysis caching idempotence** — verify repeated get_analysis returns same analysis_id, persons count, patterns count
    - **Validates: Requirements 9.3**
    - **Property 15: Filtering returns only matching items** — verify risk_level filter returns only matching profiles, pattern_type filter returns only matching patterns
    - **Validates: Requirements 10.3, 10.6**
    - **Property 18: Incremental analysis monotonicity** — verify total_entities_analyzed >= previous and all previous persons still present
    - **Validates: Requirements 8.8**

  - [x] 3.11 Implement `spawn_sub_case(case_id, person_id)` method
    - Gather relevant evidence from parent case
    - Generate Case_Initiation_Brief via Bedrock
    - Create AI_Proposed decision for sub-case proposal
    - On confirmation, delegate to CrossCaseService for sub-case graph creation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 3.12 Write property tests for sub-case spawning
    - **Property 11: Sub-case proposal for confirmed high-risk profiles** — verify high-risk + human_confirmed produces sub-case proposal with correct decision_type
    - **Validates: Requirements 3.1, 3.5**

- [x] 4. Checkpoint — Ensure NetworkDiscoveryService tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 5. Extend existing services
  - [x] 5.1 Extend `PatternDiscoveryService` with four new pattern detection methods
    - Add `discover_financial_patterns(case_id)` — analyze financial entities/relationships for unusual transactions, shell companies, money laundering indicators
    - Add `discover_communication_patterns(case_id)` — analyze phone/email entities for frequency anomalies, timing patterns, encrypted communication indicators
    - Add `discover_geographic_patterns(case_id)` — analyze location entities for travel patterns, co-location events, venue clustering
    - Add `discover_temporal_patterns(case_id)` — analyze date/event entities for event clustering, timeline anomalies, timing correlations
    - Each method returns `list[Pattern]` with confidence scores and evidence document links
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.7_

  - [ ]* 5.2 Write unit tests for PatternDiscoveryService extensions
    - Test each pattern detection method with mock Neptune data
    - Test edge cases: no financial entities, no communication entities, single location, no date entities
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 5.3 Extend `CrossCaseService` with `create_sub_case_from_conspirator` method
    - Create new case_files record in Aurora
    - Copy relevant Neptune subgraph entities/relationships
    - Create CROSS_CASE_LINK edges between parent and sub-case
    - Preserve provenance links back to parent case
    - _Requirements: 3.4, 3.6_

  - [ ]* 5.4 Write unit tests for CrossCaseService extension
    - Test sub-case creation with mock Neptune/Aurora
    - Test provenance link creation
    - _Requirements: 3.4, 3.6_

  - [x] 5.5 Extend `ChatService` with network intent patterns and handlers
    - Add five new intent patterns to INTENT_PATTERNS: network_who_list, network_travel, network_financial, network_flag, network_sub_case
    - Implement `_handle_network_who_list`, `_handle_network_travel`, `_handle_network_financial`, `_handle_network_flag`, `_handle_network_sub_case` command handlers
    - Wire handlers into existing dispatch logic without modifying existing intent classification
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 5.6 Write property tests for ChatService network intents
    - **Property 8: Network intent classification** — verify messages matching network patterns return correct intent names
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.6, 6.7**
    - **Property 9: Existing intent classification unchanged** — verify non-network messages still return original intents
    - **Validates: Requirements 6.8**

- [x] 6. Checkpoint — Ensure service extension tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Lambda handler and API routes
  - [x] 7.1 Create Lambda handler `src/lambdas/api/network_discovery.py`
    - Implement `dispatch_handler(event, context)` with route matching for all 6 routes
    - Implement `trigger_analysis_handler` (POST /network-analysis)
    - Implement `get_analysis_handler` (GET /network-analysis)
    - Implement `list_persons_handler` (GET /persons-of-interest) with risk_level and min_score query params
    - Implement `get_person_handler` (GET /persons-of-interest/{pid})
    - Implement `create_sub_case_handler` (POST /sub-cases) with validation (person must be Human_Confirmed)
    - Implement `get_patterns_handler` (GET /network-patterns) with pattern_type query param
    - Implement `_build_network_discovery_service()` constructor following existing patterns
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [ ]* 7.2 Write unit tests for Lambda handler routing and error handling
    - Test dispatch to correct handler for each route
    - Test 404 for unknown routes, 400 for invalid requests
    - Test CORS OPTIONS handling
    - _Requirements: 10.7_

  - [x] 7.3 Add API Gateway route definitions to `infra/api_gateway/api_definition.yaml`
    - Add all 6 resource paths with methods, parameters, and CORS options
    - Follow existing YAML structure and naming conventions
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 8. Implement frontend page
  - [x] 8.1 Create `src/frontend/network_discovery.html`
    - Network Graph Panel: vis.js force-directed graph with nodes sized by Involvement Score, color-coded by Risk Level (red=High, yellow=Medium, green=Low), decision state badges (yellow=AI_Proposed, green=Human_Confirmed, blue=Human_Overridden)
    - Filter Controls: relationship type, time period, minimum Connection Strength, Risk Level
    - Profile Detail Panel: click node to show full Co-Conspirator Profile with Accept/Override buttons
    - Patterns Panel: tabbed view by pattern type with confidence scores, evidence links, AI reasoning, Accept/Override buttons
    - Sub-Case Panel: "Propose Sub-Case" button for confirmed high-risk persons, Case Initiation Brief display
    - Support force-directed and hierarchical layouts
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.4_

  - [x] 8.2 Add navigation links to existing pages
    - Add Network Discovery link to `investigator.html`
    - Add Network Discovery link to `prosecutor.html`
    - _Requirements: 5.5_

- [x] 9. Wire decision workflow integration
  - [x] 9.1 Integrate DecisionWorkflowService calls in NetworkDiscoveryService
    - Ensure `analyze_network` creates AI_Proposed decisions with decision_type "person_of_interest" for each POI
    - Ensure pattern detection creates AI_Proposed decisions with decision_type "network_pattern" for each pattern
    - Ensure `spawn_sub_case` creates AI_Proposed decisions with decision_type "sub_case_proposal"
    - Wire Accept/Override buttons in frontend to existing decision workflow API endpoints
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 9.2 Write property tests for decision workflow integration
    - **Property 10: Decision workflow transitions for network decision types** — verify confirm transitions to human_confirmed with timestamps, override transitions to human_overridden with rationale, empty rationale rejected
    - **Validates: Requirements 7.2, 7.3**

- [x] 10. Implement error handling and graceful degradation
  - [x] 10.1 Add error handling to NetworkDiscoveryService
    - Neptune unavailable: return partial result with `analysis_status = "partial"` using Aurora/OpenSearch-only findings
    - Gremlin timeout: return partial results from completed stages, log timeout
    - Bedrock failure: use fallback template for legal reasoning
    - OpenSearch unavailable: skip co-occurrence, set factor to 0
    - Sub-case creation failure: rollback partial changes, return error with proposal intact
    - Duplicate analysis trigger: return existing analysis if processing/completed within last hour
    - _Requirements: 8.6, 9.5_

  - [ ]* 10.2 Write unit tests for error handling paths
    - Test Neptune unavailable returns partial result
    - Test Bedrock failure uses fallback template
    - Test OpenSearch unavailable zeroes co-occurrence factor
    - Test duplicate analysis trigger returns existing
    - _Requirements: 8.6, 9.5_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (18 properties total)
- The design uses Python throughout — no language selection needed
- Reuses existing DecisionWorkflowService from prosecutor-case-review for all decision management
