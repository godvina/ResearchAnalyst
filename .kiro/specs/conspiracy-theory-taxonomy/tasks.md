# Implementation Plan: Conspiracy Theory Taxonomy

## Overview

Build the universal 5-level conspiracy theory taxonomy (Domain → Typology → Method → Signature → Precedent Case) with 10-domain classification, multi-theory seeding, sequential validation, ACH scoring, cross-theory detection, and coverage monitoring. Implementation follows: infrastructure (Aurora schema + OpenSearch index) → file format adapters → taxonomy service + ACH scoring → agent handlers → seeding pipeline → validation pipeline → coverage API.

## Tasks

- [ ] 1. Set up infrastructure: Aurora schema and OpenSearch index
  - [ ] 1.1 Create Aurora PostgreSQL schema migration for conspiracy taxonomy
    - Create `conspiracy` schema with all tables: `domains`, `typologies`, `methods`, `signatures`, `precedent_cases`
    - Create supporting tables: `theory_specific_patterns`, `document_matches`, `processing_status`, `skipped_files`, `taxonomy_audit_log`
    - Add all indexes, foreign keys, and constraints per the design data model
    - Include the `acm_matrices` table for ACH scoring storage
    - _Requirements: 1.5, 1.8, 2.6, 7.6, 9.6_

  - [ ] 1.2 Create OpenSearch Serverless index mappings for conspiracy documents
    - Create index mapping for `conspiracy-documents` index with fields: theory_name, source_file, document_id, ingestion_timestamp, content_vector (1024-dim)
    - Update existing `typology-patterns` index mapping to support conspiracy taxonomy signatures with status field and theory metadata
    - Configure k-NN settings (HNSW, nmslib engine, cosine similarity)
    - _Requirements: 1.6, 6.1, 6.2_

  - [ ] 1.3 Create Neptune graph schema for conspiracy theory vertices and edges
    - Create vertex labels: `Theory`, `Document`, `Domain`, `Typology`, `Method`, `Signature`, `PrecedentCase`
    - Create edge labels: `belongs_to`, `matches`, `contains` (hierarchy), `cross_connects`, `geo_correlates`
    - Define edge properties: shared_signature_id, similarity_score, justification_text, detected_at, distance_km
    - _Requirements: 8.1, 8.2, 8.3, 8.6_

- [ ] 2. Implement file format adapters
  - [ ] 2.1 Create base adapter interface and NormalizedRecord dataclass
    - Implement `BaseAdapter` ABC with `can_handle()` and `extract()` methods in `src/services/conspiracy_ingestion_adapters.py`
    - Implement `NormalizedRecord` dataclass with all fields: record_id, theory_name, source_file, source_type, content_text, metadata, extracted_entities, extracted_dates, extracted_locations, ingested_at
    - Implement adapter registry that routes files to correct adapter by MIME type
    - Implement skipped_files logging for unrecognized formats
    - _Requirements: 5.7, 5.8_

  - [ ] 2.2 Implement PDFAdapter for text/table/image extraction
    - Use PyPDF2 + pdfplumber to extract text content, embedded image metadata references, and structural elements (headings, tables, footnotes)
    - Handle multi-page documents up to 6M+ pages (streaming/chunked extraction)
    - Output normalized JSON to S3 path: `data-lake/conspiracy-theories/{theory_name}/pdf/{filename}.json`
    - _Requirements: 5.1, 5.8_

  - [ ] 2.3 Implement XMLAdapter for NTSB accident reports
    - Use ElementTree to extract all element content, attribute values, and nested structures
    - Parse Bermuda Triangle NTSB XML format specifically
    - Output normalized JSON to S3 path: `data-lake/conspiracy-theories/{theory_name}/xml/{filename}.json`
    - _Requirements: 5.2, 5.8_

  - [ ] 2.4 Implement CSVJSONAdapter for tabular data
    - Use pandas to extract column headers as field names and row data as individual records
    - Handle UFO 80K sighting records (CSV), Vaccine Conspiracies (CSV/JSON), Flat Earth 88M-token JSON corpus
    - Support streaming for large JSON files to avoid memory exhaustion
    - _Requirements: 5.3, 5.8_

  - [ ] 2.5 Implement HTMLTableAdapter for Wikipedia tables
    - Use BeautifulSoup to extract table headers and cell values into structured records
    - Handle Bermuda Triangle Wikipedia tables and NWO HTML data
    - _Requirements: 5.4, 5.8_

  - [ ] 2.6 Implement ImageMetadataAdapter and FASTAAdapter
    - ImageMetadataAdapter: Use Pillow to extract EXIF metadata (date, location, camera model) from TIFF/JPEG without image content analysis
    - FASTAAdapter: Use BioPython to extract sequence headers (organism, accession, description) as metadata records without analyzing sequence content
    - _Requirements: 5.5, 5.6, 5.8_

  - [ ]* 2.7 Write unit tests for all file format adapters
    - Test each adapter's `can_handle()` and `extract()` with sample files
    - Test NormalizedRecord serialization and S3 path generation
    - Test skipped_files logging for unrecognized formats
    - Test adapter registry routing
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [ ] 3. Checkpoint - Ensure infrastructure and adapters work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement conspiracy taxonomy service
  - [ ] 4.1 Create ConspiracyTaxonomyService with CRUD operations
    - Implement `create_domain()`, `create_typology()`, `create_method()`, `create_signature()` in `src/services/conspiracy_taxonomy_service.py`
    - Implement `validate_no_proper_nouns()` with blocklist checking (JFK, Roswell, COVID, Diana, etc.)
    - Implement `get_context_key()` returning `conspiracy/{domain}/{typology}/{method}/{signature}` format (max 512 chars)
    - Implement `get_coverage_report()` and `get_balance_score()` (min/max signature ratio)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 1.8, 9.1, 9.2_

  - [ ] 4.2 Implement taxonomy embedding integration with OpenSearch
    - When a signature is created, generate vector embedding via `amazon.titan-embed-text-v2:0` (1024-dim)
    - Store signature embedding in `typology-patterns` OpenSearch index with context_key and metadata
    - Support batch embedding for initial seeding of multiple signatures
    - _Requirements: 1.6, 6.1_

  - [ ]* 4.3 Write unit tests for taxonomy service
    - Test CRUD operations create correct hierarchy
    - Test proper noun validation rejects theory-specific text
    - Test context_key generation format and length validation
    - Test balance_score calculation
    - _Requirements: 1.1, 1.7, 1.8, 9.2_

- [ ] 5. Implement ACH scoring service
  - [ ] 5.1 Create ACHScoringService with Bedrock integration
    - Implement dataclasses: `ACHHypothesis`, `ACHScore`, `ACHMatrix` in `src/services/ach_scoring_service.py`
    - Implement `score_finding()` using Bedrock Claude Sonnet to evaluate each finding against 4 hypotheses (conspiracy, official, coincidence, hybrid)
    - Implement Heuer-scale scoring (-2 to +2) with reasoning generation
    - Store ACH matrices in Aurora `conspiracy.ach_matrices` table
    - _Requirements: 6.3 (design component)_

  - [ ] 5.2 Implement ACH aggregation and key assumptions check
    - Implement `aggregate_theory_scores()` to compute per-hypothesis totals across all findings for a theory
    - Implement `get_key_assumptions()` to identify assumptions that, if wrong, would change the dominant hypothesis
    - Calculate confidence_delta between top two hypotheses
    - _Requirements: 6.3 (design component)_

  - [ ]* 5.3 Write unit tests for ACH scoring service
    - Test score_finding produces valid -2 to +2 scores for all 4 hypotheses
    - Test aggregate_theory_scores correctly sums across findings
    - Test confidence_delta calculation
    - _Requirements: 6.3_

- [ ] 6. Implement agent chain handlers
  - [ ] 6.1 Implement conspiracy_broad_scanner_handler
    - Add handler function to `src/services/agent_orchestrator.py`
    - Extract named entities (people, organizations, documents, locations), claims/counter-claims, temporal markers, behavioral indicators, and SIU red flags
    - Use Bedrock Claude Sonnet for extraction via structured prompt
    - Store extracted content in Aurora and trigger follow-up to taxonomy scanner
    - Register `CONSPIRACY_BROAD_SCANNER` AgentDefinition with TriggerType.MANUAL
    - _Requirements: 2.1, 3.1, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 6.2 Implement conspiracy_taxonomy_scanner_handler
    - Add handler function to `src/services/agent_orchestrator.py`
    - Generate Titan Embed v2 embedding of document content
    - Execute k-NN query against `typology-patterns` index (k=5, cosine, threshold 0.80)
    - For each match: invoke ACH scoring, store match in Aurora with document_id, signature_id, similarity_score, theory_name, assigned_at, matched_text_excerpt (max 1000 chars)
    - Log unclassified documents (no match at 0.80) with highest score and nearest signature
    - Register `CONSPIRACY_TAXONOMY_SCANNER` AgentDefinition with TriggerType.ON_FINDINGS
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 6.3 Implement conspiracy_cross_pattern_handler
    - Add handler function to `src/services/agent_orchestrator.py`
    - For each signature match: k-NN search (k=10, threshold 0.85) excluding same-theory documents
    - Generate justification via Bedrock for structural parallels
    - Calculate reproducibility score (independent_sources × source_diversity_weight / max_possible_score)
    - Create Neptune `cross_connects` edges with shared_signature_id, similarity_score, justification_text, detected_at
    - Check geographic proximity (50km) with Ancient Mysteries nodes, create `geo_correlates` edges
    - Promote signatures matching 5+ theories to "universal_confirmed" status
    - Generate cross-theory connection summary (top 10 most-connected signatures, top 10 strongest connections)
    - Register `CONSPIRACY_CROSS_PATTERN_AGENT` AgentDefinition with TriggerType.ON_SIGNATURE
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 6.4 Write unit tests for agent chain handlers
    - Test broad scanner extracts entities, claims, dates from sample documents
    - Test taxonomy scanner performs k-NN and stores matches correctly
    - Test cross-pattern handler creates Neptune edges and calculates reproducibility scores
    - Test universal promotion threshold (5+ theories)
    - _Requirements: 2.1, 4.1, 4.6, 6.2, 6.5_

- [ ] 7. Checkpoint - Ensure core services and agents work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement seeding pipeline
  - [ ] 8.1 Create ConspiracySeedingPipeline class
    - Implement `src/services/conspiracy_seeding_pipeline.py` with THEORY_DATASETS configuration (10 theories with their file formats)
    - Implement `initiate_seeding()` to process 50+ docs per theory through the Broad Scanner
    - Wire to file format adapters for multi-format ingestion per theory
    - _Requirements: 2.1, 2.4, 2.5_

  - [ ] 8.2 Implement universal pattern derivation
    - Implement `derive_universal_patterns()` using Bedrock Claude to cluster extracted behavioral indicators
    - Verify each cluster appears across 3+ distinct theory datasets to qualify as universal
    - Implement `classify_theory_specific()` to route patterns appearing in <3 theories to `theory_specific_patterns` table
    - Auto-classify derived patterns into Domains and Typologies, creating Methods and Signatures as needed
    - _Requirements: 2.2, 2.3, 2.6_

  - [ ] 8.3 Implement seeding coverage report generation
    - Implement `generate_coverage_report()` showing signatures derived per theory dataset
    - Flag domains with fewer than 3 typologies
    - Flag domains with fewer than 5 signatures as "under-specified"
    - _Requirements: 2.7, 9.4_

  - [ ]* 8.4 Write unit tests for seeding pipeline
    - Test pattern derivation correctly filters by 3-theory threshold
    - Test theory-specific classification routing
    - Test coverage report identifies under-specified domains
    - _Requirements: 2.2, 2.6, 2.7_

- [ ] 9. Implement validation pipeline
  - [ ] 9.1 Create ConspiracyValidationPipeline class with sequential gating
    - Implement `src/services/conspiracy_validation_pipeline.py` with PROCESSING_ORDER (Bermuda → Diana → Flat → UFO → JFK) and UNGATED_THEORIES
    - Implement `start_validation()` to process entire theory dataset through all 3 agents
    - Implement `check_gate()` to verify ≥50% signature match rate before unlocking next theory
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 9.2 Implement validation reporting and gap analysis
    - Implement `produce_validation_report()` with: total docs processed, signatures matched, signatures with zero matches, cross-theory connections found, average confidence score
    - Implement `produce_gap_analysis()` identifying which Domains lack coverage for a failing theory
    - Update `processing_status` table on each validation completion (theory_name, status, documents_processed, signatures_matched, cross_connections_found, started_at, completed_at)
    - Implement flag for over-fitted taxonomy when <50% signature match rate
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 7.5, 7.6, 7.7_

  - [ ]* 9.3 Write unit tests for validation pipeline
    - Test gating logic: next theory only unlocked after previous passes
    - Test 50% threshold calculation and failure handling
    - Test gap analysis identifies under-covered domains
    - Test processing_status table updates
    - _Requirements: 3.6, 3.7, 7.1, 7.5_

- [ ] 10. Implement coverage monitoring API endpoints
  - [ ] 10.1 Create GET /taxonomy/conspiracy/coverage endpoint
    - Implement `get_coverage_handler()` returning: total_domains, total_typologies, total_methods, total_signatures, total_precedent_cases, per_domain counts, balance_score, under_specified_domains, last_updated
    - Query Aurora conspiracy schema for all counts
    - Calculate balance_score as ratio of min domain signatures to max domain signatures
    - Ensure response within 60 seconds of validation completion
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

  - [ ] 10.2 Create GET /taxonomy/conspiracy/cross-theory-report endpoint
    - Implement `get_cross_theory_report_handler()` returning: total_connections, connections_per_theory_pair, most_connected_signatures, theories_with_zero_connections, universal_confirmed_signatures, average_reproducibility_score
    - Query Neptune for cross_connects edges and aggregate by theory pair
    - Identify top 10 most-connected signatures and top 10 strongest connections
    - _Requirements: 9.3, 4.5_

  - [ ] 10.3 Implement taxonomy audit logging
    - Create audit trail for all taxonomy modifications (additions, removals, reclassifications)
    - Store in Aurora `conspiracy.taxonomy_audit_log` with: action, level, context_key, old_value, new_value, reason, modified_at
    - Wire into ConspiracyTaxonomyService CRUD operations
    - _Requirements: 9.6_

  - [ ]* 10.4 Write integration tests for coverage API
    - Test coverage endpoint returns correct structure and balance_score
    - Test cross-theory-report aggregates connections correctly
    - Test audit log captures all taxonomy modifications
    - _Requirements: 9.1, 9.3, 9.6_

- [ ] 11. Wire components together and end-to-end integration
  - [ ] 11.1 Wire seeding pipeline to adapter registry and agent chain
    - Connect `ConspiracySeedingPipeline.initiate_seeding()` to adapter registry for multi-format ingestion
    - Connect adapter output to `conspiracy_broad_scanner_handler` trigger
    - Ensure agent chain flows: Broad Scanner → Taxonomy Scanner → Cross-Pattern Agent
    - Verify S3 output paths follow convention: `data-lake/conspiracy-theories/{theory_name}/{source_type}/{filename}.json`
    - _Requirements: 2.1, 2.4, 5.8, 6.4_

  - [ ] 11.2 Wire validation pipeline to sequential gating and reporting
    - Connect `ConspiracyValidationPipeline.start_validation()` to full agent chain processing
    - Wire gate checks to processing_status table updates
    - Connect validation report generation to coverage API refresh
    - Ensure Bermuda Triangle full validation triggers Diana unlock on pass
    - _Requirements: 3.1, 3.2, 3.3, 3.7, 7.1, 7.6_

  - [ ]* 11.3 Write end-to-end integration tests
    - Test complete flow: adapter → S3 → Broad Scanner → Taxonomy Scanner → Cross-Pattern Agent
    - Test seeding pipeline produces universal patterns from multi-theory input
    - Test validation pipeline gates correctly and produces reports
    - Test coverage API reflects pipeline state
    - _Requirements: 2.1, 3.5, 6.4, 9.5_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The design does not include a Correctness Properties section, so unit tests and integration tests are used instead of property-based tests
- All file format adapters normalize to JSON before downstream processing
- The ACH scoring layer is a design-level addition that prevents confirmation bias — it's referenced in agent handlers rather than being a standalone requirement
- Sequential processing order (Bermuda → Diana → Flat → UFO → JFK) is enforced by the validation pipeline gating logic
- Remaining 5 theories (9/11, COVID-19, Moon Landing, Vaccines, NWO) are ungated after the first 5 pass

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "4.2", "5.1"] },
    { "id": 3, "tasks": ["2.7", "4.3", "5.2"] },
    { "id": 4, "tasks": ["5.3", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3"] },
    { "id": 6, "tasks": ["6.4", "8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3"] },
    { "id": 8, "tasks": ["8.4", "9.1"] },
    { "id": 9, "tasks": ["9.2", "10.1", "10.2", "10.3"] },
    { "id": 10, "tasks": ["9.3", "10.4", "11.1"] },
    { "id": 11, "tasks": ["11.2"] },
    { "id": 12, "tasks": ["11.3"] }
  ]
}
```
