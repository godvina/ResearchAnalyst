# Implementation Plan: Bulk Ingestion & Triage

## Overview

Extends the matter-collection-hierarchy with Customer fields, Cases, Bulk Ingestion Jobs, multi-modal processing, AI classification with auto-routing, triage queue, deduplication, and chain-of-custody. Implementation proceeds: schema migration → Pydantic models → core services (CaseService, BulkIngestionService, MediaTypeDetector, DeduplicationService, ChainOfCustodyService) → classification and triage services → Pipeline Wizard → Step Functions extension → API handlers → wiring and integration. Each step builds on the previous.

## Tasks

- [-] 1. Aurora schema migration and Pydantic models
  - [x] 1.1 Create Aurora migration `src/db/migrations/007_bulk_ingestion_triage.sql`
    - ALTER organizations table: add customer_code (TEXT UNIQUE), primary_contact (TEXT), contract_tier (TEXT DEFAULT 'standard'), onboarded_at (TIMESTAMPTZ)
    - ALTER matters table: add parent_type (TEXT DEFAULT 'matter')
    - CREATE cases table: case_id UUID PK, matter_id FK, org_id FK, docket_number, case_title, judge, parties JSONB, filing_date, case_status, court_jurisdiction, created_at, last_activity with indexes
    - CREATE bulk_ingestion_jobs table: all fields from design (job_id, customer_id FK, job_name, source_description, status, ingestion_mode, target_matter_id FK, target_case_id FK, pipeline_config JSONB, all counters, timestamps) with indexes
    - ALTER triage_queue table: add job_id FK, ai_suggestions JSONB, extracted_entities JSONB, document_type, assigned_matter_id FK, assigned_case_id FK
    - ALTER documents table: add job_id FK, case_id FK, media_type, file_hash, processing_status, chain_of_custody JSONB, bates_number, original_filepath, is_duplicate, duplicate_of, source_media_type, parsed_text with indexes
    - CREATE document_hashes table: hash_id UUID PK, customer_id FK, file_hash, document_id, UNIQUE(customer_id, file_hash)
    - _Requirements: 1.1, 2.1, 2.2, 3.1, 4.2, 7.3, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ] 1.2 Create Pydantic models in `src/models/bulk_ingestion.py`
    - Define Customer (extends Organization), CaseStatus, Case, IngestionMode, JobStatus, BulkIngestionJob (with throughput_rate and estimated_completion_time properties), MediaType, DocumentProcessingStatus, TriageStatus, TriageItem, ChainOfCustodyEvent models per design
    - Add BulkIngestionJob.throughput_rate computed property (processed_count / elapsed seconds)
    - Add BulkIngestionJob.estimated_completion_time computed property (remaining / throughput_rate)
    - Export new models from `src/models/__init__.py`
    - _Requirements: 1.1, 1.2, 2.2, 3.1, 3.3, 3.4, 7.3, 13.1, 17.1_

  - [ ]* 1.3 Write property test for Customer creation round trip
    - **Property 1: Customer creation round trip**
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 1.4 Write property test for Case creation round trip and Matter validation
    - **Property 4: Case creation round trip and Matter validation**
    - **Validates: Requirements 2.2, 2.3, 2.4, 11.1**

  - [ ]* 1.5 Write property test for Bulk Ingestion Job creation round trip
    - **Property 7: Bulk Ingestion Job creation round trip**
    - **Validates: Requirements 3.1, 3.2, 11.2**

  - [ ]* 1.6 Write property test for Job metrics computation
    - **Property 8: Job metrics computation**
    - **Validates: Requirements 3.3, 3.4**

- [ ] 2. Checkpoint — Ensure migration and models are correct
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. CaseService and Customer extensions
  - [ ] 3.1 Extend `src/services/organization_service.py` with Customer fields
    - Add methods to update customer_code, primary_contact, contract_tier, onboarded_at on existing organizations
    - Add `get_customer(org_id)` returning Organization with customer fields populated
    - Ensure all queries enforce tenant isolation by org_id
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ] 3.2 Create `src/services/case_service.py`
    - Implement CaseService with create_case, get_case, list_cases, update_status
    - create_case validates matter_id exists and belongs to same org_id
    - list_cases filters by matter_id and org_id
    - update_status enforces valid CaseStatus transitions
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [ ] 3.3 Extend `src/services/matter_service.py` with cascade behavior
    - Add archive cascade: when Matter is archived, cascade status to all child Cases
    - Add parent_type field support
    - _Requirements: 2.6_

  - [ ]* 3.4 Write property test for hierarchy chain integrity
    - **Property 5: Hierarchy chain integrity**
    - **Validates: Requirements 2.5**

  - [ ]* 3.5 Write property test for Matter archive cascades to child Cases
    - **Property 6: Matter archive cascades to child Cases**
    - **Validates: Requirements 2.6**

  - [ ]* 3.6 Write property test for tenant isolation across bulk ingestion data
    - **Property 2: Tenant isolation across bulk ingestion data**
    - **Validates: Requirements 1.3**

- [ ] 4. BulkIngestionService and ChainOfCustodyService
  - [ ] 4.1 Create `src/services/bulk_ingestion_service.py`
    - Implement BulkIngestionService with create_job, stage_files, start_processing, get_job_status, get_job_documents, get_job_breakdown, increment_counter
    - create_job validates customer_id, sets status to "created", initializes all counters to 0
    - stage_files uploads to `orgs/{customer_id}/bulk-staging/{job_id}/raw/`, creates document records with NULL matter_id/case_id
    - start_processing transitions job to "processing", dispatches documents to SQS
    - increment_counter uses atomic SQL UPDATE (not read-modify-write)
    - get_job_status computes throughput_rate and estimated_completion_time
    - Validate ingestion_mode: if pre_assigned, require target_matter_id; if hybrid, require target_matter_id
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 9.1, 9.2, 10.1, 14.1, 14.5, 14.6_

  - [ ] 4.2 Create `src/services/chain_of_custody_service.py`
    - Implement ChainOfCustodyService with record_event and get_chain
    - record_event appends to chain_of_custody JSONB array (append-only, never modify/delete)
    - Each event includes event_type, timestamp, actor, details
    - _Requirements: 17.1, 17.2, 17.4_

  - [ ]* 4.3 Write property test for Job and document state machine validity
    - **Property 9: Job and document state machine validity**
    - **Validates: Requirements 3.5, 4.4**

  - [ ]* 4.4 Write property test for staging S3 prefix isolation
    - **Property 10: Staging S3 prefix isolation**
    - **Validates: Requirements 4.1, 10.1**

  - [ ]* 4.5 Write property test for staged documents have NULL routing
    - **Property 11: Staged documents have NULL routing**
    - **Validates: Requirements 4.2**

  - [ ]* 4.6 Write property test for counter consistency invariant
    - **Property 13: Counter consistency invariant**
    - **Validates: Requirements 5.4, 6.6, 7.5, 9.2, 13.3**

  - [ ]* 4.7 Write property test for concurrent job isolation
    - **Property 3: Concurrent job isolation**
    - **Validates: Requirements 1.4, 3.6, 10.3**

  - [ ]* 4.8 Write property test for chain of custody append-only integrity
    - **Property 30: Chain of custody append-only integrity**
    - **Validates: Requirements 17.1, 17.2, 17.4**

- [ ] 5. Checkpoint — Ensure core services pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. MediaTypeDetector and DeduplicationService
  - [ ] 6.1 Create `src/services/media_type_detector.py`
    - Implement MediaTypeDetector with MEDIA_TYPE_MAP, detect, is_scanned_pdf, scan_staged_files
    - detect returns media_type from extension and MIME type: document, image, audio, video, spreadsheet, email, database, other
    - is_scanned_pdf tests PDF readability (text per page < configurable threshold, default 50 chars)
    - scan_staged_files scans up to sample_size files from S3 prefix, returns media type distribution
    - _Requirements: 13.1, 13.2, 13.6_

  - [ ] 6.2 Create `src/services/deduplication_service.py`
    - Implement DeduplicationService with compute_hash, check_exact_duplicate, check_near_duplicate, get_job_dedup_stats
    - compute_hash returns SHA-256 of file content
    - check_exact_duplicate queries document_hashes table for matching hash within same customer
    - check_near_duplicate uses embedding cosine similarity with configurable threshold (default 0.95)
    - get_job_dedup_stats returns {exact_duplicate_count, near_duplicate_count} for a job
    - _Requirements: 10.4, 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 6.3 Write property test for media type detection and routing
    - **Property 24: Media type detection and routing**
    - **Validates: Requirements 13.1, 13.2**

  - [ ]* 6.4 Write property test for scanned PDF detection
    - **Property 25: Scanned PDF detection**
    - **Validates: Requirements 13.6**

  - [ ]* 6.5 Write property test for exact deduplication
    - **Property 22: Exact deduplication**
    - **Validates: Requirements 10.4, 16.1, 16.2**

  - [ ]* 6.6 Write property test for near-duplicate detection
    - **Property 23: Near-duplicate detection**
    - **Validates: Requirements 16.3, 16.4**

  - [ ]* 6.7 Write property test for deduplication statistics accuracy
    - **Property 31: Deduplication statistics accuracy**
    - **Validates: Requirements 16.5**

- [ ] 7. BulkClassificationService and TriageService
  - [ ] 7.1 Create `src/services/bulk_classification_service.py`
    - Implement BulkClassificationService with classify_for_bulk and auto_route
    - classify_for_bulk extends existing DocumentClassificationService with case-number and matter-reference extraction prompts via Bedrock
    - Returns ClassificationResult with confidence, document_type, extracted case numbers, matter references, entities
    - auto_route matches extracted identifiers to existing Matters/Cases, auto-creates new ones for unrecognized references, sends to triage if below confidence threshold
    - Supports all three ingestion modes: auto_classify (full AI), pre_assigned (skip routing classification), hybrid (pre-assign Matter, AI sub-classifies Cases)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 14.2, 14.3, 14.4_

  - [ ] 7.2 Create `src/services/triage_service.py`
    - Implement TriageService with add_to_triage, list_triage_items, get_triage_item, assign_to_matter_case, create_matter_from_triage, create_case_from_triage, mark_irrelevant, mark_duplicate
    - add_to_triage creates triage item with ai_suggestions, document_type, extracted_entities, status "pending"
    - get_triage_item returns document preview (first 5000 chars of parsed_text), AI suggestions with confidence/reasoning, extracted entities
    - All triage operations validate item is in "pending" status before proceeding
    - All triage operations record chain_of_custody events with acting user identity
    - list_triage_items supports filtering by job_id, status, document_type with pagination
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 17.4_

  - [ ]* 7.3 Write property test for classification output invariants
    - **Property 12: Classification output invariants**
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 7.4 Write property test for confidence threshold routing
    - **Property 14: Confidence threshold routing**
    - **Validates: Requirements 6.5, 7.1, 7.2**

  - [ ]* 7.5 Write property test for auto-routing matches existing entities
    - **Property 15: Auto-routing matches existing entities**
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 7.6 Write property test for auto-creation of new Matters and Cases
    - **Property 16: Auto-creation of new Matters and Cases**
    - **Validates: Requirements 6.3, 6.4**

  - [ ]* 7.7 Write property test for triage item round trip
    - **Property 17: Triage item round trip**
    - **Validates: Requirements 7.3, 7.4, 11.3**

  - [ ]* 7.8 Write property test for triage filtering correctness
    - **Property 18: Triage filtering correctness**
    - **Validates: Requirements 8.1**

  - [ ]* 7.9 Write property test for triage operations update status and route document
    - **Property 19: Triage operations update status and route document**
    - **Validates: Requirements 8.3, 8.4, 8.5, 8.6, 8.7**

  - [ ]* 7.10 Write property test for ingestion mode routing behavior
    - **Property 29: Ingestion mode routing behavior**
    - **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6**

- [ ] 8. Checkpoint — Ensure classification and triage services pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. PipelineWizardService and job monitoring
  - [ ] 9.1 Create `src/services/pipeline_wizard_service.py`
    - Implement PipelineWizardService with scan_and_recommend, save_config, get_defaults
    - scan_and_recommend uses MediaTypeDetector.scan_staged_files, generates recommended pipeline_config JSONB
    - Recommendations include: Rekognition config if images detected, Transcribe config if audio detected, Rekognition Video + Transcribe if video detected, Textract OCR if scanned PDFs exceed threshold (default 10%), Neptune config always present
    - save_config stores pipeline_config JSONB on bulk_ingestion_jobs record
    - get_defaults returns sensible defaults for all detected media types
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8, 13.9_

  - [ ] 9.2 Add job monitoring logic to BulkIngestionService
    - Implement error threshold warning: flag job when error_count exceeds configurable threshold (default 5% of total_files)
    - Implement job completion: transition to "completing" then "completed" when processed_count equals total_files
    - Implement get_job_breakdown: per-job breakdown of auto-routed by Matter, by Case, triage, error
    - _Requirements: 9.3, 9.4, 9.5_

  - [ ]* 9.3 Write property test for Pipeline Wizard recommendation completeness
    - **Property 27: Pipeline Wizard recommendation completeness**
    - **Validates: Requirements 13.9, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.8**

  - [ ]* 9.4 Write property test for pipeline config round trip
    - **Property 28: Pipeline config round trip**
    - **Validates: Requirements 15.7**

  - [ ]* 9.5 Write property test for error threshold warning
    - **Property 20: Error threshold warning**
    - **Validates: Requirements 9.3**

  - [ ]* 9.6 Write property test for job completion invariant
    - **Property 21: Job completion invariant**
    - **Validates: Requirements 9.4, 9.5**

- [ ] 10. Step Functions pipeline extension
  - [ ] 10.1 Extend `infra/step_functions/ingestion_pipeline.json` with bulk ingestion states
    - Add DetectMediaType choice state branching on $.media_type to: ParseDocument, ProcessImage, ProcessAudio, ProcessVideo, ParseSpreadsheet, ParseEmail
    - Add CheckScannedPDF choice state after ParseDocument: route scanned PDFs ($.parse_result.is_scanned == true) to TextractOCR, native text to ExtractEntities
    - Add ProcessVideo parallel state: RekognitionVideo and TranscribeAudio branches running concurrently, merging into MergeVideoResults before ExtractEntities
    - Add ClassifyAndRoute state after ExtractEntities
    - Add GenerateEmbedding and NeptuneGraphLoad states to complete the pipeline
    - Add UpdateJobStatus terminal state
    - _Requirements: 13.2, 13.6, 13.7, 13.8_

  - [ ]* 10.2 Write property test for processing pipeline order invariant
    - **Property 26: Processing pipeline order invariant**
    - **Validates: Requirements 13.7, 13.8**

- [ ] 11. Checkpoint — Ensure pipeline and wizard services pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. API handlers for bulk ingestion, triage, and cases
  - [ ] 12.1 Create `src/lambdas/api/bulk_ingestion.py`
    - Implement dispatch_handler for:
      - POST `/customers/{id}/bulk-ingestion-jobs` — create job (wire to BulkIngestionService.create_job)
      - GET `/bulk-ingestion-jobs/{id}` — get job status with computed metrics
      - GET `/bulk-ingestion-jobs/{id}/documents` — list documents with classification outcomes
      - GET `/bulk-ingestion-jobs/{id}/breakdown` — per-job classification breakdown
      - GET `/bulk-ingestion-jobs/{id}/triage` — list triage items for job
      - POST `/bulk-ingestion-jobs/{id}/wizard/scan` — trigger Pipeline Wizard scan
      - POST `/bulk-ingestion-jobs/{id}/wizard/config` — save Pipeline Wizard config
    - All endpoints enforce customer-level tenant isolation
    - _Requirements: 12.1, 12.4_

  - [ ] 12.2 Create `src/lambdas/api/triage.py`
    - Implement dispatch_handler for:
      - POST `/triage/{id}/assign` — assign triage item to Matter/Case
      - POST `/triage/{id}/create-matter` — create Matter from triage item
      - POST `/triage/{id}/create-case` — create Case from triage item
      - POST `/triage/{id}/mark-irrelevant` — mark triage item irrelevant
      - POST `/triage/{id}/mark-duplicate` — mark triage item as duplicate
    - All endpoints record chain_of_custody events
    - All endpoints enforce tenant isolation
    - _Requirements: 12.2, 12.4_

  - [ ] 12.3 Create `src/lambdas/api/cases.py`
    - Implement dispatch_handler for:
      - GET `/customers/{id}/matters/{mid}/cases` — list Cases under a Matter
      - POST `/customers/{id}/matters/{mid}/cases` — create a Case
      - GET `/cases/{id}` — get Case detail
    - Wire to CaseService
    - Enforce tenant isolation
    - _Requirements: 12.3, 12.4_

  - [ ] 12.4 Update API Gateway definition `infra/api_gateway/api_definition.yaml`
    - Add routes for all bulk ingestion, triage, and case endpoints
    - Wire to appropriate Lambda handlers
    - _Requirements: 12.1, 12.2, 12.3_

- [ ] 13. Integration wiring and document processing Lambda handlers
  - [ ] 13.1 Create `src/lambdas/ingestion/bulk_processing_handler.py`
    - Implement Lambda handler that reads from SQS document queue
    - For each document: call MediaTypeDetector.detect → route to appropriate content extraction → call EntityExtractionService → call BulkClassificationService.classify_for_bulk → call auto_route → call DeduplicationService → generate embedding → Neptune graph load
    - Read pipeline_config from job record to configure processing steps
    - Call ChainOfCustodyService.record_event at each processing step
    - Call BulkIngestionService.increment_counter after each document completes
    - Handle errors: mark document as "error", increment error_count, continue processing
    - _Requirements: 4.4, 5.5, 13.2, 13.4, 13.7, 13.8, 17.1_

  - [ ] 13.2 Create `src/lambdas/ingestion/media_handlers.py`
    - Implement handler functions for each media type branch:
      - process_document: parse text, check scanned PDF, route to Textract OCR if needed
      - process_image: call Rekognition (face detection, label detection, OCR via Textract)
      - process_audio: call Transcribe, extract text from transcript
      - process_video: parallel Rekognition Video + Transcribe, merge results
      - process_spreadsheet: tabular parser, extract cell contents
      - process_email: parse headers/body/attachments, recursively process attachments as separate documents
    - All handlers output uniform format: parsed_text, extracted_entities, source_media_type
    - _Requirements: 13.2, 13.4, 13.5, 13.6, 13.8_

  - [ ] 13.3 Wire all services together in bulk processing flow
    - Ensure BulkIngestionService.start_processing dispatches to SQS
    - Ensure bulk_processing_handler reads pipeline_config and routes correctly
    - Ensure deduplication runs before redundant processing (exact hash check early, near-duplicate after embedding)
    - Ensure job status transitions happen at correct points: staging → processing → classifying → completing → completed
    - _Requirements: 3.5, 4.3, 10.2, 16.2_

- [ ] 14. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)`
- The migration (1.1) uses ALTER TABLE to extend existing tables non-destructively
- All existing API endpoints continue to function without modification (Requirement 11.6)
- Checkpoints ensure incremental validation at logical boundaries
- The bulk processing handler (13.1) is the central integration point that wires all services together
- Chain of custody events are recorded at every processing step for court admissibility
