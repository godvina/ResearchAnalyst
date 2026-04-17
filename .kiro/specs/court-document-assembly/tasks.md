# Implementation Plan: Court Document Assembly

## Overview

Implements AI-powered court document generation with section-level decision workflow, version control, multi-format export, discovery tracking, and USSG calculations. Builds on existing prosecutor-case-review infrastructure (DecisionWorkflowService, Evidence_Matrix, ai_decisions). Order: schema → models → service (generators, version control, export, discovery, USSG) → Lambda handler → API routes → frontend → integration.

## Tasks

- [x] 1. Create Aurora schema migration for document assembly tables
  - [x] 1.1 Create migration file `infra/migrations/004_court_document_assembly.sql`
    - Define `document_drafts` table with case_id FK, document_type CHECK constraint, status CHECK, sign-off fields, is_work_product flag
    - Define `document_sections` table with draft_id FK, section_type, section_order, content, decision_id FK to ai_decisions, UNIQUE(draft_id, section_order)
    - Define `document_versions` table with draft_id FK, version_number, content_snapshot JSONB, changed_sections JSONB, author fields, UNIQUE(draft_id, version_number)
    - Define `document_templates` table with template_type CHECK, template_content, section_definitions JSONB
    - Define `discovery_documents` table with case_id FK, document_id, privilege_category CHECK (6 values incl pending), production_status CHECK, privilege fields, disclosure_alert, waiver_flag, decision_id FK, UNIQUE(case_id, document_id)
    - Define `production_sets` table with case_id FK, production_number, recipient, document_ids JSONB, UNIQUE(case_id, production_number)
    - Define `ussg_guidelines` table with statute_citation, base_offense_level, specific_offense_characteristics JSONB, chapter_adjustments JSONB
    - Create all indexes per design (idx_document_drafts_case, idx_document_drafts_type, idx_document_drafts_status, idx_document_sections_draft, idx_document_sections_decision, idx_document_versions_draft, idx_discovery_documents_case, idx_discovery_documents_category, idx_discovery_documents_status, idx_production_sets_case, idx_ussg_guidelines_statute)
    - _Requirements: 9.5, 12.2, 7.1, 7.6_

- [x] 2. Create Pydantic models for document assembly
  - [x] 2.1 Create `src/models/document_assembly.py` with all enums and models
    - Define enums: DocumentType (11 values), DocumentStatus (4 values), PrivilegeCategory (6 values), ProductionStatus (3 values), WitnessRole (5 values), ExhibitType (4 values)
    - Define models: DocumentSection, DocumentDraft, DocumentVersion, VersionDiff, WitnessEntry, ExhibitEntry, GuidelineCalculation, DiscoveryDocument, ProductionSet, DiscoveryStatus, PrivilegeLogEntry
    - All models per design Pydantic section
    - _Requirements: 9.2, 7.2, 5.3_

  - [ ]* 2.2 Write unit tests for Pydantic model validation
    - Test enum membership for all 6 enums
    - Test DocumentDraft serialization round-trip
    - Test GuidelineCalculation range constraint (low <= high)
    - Test DiscoveryStatus count fields
    - _Requirements: 9.2, 5.3_

- [x] 3. Implement DocumentAssemblyService core and indictment generator
  - [x] 3.1 Create `src/services/document_assembly_service.py` with constructor and constants
    - Implement `__init__` with aurora_cm, neptune_endpoint, neptune_port, bedrock_client, decision_workflow_svc, element_assessment_svc, case_weakness_svc, precedent_analysis_svc
    - Define SENIOR_LEGAL_ANALYST_PERSONA, DOCUMENT_TYPES, PAGE_SIZE=1000, MAX_BEDROCK_TOKENS=100000, ASYNC_THRESHOLD=10000
    - Implement `_gather_evidence_data` with paginated Aurora queries (batches of 1000)
    - Implement `_summarize_for_bedrock` to fit within MAX_BEDROCK_TOKENS
    - Implement `_invoke_bedrock_section` with Senior_Legal_Analyst_Persona system prompt
    - _Requirements: 9.1, 9.3, 9.4, 13.1, 13.2, 13.4_

  - [x] 3.2 Implement `generate_document` orchestration method
    - Validate document_type against DOCUMENT_TYPES
    - Check evidence count against ASYNC_THRESHOLD; return {status: 'processing'} if exceeded
    - Dispatch to type-specific generator (_generate_indictment, _generate_evidence_summary, etc.)
    - Create AI_Proposed decision for each section via DecisionWorkflowService
    - Store DocumentDraft with all sections in Aurora
    - Handle Bedrock unavailability: return partial document with deterministic sections and warnings
    - _Requirements: 9.2, 9.4, 9.7, 13.3_

  - [x] 3.3 Implement `_generate_indictment` generator
    - Generate caption section from case metadata (case number, district court, defendant names from Neptune, statute citations)
    - Generate one count section per charge from Evidence_Matrix statutory elements
    - Generate factual basis section per count with evidence citations
    - Generate overt acts section with chronologically ordered events from Neptune
    - Generate forfeiture allegations section from Neptune asset/financial entities
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 3.4 Write property test for document structural completeness
    - **Property 1: Document structural completeness**
    - Generate random document types with case data, verify all required sections present per type
    - **Validates: Requirements 1.1, 2.1, 5.1, 6.1**

  - [ ]* 3.5 Write property test for section-decision invariant
    - **Property 2: Section-decision invariant**
    - Generate random documents, verify decision count equals section count and all decisions are AI_Proposed
    - **Validates: Requirements 1.7, 2.7, 3.7, 4.6, 5.7, 6.7, 7.8, 8.7**

  - [ ]* 3.6 Write property test for attorney sign-off invariant
    - **Property 3: Attorney sign-off requires all sections reviewed**
    - Generate random documents with various section states, verify sign-off constraints
    - **Validates: Requirements 1.8, 5.8, 8.8**

  - [ ]* 3.7 Write property test for caption required fields
    - **Property 4: Caption section contains required fields**
    - Generate random case metadata, verify caption contains case number, court, defendant name, statute citation
    - **Validates: Requirements 1.3**

  - [ ]* 3.8 Write property test for overt acts chronological ordering
    - **Property 5: Overt acts chronological ordering**
    - Generate random lists of dated events, verify chronological ordering in output
    - **Validates: Requirements 1.5**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement evidence summary, witness list, and exhibit list generators
  - [x] 5.1 Implement `_generate_evidence_summary` generator
    - Generate one section per statutory element from Evidence_Matrix
    - Include evidence items with strength ratings (green/yellow/red) and source document references
    - Include evidence chain subsections (source system, ingestion timestamp, analysis method)
    - Generate AI narrative summaries per evidence category (documentary, testimonial, physical, digital)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6_

  - [x] 5.2 Implement `_gather_witness_data` and `_generate_witness_list` generator
    - Query Neptune for person entities with document co-occurrence >= 2
    - Classify witnesses by role (victim, fact_witness, expert_witness, cooperating_witness, law_enforcement)
    - Generate testimony summaries and credibility assessments via Bedrock
    - Flag impeachment issues from Case_Weakness_Analyzer conflicting statements
    - Paginate Neptune traversals in batches of 10,000 for large cases
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8_

  - [x] 5.3 Implement `_gather_exhibit_data` and `_generate_exhibit_list` generator
    - Produce numbered exhibit index from Aurora documents and Neptune entity links
    - Categorize exhibits by type via Bedrock (documentary, physical, digital, testimonial)
    - Link exhibits to statutory elements from element_assessments (green/yellow ratings only)
    - Generate authentication notes from evidence chain metadata
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 5.4 Write property test for witness co-occurrence filter
    - **Property 6: Witness co-occurrence filter**
    - Generate random person entities with varying co-occurrence counts, verify only count >= 2 included
    - **Validates: Requirements 3.1**

  - [ ]* 5.5 Write property test for witness entry completeness
    - **Property 7: Witness entry completeness and role domain**
    - Generate random witness entries, verify all required fields and role in valid domain
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 5.6 Write property test for impeachment flags
    - **Property 8: Impeachment flags from weakness data**
    - Generate random witnesses with/without conflicting statements, verify flags present when conflicts exist
    - **Validates: Requirements 3.5, 3.6**

  - [ ]* 5.7 Write property test for exhibit numbering
    - **Property 9: Exhibit sequential numbering and type domain**
    - Generate random exhibit lists, verify sequential numbering 1..N and valid types
    - **Validates: Requirements 4.1, 4.3**

  - [ ]* 5.8 Write property test for exhibit element linkage
    - **Property 10: Exhibit element linkage filter**
    - Generate random exhibits with element assessments of varying ratings, verify only green/yellow linked
    - **Validates: Requirements 4.4**

- [x] 6. Implement version control and attorney sign-off
  - [x] 6.1 Implement `sign_off_document` method
    - Verify all sections are Human_Confirmed or Human_Overridden (reject if any AI_Proposed)
    - Record attorney_id, attorney_name, sign_off_at timestamp
    - Update document_drafts status to 'final'
    - Return 400 if unreviewed sections, 409 if already final
    - _Requirements: 1.8, 5.8, 8.8_

  - [x] 6.2 Implement version control methods
    - Implement `create_version`: snapshot content_snapshot JSONB, record changed_sections, increment version_number
    - Implement `get_version_history`: chronological list with author, timestamp, changed sections
    - Implement `get_version`: retrieve specific historical version
    - Implement `compare_versions`: section-level diffs between two versions
    - Implement `update_section_content`: update section, create new version, handle concurrent updates with ON CONFLICT retry
    - _Requirements: 8.5, 12.1, 12.2, 12.3, 12.6_

  - [ ]* 6.3 Write property test for version history growth
    - **Property 21: Version history growth on section state change**
    - Generate random documents with N state transitions, verify N+1 versions with monotonic numbering
    - **Validates: Requirements 12.1, 12.2**

  - [ ]* 6.4 Write property test for document draft round-trip
    - **Property 20: Document draft round-trip**
    - Generate random DocumentDrafts, store and retrieve, verify equality of all fields
    - **Validates: Requirements 9.2, 9.5**

- [x] 7. Implement sentencing memorandum, case brief, and USSG calculator
  - [x] 7.1 Implement `compute_sentencing_guidelines` (USSG calculator)
    - Compute base offense level from statute
    - Apply specific offense characteristics (level adjustments)
    - Apply chapter adjustments
    - Clamp total offense level to 1-43
    - Cross-reference with criminal history category (1-6) to produce guideline range in months
    - Ensure guideline_range_months_low <= guideline_range_months_high
    - _Requirements: 5.3_

  - [x] 7.2 Implement `_generate_sentencing_memo` generator
    - Generate sections: introduction, offense conduct narrative, criminal history, USSG calculations, aggravating factors, mitigating factors, victim impact, recommendation
    - Cite precedent cases from Precedent_Analysis_Service (case name, citation, sentence, factual similarity)
    - Extract aggravating factors from Evidence_Matrix (leadership role, vulnerable victims, obstruction)
    - Extract mitigating factors from case documents (cooperation, acceptance of responsibility)
    - Include victim impact summary from Neptune victim entities
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.6_

  - [x] 7.3 Implement `_generate_case_brief` generator
    - Generate sections: case overview, investigation summary, evidence analysis, legal theory, anticipated defenses, trial strategy
    - Set is_work_product = true on the DocumentDraft
    - Include risk assessment with Prosecution_Readiness_Score and risk rating (Low/Medium/High)
    - Generate anticipated defenses from Case_Weakness_Analyzer weaknesses
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.8_

  - [x] 7.4 Implement `_generate_template_filing` for template-based documents
    - Load template from document_templates table
    - Resolve {{placeholders}} with case data (case number, defendant names, statute citations, evidence references)
    - Generate AI legal argument sections via Bedrock
    - Support: motion_in_limine, motion_to_compel, response_to_motion, notice_of_evidence, plea_agreement
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 7.5 Write property test for USSG guideline calculation
    - **Property 11: USSG guideline calculation**
    - Generate random offense levels (1-43), adjustments, criminal history categories (1-6), verify total clamped 1-43 and range_low <= range_high
    - **Validates: Requirements 5.3**

  - [ ]* 7.6 Write property test for sentencing memo citations
    - **Property 12: Sentencing memorandum cites precedent**
    - Generate random sentencing memos with precedent data, verify precedent case name and USSG reference present
    - **Validates: Requirements 5.4**

  - [ ]* 7.7 Write property test for case brief work product
    - **Property 13: Case brief work product exclusion**
    - Generate random case briefs, verify is_work_product = true
    - **Validates: Requirements 6.8**

  - [ ]* 7.8 Write property test for case brief risk rating
    - **Property 14: Case brief risk rating domain**
    - Generate random case briefs, verify risk rating in {Low, Medium, High}
    - **Validates: Requirements 6.5**

  - [ ]* 7.9 Write property test for template placeholder resolution
    - **Property 19: Template placeholder resolution**
    - Generate random templates with placeholders and case data, verify no unresolved {{...}} patterns
    - **Validates: Requirements 8.2**

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement multi-format export
  - [x] 9.1 Implement `export_document` method with format dispatch
    - Implement `_render_html`: HTML preview with section headers, content, decision state badges
    - Implement `_render_pdf`: Court_Filing_Format (Times New Roman 12pt, double-spaced, 1-inch margins, page numbering)
    - Implement `_render_docx`: DOCX for editing with proper formatting
    - Validate format parameter (html, pdf, docx); return 400 for invalid
    - _Requirements: 2.5, 4.7, 8.4, 8.6, 9.6_

- [x] 10. Implement discovery tracking
  - [x] 10.1 Implement discovery tracking methods in DocumentAssemblyService
    - Implement `categorize_document_privilege`: auto-categorize via Bedrock into 5 Privilege_Categories, create AI_Proposed decision
    - Implement `get_discovery_status`: return dashboard counts by privilege category and production status
    - Implement `create_production_set`: create Production_Set with metadata, validate document_ids exist
    - Implement `generate_privilege_log`: generate privilege log entries for all withheld documents
    - Implement Brady auto-alert: set disclosure_alert=true and timestamp when category=brady_material
    - Implement Jencks witness linkage: require linked_witness_id when category=jencks_material
    - Implement privilege waiver detection: set waiver_flag=true when produced document category changes to privileged
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_

  - [ ]* 10.2 Write property test for privilege category domain and Brady alert
    - **Property 15: Discovery privilege category domain and Brady alert**
    - Generate random discovery documents with all categories, verify domain and Brady alert invariant
    - **Validates: Requirements 7.2, 7.3**

  - [ ]* 10.3 Write property test for Jencks witness linkage
    - **Property 16: Jencks material witness linkage**
    - Generate random Jencks material documents, verify linked_witness_id non-null
    - **Validates: Requirements 7.4**

  - [ ]* 10.4 Write property test for dashboard count invariant
    - **Property 17: Discovery dashboard count invariant**
    - Generate random sets of discovery documents, verify privilege counts sum to total and production status counts sum to total
    - **Validates: Requirements 7.7**

  - [ ]* 10.5 Write property test for privilege waiver detection
    - **Property 18: Privilege waiver detection**
    - Generate random produced documents, change category to privileged, verify waiver_flag=true
    - **Validates: Requirements 7.9**

  - [ ]* 10.6 Write property test for privilege log completeness
    - **Property 23: Privilege log completeness for withheld documents**
    - Generate random withheld documents, verify privilege log entries with non-empty description and doctrine
    - **Validates: Requirements 7.5**

  - [ ]* 10.7 Write property test for production set metadata
    - **Property 24: Production set metadata completeness**
    - Generate random production sets, verify production_number > 0, valid date, non-empty recipient, non-empty document_ids, document_count = len(document_ids)
    - **Validates: Requirements 7.6**

- [x] 11. Implement async generation threshold
  - [x] 11.1 Implement async threshold logic in `generate_document`
    - When evidence count > ASYNC_THRESHOLD (10,000), return 202 with {status: 'processing', draft_id}
    - When evidence count <= 10,000, return complete DocumentDraft with status='draft'
    - Handle Lambda timeout approaching (>800s): save partial document with completed sections, status='processing'
    - _Requirements: 13.3, 13.5_

  - [ ]* 11.2 Write property test for async threshold behavior
    - **Property 22: Async threshold behavior**
    - Generate random evidence counts above and below 10,000, verify response status
    - **Validates: Requirements 13.3**

- [x] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Create Lambda handler and API routes
  - [x] 13.1 Create `src/lambdas/api/document_assembly.py` Lambda handler
    - Implement `dispatch_handler` with route table matching existing cross_case.py pattern
    - Implement `_build_document_assembly_service` constructor with all dependencies from environment
    - Implement `generate_handler`: parse body, call generate_document, return DocumentDraft JSON
    - Implement `list_documents_handler`: parse query params (document_type, status), call list_documents
    - Implement `get_document_handler`: parse path param doc_id, call get_document
    - Implement `sign_off_handler`: parse body (attorney_id, attorney_name), call sign_off_document
    - Implement `export_handler`: parse query param format, call export_document, return binary response with correct Content-Type
    - Implement `get_discovery_handler`: call get_discovery_status
    - Implement `produce_handler`: parse body (recipient, document_ids), call create_production_set
    - Add CORS headers for OPTIONS preflight
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [ ]* 13.2 Write unit tests for Lambda handler routing
    - Test dispatch_handler routes correctly for each HTTP method/resource combination
    - Test CORS preflight returns correct headers
    - Test 404 for unknown routes
    - Test error responses for invalid inputs
    - _Requirements: 10.8_

  - [x] 13.3 Add API Gateway route definitions to `infra/api_gateway/api_definition.yaml`
    - Add all 7 new routes per design: generate, list, get, sign-off, export, discovery status, produce
    - Add OPTIONS methods for CORS preflight on each route
    - Add Lambda integration for document_assembly handler
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [x] 14. Create frontend document assembly page
  - [x] 14.1 Create `src/frontend/document_assembly.html`
    - Follow same layout patterns as prosecutor.html with orange (#f6ad55) accent
    - Implement document type selector dropdown (11 document types) with optional statute and defendant selectors
    - Implement document generation panel with Generate button, progress indicator, async polling for large cases
    - Implement section review panel with expandable sections, decision state badges (yellow/green/blue), Accept and Override buttons
    - Implement inline text editor for section overrides, pre-populated with AI content
    - Implement Attorney Sign-Off panel: enabled only when all sections confirmed/overridden, attorney identity field, disabled tooltip when sections unreviewed
    - Implement export buttons: HTML preview, PDF download, DOCX download
    - Implement version history panel: chronological version list, side-by-side comparison for two selected versions
    - Implement Discovery Production tab: production status dashboard, privilege categorization review with Accept/Override, production set management, privilege log viewer/exporter
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 12.4, 12.5_

  - [x] 14.2 Add document assembly navigation link to prosecutor.html
    - Add link/button to document_assembly.html in prosecutor navigation
    - _Requirements: 11.1_

- [x] 15. Integration wiring and final validation
  - [x] 15.1 Wire `_gather_conspirator_data` to conspiracy-network-discovery's conspirator_profiles table
    - Query conspirator_profiles for co-conspirator data used in indictment and case brief generators
    - _Requirements: 1.1, 6.1_

  - [x] 15.2 Wire `get_section`, `list_documents`, `get_document` query methods
    - Implement `get_section` to retrieve single section with decision state
    - Implement `list_documents` with filtering by document_type and status
    - Implement `get_document` with full sections, version history, and decision states
    - _Requirements: 10.2, 10.3_

  - [ ]* 15.3 Write integration tests for end-to-end document generation flow
    - Test generate indictment → review sections → sign off → export PDF
    - Test discovery categorization → production set creation → privilege log generation
    - Test version history after multiple section overrides
    - Test async threshold with mocked large evidence set
    - _Requirements: 9.2, 9.5, 9.6, 12.1, 13.3_

- [x] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (24 total across Properties 1-24)
- The design uses Python throughout; all code in Python with Hypothesis for property-based tests
- Reuses existing DecisionWorkflowService, ElementAssessmentService, CaseWeaknessService, PrecedentAnalysisService via constructor injection
