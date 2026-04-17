# Implementation Plan: Batch Loader UI

## Overview

Expose the existing incremental batch loader through a browser-based UI. The implementation follows dependency order: S3 state service → Lambda handler → frontend page → API Gateway routes → nav bar updates. The backend reuses existing `scripts/batch_loader/` modules and follows the dispatch pattern from `pipeline_config.py`. The frontend follows the same structure as `pipeline-config.html`.

## Tasks

- [x] 1. Implement BatchLoaderState service
  - [x] 1.1 Create `src/services/batch_loader_state.py` with the `BatchLoaderState` class
    - Constructor accepts `s3_client`, `data_lake_bucket`, and `case_id`
    - Implement `read_progress()` — read `batch-progress/{case_id}/batch_progress.json` from S3, return dict or None
    - Implement `write_progress(progress: dict)` — write progress JSON to S3
    - Implement `read_quarantine()` — read `batch-progress/{case_id}/quarantine.json` from S3, return list of dicts
    - Implement `write_quarantine(entries: list[dict])` — write quarantine JSON to S3
    - Implement `read_ledger()` — read `batch-progress/{case_id}/ingestion_ledger.json` from S3
    - Implement `append_ledger_entry(entry: dict)` — read-modify-write ledger in S3
    - Implement `list_manifests()` — list all `batch-manifests/{case_id}/batch_*.json` objects, parse each for summary stats (batch_id, batch_number, started_at, completed_at, total_files, succeeded, failed, blank_filtered, quarantined)
    - Implement `read_manifest(batch_id: str)` — read a specific manifest JSON from S3
    - Implement `is_batch_in_progress()` — read progress, return `(True, batch_id)` if status is non-terminal, else `(False, None)`
    - Use `botocore.exceptions.ClientError` with error code `NoSuchKey` for missing-key handling
    - _Requirements: 5.1, 5.7, 6.1, 6.2, 7.1, 8.1, 9.4, 9.5_

  - [ ]* 1.2 Write unit tests for BatchLoaderState in `tests/unit/test_batch_loader_state.py`
    - Mock S3 client using unittest.mock
    - Test `read_progress` returns None when key missing, returns parsed dict when present
    - Test `write_progress` calls `put_object` with correct bucket/key/JSON
    - Test `read_quarantine` returns empty list when key missing
    - Test `list_manifests` aggregates summary stats from multiple manifest files
    - Test `read_manifest` returns full manifest JSON
    - Test `is_batch_in_progress` returns True for non-terminal statuses, False for completed/failed/None
    - _Requirements: 5.1, 6.1, 6.2, 7.1, 9.4_

  - [ ]* 1.3 Write property test: Status round-trip (Property 6)
    - **Property 6: Status endpoint round-trip**
    - For any valid batch_progress dict written via `write_progress`, reading it back via `read_progress` should return identical content
    - Use Hypothesis to generate progress dicts with valid status values and counters
    - **Validates: Requirements 5.1**

  - [ ]* 1.4 Write property test: Progress phase invariants (Property 7)
    - **Property 7: Progress file phase invariants**
    - For any batch_progress dict, status must be one of the valid values; when "completed", files_processed == batch_size; when "paused"/"failed", error_reason is non-null
    - **Validates: Requirements 5.7, 10.4**

  - [ ]* 1.5 Write property test: Manifest list completeness (Property 8)
    - **Property 8: Manifest list completeness**
    - For any set of manifest dicts stored in S3, `list_manifests` returns one entry per manifest with correct summary counts matching the files array
    - **Validates: Requirements 6.1, 6.5**

  - [ ]* 1.6 Write property test: Manifest retrieval round-trip (Property 9)
    - **Property 9: Manifest retrieval round-trip**
    - For any manifest JSON written to S3, `read_manifest(batch_id)` returns the same JSON content
    - **Validates: Requirements 6.2**

  - [ ]* 1.7 Write property test: Concurrent batch prevention (Property 5)
    - **Property 5: Concurrent batch prevention**
    - For any progress with non-terminal status, `is_batch_in_progress` returns `(True, batch_id)`; for terminal or missing, returns `(False, None)`
    - **Validates: Requirements 4.4**

- [x] 2. Checkpoint — Backend state service
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Implement Lambda handler dispatch and sync endpoints
  - [x] 3.1 Create `src/lambdas/api/batch_loader_handler.py` with `dispatch_handler`
    - Follow the same dispatch pattern as `pipeline_config.py`
    - Route OPTIONS to CORS response, `action == "process_batch"` to async worker
    - Route GET /batch-loader/discover, POST /batch-loader/start, GET /batch-loader/status, GET /batch-loader/manifests, GET /batch-loader/manifests/{batch_id}, GET /batch-loader/quarantine, GET /batch-loader/history
    - Return 404 for unrecognized routes
    - Import `CORS_HEADERS`, `success_response`, `error_response` from `lambdas.api.response_helper`
    - _Requirements: 9.1, 9.3_

  - [x] 3.2 Implement `handle_discover` endpoint handler
    - Parse query params: case_id (required), batch_size (default 5000), source_prefixes (default "pdfs/,bw-documents/")
    - Instantiate `BatchConfig` with parsed params, create S3 client, instantiate `BatchDiscovery`
    - Call discovery to get unprocessed keys, compute source_prefix_breakdown
    - Instantiate `CostEstimator`, call `estimate(actual_batch_size)` for cost_preview
    - If total_unprocessed_count == 0, return cumulative_stats from progress file instead of cost_preview
    - Return 400 if case_id missing
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 3.3 Implement `handle_start` endpoint handler
    - Parse request body: case_id, batch_size, sub_batch_size, source_prefixes, enable_entity_resolution, ocr_threshold, blank_threshold
    - Validate: batch_size positive integer, sub_batch_size 1-200, source_prefixes non-empty
    - Check `is_batch_in_progress()` — return 409 with active batch_id if running
    - Generate batch_id (e.g. `batch_{next_number:03d}`)
    - Write initial batch_progress.json to S3 with status "discovery"
    - Invoke self asynchronously via `lambda_client.invoke(FunctionName=context.function_name, InvocationType='Event', Payload=...)`
    - Return 202 with batch_id
    - _Requirements: 4.1, 4.2, 4.4, 9.5, 3.4_

  - [x] 3.4 Implement `handle_status` endpoint handler
    - Parse query param: case_id (required)
    - Read batch_progress.json from S3 via BatchLoaderState
    - Compute elapsed_time from started_at to now
    - Return full progress dict with elapsed_time_seconds
    - Return 404 if no progress file exists
    - _Requirements: 5.1_

  - [x] 3.5 Implement `handle_list_manifests` and `handle_get_manifest` endpoint handlers
    - `handle_list_manifests`: parse case_id, call `state.list_manifests()`, return list
    - `handle_get_manifest`: parse case_id and batch_id path param, call `state.read_manifest(batch_id)`, return full manifest or 404
    - _Requirements: 6.1, 6.2_

  - [x] 3.6 Implement `handle_quarantine` endpoint handler
    - Parse case_id query param
    - Read quarantine entries from S3 via BatchLoaderState
    - Compute summary: total_quarantined, by_reason breakdown (categorize reasons into extraction_failed, pipeline_failed, timeout), most_recent timestamp
    - Return quarantined_files list and summary
    - _Requirements: 7.1, 7.3_

  - [x] 3.7 Implement `handle_history` endpoint handler
    - Parse case_id query param
    - Read ingestion ledger from S3 via BatchLoaderState
    - Read batch_progress.json for cumulative_stats
    - Return batches list (reverse-chronological) and cumulative_stats
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 3.8 Implement `async_process_batch` worker function
    - Invoked when `event.get("action") == "process_batch"`
    - Read config from event payload, instantiate BatchConfig, S3 client, BatchLoaderState
    - Phase 1 — Discovery: use `BatchDiscovery` to get batch keys, update progress to "extracting"
    - Phase 2 — Extraction: use `TextExtractor` to extract text from each PDF, update progress periodically
    - Phase 3 — Filtering: use `BlankFilter` to filter blanks, update progress to "ingesting"
    - Phase 4 — Ingestion: use `PipelineIngestion.send_sub_batches()` for non-blank docs, update sub_batches_sent counter after each sub-batch
    - Phase 5 — SFN Polling: use `PipelineIngestion.poll_executions()`, update sfn_succeeded/sfn_failed
    - Phase 6 — Entity Resolution: if enabled, call POST /case-files/{id}/entity-resolution
    - Write batch manifest to S3 via `BatchManifest.save()`
    - Update quarantine for failed files via `QuarantineManager`
    - Append ledger entry via `BatchLoaderState.append_ledger_entry()`
    - Set final status to "completed" (or "failed"/"paused" on errors)
    - Check failure threshold after ingestion — if exceeded, set status to "paused" with error_reason
    - Wrap entire worker in try/except — on unhandled exception, set status to "failed" with error_reason
    - _Requirements: 4.3, 5.7, 9.4, 9.5, 10.4_

  - [ ]* 3.9 Write unit tests for handler dispatch and sync endpoints in `tests/unit/test_batch_loader_handler.py`
    - Mock BatchLoaderState and batch_loader modules
    - Test dispatch routes each method/resource to correct handler
    - Test OPTIONS returns CORS headers
    - Test unrecognized route returns 404
    - Test handle_discover returns correct response shape with cost_preview
    - Test handle_discover returns cumulative_stats when no unprocessed files
    - Test handle_start returns 202 with batch_id for valid request
    - Test handle_start returns 409 when batch in progress
    - Test handle_start returns 400 for invalid params (negative batch_size, empty prefixes)
    - Test handle_status returns progress dict
    - Test handle_status returns 404 when no progress file
    - Test handle_quarantine computes summary correctly
    - Test handle_history returns reverse-chronological entries
    - _Requirements: 2.2, 4.2, 4.4, 5.1, 7.3, 8.2, 9.1, 9.3_

  - [ ]* 3.10 Write property test: Dispatch routing (Property 1)
    - **Property 1: Dispatch handler routes requests correctly**
    - For any valid method/resource combination, dispatch invokes the correct handler; OPTIONS returns CORS; unknown routes return 404
    - **Validates: Requirements 2.2, 9.3**

  - [ ]* 3.11 Write property test: Discovery response completeness (Property 2)
    - **Property 2: Discovery response completeness**
    - For any case_id, batch_size, and source_prefixes, the response contains all required fields with correct types and actual_batch_size <= total_unprocessed_count
    - **Validates: Requirements 2.1, 2.3**

  - [ ]* 3.12 Write property test: Start parameter validation (Property 3)
    - **Property 3: Start batch parameter validation**
    - For any request body, invalid batch_size/sub_batch_size/source_prefixes are rejected with 400; valid requests are accepted
    - **Validates: Requirements 3.4, 4.2**

  - [ ]* 3.13 Write property test: Start initializes progress (Property 4)
    - **Property 4: Start batch initializes progress and returns batch_id**
    - For any valid start request with no in-progress batch, progress is written to S3 with status "discovery" and 202 response contains matching batch_id
    - **Validates: Requirements 4.2, 9.5**

  - [ ]* 3.14 Write property test: Partial batch acceptance (Property 15)
    - **Property 15: Partial batch acceptance**
    - For any start request where batch_size > unprocessed files, the API accepts and sets actual_batch_size to unprocessed count
    - **Validates: Requirements 10.2**

- [x] 4. Checkpoint — Backend Lambda handler
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement filter and aggregation helpers
  - [x] 5.1 Add manifest file filtering logic (used by frontend and testable standalone)
    - Implement a `filter_manifest_files(files: list[dict], pipeline_status: str | None, extraction_method: str | None) -> list[dict]` helper function
    - Filter entries where specified field matches the filter value
    - Place in `src/services/batch_loader_state.py` or as a standalone utility
    - _Requirements: 6.4_

  - [x] 5.2 Add quarantine summary computation and search filtering logic
    - Implement `compute_quarantine_summary(entries: list[dict]) -> dict` — total_quarantined, by_reason breakdown, most_recent timestamp
    - Implement `filter_quarantine(entries: list[dict], search: str) -> list[dict]` — case-insensitive substring match on s3_key or reason
    - _Requirements: 7.3, 7.4_

  - [x] 5.3 Add history aggregation logic
    - Implement `sort_history_entries(entries: list[dict]) -> list[dict]` — reverse-chronological by timestamp
    - Implement `compute_cumulative_stats(entries: list[dict]) -> dict` — sum docs_sent_to_pipeline, blanks_skipped, cost_actual across entries
    - _Requirements: 8.2, 8.3_

  - [ ]* 5.4 Write property test: Manifest file filtering (Property 10)
    - **Property 10: Manifest file filtering**
    - For any file list and filter criteria, filtered results contain only matching entries and are a subset of the full list
    - **Validates: Requirements 6.4**

  - [ ]* 5.5 Write property test: Quarantine summary computation (Property 11)
    - **Property 11: Quarantine summary computation**
    - For any quarantine entry list, total_quarantined == len(entries), by_reason counts sum to total, most_recent == max(failed_at)
    - **Validates: Requirements 7.1, 7.3**

  - [ ]* 5.6 Write property test: Quarantine search filtering (Property 12)
    - **Property 12: Quarantine search filtering**
    - For any entries and search string, filtered results contain only entries where s3_key or reason contains the search string (case-insensitive)
    - **Validates: Requirements 7.4**

  - [ ]* 5.7 Write property test: History reverse-chronological (Property 13)
    - **Property 13: History entries are reverse-chronological**
    - For any list of history entries, sorted output has timestamps in descending order
    - **Validates: Requirements 8.2**

  - [ ]* 5.8 Write property test: Cumulative statistics consistency (Property 14)
    - **Property 14: Cumulative statistics consistency**
    - For any list of batch entries, cumulative total_processed == sum(docs_sent_to_pipeline), total_blanks_filtered == sum(blanks_skipped), total_estimated_cost == sum(cost_actual)
    - **Validates: Requirements 8.1, 8.3**

- [x] 6. Checkpoint — Filter and aggregation helpers
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement frontend page
  - [x] 7.1 Create `src/frontend/batch-loader.html` with page structure and nav bar
    - Use same `<head>`, `common.css`, `config.js`, header, and nav bar pattern as `pipeline-config.html`
    - Add "📦 Batch Loader" link to nav bar (active on this page)
    - Add case selector dropdown that fetches from GET /case-files on load, defaults to Epstein Combined (ed0b6c27)
    - Add four sub-tabs: "Discovery & Launch", "Live Progress", "Batch History", "Quarantine"
    - Implement tab switching JavaScript (same pattern as pipeline-config.html `switchSubTab`)
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 7.2 Implement Discovery & Launch tab
    - Add configuration controls: batch_size (numeric, default 5000, range 1-50000), sub_batch_size (numeric, default 50, range 1-200), source_prefixes (text input, default "pdfs/, bw-documents/"), enable_entity_resolution (toggle, default on)
    - Add OCR threshold slider (default 50, range 10-200) and blank threshold slider (default 10, range 1-100)
    - Add "Preview Batch" button that calls GET /batch-loader/discover with current params
    - Display discovery preview card: unprocessed file count, proposed batch size, cost breakdown table
    - Display "All files processed" message when total_unprocessed_count == 0
    - Re-fetch preview when any config param changes
    - Add "Start Batch" button — validate batch_size > 0 and source_prefixes non-empty before enabling
    - Disable Start Batch button and show spinner while request in flight
    - On successful start (202), auto-switch to Live Progress tab
    - On 409, show message with link to Live Progress tab
    - _Requirements: 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.4, 4.5, 10.5_

  - [x] 7.3 Implement Live Progress tab
    - Add phase indicator bar: discovery → extraction → filtering → ingestion → SFN polling → entity resolution → complete
    - Add numeric progress counter for current phase (items_completed / items_total)
    - Add overall progress bar (files_processed / batch_size)
    - Add real-time stats cards: extraction method breakdown (PyPDF2/Textract/failed), blank filter count, sub-batches sent, SFN succeeded/failed
    - Implement Progress_Poller: poll GET /batch-loader/status every 5s during active phases, every 15s during entity_resolution
    - On "completed" status: stop polling, show completion summary with link to manifest
    - On "failed"/"paused" status: show error reason, provide "Resume" button for paused
    - On network error: show "Connection lost — retrying" indicator, exponential backoff up to 60s
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.3_

  - [x] 7.4 Implement Batch History tab
    - Fetch history from GET /batch-loader/history on tab activation
    - Display cumulative statistics card: total files discovered, total processed, total remaining, total blanks, total quarantined, total cost, cursor position
    - Display reverse-chronological table: Batch ID, Timestamp, Source Files, Blanks Skipped, Docs Sent, SFN Succeeded, SFN Failed, Textract OCR Count, Entity Resolution Result, Estimated Cost
    - On row click, switch to a manifest detail view (call GET /batch-loader/manifests/{batch_id})
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 7.5 Implement Quarantine tab
    - Fetch quarantine from GET /batch-loader/quarantine on tab activation
    - Display summary card: total quarantined, breakdown by reason category, most recent timestamp
    - Display sortable table: S3 Key, Failure Reason, Failed At, Retry Count, Batch Number
    - Add search/filter input for s3_key substring or failure reason filtering
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 7.6 Implement Manifest Viewer (inline in Batch History tab)
    - When a batch is selected from history, display per-file details in scrollable table: S3 Key, Extraction Method, Char Count, Blank, Pipeline Status, SFN ARN, Error
    - Add filter controls for pipeline_status and extraction_method
    - Display summary bar with counts per status category
    - _Requirements: 6.3, 6.4, 6.5_

- [x] 8. Checkpoint — Frontend page
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Add API Gateway routes
  - [x] 9.1 Add 7 batch-loader routes to `infra/api_gateway/api_definition.yaml`
    - Add `/batch-loader/discover` (GET + OPTIONS) with Lambda proxy integration to `${BatchLoaderLambdaArn}`
    - Add `/batch-loader/start` (POST + OPTIONS) with Lambda proxy integration
    - Add `/batch-loader/status` (GET + OPTIONS) with Lambda proxy integration
    - Add `/batch-loader/manifests` (GET + OPTIONS) with Lambda proxy integration
    - Add `/batch-loader/manifests/{batch_id}` (GET + OPTIONS) with Lambda proxy integration
    - Add `/batch-loader/quarantine` (GET + OPTIONS) with Lambda proxy integration
    - Add `/batch-loader/history` (GET + OPTIONS) with Lambda proxy integration
    - Follow the same YAML structure and `x-amazon-apigateway-integration` pattern as existing `/case-files/{id}/pipeline-config` routes
    - _Requirements: 9.2_

- [ ] 10. Update nav bar on all existing frontend pages
  - [x] 10.1 Add "📦 Batch Loader" link to the nav bar in all existing HTML pages
    - Update `src/frontend/investigator.html` — add `<a href="batch-loader.html" class="nav-link">📦 Batch Loader</a>` to the nav-bar div
    - Update `src/frontend/pipeline-config.html` — add Batch Loader nav link
    - Update `src/frontend/chatbot.html` — add Batch Loader nav link
    - Update `src/frontend/wizard.html` — add Batch Loader nav link
    - Update `src/frontend/portfolio.html` — add Batch Loader nav link
    - Update `src/frontend/workbench.html` — add Batch Loader nav link
    - Insert the link after Pipeline Config and before Chat in the nav order
    - _Requirements: 1.1_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after backend, frontend, and integration phases
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The Lambda handler reuses existing `scripts/batch_loader/` modules — no reimplementation of discovery, cost estimation, manifest, or quarantine logic
- The async worker uses Lambda self-invocation with `InvocationType='Event'` for long-running batch processing
