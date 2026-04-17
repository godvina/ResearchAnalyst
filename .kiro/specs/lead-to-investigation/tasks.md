# Implementation Plan: Lead to Investigation

## Overview

Extends the Research Analyst platform with lead ingestion from an external lead-finding app. Phase A (implementable): accept lead JSON via `POST /leads/ingest`, validate, create Matter/Collection in Aurora, seed Neptune with subjects and connections, run AI Research Agent (Bedrock Haiku) to produce synthetic research documents, feed through existing Step Functions pipeline. Phase C (aspirational/optional): autonomous investigation agent. All changes EXTEND existing code — no rewrites. New routes go through the `case_files.py` mega-dispatcher. Per lessons-learned: never replace working modules.

## Tasks

- [x] 1. Aurora schema migration and Pydantic lead models
  - [x] 1.1 Create migration `src/db/migrations/008_lead_to_investigation.sql`
    - ALTER TABLE matters ADD COLUMN lead_metadata JSONB
    - ALTER TABLE matters ADD COLUMN lead_status TEXT
    - ALTER TABLE matters ADD COLUMN lead_id TEXT
    - CREATE UNIQUE INDEX idx_matters_lead_id ON matters(lead_id) WHERE lead_id IS NOT NULL
    - CREATE INDEX idx_matters_lead_status ON matters(lead_status) WHERE lead_status IS NOT NULL
    - Additive only — no existing columns or tables modified or dropped
    - Wrap in BEGIN/COMMIT
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 1.2 Create Pydantic models in `src/models/lead.py`
    - Define LeadSubject (name, type, role, aliases, identifiers)
    - Define LeadConnection (from_subject aliased from "from", to_subject aliased from "to", relationship, confidence, source)
    - Define EvidenceHint (description, url, document_type, relevant_subjects)
    - Define LeadJSON (lead_id, classification, subcategory, title, summary, source_app, priority, subjects with min_length=1, connections, evidence_hints, osint_directives, tags, statutes)
    - Use Pydantic Field validators: confidence 0.0-1.0, subject type in {"person", "organization"}
    - Export from `src/models/__init__.py`
    - _Requirements: 1.1, 1.2, 1.4, 1.5_

  - [ ]* 1.3 Write property test for lead JSON validation (Property 1)
    - **Property 1: Invalid lead JSON is rejected with descriptive errors**
    - Test file: `tests/unit/test_lead_models.py`
    - Generate payloads with random required fields removed, verify validation errors reference the missing field
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 1.4 Write property test for subject validation (Property 2)
    - **Property 2: Subject validation rejects invalid subjects**
    - Test file: `tests/unit/test_lead_models.py`
    - Generate subjects with empty names or invalid types, verify error messages
    - **Validates: Requirements 1.4**

  - [ ]* 1.5 Write property test for connection reference validation (Property 3)
    - **Property 3: Connection reference validation**
    - Test file: `tests/unit/test_lead_models.py`
    - Generate connections with from/to not in subjects array, verify errors
    - **Validates: Requirements 1.5**

- [x] 2. Checkpoint — Ensure migration and models are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Lead Ingestion Service — validation, Matter/Collection creation, status tracking
  - [x] 3.1 Create `src/services/lead_ingestion_service.py` — validation and duplicate check
    - Implement LeadIngestionService.__init__(connection_manager, matter_service, collection_service)
    - Implement validate_lead_json(payload) returning list of error messages
      - Check required fields: lead_id, classification, title, summary, subjects, connections
      - Check subjects array has >= 1 entry, each with non-empty name and valid type
      - Check each connection from/to references existing subject names
      - Check confidence values 0.0-1.0
    - Implement check_duplicate(lead_id) querying matters WHERE lead_id = ? returning matter_id or None
    - Use existing ConnectionManager pattern from matter_service.py
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 3.2 Add Matter/Collection creation to `src/services/lead_ingestion_service.py`
    - Implement create_matter_from_lead(payload, org_id) returning (Matter, Collection)
    - Create Matter via MatterService.create_matter with matter_name=title, description=summary, matter_type='lead_investigation'
    - Create Collection via CollectionService.create_collection with collection_name='Lead: {lead_id}', source_description from classification
    - Store lead.json in S3 at {collection_s3_prefix}lead_data/lead.json using s3_helper.upload_file
    - Store lead_metadata JSONB (lead_id, classification, subcategory, priority, tags, statutes) on matter row
    - Set lead_status='accepted' and lead_id on matter row via direct SQL UPDATE (extending, not modifying MatterService)
    - Use DEFAULT_ORG_ID env var for org_id (consistent with ACCESS_CONTROL_ENABLED=false)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.4_

  - [x] 3.3 Add status tracking to `src/services/lead_ingestion_service.py`
    - Implement update_lead_status(matter_id, org_id, status, error_details=None)
      - UPDATE matters SET lead_status=?, last_activity=NOW() WHERE matter_id=? AND org_id=?
      - Valid statuses: accepted, seeding_graph, researching, pipeline_running, indexed, error
    - Implement get_lead_status(lead_id) querying matter by lead_id, returning status summary dict
    - Implement get_lead_metadata(matter_id, org_id) returning lead_metadata JSONB from matter row
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 3.4 Write property test for duplicate lead detection (Property 4)
    - **Property 4: Duplicate lead detection**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Ingest a lead, then attempt same lead_id again, verify 409 with existing matter_id
    - **Validates: Requirements 1.3**

  - [ ]* 3.5 Write property test for valid lead response (Property 5)
    - **Property 5: Valid lead produces correct response**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Generate valid lead payloads, verify response contains non-empty matter_id, collection_id, status="processing"
    - **Validates: Requirements 1.6**

  - [ ]* 3.6 Write property test for Matter/Collection field mapping (Property 6)
    - **Property 6: Matter and Collection field mapping from lead**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Generate valid leads, verify matter_name=title, description=summary, matter_type='lead_investigation', collection_name='Lead: {lead_id}'
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 3.7 Write property test for S3 round-trip (Property 7)
    - **Property 7: Lead JSON S3 round-trip**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Serialize lead JSON to S3, read back, verify identical subjects/connections/evidence_hints/osint_directives/tags/statutes
    - **Validates: Requirements 2.3, 12.1, 12.3**

  - [ ]* 3.8 Write property test for JSONB round-trip (Property 8)
    - **Property 8: Lead metadata Aurora JSONB round-trip**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Store lead_metadata subset as JSONB, read back, verify equivalent dict
    - **Validates: Requirements 2.4, 12.2**

  - [ ]* 3.9 Write property test for status transitions (Property 16)
    - **Property 16: Lead status transitions are valid**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Verify status only transitions through accepted → seeding_graph → researching → pipeline_running → indexed, or to error from any state
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 3.10 Write property test for error status (Property 17)
    - **Property 17: Error at any phase sets error status**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Simulate errors at each phase, verify lead_status='error' and non-empty error_details
    - **Validates: Requirements 7.3**

- [x] 4. Checkpoint — Ensure lead ingestion service passes
  - Ensure all tests pass, ask the user if questions arise.


- [x] 5. Neptune graph seeding
  - [x] 5.1 Add Neptune seeding to `src/services/lead_ingestion_service.py`
    - Implement seed_neptune_graph(matter, payload) returning {subjects_seeded, connections_seeded, failures}
    - Use Neptune HTTP API via _gremlin_http() pattern from graph_load_handler.py (not WebSocket)
    - For each subject: g.addV(Entity_{matter_id}).property('canonical_name', name).property('entity_type', type).property('confidence', 1.0).property('occurrence_count', 1).property('case_file_id', matter_id)
    - For subjects with aliases: add multi-value 'aliases' property
    - For subjects with identifiers: add 'id_{key}' properties (e.g. id_ein, id_ssn_last4)
    - For each connection: g.V().has(label, 'canonical_name', from).addE('RELATED_TO').to(g.V().has(label, 'canonical_name', to)).property('relationship_type', rel).property('confidence', conf).property('source_document_ref', 'lead:{lead_id}')
    - Individual failures logged and counted, do not halt processing
    - If ALL subjects fail, set lead_status to 'error'
    - Use 15-second timeout per query (consistent with patterns.py)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 5.2 Write property test for Neptune subject node creation (Property 9)
    - **Property 9: Neptune subject node creation**
    - Test file: `tests/unit/test_neptune_lead_seeding.py`
    - Generate N subjects, verify N entity nodes created with correct properties
    - **Validates: Requirements 3.1**

  - [ ]* 5.3 Write property test for Neptune connection edge creation (Property 10)
    - **Property 10: Neptune connection edge creation**
    - Test file: `tests/unit/test_neptune_lead_seeding.py`
    - Generate M connections, verify M RELATED_TO edges with correct properties
    - **Validates: Requirements 3.2**

  - [ ]* 5.4 Write property test for Neptune optional properties (Property 11)
    - **Property 11: Neptune optional properties for aliases and identifiers**
    - Test file: `tests/unit/test_neptune_lead_seeding.py`
    - Generate subjects with aliases and identifiers, verify properties stored correctly
    - **Validates: Requirements 3.3, 3.4**

- [x] 6. AI Research Agent
  - [x] 6.1 Create `src/services/ai_research_agent.py`
    - Implement AIResearchAgent.__init__(bedrock_client=None) with optional client for testing
    - Implement _build_research_prompt(subject, osint_directives, evidence_hints) building structured prompt
    - Implement _call_bedrock(prompt) calling Bedrock Haiku with retry (2 retries, exponential backoff 2s/4s)
      - Model: anthropic.claude-3-haiku-20240307-v1:0 (from BEDROCK_LLM_MODEL_ID env var)
      - Max tokens: 4096, Temperature: 0.3
      - Timeout: read_timeout=120, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"}
    - Implement research_subject(subject, osint_directives, evidence_hints) returning research text
      - Include subject name, type, role, aliases, identifiers in prompt
      - Include OSINT directives and evidence hints
      - Return structured text with sections: PUBLIC RECORDS, NEWS AND MEDIA, REGULATORY, EVIDENCE HINTS, OSINT FINDINGS, CONNECTIONS
    - Implement research_all_subjects(subjects, osint_directives, evidence_hints) returning list of result dicts
      - Process subjects sequentially
      - Each result: {subject_name, slug, research_text, success, error}
      - Continue on individual subject failure
    - _Requirements: 4.1, 4.2, 4.3, 4.6_

  - [ ]* 6.2 Write property test for one research document per subject (Property 12)
    - **Property 12: One structured research document per subject**
    - Test file: `tests/unit/test_ai_research_agent.py`
    - Generate N subjects, verify N result entries with matching subject_names
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 6.3 Write property test for evidence hints in research docs (Property 13)
    - **Property 13: Evidence hints included in research documents**
    - Test file: `tests/unit/test_ai_research_agent.py`
    - Generate evidence hints referencing subjects, verify description appears in research text
    - **Validates: Requirements 4.3**

- [x] 7. Checkpoint — Ensure Neptune seeding and AI Research Agent pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Pipeline integration and full orchestration
  - [x] 8.1 Add research document storage and pipeline triggering to `src/services/lead_ingestion_service.py`
    - After AI research completes, store each research doc in S3 at {collection_s3_prefix}research/{slug}.txt
      - slug: lowercase, spaces→underscores, strip non-alphanumeric
    - Register each research doc in Aurora documents table with case_file_id=matter_id, collection_id, source_metadata={"source": "ai_research_agent", "subject": subject_name, "lead_id": lead_id}
    - Trigger existing Step Functions pipeline via boto3 sfn.start_execution with case_id and upload_result
    - Update lead_status through transitions: seeding_graph → researching → pipeline_running
    - _Requirements: 4.4, 4.5, 5.1, 5.2, 5.3, 5.4_

  - [x] 8.2 Implement full ingest_lead() orchestration in `src/services/lead_ingestion_service.py`
    - Wire together: validate → check_duplicate → create_matter_from_lead → seed_neptune_graph → research_all_subjects → store_research_docs → trigger_pipeline
    - Return {matter_id, collection_id, status: "processing", lead_id}
    - Wrap each phase in try/except, set lead_status='error' with descriptive error_details on failure
    - Use update_lead_status at each phase transition
    - _Requirements: 1.6, 7.1, 7.2, 7.3_

  - [ ]* 8.3 Write property test for research document S3 path (Property 14)
    - **Property 14: Research document S3 storage path**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Generate subject names with special characters, verify slug and S3 path correctness
    - **Validates: Requirements 4.4**

  - [ ]* 8.4 Write property test for research document Aurora registration (Property 15)
    - **Property 15: Research document Aurora registration**
    - Test file: `tests/unit/test_lead_ingestion_service.py`
    - Verify documents table row has correct case_file_id, collection_id, source_metadata
    - **Validates: Requirements 5.1**

- [x] 9. API handlers and mega-dispatcher wiring
  - [x] 9.1 Create `src/lambdas/api/leads.py` — thin API handler module
    - Implement handle_ingest(event, context) for POST /leads/ingest
      - Parse JSON body, call LeadIngestionService.ingest_lead()
      - Return success_response(result, 202, event) on success
      - Return error_response(400, "VALIDATION_ERROR", ...) for validation errors
      - Return error_response(409, "CONFLICT", ...) for duplicate lead_id
      - Return error_response(500, "INTERNAL_ERROR", ...) for unexpected errors
    - Implement handle_lead_status(event, context) for GET /leads/{lead_id}/status
      - Extract lead_id from pathParameters
      - Call LeadIngestionService.get_lead_status(lead_id)
      - Return 200 with status summary or 404 if not found
    - Implement handle_matter_lead(event, context) for GET /matters/{id}/lead
      - Extract matter_id from pathParameters
      - Call LeadIngestionService.get_lead_metadata(matter_id, org_id)
      - Return 200 with lead metadata or 404 if not found
    - Use existing response_helper.py pattern (success_response, error_response, CORS_HEADERS)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 9.2 Extend `src/lambdas/api/case_files.py` mega-dispatcher with lead routes
    - Add to _normalize_resource(): handle /leads/{lead_id}/status path parameter extraction
      - When parts[0] == "leads" and i == 1 and part is not "ingest": extract lead_id
    - Add to dispatch_handler() BEFORE the case-file CRUD catch-all:
      - Route /leads/ingest POST → leads.handle_ingest
      - Route /leads/{lead_id}/status GET → leads.handle_lead_status
      - Route /matters/{id}/lead GET → leads.handle_matter_lead (within existing /matters/ block or as new block)
    - DO NOT REWRITE dispatch_handler — only ADD new routing blocks
    - Follow the exact pattern used by existing routes (lazy import, path matching)
    - Per lessons-learned: EXTEND, never REPLACE case_files.py
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 9.3 Write unit tests for API handlers in `tests/unit/test_leads_handler.py`
    - Test handle_ingest with valid payload → 202
    - Test handle_ingest with invalid payload → 400
    - Test handle_ingest with duplicate lead_id → 409
    - Test handle_lead_status with known lead_id → 200
    - Test handle_lead_status with unknown lead_id → 404
    - Test handle_matter_lead with lead matter → 200
    - Test dispatcher routes /leads/* correctly
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 10. Final checkpoint — Ensure all Phase A tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 11. Phase C — Autonomous Investigation Agent (aspirational)
  - [ ]* 11.1 Create graph snapshot builder service
    - Query Neptune for all entities and edges under matter's subgraph label
    - Compute centrality scores and community clusters via Gremlin traversals
    - _Requirements: 9.1_

  - [ ]* 11.2 Create gap analyzer and hypothesis generator
    - Send graph snapshot to Bedrock Haiku to identify gaps (few connections, missing relationship types, lacking evidence)
    - Generate scored hypotheses with confidence, evidence references, and research task lists
    - _Requirements: 9.2, 9.3_

  - [ ]* 11.3 Create investigation loop controller
    - Implement loop: snapshot → analyze → plan → research → ingest → re-analyze
    - Enforce max_iterations, confidence_threshold, max_research_documents, timeout_minutes
    - Save state to S3 at {matter_s3_prefix}/agent_state/state.json for pause/resume
    - _Requirements: 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 11.4 Create human-in-the-loop API endpoints
    - POST /matters/{id}/agent/start — start autonomous loop
    - GET /matters/{id}/agent/status — current iteration, hypotheses, loop state
    - POST /matters/{id}/agent/directive — add directive, pause, resume, terminate
    - GET /matters/{id}/agent/report — final or partial summary report
    - Wire through case_files.py mega-dispatcher
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Phase A tasks (1-10) are implementable now — these are the ones to execute
- Phase C tasks (11.*) are aspirational — the user will implement independently
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)`
- Per lessons-learned: all changes EXTEND existing code, never REPLACE working modules
- The mega-dispatcher extension (9.2) adds routing blocks to case_files.py — it does NOT rewrite the file
- Neptune seeding uses HTTP API (_gremlin_http pattern), not WebSocket
- Bedrock calls use the same model/timeout config as existing services
- All handlers use the existing response_helper.py pattern
