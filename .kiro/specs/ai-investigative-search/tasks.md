# Implementation Plan: AI Investigative Search

## Overview

Implement an intelligence-grade investigative search orchestration layer on top of six existing services (SemanticSearchService, QuestionAnswerService, InvestigatorAIEngine, NetworkDiscoveryService, AIResearchAgent, LeadIngestionService). The implementation adds a thin orchestrator (`InvestigativeSearchService`), Pydantic data models, API handlers, a findings persistence layer (`FindingsService`), a database migration, and frontend UI extensions to `investigator.html`. All changes extend existing code — nothing is replaced. Python 3.10 compatible (use `Optional[type]` not `type|None`).

## Tasks

- [x] 1. Create data models and request/response schemas
  - [x] 1.1 Create Pydantic models in `src/models/investigative_search.py`
    - Define `ConfidenceLevel`, `CaseViability`, `FindingType` enums
    - Define `EvidenceCitation`, `GraphConnection`, `EvidenceGap`, `NextStep`, `CrossReferenceEntry` models
    - Define `InvestigativeAssessment`, `LeadAssessmentResponse` response models
    - Define `InvestigativeSearchRequest`, `LeadAssessmentRequest` request models
    - Define `ExtractedQueryEntity` model
    - Define `SaveFindingRequest`, `UpdateFindingRequest`, `FindingResponse` models
    - Use `Optional[type]` for all optional fields (Python 3.10 Lambda compatibility)
    - _Requirements: 6.1, 8.1, 9.1, 10.2_

  - [ ]* 1.2 Write property test for assessment structural completeness
    - **Property 1: Assessment structural completeness**
    - Generate random valid inputs, construct `InvestigativeAssessment`, verify all required top-level keys and nested field presence
    - **Validates: Requirements 1.3, 1.5, 6.1, 6.3, 6.4, 6.5, 8.2, 3.2**

  - [ ]* 1.3 Write property test for default parameter application
    - **Property 13: Default parameter application**
    - Generate partial `InvestigativeSearchRequest` bodies, verify `search_scope` defaults to `"internal"`, `top_k` to `10`, `output_format` to `"full"`
    - **Validates: Requirements 4.1, 8.1**

  - [ ]* 1.4 Write unit tests for model validation edge cases
    - Test empty query rejection, invalid enum values, `top_k` out of range, `subjects` list exceeding 20
    - _Requirements: 8.5, 8.6, 9.4_

- [x] 2. Implement InvestigativeSearchService orchestrator
  - [x] 2.1 Create `src/services/investigative_search_service.py` with constructor and dependency injection
    - Accept `SemanticSearchService`, `QuestionAnswerService`, `InvestigatorAIEngine`, `AIResearchAgent`, `bedrock_client`, optional `FindingsService`
    - Wire Neptune endpoint/port configuration
    - _Requirements: 1.1, 1.2_

  - [x] 2.2 Implement `_extract_entities_from_query()` using Bedrock Haiku
    - Build entity extraction prompt template
    - Parse JSON response into `ExtractedQueryEntity` list
    - Handle aliases and partial names
    - Fallback to keyword tokenization if Bedrock fails
    - _Requirements: 2.3, 2.4_

  - [ ]* 2.3 Write property test for entity extraction
    - **Property 2: Entity extraction from natural language queries**
    - Generate query strings with embedded entity names, verify extraction returns non-empty subset with `name` and `type` fields
    - **Validates: Requirements 2.3**

  - [x] 2.4 Implement `_search_documents()` delegating to `SemanticSearchService.search()`
    - Pass `case_id`, `query`, `mode="hybrid"`, `top_k`
    - _Requirements: 1.1_

  - [x] 2.5 Implement `_get_graph_context()` delegating to `InvestigatorAIEngine.get_entity_neighborhood()`
    - Iterate extracted entities, call `get_entity_neighborhood(case_id, entity, hops=2)` for each
    - Merge results into unified graph context dict
    - _Requirements: 2.2_

  - [x] 2.6 Implement `_find_entity_paths()` for multi-entity Neptune path queries
    - Query Neptune for paths between entity pairs (up to 3 hops)
    - Use sampled queries for high-degree nodes (reuse existing `bothE().limit(200)` pattern)
    - _Requirements: 2.1_

  - [ ]* 2.7 Write property test for multi-entity path routing
    - **Property 3: Multi-entity path query routing**
    - Verify that when 2+ entities extracted, `_find_entity_paths()` is invoked for each pair
    - **Validates: Requirements 2.1**

  - [ ]* 2.8 Write property test for single-entity neighborhood routing
    - **Property 4: Single-entity neighborhood routing**
    - Verify that when exactly 1 entity extracted, `get_entity_neighborhood(hops=2)` is invoked
    - **Validates: Requirements 2.2**

  - [x] 2.9 Implement `_synthesize_intelligence_brief()` using Bedrock Sonnet (full) / Haiku (brief)
    - Build synthesis prompt with search results, graph context, and prior findings (if available)
    - Parse structured response into Intelligence Brief sections
    - Handle synthesis timeout with graceful degradation
    - _Requirements: 1.2, 1.3, 1.6_

  - [x] 2.10 Implement `_generate_cross_reference_report()` comparing internal vs external findings
    - Categorize each finding as `confirmed_internally`, `external_only`, or `needs_research`
    - _Requirements: 4.3, 4.4_

  - [x] 2.11 Implement `_compute_confidence_level()` based on document count and graph connections
    - `insufficient`: fewer than 2 unique document sources
    - `strong_case`: 3+ documents corroborate AND graph connections confirm
    - `needs_more_evidence`: otherwise
    - _Requirements: 6.2_

  - [ ]* 2.12 Write property test for confidence level computation
    - **Property 8: Confidence level computation**
    - Generate random `(doc_count, graph_connection_count)` tuples, verify confidence follows rules
    - **Validates: Requirements 6.2**

  - [x] 2.13 Implement `_assemble_assessment()` to build final `InvestigativeAssessment`
    - Combine all sections: evidence, graph, analysis, gaps, next steps, confidence, cross-reference
    - _Requirements: 6.1, 6.3, 6.4, 6.5_

  - [x] 2.14 Implement `investigative_search()` main orchestration method
    - Entity extraction → parallel fan-out (documents + graph) → synthesis → optional external research → assembly
    - Handle `output_format="brief"` truncation (executive_summary + confidence + top 3 citations only)
    - Integrate prior findings enrichment via `FindingsService.get_findings_for_entities()` when available
    - _Requirements: 1.1, 1.2, 1.4, 4.1, 4.2, 8.2, 8.3, 10.6_

  - [ ]* 2.15 Write property test for entity list deduplication and ranking
    - **Property 5: Entity list deduplication and ranking**
    - Generate entity lists with duplicates, verify merged output has unique names (case-insensitive) and descending relevance score
    - **Validates: Requirements 3.1, 3.3, 3.4**

  - [ ]* 2.16 Write property test for internal scope excludes external research
    - **Property 6: Internal scope excludes external research**
    - Verify `scope="internal"` → `cross_reference_report` is None, `AIResearchAgent` not invoked
    - **Validates: Requirements 4.2**

  - [ ]* 2.17 Write property test for internal+external scope cross-reference
    - **Property 7: Internal+external scope includes cross-reference report**
    - Verify `scope="internal_external"` → non-None cross-reference with valid categories
    - **Validates: Requirements 4.3, 4.4**

  - [ ]* 2.18 Write property test for brief output format truncation
    - **Property 9: Brief output format truncation**
    - Verify brief format returns only `executive_summary`, `confidence_level`, `internal_evidence` (≤3 entries)
    - **Validates: Requirements 8.3**

- [x] 3. Implement lead assessment
  - [x] 3.1 Implement `lead_assessment()` method in `InvestigativeSearchService`
    - Validate via `LeadIngestionService.validate_lead_json()`
    - Run investigative search per subject with `scope="internal_external"`
    - Cross-reference connections between subjects
    - Compute `case_viability` rating
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.2, 9.3_

  - [x] 3.2 Implement async threshold for >5 subjects (return 202 + job_id)
    - Store job state, support polling via `get_lead_assessment_result()`
    - _Requirements: 9.5_

  - [ ]* 3.3 Write property test for lead assessment subject coverage
    - **Property 10: Lead assessment subject coverage**
    - Generate payloads with 1-20 subjects, verify `subjects_assessed == N` and `len(subject_assessments) == N`
    - **Validates: Requirements 5.1, 9.2**

  - [ ]* 3.4 Write property test for OSINT directives forwarding
    - **Property 11: Lead OSINT directives and evidence hints forwarding**
    - Verify non-empty directives/hints are passed to `AIResearchAgent.research_all_subjects()`
    - **Validates: Requirements 5.3, 5.4**

  - [ ]* 3.5 Write property test for lead validation error structure
    - **Property 12: Lead validation error structure**
    - Generate invalid payloads, verify error response contains field path and expected format
    - **Validates: Requirements 5.5**

  - [ ]* 3.6 Write property test for case viability assignment
    - **Property 14: Case viability assignment**
    - Generate subject assessment results, verify viability follows rules
    - **Validates: Requirements 9.3**

  - [ ]* 3.7 Write property test for async threshold
    - **Property 15: Async threshold for large lead assessments**
    - Verify >5 subjects returns 202 with `job_id`, polling returns completed result
    - **Validates: Requirements 9.5**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Create database migration for investigation_findings table
  - [x] 5.1 Create `src/db/migrations/008_investigation_findings.sql`
    - Define `investigation_findings` table with all columns per design schema
    - Add GIN indexes on `entity_names` and `tags` JSONB columns
    - Add index on `case_id`
    - _Requirements: 10.2_

- [x] 6. Implement FindingsService for persistence
  - [x] 6.1 Create `src/services/findings_service.py`
    - Implement `save_finding()` — INSERT into Aurora + upload full assessment JSON to S3 at `cases/{case_id}/findings/{finding_id}.json`
    - Implement `list_findings()` — SELECT with optional tag/entity GIN filters, sorting, limit
    - Implement `update_finding()` — UPDATE notes, tags, is_key_evidence, needs_follow_up; set updated_at
    - Implement `delete_finding()` — DELETE from Aurora + remove S3 artifact
    - Implement `get_findings_for_entities()` — query by entity_names JSONB overlap for search enrichment
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 6.2 Write property test for finding persistence round-trip
    - **Property 16: Finding persistence round-trip**
    - Save a finding, list findings, verify the saved finding appears with matching title, type, tags, entity_names
    - **Validates: Requirements 10.1, 10.2**

  - [ ]* 6.3 Write property test for S3 archival on save
    - **Property 17: S3 archival on save**
    - Verify `save_finding()` stores JSON at `cases/{case_id}/findings/{finding_id}.json` and sets `s3_artifact_key`
    - **Validates: Requirements 10.3**

  - [ ]* 6.4 Write property test for notebook listing and sorting
    - **Property 18: Notebook listing completeness and sorting**
    - Save N findings, verify `list_findings()` returns N results in descending chronological order
    - **Validates: Requirements 10.4**

  - [ ]* 6.5 Write property test for finding update immutability
    - **Property 19: Finding update preserves immutable fields**
    - Update tags/notes/flags, verify immutable fields unchanged and `updated_at` advanced
    - **Validates: Requirements 10.5**

  - [ ]* 6.6 Write property test for prior findings enrichment
    - **Property 20: Prior findings enrichment in search context**
    - Save findings with entity names, run search for same entities, verify prior findings included in synthesis context
    - **Validates: Requirements 10.6**

  - [ ]* 6.7 Write property test for CRUD completeness
    - **Property 21: Findings CRUD API completeness**
    - Create → list (present) → update → list (updated) → delete → list (absent)
    - **Validates: Requirements 10.7**

  - [ ]* 6.8 Write unit tests for FindingsService edge cases
    - Test: delete non-existent finding, update non-existent finding, list empty case, save with empty tags/entities
    - _Requirements: 10.2, 10.5, 10.7_

- [x] 7. Create API handlers
  - [x] 7.1 Create `src/lambdas/api/investigative_search.py`
    - Implement `investigative_search_handler` for `POST /case-files/{id}/investigative-search`
    - Implement `lead_assessment_handler` for `POST /case-files/{id}/lead-assessment`
    - Implement `lead_assessment_status_handler` for `GET /case-files/{id}/lead-assessment/{job_id}`
    - Validate request bodies, construct service with DI, handle errors with proper HTTP status codes
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.4, 9.5_

  - [x] 7.2 Create `src/lambdas/api/findings.py`
    - Implement `save_finding_handler` for `POST /case-files/{id}/findings`
    - Implement `list_findings_handler` for `GET /case-files/{id}/findings`
    - Implement `update_finding_handler` for `PUT /case-files/{id}/findings/{finding_id}`
    - Implement `delete_finding_handler` for `DELETE /case-files/{id}/findings/{finding_id}`
    - _Requirements: 10.1, 10.7_

  - [ ]* 7.3 Write unit tests for investigative search handler
    - Test request validation, 400/404 error codes, successful routing, async 202 response
    - _Requirements: 8.5, 8.6, 9.4, 9.5_

  - [ ]* 7.4 Write unit tests for findings handler
    - Test CRUD routing, validation errors, 404 for missing findings
    - _Requirements: 10.7_

- [x] 8. Register API routes
  - [x] 8.1 Add investigative search and findings routes to `infra/api_gateway/api_definition.yaml`
    - `POST /case-files/{id}/investigative-search`
    - `POST /case-files/{id}/lead-assessment`
    - `GET /case-files/{id}/lead-assessment/{job_id}`
    - `POST /case-files/{id}/findings`
    - `GET /case-files/{id}/findings`
    - `PUT /case-files/{id}/findings/{finding_id}`
    - `DELETE /case-files/{id}/findings/{finding_id}`
    - _Requirements: 8.1, 9.1, 10.7_

  - [x] 8.2 Add route registrations to `infra/cdk/add_routes.py`
    - Wire Lambda handlers for all new endpoints
    - _Requirements: 8.1, 9.1, 10.7_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement frontend UI extensions
  - [x] 10.1 Add search scope toggle and Intelligence Brief display to `src/frontend/investigator.html`
    - Add "Internal Only" / "Internal + External" toggle above search bar
    - Add collapsible Intelligence Brief panel above raw search results
    - Render assessment sections (evidence, graph, analysis, gaps, next steps) as distinct visual blocks with icons
    - Display confidence badge (green/amber/red)
    - Make evidence citations clickable
    - Show warning banner when synthesis fails
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 10.2 Add "Save Finding" button and Research Notebook panel to `src/frontend/investigator.html`
    - Add "Save Finding" button on every Intelligence Brief card
    - Save dialog: title input, optional tags, optional notes
    - Add collapsible "Research Notebook" panel below search results
    - Notebook view: finding cards with title, summary snippet, tags, date, confidence badge
    - Sort controls: by date, confidence, tags
    - Inline note editing, tag add/remove chips
    - "Key Evidence" and "Needs Follow-up" toggle buttons per finding
    - Delete button with confirmation dialog
    - Wire all actions to findings API endpoints
    - _Requirements: 10.1, 10.4, 10.5_

- [ ] 11. Wire prior findings enrichment into search flow
  - [ ] 11.1 Update `InvestigativeSearchService.investigative_search()` to call `FindingsService.get_findings_for_entities()`
    - When `FindingsService` is available, retrieve prior findings matching extracted entities
    - Append prior findings to Bedrock synthesis context under "Prior Research" section
    - _Requirements: 10.6_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All code uses `Optional[type]` not `type|None` for Lambda Python 3.10 compatibility
- Existing services (SemanticSearchService, QuestionAnswerService, InvestigatorAIEngine, etc.) are reused unchanged
- OpenSearch uses 1536-dim Titan v1 vectors
- Neptune queries use sampled `bothE().limit(200)` for high-degree nodes
- API Gateway 29s timeout — partial results returned if approaching limit

## Phase 2 — Intelligence Trawler (PRIORITY — build immediately after Phase 1)

Persistent collection / standing query system that monitors external sources for new intelligence on case entities. Like setting a fishing trawl line — the investigator defines what to watch for, sets the frequency, and the system alerts when new evidence surfaces.

### Concept
- Investigator clicks "Set Monitor" on any saved finding or entity
- System stores a watch query with target entities, keywords, frequency (daily/weekly/custom)
- EventBridge scheduled rule triggers a Lambda on the configured schedule
- Lambda runs each active monitor's query through `InvestigativeSearchService` (reuses Phase 1 search)
- Compares new results against the last saved finding for that monitor
- If new evidence found (new documents, new graph connections, confidence level changed):
  - Saves a new finding automatically to the Research Notebook
  - Sends SNS/SES notification to the investigator
  - Updates case status badge with "New Intelligence" indicator
- Stale cases get automatically re-activated when the trawler finds something

### Key Components
- `investigation_monitors` table in Aurora (monitor_id, case_id, user_id, watch_query, target_entities, frequency, last_run_at, last_finding_id, alert_threshold, is_active, created_at)
- `IntelligenceTrawlerService` — runs monitors, diffs results, triggers alerts
- EventBridge rule + Lambda for scheduled execution
- SNS topic for investigator notifications
- UI: "Set Monitor" button on findings/entities, monitor management panel, "New Intelligence" badge

### Why This Is a Great Demo Feature
- Shows the system working autonomously — "set it and forget it" intelligence gathering
- Demonstrates the value of persistent collection in investigative workflows
- Differentiator vs competitors — most tools require manual re-searching
- Natural extension of the Research Notebook — monitors create findings automatically
- Reuses 100% of Phase 1 infrastructure (InvestigativeSearchService, FindingsService, AIResearchAgent)

### AWS Infrastructure
- EventBridge Scheduler (cron rules for daily/weekly)
- Lambda function (reuses existing mega-dispatcher pattern)
- SNS topic + SES for email notifications
- Aurora table for monitor state
- No new services needed — pure orchestration on existing stack

## Future Roadmap — Palantir Gotham Gap Analysis (revisit later)

Modules we're missing compared to Gotham's core platform. Noted for future prioritization.

### 1. Collaboration & Annotations (HIGH VALUE)
- Multi-user shared workspaces per case
- Comment threads on entities, documents, and findings
- @mention investigators, assign tasks
- Real-time presence indicators ("John is viewing this entity")
- Partially covered by Research Notebook — extend with multi-user support

### 2. Full Audit Trail & Provenance (COMPLIANCE CRITICAL)
- Complete chain of custody: who viewed/changed/exported what, when
- Data lineage: trace any finding back through processing chain to original source
- Immutable audit log (append-only, tamper-evident)
- We have `audit_service.py` but it's basic — needs full event sourcing
- Required for court admissibility of AI-generated findings

### 3. Investigation Playbooks / Workflow Automation (DIFFERENTIATOR)
- Configurable step-by-step investigation templates (e.g., "Financial Fraud Playbook")
- Auto-trigger actions at each step (run search, check OFAC, pull financials)
- Progress tracking with supervisor approval gates
- Our `configurable-pipeline` spec is close but pipeline-focused, not investigator-facing
- Could be a killer demo feature — "AI-guided investigation"

### 4. Data Lineage & Processing Provenance
- Visual trace from any entity/finding back to the original document page
- Show the full processing chain: PDF → parse → extract → embed → graph load
- "Why does the system think X is connected to Y?" — show the evidence chain
- We have the data in S3/Aurora but no UI to visualize the lineage

### 5. Court-Ready Export & Reporting (DEMO PRIORITY)
- Generate formatted PDF/DOCX case summary reports
- Include evidence citations, graph visualizations, timeline, map screenshots
- Court filing templates with proper legal formatting
- We have `court_document_assembly` spec + `report_generation_service.py` — needs frontend

### 6. Role-Based Dashboards & Views
- Analyst view: deep research, graph exploration, evidence review
- Supervisor view: case portfolio, team workload, approval queue
- Prosecutor view: case strength assessment, element analysis, filing readiness
- We have `access_control_service` + `prosecutor.html` — needs role-switching UI

### Priority Order for Future Build
1. Court-Ready Export (demo impact, spec exists)
2. Investigation Playbooks (differentiator, AI-guided)
3. Collaboration & Annotations (multi-user, extends Research Notebook)
4. Full Audit Trail (compliance, extends audit_service)
5. Data Lineage (trust/transparency)
6. Role-Based Dashboards (extends existing access control)
