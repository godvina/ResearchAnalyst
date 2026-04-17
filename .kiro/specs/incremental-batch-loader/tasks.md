# Implementation Plan: Incremental Batch Loader

## Overview

Implement the incremental batch loader as a modular Python CLI script (`scripts/batch_loader.py`) with supporting modules under `scripts/batch_loader/`. Modules are built in dependency order — config and data models first, then leaf modules (filter, cost estimator), then modules with S3/API dependencies (discovery, extractor, ingestion, entity index, manifest, ledger), and finally the main orchestrator that wires everything together. Each module includes its corresponding property-based tests as optional sub-tasks. All code follows the proven patterns from `scripts/phase1_load_ds15.py` and `scripts/phase2_load_ds11.py`.

## Tasks

- [x] 1. Set up project structure and config module
  - [x] 1.1 Create `scripts/batch_loader/__init__.py` and `scripts/batch_loader/config.py`
    - Define `BatchConfig` dataclass with all fields from the design: batch_size, case_id, sub_batch_size, dry_run, confirm, no_entity_resolution, max_batches, ocr_threshold, blank_threshold, source_prefixes, source_bucket, data_lake_bucket, api_url, sub_batch_delay, max_retries, failure_threshold, poll_initial_delay, poll_max_delay
    - Implement `parse_args() -> BatchConfig` using argparse with all CLI flags from Requirement 10.1: --batch-size, --case-id, --sub-batch-size, --dry-run, --confirm, --no-entity-resolution, --max-batches, --ocr-threshold, --blank-threshold, --source-prefixes
    - _Requirements: 10.1_

- [x] 2. Implement blank filter module
  - [x] 2.1 Create `scripts/batch_loader/filter.py`
    - Define `FilterResult` dataclass with fields: s3_key, is_blank, char_count
    - Implement `BlankFilter.__init__(config)` storing blank_threshold from config
    - Implement `BlankFilter.filter(extraction: ExtractionResult) -> FilterResult` that marks documents as blank when non-whitespace character count < blank_threshold
    - Implement `BlankFilter.compute_blank_ratio(results: list[FilterResult]) -> float` returning blank_count / total_count
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 2.2 Write property test for blank filter correctness
    - **Property 6: Blank filter correctness**
    - Test that for any string, blank filter marks it blank iff non-whitespace chars < blank_threshold, and blank ratio equals blank_count / total_count
    - Create `tests/unit/test_blank_filter.py` using hypothesis
    - **Validates: Requirements 3.1, 3.3**

- [x] 3. Implement cost estimator module
  - [x] 3.1 Create `scripts/batch_loader/cost_estimator.py`
    - Define `CostEstimate` dataclass with fields: textract_ocr_cost, bedrock_entity_cost, bedrock_embedding_cost, neptune_write_cost, total_estimated, estimated_ocr_pages, estimated_non_blank_docs
    - Implement `CostEstimator.__init__(config, historical_blank_rate=0.45)` loading pricing from `config/aws_pricing.json`
    - Implement `CostEstimator.estimate(file_count, avg_pages=3.0) -> CostEstimate` calculating per-component costs
    - Implement `CostEstimator.display(estimate)` printing formatted cost breakdown to stdout
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 3.2 Write property test for cost estimation correctness
    - **Property 15: Cost estimation correctness**
    - Test that total equals sum of components and each component is non-negative for any positive file count, blank rate in [0,1], and avg page count
    - Create `tests/unit/test_cost_estimator.py` using hypothesis
    - **Validates: Requirements 8.1, 8.2**

- [x] 4. Implement batch discovery and cursor management
  - [x] 4.1 Create `scripts/batch_loader/discovery.py`
    - Implement `BatchDiscovery.__init__(config, s3_client)` storing config and S3 client
    - Implement `list_all_raw_keys() -> list[str]` using S3 paginator over configured source_prefixes, filtering for .pdf files
    - Implement `load_processed_keys() -> set[str]` reading keys from completed manifests and quarantine.json
    - Implement `get_cursor() -> str | None` reading cursor from batch_progress.json
    - Implement `discover_batch() -> list[str]` returning next batch_size unprocessed keys starting from cursor, excluding processed and quarantined keys
    - Implement `save_cursor(last_key)` persisting cursor to batch_progress.json
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 4.2 Write property test for discovery exclusion
    - **Property 1: Discovery excludes processed and quarantined keys**
    - Test that for any set of S3 keys, completed manifest keys, and quarantined keys, discover_batch returns no keys from either set
    - Create `tests/unit/test_batch_discovery.py` using hypothesis
    - **Validates: Requirements 1.1, 1.3**

  - [ ]* 4.3 Write property test for cursor round-trip
    - **Property 2: Cursor round-trip persistence**
    - Test that for any valid S3 key string, save_cursor then get_cursor returns the identical string
    - Add to `tests/unit/test_batch_discovery.py`
    - **Validates: Requirements 1.2**

  - [ ]* 4.4 Write property test for batch size cap
    - **Property 3: Batch size cap**
    - Test that for any list of unprocessed files and positive batch_size, discover_batch returns at most batch_size files
    - Add to `tests/unit/test_batch_discovery.py`
    - **Validates: Requirements 1.4, 1.5**

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement text extractor module
  - [x] 6.1 Create `scripts/batch_loader/extractor.py`
    - Define `ExtractionResult` dataclass with fields: s3_key, text, method (pypdf2/textract/cached/failed), char_count, error
    - Implement `TextExtractor.__init__(config, s3_client, textract_client)` storing clients and config
    - Implement `extract(s3_key) -> ExtractionResult` that checks cache first, then tries PyPDF2, falls back to Textract if chars/page < ocr_threshold
    - Implement `_check_cache(s3_key, batch_id) -> str | None` checking S3 extraction cache
    - Implement `_extract_pypdf2(pdf_bytes) -> tuple[str, int]` extracting text via PyPDF2
    - Implement `_extract_textract(s3_key) -> str` submitting to Textract OCR and combining output
    - Implement `_save_to_cache(s3_key, batch_id, text, method)` saving extracted text JSON to S3
    - Handle PyPDF2 PdfReadError (corrupted/encrypted) by logging and returning failed result
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 6.2 Write property test for OCR fallback decision
    - **Property 4: OCR fallback decision**
    - Test that for any extraction result with known page count and char count, method is "textract" iff chars/pages < ocr_threshold
    - Create `tests/unit/test_text_extractor.py` using hypothesis
    - **Validates: Requirements 2.2**

  - [ ]* 6.3 Write property test for extraction cache round-trip
    - **Property 5: Extraction cache round-trip**
    - Test that for any text string and S3 key, saving to cache and reading back returns identical text
    - Add to `tests/unit/test_text_extractor.py`
    - **Validates: Requirements 2.4**

- [x] 7. Implement pipeline ingestion module
  - [x] 7.1 Create `scripts/batch_loader/ingestion.py`
    - Implement `PipelineIngestion.__init__(config)` storing config
    - Implement `send_sub_batches(documents: list[tuple[str, str]]) -> list[str]` partitioning documents into sub-batches of sub_batch_size, sending each via POST /case-files/{case_id}/ingest with base64-encoded text (matching phase1/phase2 pattern), inserting sub_batch_delay between calls, returning execution ARNs
    - Implement `poll_executions(execution_arns: list[str]) -> dict` polling Step Functions via boto3 with exponential backoff (poll_initial_delay doubling up to poll_max_delay) until all reach terminal state
    - Implement `_send_single_batch(case_id, texts: list[tuple[str, str]]) -> str | None` making the actual POST request with retry logic
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 7.2 Write property test for sub-batch partitioning
    - **Property 7: Sub-batch partitioning**
    - Test that for any list of N documents and positive sub_batch_size S, produces ceil(N/S) batches each with at most S docs, and union equals original list
    - Create `tests/unit/test_pipeline_ingestion.py` using hypothesis
    - **Validates: Requirements 4.1**

  - [ ]* 7.3 Write property test for SFN polling terminal state
    - **Property 8: SFN polling reaches terminal state**
    - Test that for any set of ARNs that eventually reach terminal state, poll_executions returns all ARNs with terminal status
    - Add to `tests/unit/test_pipeline_ingestion.py`
    - **Validates: Requirements 4.4**

  - [ ]* 7.4 Write property test for exponential backoff
    - **Property 9: Exponential backoff sequence**
    - Test that delay at iteration i equals min(initial_delay * 2^i, max_delay), sequence is monotonically non-decreasing, capped at max_delay
    - Add to `tests/unit/test_pipeline_ingestion.py`
    - **Validates: Requirements 4.5**

- [x] 8. Implement canonical entity index module
  - [x] 8.1 Create `scripts/batch_loader/entity_index.py`
    - Define `CanonicalEntry` dataclass with fields: canonical_name, entity_type, aliases, occurrence_count
    - Implement `CanonicalEntityIndex.__init__(config, s3_client)` storing config and S3 client
    - Implement `load() -> dict[tuple[str, str], CanonicalEntry]` loading index from S3 (canonical-entity-index/{case_id}.json) or initializing empty
    - Implement `lookup(normalized_name, entity_type) -> CanonicalEntry | None` for O(1) lookup by (normalized_name, entity_type) key, also checking aliases
    - Implement `register_merge(canonical, aliases, entity_type)` adding new merge cluster to the index
    - Implement `save()` persisting index back to S3
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 8.2 Write property test for entity index round-trip
    - **Property 10: Canonical entity index round-trip**
    - Test that serializing and deserializing the index produces equivalent entries, aliases, and occurrence counts
    - Create `tests/unit/test_canonical_entity_index.py` using hypothesis
    - **Validates: Requirements 6.1, 6.5**

  - [ ]* 8.3 Write property test for alias resolution after merge
    - **Property 11: Canonical index alias resolution after merge**
    - Test that after register_merge, looking up any alias or the canonical name returns the canonical entry
    - Add to `tests/unit/test_canonical_entity_index.py`
    - **Validates: Requirements 6.2, 6.3**

  - [ ]* 8.4 Write property test for entity type partitioning
    - **Property 12: Entity type partitioning**
    - Test that comparison never crosses entity types — all merge candidates have matching entity_type
    - Add to `tests/unit/test_canonical_entity_index.py`
    - **Validates: Requirements 6.4**

- [x] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement batch manifest module
  - [x] 10.1 Create `scripts/batch_loader/manifest.py`
    - Define `FileEntry` dataclass with fields: s3_key, file_size_bytes, extraction_method, extracted_char_count, blank_filtered, pipeline_status, sfn_execution_arn, error_message
    - Define `BatchManifestData` dataclass with fields: batch_id, batch_number, started_at, completed_at, source_prefix, files
    - Implement `BatchManifest.__init__(config, s3_client)` storing config and S3 client
    - Implement `create(batch_number, source_prefixes) -> BatchManifestData` initializing a new manifest
    - Implement `add_file(manifest, entry: FileEntry)` adding a file entry
    - Implement `save(manifest)` saving to S3 (batch-manifests/{case_id}/batch_{number}.json) and locally (scripts/batch_manifests/)
    - Implement `load_completed_keys() -> set[str]` loading all S3 keys from completed manifests
    - _Requirements: 11.1, 11.2, 11.3, 1.6_

  - [ ]* 10.2 Write property test for manifest completeness
    - **Property 18: Manifest completeness**
    - Test that for any batch of processed files, the manifest contains exactly one entry per input file with all required fields, and s3_keys match input keys
    - Create `tests/unit/test_batch_manifest.py` using hypothesis
    - **Validates: Requirements 11.1, 1.6, 2.6, 3.2, 4.3**

- [x] 11. Implement ledger integration module
  - [x] 11.1 Create `scripts/batch_loader/ledger_integration.py`
    - Implement `LedgerIntegration.__init__(config)` storing config
    - Implement `record_batch(batch_number, stats)` appending a load entry to ingestion_ledger.json using the existing `ledger.record_load` function, with all required fields: load_id, timestamp, source_prefixes, source_files_total, blanks_skipped, docs_sent_to_pipeline, sfn_executions, sfn_succeeded, sfn_failed, entity_resolution_result, textract_ocr_count, extraction_method_breakdown, notes
    - Implement `update_progress(progress)` updating batch_progress.json with running totals: total_files_discovered, total_processed, total_remaining, current_batch_number, cursor, cumulative_blanks, cumulative_quarantined, cumulative_cost, last_updated
    - Implement `update_aurora_doc_counts()` calling the existing update pattern from `scripts/update_case_doc_counts.py`
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 11.2 Write property test for ledger entry completeness
    - **Property 16: Ledger entry completeness**
    - Test that for any batch result, the generated ledger entry contains all required fields and none are null
    - Create `tests/unit/test_ledger_integration.py` using hypothesis
    - **Validates: Requirements 9.1, 5.3, 7.4**

  - [ ]* 11.3 Write property test for running total invariant
    - **Property 17: Running total invariant**
    - Test that running_total_s3_docs equals sum of docs_sent_to_pipeline across all load entries for a case
    - Add to `tests/unit/test_ledger_integration.py`
    - **Validates: Requirements 9.2**

- [x] 12. Implement error handling and quarantine
  - [x] 12.1 Add retry and quarantine logic to extractor and ingestion modules
    - Add retry loop (up to max_retries with exponential backoff) to `TextExtractor.extract()` for extraction failures
    - Add retry loop to `PipelineIngestion._send_single_batch()` for API errors (429, 5xx)
    - Implement quarantine file management: load/save `scripts/quarantine.json` with quarantined_keys list (each entry: s3_key, reason, failed_at, retry_count, batch_number)
    - Add failure threshold check: if failed_count / total_count > failure_threshold, signal pause condition
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 12.2 Write property test for retry exhaustion leading to quarantine
    - **Property 13: Retry exhaustion leads to quarantine**
    - Test that after max_retries failures, the document's S3 key appears in quarantine with reason and timestamp, and persists across save/load
    - Create `tests/unit/test_batch_error_handling.py` using hypothesis
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [ ]* 12.3 Write property test for failure threshold pause
    - **Property 14: Failure threshold triggers pause**
    - Test that when failed/total > failure_threshold, the batch loader signals pause
    - Add to `tests/unit/test_batch_error_handling.py`
    - **Validates: Requirements 7.5**

- [x] 13. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Implement main orchestrator and CLI entry point
  - [x] 14.1 Create `scripts/batch_loader.py` main entry point
    - Import all modules from `scripts/batch_loader/`
    - Parse CLI args via `config.parse_args()`
    - Initialize S3, Textract, and SFN boto3 clients
    - Implement main loop: for each batch up to max_batches:
      1. Run discovery to get next batch of unprocessed keys
      2. If dry_run: run cost estimator, display estimate, print file list, exit
      3. If not confirm: display cost estimate, prompt for confirmation
      4. Create batch manifest
      5. Extract text for each PDF (PyPDF2 + Textract fallback), update manifest
      6. Filter blanks, update manifest
      7. Send non-blank docs through ingest API in sub-batches, collect ARNs
      8. Poll Step Functions until all terminal
      9. Run entity resolution (unless --no-entity-resolution) using canonical entity index
      10. Update manifest with pipeline results
      11. Save manifest to S3 and local
      12. Record batch in ledger, update progress, update Aurora doc counts
      13. Save cursor for next batch
      14. Check failure threshold — pause if exceeded
    - Print final summary: total processed, blanks, quarantined, cost, entity resolution stats, next cursor
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 8.3, 8.4_

- [x] 15. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each group of modules
- Property tests use the `hypothesis` library with `@settings(max_examples=100)`
- All modules follow the proven patterns from `scripts/phase1_load_ds15.py` and `scripts/phase2_load_ds11.py`
- The existing `scripts/ledger.py` `record_load` function is reused for ledger integration
- The existing `scripts/update_case_doc_counts.py` pattern is reused for Aurora updates
