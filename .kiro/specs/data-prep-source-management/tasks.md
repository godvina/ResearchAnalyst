# Implementation Plan: Data Prep & Source Management

## Overview

Extend the Batch Loader UI and Lambda handler with source bucket browsing, UI-driven zip extraction, blank-adjusted cost estimates, pipeline dashboard, and multi-prefix scanning. All backend changes go into the existing Lambda (Python). Frontend changes extend `batch-loader.html`. New API routes are registered via `add_routes.py`. No CDK stack changes — deployment uses `deploy.py` for Lambda code updates. Modules are built in dependency order: data models and services first, then handler endpoints, then frontend UI, then wiring and deployment.

## Tasks

- [x] 1. Create SourceBrowserService with S3 inventory logic
  - [x] 1.1 Create `src/services/source_browser_service.py`
    - Define `PrefixInfo`, `ZipFileInfo`, `ZipMetadata`, and `BucketSummary` dataclasses matching the design data models
    - Implement `SourceBrowserService.__init__(s3_client, source_bucket, data_lake_bucket)`
    - Implement `list_prefixes() -> list[PrefixInfo]` using S3 `list_objects_v2` with `Delimiter='/'` to get top-level prefixes, then paginate each prefix to count objects, sum sizes, identify PDF vs zip files
    - Implement `get_zip_metadata(zip_key) -> ZipMetadata` that reads only the last ~64KB of the zip (central directory) via S3 range reads, parses with `zipfile` module to get entry count and filenames
    - Implement `get_summary(prefixes) -> BucketSummary` computing total files, extracted PDFs, processed count (from manifests), and remaining unprocessed
    - Implement `get_extraction_records() -> dict` reading completion records from `extract-jobs/` prefix in data lake bucket
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.2 Write property test for prefix inventory completeness
    - **Property 1: Prefix inventory completeness**
    - Generate random S3 object listings (varying prefixes, file types, sizes). Verify `list_prefixes` returns correct counts per prefix for total_objects, total_size_bytes, pdf_count, zip_count
    - Create `tests/unit/test_source_browser_service.py` using hypothesis
    - **Validates: Requirements 1.1**

  - [ ]* 1.3 Write property test for bucket summary arithmetic
    - **Property 2: Bucket summary arithmetic consistency**
    - Generate random `PrefixInfo` lists and manifest data. Verify `remaining_unprocessed == total_extracted_pdfs - already_processed`
    - Add to `tests/unit/test_source_browser_service.py`
    - **Validates: Requirements 1.2, 4.2**

  - [ ]* 1.4 Write property test for zip-prefix association
    - **Property 3: Zip files associated with correct prefix**
    - Generate prefixes with random zip files. Verify each `ZipFileInfo.key` starts with its parent prefix and count matches `zip_count`
    - Add to `tests/unit/test_source_browser_service.py`
    - **Validates: Requirements 1.3**

  - [ ]* 1.5 Write unit tests for S3 error handling
    - Test `list_prefixes` returns error response when S3 `ListObjects` raises `ClientError` (AccessDenied, NoSuchBucket)
    - Test `get_zip_metadata` handles corrupted zip gracefully
    - Test empty bucket returns empty prefix list
    - Add to `tests/unit/test_source_browser_service.py`
    - _Requirements: 1.5_

- [x] 2. Create ZipExtractorService with async extraction logic
  - [x] 2.1 Create `src/services/zip_extractor_service.py`
    - Define `ExtractionJobProgress` and `ExtractionCompletionRecord` as dataclasses matching the design JSON schemas
    - Implement `ZipExtractorService.__init__(s3_client, source_bucket, data_lake_bucket)`
    - Implement `start_extraction(zip_keys, job_id) -> dict` that writes initial progress JSON to `extract-jobs/{job_id}/progress.json` in data lake bucket
    - Implement `extract_zip(zip_key, job_id, start_index=0) -> dict` that streams zip from S3, iterates entries with `zipfile.ZipFile`, uploads each PDF to `pdfs/{dataset_prefix}_{filename}`, updates progress every 50 files, checks `context.get_remaining_time_in_millis()` for Lambda timeout and re-invokes self async if needed
    - Implement `read_progress(job_id) -> dict | None` reading progress JSON from S3
    - Implement `write_completion_record(job_id, zip_key, stats)` writing completion JSON for already-extracted detection
    - Handle duplicate filenames across zips by prefixing with dataset name (e.g., `DataSet11_filename.pdf`)
    - Skip corrupted entries with logging, increment `files_skipped`, continue extraction
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 2.2 Write property test for extraction progress fields
    - **Property 4: Extraction progress contains all required fields**
    - Generate random extraction job states. Verify all required fields present and `files_extracted + files_skipped <= files_total`
    - Create `tests/unit/test_zip_extractor_service.py` using hypothesis
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 2.3 Write property test for completion record consistency
    - **Property 7: Completion record consistency**
    - Generate completed extraction stats. Verify `total_extracted + total_skipped == total_entries_in_zip`
    - Add to `tests/unit/test_zip_extractor_service.py`
    - **Validates: Requirements 2.6**

  - [ ]* 2.4 Write property test for already-extracted detection
    - **Property 8: Already-extracted detection**
    - Generate random zip keys with/without completion records. Verify `already_extracted` flag matches presence of completion record
    - Add to `tests/unit/test_zip_extractor_service.py`
    - **Validates: Requirements 2.7**

  - [ ]* 2.5 Write property test for dataset-prefixed filenames
    - **Property 9: Dataset-prefixed filenames prevent collisions**
    - Generate multiple zip archives with intentionally overlapping internal filenames. Verify all extracted S3 keys are unique
    - Add to `tests/unit/test_zip_extractor_service.py`
    - **Validates: Requirements 2.8**

  - [ ]* 2.6 Write unit tests for extraction edge cases
    - Test single corrupted zip entry is skipped and extraction continues (Req 2.5)
    - Test chunked extraction produces no duplicate S3 keys (Property 6)
    - Test already-extracted zip returns correct status
    - Add to `tests/unit/test_zip_extractor_service.py`
    - _Requirements: 2.4, 2.5, 2.7_

- [x] 3. Enhance CostEstimator with blank-adjusted dual estimates
  - [x] 3.1 Add `estimate_dual` method to `scripts/batch_loader/cost_estimator.py`
    - Define `DualCostEstimate` dataclass with `gross`, `net`, `blank_page_rate`, and `component_breakdown` fields
    - Implement `estimate_dual(file_count, blank_page_rate=0.40, avg_pages=3.0) -> DualCostEstimate`
    - Gross estimate: all files treated as non-blank (`estimated_non_blank_docs == file_count`)
    - Net estimate: apply `blank_page_rate` reduction to Textract OCR, Bedrock entity, Bedrock embedding, and Neptune write costs
    - Component breakdown: `{component: {gross: float, net: float}}` for each of the four cost components
    - Clamp `blank_page_rate` to [0.0, 1.0] range with warning log if out of bounds
    - Return zero-cost estimate when `file_count <= 0`
    - _Requirements: 3.1, 3.2, 3.5_

  - [ ]* 3.2 Write property test for dual cost estimate correctness
    - **Property 10: Dual cost estimate correctness**
    - Generate random `(file_count, blank_page_rate)` pairs. Verify: gross `estimated_non_blank_docs == file_count`, net `estimated_non_blank_docs == round(file_count * (1 - blank_page_rate))`, and for each component `net_cost == gross_cost * (1 - blank_page_rate)`
    - Create `tests/unit/test_cost_estimator_v2.py` using hypothesis
    - **Validates: Requirements 3.1, 3.2, 3.5**

  - [ ]* 3.3 Write unit tests for cost estimator edge cases
    - Test `blank_page_rate = 0.0` → gross equals net
    - Test `blank_page_rate = 1.0` → net costs are all zero
    - Test `file_count = 0` → all costs zero
    - Test out-of-range `blank_page_rate` is clamped
    - Add to `tests/unit/test_cost_estimator_v2.py`
    - _Requirements: 3.1, 3.2_

- [ ] 4. Checkpoint — Verify services and tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Add new handler endpoints to batch_loader_handler.py
  - [x] 5.1 Add `handle_sources` endpoint (GET /batch-loader/sources)
    - Import and instantiate `SourceBrowserService` with S3 client and source bucket
    - Call `list_prefixes()`, `get_extraction_records()`, and `get_summary()`
    - For each prefix with zip files, call `get_zip_metadata()` and merge `already_extracted` status from extraction records
    - Return JSON with `prefixes`, `summary`, and per-zip metadata
    - Handle S3 errors: return 503 with error code and retry message (Req 1.5)
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

  - [x] 5.2 Add `handle_extract` endpoint (POST /batch-loader/extract)
    - Parse `zip_keys` from request body
    - Generate unique `job_id` (e.g., `ext_{timestamp}_{counter}`)
    - Instantiate `ZipExtractorService`, call `start_extraction(zip_keys, job_id)`
    - Invoke self asynchronously (`InvocationType=Event`) with `action=extract_zip` payload containing `job_id`, `zip_keys`
    - Return 202 with `job_id`
    - _Requirements: 2.1_

  - [x] 5.3 Add async worker for zip extraction
    - Add `action == "extract_zip"` branch in `dispatch_handler`
    - Call `ZipExtractorService.extract_zip()` for each zip key in the job
    - Handle Lambda timeout by checking `context.get_remaining_time_in_millis()` and re-invoking self with `start_index` for resume
    - Write completion record on finish
    - _Requirements: 2.3, 2.4, 2.5, 2.6_

  - [x] 5.4 Add `handle_extract_status` endpoint (GET /batch-loader/extract-status)
    - Parse `job_id` from query string
    - Read progress JSON from S3 via `ZipExtractorService.read_progress()`
    - Return progress data or 404 if job not found
    - _Requirements: 2.2_

  - [x] 5.5 Add `handle_pipeline_summary` endpoint (GET /batch-loader/pipeline-summary)
    - Count zip archives in source bucket, extracted PDFs in selected prefixes, blank-filtered docs from batch manifests, and ingested docs from manifests
    - Return `stages` object with counts and labels, `selected_prefixes`, and `active_batch` status
    - Handle empty/missing manifests gracefully (return zero counts)
    - _Requirements: 4.1, 4.2, 4.5_

  - [x] 5.6 Modify `handle_discover` to support dual cost estimates
    - Add `blank_page_rate` query parameter (default 0.40)
    - Call `CostEstimator.estimate_dual()` instead of `estimate()` when `blank_page_rate` param is present
    - Return both `gross_estimate` and `net_estimate` in the response alongside existing fields
    - _Requirements: 3.2, 3.5_

  - [x] 5.7 Update dispatch routing in `dispatch_handler`
    - Add routing for new resources: `/batch-loader/sources` (GET), `/batch-loader/extract` (POST), `/batch-loader/extract-status` (GET), `/batch-loader/pipeline-summary` (GET)
    - Add `action == "extract_zip"` check for async worker invocation
    - _Requirements: 1.1, 2.1, 2.2, 4.2_

  - [ ]* 5.8 Write unit tests for handler endpoints
    - Test `handle_sources` returns correct prefix structure with mock S3
    - Test `handle_extract` returns 202 with job_id
    - Test `handle_extract_status` returns progress or 404
    - Test `handle_pipeline_summary` returns stage counts
    - Test `handle_discover` with `blank_page_rate` returns dual estimates
    - Create `tests/unit/test_data_prep_handlers.py`
    - _Requirements: 1.1, 2.1, 2.2, 3.2, 4.2_

- [ ] 6. Checkpoint — Verify handler endpoints and tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Register new API Gateway routes via add_routes.py
  - [x] 7.1 Add source browser routes to `infra/cdk/add_routes.py`
    - Add route creation for `/batch-loader/sources` (GET), `/batch-loader/extract` (POST), `/batch-loader/extract-status` (GET), `/batch-loader/pipeline-summary` (GET)
    - Each route gets Lambda proxy integration pointing to the existing CaseFiles Lambda
    - Each route gets CORS OPTIONS method
    - Follow the existing pattern in `main()` for batch-loader sub-routes
    - _Requirements: 1.1, 2.1, 2.2, 4.2_

- [x] 8. Build Source Browser tab in batch-loader.html
  - [x] 8.1 Add Source Browser tab and prefix inventory table
    - Add new sub-tab button "📂 Source Browser" to the sub-tabs bar (before Discovery & Launch)
    - Create `sub-sources` content section with:
      - Summary row at top: total files, extracted PDFs ready, already processed, remaining unprocessed
      - Table of prefixes with columns: Prefix, Total Objects, Total Size, PDFs, Zips
      - Expandable rows for zip archives within each prefix showing: zip name, size, estimated file count, extraction status
      - Refresh button that re-fetches `/batch-loader/sources`
    - Style using existing CSS patterns (`.data-table`, `.stat-card-sm`, `.section-card`)
    - Show error message with S3 error code and retry button on failure (Req 1.5)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 8.2 Add zip extraction UI controls
    - Add checkbox per zip archive row for selection
    - Add "Extract Selected" button that POSTs to `/batch-loader/extract` with selected `zip_keys`
    - Show extraction progress panel: job ID, current zip, progress bar, files extracted/total, elapsed time
    - Poll `/batch-loader/extract-status` every 5 seconds while extraction is running
    - Display "Already Extracted" badge and disable checkbox for zips with completion records (Req 2.7)
    - Show error list for skipped files on completion
    - _Requirements: 2.1, 2.2, 2.5, 2.6, 2.7_

  - [x] 8.3 Add Pipeline Dashboard tab
    - Add new sub-tab button "🔄 Pipeline" to the sub-tabs bar
    - Create `sub-pipeline` content section with visual flow diagram:
      - Stages displayed left-to-right: Source Archives (zips) → Extract → Raw PDFs → Blank Filter → Ingestion Pipeline
      - Each stage shows file count and label
      - Stages with zero files show grey indicator (not hidden) (Req 4.5)
    - Fetch data from `GET /batch-loader/pipeline-summary`
    - Show selected prefixes with link to navigate to prefix selector
    - Auto-refresh every 5 seconds when a batch is in progress (Req 4.3)
    - Style as connected cards with arrows between stages
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 8.4 Add multi-prefix selector with checkboxes to Discovery & Launch tab
    - Replace the text input `cfgSourcePrefixes` with a checkbox list populated from `/batch-loader/sources`
    - Show only prefixes with `pdf_count > 0` (Property 11, Req 5.1)
    - Default check `pdfs/` and `bw-documents/` (Req 5.2)
    - Show unprocessed file count badge next to each prefix checkbox (Req 5.5)
    - Update counts when selection changes and Preview Batch is clicked
    - Disable Preview Batch and Start Batch buttons when no prefixes selected, show message (Req 5.6)
    - Pass selected prefixes to `handle_discover` and `handle_start` as comma-separated list
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 8.5 Add blank-adjusted cost estimate display to Discovery & Launch tab
    - Add blank page rate slider (0%–100%, default 40%) below the batch config section
    - Display dual cost estimate table: Gross column, Net column, with blank rate percentage shown between them
    - Show per-component breakdown rows: Textract OCR, Bedrock Entity, Bedrock Embedding, Neptune Writes, Total
    - Recalculate net estimates client-side when slider changes (no new API call) (Req 3.4)
    - Pass `blank_page_rate` to the discover API call
    - _Requirements: 3.2, 3.3, 3.4, 3.5_

- [ ] 9. Checkpoint — Verify full UI functionality
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Wire everything together and deploy
  - [x] 10.1 Register API routes
    - Run `python infra/cdk/add_routes.py` to create the 4 new API Gateway routes (sources, extract, extract-status, pipeline-summary) with Lambda proxy integrations and CORS
    - Verify routes are created by checking API Gateway console or listing resources
    - _Requirements: 1.1, 2.1, 2.2, 4.2_

  - [x] 10.2 Deploy Lambda code update
    - Build the Lambda zip including all new/modified files: `src/services/source_browser_service.py`, `src/services/zip_extractor_service.py`, updated `src/lambdas/api/batch_loader_handler.py`, updated `scripts/batch_loader/cost_estimator.py`, `scripts/batch_loader/` directory, and `config/` directory
    - Deploy via `aws lambda update-function-code` using the built zip (same pattern as existing deploy workflow)
    - Verify deployment by calling `GET /batch-loader/sources` and confirming a response
    - _Requirements: all_

- [ ] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Documentation
  - [ ] 12.1 Add Data Prep & Source Management section to `docs/deployment-guide.md`
    - Document the 4 new API endpoints: `/batch-loader/sources`, `/batch-loader/extract`, `/batch-loader/extract-status`, `/batch-loader/pipeline-summary`
    - Document the new UI tabs: Source Browser, Pipeline Dashboard
    - Document the multi-prefix selector and blank-adjusted cost estimate features
    - Document the zip extraction workflow: how to select zips, monitor progress, handle chunked extraction
    - Document deployment steps: running `add_routes.py` for new routes, rebuilding Lambda zip with `scripts/batch_loader/` and `config/` included, updating Lambda code
    - Document configuration: default blank page rate, source bucket, data lake bucket
    - Include troubleshooting: S3 permission errors, Lambda timeout on large zips, extraction resume behavior
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- No CDK stack changes — all Lambda updates via `deploy.py`, all API routes via `add_routes.py`
- The user should run `python infra/cdk/add_routes.py` once to register new routes, then rebuild and deploy the Lambda zip
