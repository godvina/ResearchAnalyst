# Implementation Plan: Research Analyst Platform

## Overview

Incremental implementation of the Research Analyst Platform — a serverless research engine built on Aurora Serverless v2 (pgvector), Neptune Serverless, Bedrock, S3, Lambda, Step Functions, and Streamlit. Python codebase with Hypothesis for property-based testing. Each task builds on previous steps, wiring components together progressively.

## Tasks

- [x] 1. Set up project structure, core data models, and database schemas
  - [x] 1.1 Create project directory structure and install dependencies
    - Create directories: `src/services/`, `src/models/`, `src/lambdas/`, `src/api/`, `src/frontend/`, `tests/unit/`, `tests/property/`, `tests/integration/`
    - Create `requirements.txt` with boto3, psycopg2-binary, gremlinpython, streamlit, hypothesis, pytest, pydantic
    - Create `pyproject.toml` or `setup.py` for project configuration
    - _Requirements: 8.1–8.6_

  - [x] 1.2 Implement core data model classes and enums
    - Create `src/models/case_file.py` with `CaseFile`, `CaseFileStatus` enum, and `CrossCaseGraph` dataclasses
    - Create `src/models/document.py` with `ParsedDocument`, `ExtractionResult`, `BatchResult` dataclasses
    - Create `src/models/entity.py` with `EntityType`, `RelationshipType` enums, `ExtractedEntity`, `ExtractedRelationship` dataclasses
    - Create `src/models/pattern.py` with `Pattern`, `PatternReport`, `CrossCaseMatch`, `CrossReferenceReport` dataclasses
    - Create `src/models/search.py` with `SearchResult`, `AnalysisSummary` dataclasses
    - _Requirements: 1.1, 2.2, 2.3, 3.2, 5.4, 9.1, 9.2, 10.2_

  - [ ]* 1.3 Write property tests for case file data model validation
    - **Property 1: Case file creation produces a complete, correctly-scoped record**
    - **Validates: Requirements 1.1, 1.2, 1.3**
    - **Property 2: Missing required fields produce validation errors**
    - **Validates: Requirements 1.5**

  - [x] 1.4 Create Aurora database schema and migration scripts
    - Create `src/db/schema.sql` with all tables: `case_files`, `cross_case_graphs`, `cross_case_graph_members`, `documents`, `findings`, `pattern_reports`
    - Include all indexes (status, topic GIN, created_at, parent, embedding ivfflat, etc.)
    - Create `src/db/connection.py` for Aurora connection management via RDS Proxy
    - _Requirements: 1.1, 7.1, 7.3_

  - [x] 1.5 Define Neptune graph schema constants and connection helper
    - Create `src/db/neptune.py` with graph node/edge label conventions, property names, and connection helper
    - Define label templates: `Entity_{case_id}`, `CrossCase_{graph_id}`
    - Define edge labels: `RELATED_TO`, `CROSS_CASE_LINK`
    - Define Neptune bulk loader CSV column formats for nodes and edges
    - _Requirements: 2.3, 2.4, 5.1, 5.5_

  - [x] 1.6 Create S3 data lake helper with prefix conventions
    - Create `src/storage/s3_helper.py` with functions for building S3 paths: `cases/{case_id}/raw/`, `cases/{case_id}/processed/`, `cases/{case_id}/extractions/`, `cases/{case_id}/bulk-load/`
    - Implement upload, download, list, and delete operations scoped to case prefixes
    - _Requirements: 1.2, 2.1_


- [x] 2. Implement Case File Service
  - [x] 2.1 Implement CaseFileService CRUD operations
    - Create `src/services/case_file_service.py` with `CaseFileService` class
    - Implement `create_case_file()`: generate UUID, build S3 prefix and Neptune label from case ID, insert into Aurora, return `CaseFile`
    - Implement `get_case_file()`, `list_case_files()` with filters (status, topic keyword, date range, entity count range)
    - Implement `update_status()` with valid status set enforcement
    - Implement `archive_case_file()` that sets status to "archived" without deleting data
    - Implement `delete_case_file()` that removes Aurora record, S3 prefix, Neptune subgraph, and vector embeddings
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 2.2 Write property test for status validation
    - **Property 21: Only valid case file statuses are accepted**
    - **Validates: Requirements 7.1**

  - [ ]* 2.3 Write property test for case file listing completeness
    - **Property 23: Case file listing includes all required fields**
    - **Validates: Requirements 7.3**

  - [ ]* 2.4 Write property test for case file filtering
    - **Property 24: Case file filtering returns only matching results**
    - **Validates: Requirements 7.4**

  - [ ]* 2.5 Write property test for archiving data retention
    - **Property 22: Archiving retains all associated data**
    - **Validates: Requirements 7.2**

  - [ ]* 2.6 Write property test for deletion completeness
    - **Property 25: Case file deletion removes all associated data**
    - **Validates: Requirements 7.5**

  - [x] 2.7 Implement CrossCaseGraph CRUD in CaseFileService
    - Implement `create_cross_case_graph()`: generate UUID, create Neptune subgraph label, insert metadata into Aurora, insert member records
    - Implement `update_cross_case_graph()`: add/remove case IDs from membership table, update Neptune edges
    - _Requirements: 5.5, 5.6, 5.8, 5.9_

  - [ ]* 2.8 Write property test for cross-case graph metadata
    - **Property 16: Cross-case graph metadata completeness**
    - **Validates: Requirements 5.6**

  - [ ]* 2.9 Write property test for cross-case graph membership updates
    - **Property 18: Cross-case graph membership updates correctly**
    - **Validates: Requirements 5.8, 5.9**

- [x] 3. Checkpoint — Core data layer
  - Ensure all tests pass, ask the user if questions arise.


- [x] 4. Implement Document Parsing and Ingestion Pipeline
  - [x] 4.1 Implement DocumentParser
    - Create `src/services/document_parser.py` with `DocumentParser` class
    - Implement `parse()`: extract document ID, case file ID, source metadata, raw text, and sections from raw content
    - Implement `format()`: convert structured `ParsedDocument` back to human-readable text
    - Handle unsupported formats and corruption with descriptive errors including document ID and reason
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 4.2 Write property tests for document parsing
    - **Property 31: Parsed documents contain all required fields**
    - **Validates: Requirements 11.1**
    - **Property 32: Document parse/format round-trip**
    - **Validates: Requirements 11.3**
    - **Property 33: Parse errors include document identifier and reason**
    - **Validates: Requirements 11.4**

  - [x] 4.3 Implement Entity Extraction Service
    - Create `src/services/entity_extraction_service.py` with `EntityExtractionService` class
    - Implement `extract_entities()`: call Bedrock LLM to extract entities with type, canonical name, confidence, occurrences, source refs
    - Implement `extract_relationships()`: call Bedrock LLM to classify relationships (co-occurrence, causal, temporal, geographic, thematic)
    - Implement `merge_entities()`: merge duplicates by canonical name + type, sum occurrence counts, union source refs
    - _Requirements: 2.2, 9.1, 9.2, 9.3, 9.4_

  - [ ]* 4.4 Write property tests for entity extraction
    - **Property 26: Extracted entities have valid types and all required fields**
    - **Validates: Requirements 9.1, 9.2**
    - **Property 27: Entity merging preserves total occurrence count**
    - **Validates: Requirements 9.3**
    - **Property 28: Relationship types are from the valid set**
    - **Validates: Requirements 9.4**

  - [x] 4.5 Implement NeptuneGraphLoader (hybrid bulk CSV + Gremlin)
    - Create `src/services/neptune_graph_loader.py` with `NeptuneGraphLoader` class
    - Implement `generate_nodes_csv()`: build Neptune bulk loader CSV from extraction artifacts (columns: ~id, ~label, entity_type, canonical_name, confidence, occurrence_count, case_file_id), upload to S3 under `cases/{case_id}/bulk-load/`
    - Implement `generate_edges_csv()`: build Neptune bulk loader CSV from extraction artifacts (columns: ~id, ~from, ~to, ~label, relationship_type, confidence, source_document_ref), upload to S3
    - Implement `bulk_load()`: trigger Neptune bulk loader API pointing at S3 CSVs, with IAM role for S3 access
    - Implement `poll_bulk_load_status()`: poll Neptune loader status until LOAD_COMPLETED or LOAD_FAILED
    - Implement `load_via_gremlin()`: write entities as nodes and relationships as edges via Gremlin API for small incremental updates
    - Implement `merge_duplicate_nodes()`: merge duplicate entity nodes by canonical name + type in Neptune
    - _Requirements: 2.3, 2.4, 9.3_

  - [x] 4.6 Implement IngestionService orchestration
    - Create `src/services/ingestion_service.py` with `IngestionService` class
    - Implement `upload_documents()`: store raw files to S3 under `cases/{case_id}/raw/{document_id}.{ext}`, return document IDs
    - Implement `process_document()`: parse → extract entities → generate embeddings via Bedrock → store in Aurora pgvector → store extraction artifact JSON to S3
    - Implement `process_batch()`: iterate documents for extraction, then choose graph loading strategy based on batch size (≥ BULK_LOAD_THRESHOLD → bulk CSV, otherwise → Gremlin), index in Bedrock KB, update case file status and statistics. Continue on individual failures.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [ ]* 4.7 Write property tests for ingestion pipeline
    - **Property 3: Uploaded files stored under correct S3 prefix**
    - **Validates: Requirements 2.1**
    - **Property 4: Graph nodes and edges have required properties**
    - **Validates: Requirements 2.3, 2.4**
    - **Property 5: Embeddings stored with correct metadata**
    - **Validates: Requirements 2.5**
    - **Property 6: Batch completion updates status and statistics accurately**
    - **Validates: Requirements 2.7**
    - **Property 7: Failed documents are skipped without halting the pipeline**
    - **Validates: Requirements 2.8**
    - **Property 29: Extraction artifacts stored as JSON at correct path**
    - **Validates: Requirements 9.5**

  - [x] 4.8 Create Step Functions state machine definition for ingestion pipeline
    - Create `src/lambdas/ingestion/` with individual Lambda handlers for each pipeline step: upload, parse, extract, embed, generate CSVs, bulk load or Gremlin load, KB index, store artifact
    - Create Step Functions ASL definition (`infra/step_functions/ingestion_pipeline.json`) with states for each step, catch/retry blocks, parallel document processing, and a Choice state for bulk vs Gremlin loading based on batch size
    - Wire error handling: retry with exponential backoff, skip on failure, set case status to "error" on unrecoverable errors
    - _Requirements: 2.7, 2.8, 2.9, 8.3, 8.4_

- [x] 5. Checkpoint — Ingestion pipeline
  - Ensure all tests pass, ask the user if questions arise.


- [x] 6. Implement Pattern Discovery Service
  - [x] 6.1 Implement PatternDiscoveryService
    - Create `src/services/pattern_discovery_service.py` with `PatternDiscoveryService` class
    - Implement `discover_graph_patterns()`: run Neptune graph traversal (shortest path, community detection, centrality) within case subgraph
    - Implement `discover_vector_patterns()`: query Aurora pgvector for semantic clusters within case documents
    - Implement `generate_pattern_report()`: combine graph + vector patterns, deduplicate overlapping entity sets, rank by confidence × novelty, call Bedrock for natural-language explanations, store report in Aurora
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 6.2 Write property tests for pattern discovery
    - **Property 8: Pattern explanations include required fields**
    - **Validates: Requirements 3.2**
    - **Property 9: Pattern reports are ranked by confidence and novelty**
    - **Validates: Requirements 3.3**
    - **Property 10: Combined pattern reports are deduplicated**
    - **Validates: Requirements 3.5**

- [x] 7. Implement Drill-Down Investigation
  - [x] 7.1 Implement drill-down sub-case file creation
    - Add `create_sub_case_file()` to `CaseFileService`: create a new case file with `parent_case_id` set, copy relevant entity nodes and relationships from parent Neptune subgraph into sub-case subgraph as seed data
    - Ensure sub-case files can ingest additional data through the standard ingestion pipeline
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 7.2 Write property tests for drill-down hierarchy
    - **Property 11: Case file hierarchy maintains navigable parent-child links**
    - **Validates: Requirements 4.1, 4.4**
    - **Property 12: Sub-case file seed data copied from parent**
    - **Validates: Requirements 4.2**

- [x] 8. Implement Cross-Case Analysis Service
  - [x] 8.1 Implement CrossCaseService
    - Create `src/services/cross_case_service.py` with `CrossCaseService` class
    - Implement `find_shared_entities()`: query Neptune for shared/similar entities across case subgraphs
    - Implement `generate_cross_reference_report()`: produce report with shared entities, parallel patterns, AI analysis via Bedrock
    - Implement `create_cross_case_graph()`: create dedicated Neptune subgraph with CROSS_CASE_LINK edges, without modifying original subgraphs
    - Implement `scan_for_overlaps()`: scan new case against existing cases, return candidates without creating links
    - Implement `confirm_connection()`: add analyst-confirmed CROSS_CASE_LINK edge to graph
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7, 5.8, 5.9, 5.11_

  - [ ]* 8.2 Write property tests for cross-case analysis
    - **Property 13: Default case file isolation**
    - **Validates: Requirements 5.1**
    - **Property 14: Cross-reference reports contain required sections**
    - **Validates: Requirements 5.4**
    - **Property 15: Cross-case graph creation preserves source subgraphs**
    - **Validates: Requirements 5.5**
    - **Property 17: Auto-scan detects overlaps without creating links**
    - **Validates: Requirements 5.7**
    - **Property 19: Cross-referencing accepts any combination of case files and sub-case files**
    - **Validates: Requirements 5.11**

- [x] 9. Checkpoint — Core services complete
  - Ensure all tests pass, ask the user if questions arise.


- [x] 10. Implement Semantic Search Service
  - [x] 10.1 Implement SemanticSearchService
    - Create `src/services/semantic_search_service.py` with `SemanticSearchService` class
    - Implement `search()`: query Bedrock Knowledge Base for case-scoped semantic search, return results ranked by relevance with source refs, passages, and context
    - Implement `analyze_entity()`: use Bedrock Agent to generate structured analytical summary for an entity
    - Implement `analyze_pattern()`: use Bedrock Agent to generate structured analytical summary for a pattern
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 10.2 Write property test for semantic search results
    - **Property 30: Semantic search returns sorted results with complete fields**
    - **Validates: Requirements 10.2, 10.3**

- [x] 11. Implement API Layer (Lambda + API Gateway)
  - [x] 11.1 Create API handler Lambda functions
    - Create `src/lambdas/api/case_files.py` with handlers for: POST `/case-files`, GET `/case-files`, GET `/case-files/{id}`, DELETE `/case-files/{id}`, POST `/case-files/{id}/archive`
    - Create `src/lambdas/api/ingestion.py` with handler for: POST `/case-files/{id}/ingest`
    - Create `src/lambdas/api/patterns.py` with handlers for: POST `/case-files/{id}/patterns`, GET `/case-files/{id}/patterns`
    - Create `src/lambdas/api/search.py` with handler for: POST `/case-files/{id}/search`
    - Create `src/lambdas/api/drill_down.py` with handler for: POST `/case-files/{id}/drill-down`
    - Create `src/lambdas/api/cross_case.py` with handlers for: POST `/cross-case/analyze`, POST `/cross-case/graphs`, PATCH `/cross-case/graphs/{id}`, GET `/cross-case/graphs/{id}`
    - Include request validation, structured error responses with error codes and request IDs
    - _Requirements: 1.1–1.5, 2.1, 3.1–3.5, 4.1–4.4, 5.2–5.9, 7.1–7.5_

  - [x] 11.2 Create API Gateway configuration
    - Create `infra/api_gateway/api_definition.yaml` (OpenAPI spec) defining all endpoints, request/response schemas, and Lambda integrations
    - _Requirements: 6.1_

- [x] 12. Implement Research Interface (Streamlit Frontend)
  - [x] 12.1 Create Streamlit app structure and Case File Dashboard page
    - Create `src/frontend/app.py` as main Streamlit entry point with sidebar navigation
    - Create `src/frontend/pages/case_dashboard.py`: list case files with status, creation date, topic, document count, entity count, last activity; create new case file form with validation
    - _Requirements: 6.1, 7.3_

  - [x] 12.2 Create Case File Detail and Ingestion page
    - Create `src/frontend/pages/case_detail.py`: display case metadata, ingestion status, entity/relationship counts; upload documents form triggering ingestion API
    - _Requirements: 6.1, 2.1_

  - [x] 12.3 Create Graph Explorer page
    - Create `src/frontend/pages/graph_explorer.py`: interactive network graph visualization using streamlit-agraph or pyvis
    - Implement sidebar filters: entity type, relationship type, confidence threshold, source document
    - Render within-case edges and cross-case edges with visual distinction
    - _Requirements: 6.4, 6.5, 5.10_

  - [x] 12.4 Create Pattern Discovery page
    - Create `src/frontend/pages/pattern_discovery.py`: trigger pattern discovery, display pattern reports with ranked patterns, drill-down button to create sub-case files
    - _Requirements: 3.1, 3.3, 4.1_

  - [x] 12.5 Create Cross-Case Analysis page
    - Create `src/frontend/pages/cross_case.py`: select cases for cross-reference, display cross-reference reports, manage cross-case graphs (create, add/remove members, view)
    - _Requirements: 5.2, 5.4, 5.6, 5.8, 5.9, 5.10_

  - [x] 12.6 Create Semantic Search page
    - Create `src/frontend/pages/semantic_search.py`: natural language query input, display search results with passages, relevance scores, source refs, and context
    - _Requirements: 10.2, 10.3_

  - [x] 12.7 Create Findings Log page
    - Create `src/frontend/pages/findings_log.py`: record observations, tag entities, annotate patterns within a case file
    - _Requirements: 6.6_

  - [x] 12.8 Implement input validation for Research Interface
    - Add predefined input format validation for analyst notes and research parameters across all Streamlit forms
    - _Requirements: 6.7_

  - [ ]* 12.9 Write property test for analyst input validation
    - **Property 20: Analyst input validation enforces predefined formats**
    - **Validates: Requirements 6.7**

- [x] 13. Checkpoint — Full application wired
  - Ensure all tests pass, ask the user if questions arise.


- [x] 14. Infrastructure and Deployment Configuration
  - [x] 14.1 Create IaC templates for AWS resources
    - Create CloudFormation or CDK templates for: Aurora Serverless v2 (0.5 ACU min), Neptune Serverless (1 NCU min), S3 bucket with lifecycle policy (IA after 90 days), Lambda functions, Step Functions state machine, API Gateway, Bedrock Knowledge Base with Aurora pgvector vector store, RDS Proxy for connection pooling
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 10.1_

  - [x] 14.2 Wire Lambda functions to services and configure IAM roles
    - Create Lambda deployment packages referencing service modules
    - Configure IAM roles with least-privilege access to Aurora, Neptune, S3, Bedrock, Step Functions
    - Configure environment variables for database endpoints, S3 bucket name, Bedrock model IDs
    - _Requirements: 8.3_

- [x] 15. Final checkpoint — All components integrated
  - Ensure all tests pass, ask the user if questions arise.


- [x] 16. Infrastructure Hardening and Production Fixes
  - [x] 16.1 Fix VPC security group rules for all Lambda-to-endpoint connectivity
    - Add inbound rules on Bedrock Runtime VPC Endpoint SG (port 443) from all Lambda security groups
    - Add inbound rules on Secrets Manager VPC Endpoint SG (port 443) from all Lambda security groups
    - Add inbound rules on RDS Proxy SG (port 5432) from all Lambda security groups that access Aurora
    - Add inbound rules on Neptune SG (port 8182) from all Lambda security groups that access Neptune
    - Each CDK-created Lambda gets its own SG; VPC endpoint SGs must explicitly allow each one
    - _Root cause: VPC endpoints with private DNS resolve to private IPs, but SG inbound rules must match the calling Lambda's SG_

  - [x] 16.2 Implement document chunking for entity extraction
    - Replace single-pass extraction with chunked extraction in `EntityExtractionService`
    - Chunk size: 10,000 chars with 500 char overlap between chunks
    - Extract entities from each chunk independently, merge using existing `merge_entities()` (dedup by canonical_name + entity_type, sum occurrences, max confidence, union source refs)
    - Deduplicate relationships across chunks by (source_entity, target_entity, relationship_type)
    - Chunk-level fault tolerance: failed chunks don't block remaining chunks
    - _Root cause: 60-70K char transcripts caused Bedrock response times exceeding Lambda timeout_

  - [x] 16.3 Add embedding text truncation for Titan model limits
    - Truncate `raw_text` to 25,000 characters before sending to Titan Embedding model
    - Titan v1 has 8,192 token limit (~25K chars); exceeding it returns ValidationException
    - Full text still stored in Aurora `raw_text` column for retrieval
    - _Root cause: Large documents exceeded Titan embedding model input limits_

  - [x] 16.4 Configure Bedrock client timeouts and retry policy
    - Add `botocore.config.Config` with `read_timeout=120`, `connect_timeout=10`, `retries={"max_attempts": 2, "mode": "adaptive"}`
    - Applied to all Lambda handlers that call Bedrock (extract, embed)
    - _Root cause: Default boto3 timeouts caused indefinite hangs on VPC endpoint connectivity issues_

  - [x] 16.5 Improve JSON response parsing resilience
    - Add fallback JSON parser that searches for `[...]` pattern when direct parse fails
    - Handles Bedrock responses with text preambles before JSON array
    - Returns empty list (with warning log) instead of raising exception on unparseable responses
    - _Root cause: Bedrock LLM occasionally returns text before the JSON array_

  - [x] 16.6 Increase Lambda timeouts for ingestion pipeline
    - Entity Extraction Lambda: 120s → 300s (processes 7-8 chunks × 2 Bedrock calls)
    - Embedding Lambda: 120s → 300s (large documents + Bedrock + Aurora write)
    - Updated both CDK stack and live Lambda configurations
    - _Root cause: Chunked extraction requires multiple sequential Bedrock calls per document_

  - [x] 16.7 Switch Neptune graph loading to HTTP API
    - Replace WebSocket-based gremlinpython with Neptune HTTP API (`POST /gremlin`)
    - Uses `urllib.request` with SSL context and 30-second per-query timeout
    - _Root cause: WebSocket connection handshake exceeded Lambda cold start init phase in VPC_

  - [x] 16.8 Fix ConnectionManager to use Secrets Manager via VPC endpoint
    - Replace direct environment variable credentials with Secrets Manager lookup
    - Cache secret in module-level variable to avoid repeated API calls
    - _Root cause: Lambda in VPC cannot access env-var credentials; must use Secrets Manager via VPC endpoint_

  - [x] 16.9 Add CheckUploadResult Choice state to Step Functions ASL
    - Skip upload step when `upload_result.document_ids` is pre-populated in the input
    - Enables pipeline re-runs without re-uploading files already in S3
    - Increase Step Functions timeout from 2 hours to 24 hours for large batches

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- All 33 correctness properties from the design document are covered as property-based test sub-tasks
- Property tests use Hypothesis with minimum 100 iterations per property
- Python is the implementation language throughout (matching the design document)
- Bedrock API calls should be mocked in unit/property tests for determinism
