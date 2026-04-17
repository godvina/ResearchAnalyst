# Implementation Plan: Multi-Backend Search

## Overview

Incrementally build the multi-backend search architecture: start with core data models and abstractions, implement both backends, wire them through the factory into ingestion and search services, extend the API and CDK infrastructure, and finish with frontend adaptive UI. Each task builds on the previous, with property-based test tasks placed close to the code they validate.

## Tasks

- [x] 1. Define core data models and SearchBackend Protocol
  - [x] 1.1 Add SearchTier enum and update CaseFile model
    - Add `SearchTier(str, Enum)` with values `"standard"` and `"enterprise"` to `src/models/case_file.py`
    - Add `search_tier: SearchTier = SearchTier.STANDARD` field to the `CaseFile` model
    - _Requirements: 2.2, 8.1, 8.4_

  - [x] 1.2 Add FacetedFilter, SearchRequest, and SearchResponse models to `src/models/search.py`
    - Add `FacetedFilter` model with optional fields: `date_from`, `date_to`, `person`, `document_type`, `entity_type`
    - Add `SearchRequest` model with `query`, `search_mode` (default `"semantic"`), optional `filters: FacetedFilter`, and `top_k`
    - Add `SearchResponse` model with `results: list[SearchResult]`, `search_tier: str`, `available_modes: list[str]`
    - _Requirements: 4.4, 9.1, 9.2, 9.5_

  - [x] 1.3 Create SearchBackend Protocol and IndexDocumentRequest in `src/services/search_backend.py`
    - Define `IndexDocumentRequest` dataclass with `document_id`, `case_file_id`, `text`, `embedding`, `metadata`
    - Define `SearchBackend` as a `@runtime_checkable` `Protocol` with methods: `index_documents`, `search`, `delete_documents`, and property `supported_modes`
    - _Requirements: 1.1_

- [x] 2. Implement BackendFactory and AuroraPgvectorBackend
  - [x] 2.1 Create BackendFactory in `src/services/backend_factory.py`
    - Implement `BackendFactory` class with `get_backend(tier)` returning the correct `SearchBackend` implementation
    - Implement `validate_search_mode(tier, mode)` raising `ValueError` for unsupported modes
    - Raise `ValueError` for unknown tier strings
    - _Requirements: 1.4, 1.5, 9.3_

  - [ ]* 2.2 Write property test: BackendFactory returns correct backend type (Property 1)
    - **Property 1: BackendFactory returns the correct backend type for each tier**
    - Use Hypothesis to generate valid and invalid tier strings; verify correct backend type or ValueError
    - **Validates: Requirements 1.4, 2.3**

  - [x] 2.3 Implement AuroraPgvectorBackend in `src/services/aurora_pgvector_backend.py`
    - Implement `SearchBackend` protocol wrapping existing Aurora pgvector logic from `ConnectionManager`
    - `supported_modes` returns `["semantic"]`
    - `search` raises `ValueError` if mode is not `"semantic"`
    - `index_documents` uses INSERT ... ON CONFLICT for idempotent upserts
    - `delete_documents` deletes by case_id and optional document_ids
    - _Requirements: 1.2, 4.6_

  - [ ]* 2.4 Write property test: Standard tier rejects enterprise-only modes (Property 9)
    - **Property 9: Standard tier rejects enterprise-only search modes and filters**
    - Generate random (tier, mode, filter) combinations; verify standard tier rejects keyword/hybrid and non-None filters
    - **Validates: Requirements 4.6, 9.3, 9.4**

- [x] 3. Implement OpenSearchServerlessBackend
  - [x] 3.1 Create OpenSearchServerlessBackend in `src/services/opensearch_serverless_backend.py`
    - Implement `SearchBackend` protocol using OpenSearch Serverless APIs
    - `supported_modes` returns `["semantic", "keyword", "hybrid"]`
    - Implement `_ensure_index` to create per-case index `case-{case_id}` with knn_vector mapping
    - Implement `index_documents` with bulk indexing of text + embedding + metadata fields
    - Implement `search` with keyword (BM25), semantic (kNN), and hybrid (compound query with RRF) modes
    - Implement faceted filter translation to OpenSearch bool filter clauses
    - Implement `delete_documents` with delete-by-query or index deletion
    - _Requirements: 1.3, 3.4, 4.1, 4.2, 4.3, 4.4_

  - [ ]* 3.2 Write property test: OpenSearch indexes both text and embedding (Property 5)
    - **Property 5: OpenSearch backend indexes both text and embedding**
    - Generate random documents; verify stored OpenSearch doc contains non-empty text and embedding with dimension 1536
    - **Validates: Requirements 3.4**

  - [ ]* 3.3 Write property test: Faceted filters narrow results correctly (Property 7)
    - **Property 7: Faceted filters narrow results correctly**
    - Generate random documents with known metadata, index them, apply random FacetedFilter, verify all results satisfy filter predicates
    - **Validates: Requirements 4.4**

  - [ ]* 3.4 Write property test: Hybrid search is superset of individual modes (Property 8)
    - **Property 8: Hybrid search results are a superset of individual mode results**
    - Index known documents, run keyword, semantic, and hybrid searches with same query; verify hybrid ⊇ (keyword ∪ semantic) within top_k
    - **Validates: Requirements 4.3**

- [x] 4. Checkpoint — Core abstractions and backends
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Schema changes and tier persistence
  - [x] 5.1 Add search_tier column to Aurora case_files table
    - Create SQL migration: `ALTER TABLE case_files ADD COLUMN search_tier VARCHAR(20) NOT NULL DEFAULT 'standard' CHECK (search_tier IN ('standard', 'enterprise'))`
    - All existing rows automatically get `'standard'` via DEFAULT
    - _Requirements: 8.4, 2.2_

  - [x] 5.2 Update CaseFileService to handle search_tier on create and reject mutations
    - Modify case file creation to accept and persist `search_tier`
    - Validate `search_tier` value on creation; return validation error for invalid values
    - Reject any update to `search_tier` on existing case files with `TIER_IMMUTABLE` error
    - Default missing `search_tier` to `"standard"` when reading from DB
    - _Requirements: 2.2, 2.3, 2.4, 8.1, 8.2_

  - [ ]* 5.3 Write property test: Search tier round-trip persistence (Property 2)
    - **Property 2: Search tier round-trip persistence**
    - Generate random valid tier + case file params; create, retrieve, verify `search_tier` matches
    - **Validates: Requirements 2.2**

  - [ ]* 5.4 Write property test: Search tier immutability (Property 3)
    - **Property 3: Search tier immutability**
    - For any existing case file and any tier value, verify update is rejected and tier remains unchanged
    - **Validates: Requirements 2.4**

  - [ ]* 5.5 Write property test: Missing search tier defaults to standard (Property 11)
    - **Property 11: Missing search tier defaults to standard**
    - For case file records with absent/null `search_tier`, verify platform treats as `"standard"` and routes through AuroraPgvectorBackend
    - **Validates: Requirements 8.1, 8.2**

- [x] 6. Update IngestionService for backend routing
  - [x] 6.1 Modify IngestionService to use BackendFactory for indexing
    - Add `backend_factory: BackendFactory` to `IngestionService.__init__`
    - In `process_document`, resolve backend via `BackendFactory.get_backend(case_file.search_tier)`
    - Build `IndexDocumentRequest` from parsed document and embedding
    - Call `backend.index_documents` instead of direct Aurora `_store_document_embedding`
    - Keep `_store_document_embedding` as fallback for standard tier or remove in favor of `AuroraPgvectorBackend`
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 6.2 Update `process_batch` to handle per-document indexing failures gracefully
    - Log indexing errors with document_id and backend type
    - Continue processing remaining documents on individual failures
    - _Requirements: 3.5_

  - [ ]* 6.3 Write property test: Ingestion routes to correct backend (Property 4)
    - **Property 4: Ingestion routes to the correct backend by tier**
    - Mock both backends; for random tier values, verify the correct mock receives `index_documents`
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 6.4 Write property test: Indexing failures don't halt batch (Property 6)
    - **Property 6: Indexing failures do not halt batch processing**
    - Generate batches where a subset fail; verify pipeline continues, successful + failed = total
    - **Validates: Requirements 3.5**

- [x] 7. Checkpoint — Ingestion routing
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Update SemanticSearchService for multi-backend search
  - [x] 8.1 Extend SemanticSearchService to use BackendFactory
    - Add `backend_factory`, `case_file_service`, `bedrock_client`, `embedding_model_id`, and `enterprise_knowledge_base_id` to constructor
    - Implement updated `search` method that resolves tier, validates mode, generates embedding for semantic/hybrid, and delegates to correct backend
    - Implement `_resolve_kb_id(tier)` to return correct Bedrock Knowledge Base ID per tier
    - Implement `_generate_embedding(query)` using Bedrock embedding model
    - _Requirements: 1.5, 4.1, 4.2, 4.3, 6.1, 6.2, 6.4_

  - [ ]* 8.2 Write property test: Bedrock KB ID resolves correctly by tier (Property 10)
    - **Property 10: Bedrock Knowledge Base ID resolves correctly by tier**
    - Verify standard tier uses Aurora KB ID, enterprise tier uses OpenSearch KB ID, and the two are distinct
    - **Validates: Requirements 6.1, 6.2, 6.4**

- [x] 9. Update Search API Lambda
  - [x] 9.1 Extend search handler in `src/lambdas/api/search.py`
    - Accept optional `search_mode` parameter (default `"semantic"`) and optional `filters` parameter
    - Construct `FacetedFilter` from filters payload
    - Load case file to read `search_tier`; resolve backend via `BackendFactory`
    - Call `search_service.search` with mode and filters
    - Return `search_tier` and `available_modes` in response
    - Return HTTP 400 for unsupported mode/filter on standard tier
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 9.2 Write property test: Search response includes tier metadata (Property 12)
    - **Property 12: Search response includes tier metadata**
    - For any successful search, verify response includes `search_tier` and correct `available_modes` list per tier
    - **Validates: Requirements 9.5**

- [x] 10. Update Case Files API for tier selection
  - [x] 10.1 Extend case file creation endpoint in `src/lambdas/api/case_files.py`
    - Accept optional `search_tier` field in POST /case-files (default `"standard"`)
    - Pass `search_tier` to `CaseFileService.create_case_file`
    - Include `search_tier` in GET /case-files and GET /case-files/{id} responses
    - Return validation error for invalid `search_tier` values
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

- [x] 11. Checkpoint — Backend services and API complete
  - Ensure all tests pass, ask the user if questions arise.

- [-] 12. OpenSearch Serverless CDK provisioning
  - [x] 12.1 Add OpenSearch Serverless collection to CDK stack
    - Add `_create_opensearch_serverless` method to `ResearchAnalystStack`
    - Create encryption policy, network policy, data access policy, and vector search collection
    - Create IAM roles granting Lambda functions permission to index and search the collection
    - Pass collection endpoint and collection ID to Lambda functions via environment variables
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 12.2 Configure Bedrock Knowledge Base dual data sources
    - Add enterprise KB data source configuration backed by OpenSearch Serverless collection
    - Keep existing Aurora pgvector KB data source for standard tier
    - Pass both KB IDs to Lambda environment variables
    - _Requirements: 6.1, 6.2, 6.3_

- [ ] 13. Frontend adaptive search UI
  - [ ] 13.1 Update case file creation form in `src/frontend/pages/case_dashboard.py`
    - Add Search Tier selector (Standard / Enterprise) defaulting to Standard in the create case form
    - Pass `search_tier` to `api_client.create_case_file`
    - _Requirements: 2.1_

  - [ ] 13.2 Update case detail page in `src/frontend/pages/case_detail.py`
    - Display `search_tier` badge in case metadata section
    - _Requirements: 2.5_

  - [ ] 13.3 Update semantic search page in `src/frontend/pages/semantic_search.py`
    - Fetch case file to determine `search_tier`
    - For standard tier: show existing semantic search UI unchanged
    - For enterprise tier: add keyword search input, hybrid search toggle, and faceted filter panels (date range, person, document type, entity type)
    - Send `search_mode` and `filters` to search API
    - Display `search_tier` indicator and available modes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 13.4 Update `src/frontend/api_client.py` with new search parameters
    - Extend `search` function to accept optional `search_mode` and `filters` parameters
    - Add `search_tier` parameter to `create_case_file`
    - _Requirements: 7.3, 7.4, 9.1, 9.2_

- [ ] 14. Final checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (Properties 1–12)
- Unit tests validate specific examples and edge cases
- The design uses Python throughout — all implementations use Python 3.12
