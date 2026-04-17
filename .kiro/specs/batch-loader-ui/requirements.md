# Requirements: Batch Loader UI

## Introduction

Exposes the existing incremental batch loader (scripts/batch_loader.py and its 9 sub-modules) through the frontend UI, so users can trigger batch loads, monitor real-time progress, view batch manifests, and manage quarantined files from the browser. The backend is a new Lambda handler that reuses the existing batch_loader modules (discovery, cost_estimator, manifest, quarantine, ledger_integration) for S3 state reads, and kicks off batch processing by invoking the existing ingest API in sub-batches. Batch state is persisted in S3 (batch_progress.json, manifests, quarantine.json) so the frontend can poll for updates. The frontend is a new HTML page (batch-loader.html) integrated into the existing nav bar, following the same patterns as pipeline-config.html and investigator.html.

## Glossary

- **Batch_Loader_UI**: The new frontend HTML page (batch-loader.html) that provides a browser-based interface for configuring, launching, monitoring, and reviewing batch loads.
- **Batch_Loader_API**: The new Lambda handler (batch_loader_handler.py) that exposes batch loader operations as REST endpoints via API Gateway.
- **Discovery_Preview**: The API response from the discovery endpoint that returns the count of unprocessed raw PDFs, source prefix breakdown, and a cost estimate for the proposed batch.
- **Batch_Session**: A single batch processing run identified by a batch_id, tracked from start to completion via batch_progress.json in S3.
- **Progress_Poller**: The frontend JavaScript timer that periodically calls the batch status endpoint to update the progress display in real time.
- **Manifest_Viewer**: The UI component that displays the per-file results from a completed batch manifest, with filtering and search capabilities.
- **Quarantine_Viewer**: The UI component that displays quarantined files with their failure reasons, timestamps, and batch numbers.
- **Batch_History**: The UI component that displays past batch load entries from the ingestion ledger, showing cumulative statistics.
- **Batch_Progress_Store**: The S3-persisted batch_progress.json file in the data lake bucket that tracks current batch state, phase, and per-phase counters.
- **Cost_Preview**: The cost estimation displayed to the user before starting a batch, calculated using the existing CostEstimator module.
- **Ingest_API**: The existing REST endpoint (POST /case-files/{case_id}/ingest) that triggers Step Functions for document processing.
- **Processing_Ledger**: The existing ingestion_ledger.json extended with batch loader entries.

## Requirements


### Requirement 1: Batch Loader UI Page and Navigation

**User Story:** As an investigator, I want a dedicated Batch Loader page in the frontend nav bar, so that I can access batch loading functionality without using the CLI.

#### Acceptance Criteria

1. THE Batch_Loader_UI SHALL be accessible as a new HTML page (batch-loader.html) linked from the existing nav bar alongside Cases, Pipeline Config, Chat, Wizard, Portfolio, and Workbench.
2. THE Batch_Loader_UI SHALL use the existing common.css stylesheet, config.js for API URL configuration, and the same header/nav bar pattern used by pipeline-config.html and investigator.html.
3. THE Batch_Loader_UI SHALL organize its content into four sub-tabs: "Discovery & Launch", "Live Progress", "Batch History", and "Quarantine".
4. WHEN the Batch_Loader_UI loads, THE Batch_Loader_UI SHALL fetch the list of available cases from GET /case-files and populate a case selector dropdown, defaulting to the Epstein Combined case (ed0b6c27).

### Requirement 2: Discovery and Preview Endpoint

**User Story:** As an investigator, I want to see how many unprocessed raw PDFs are available and what a batch would cost before starting, so that I can make informed decisions about batch size and timing.

#### Acceptance Criteria

1. WHEN the user selects a case and clicks "Preview Batch", THE Batch_Loader_API SHALL call the discovery module to list all raw PDF keys under the configured S3 source prefixes, exclude keys from completed manifests and the quarantine queue, and return the count of unprocessed files.
2. THE Batch_Loader_API SHALL expose a GET /batch-loader/discover endpoint that accepts query parameters: case_id (required), batch_size (default 5000), and source_prefixes (default "pdfs/,bw-documents/").
3. THE Batch_Loader_API SHALL return a Discovery_Preview response containing: total_unprocessed_count, requested_batch_size, actual_batch_size (min of requested and available), source_prefix_breakdown (count per prefix), and a Cost_Preview with per-component cost estimates (Textract OCR, Bedrock entity extraction, Bedrock embedding, Neptune writes, total).
4. THE Batch_Loader_UI SHALL display the Discovery_Preview in a summary card showing unprocessed file count, proposed batch size, and a formatted cost breakdown table.
5. IF no unprocessed files remain, THEN THE Batch_Loader_API SHALL return total_unprocessed_count of 0 and THE Batch_Loader_UI SHALL display a "All files processed" message with cumulative statistics.


### Requirement 3: Batch Configuration Controls

**User Story:** As an investigator, I want to configure batch parameters (batch size, source prefixes, entity resolution toggle) from the UI before starting a batch, so that I can tune processing without editing CLI arguments.

#### Acceptance Criteria

1. THE Batch_Loader_UI SHALL provide input controls for: batch_size (numeric input, default 5000, range 1-50000), sub_batch_size (numeric input, default 50, range 1-200), source_prefixes (multi-select or comma-separated text input, default "pdfs/, bw-documents/"), and enable_entity_resolution (toggle, default on).
2. THE Batch_Loader_UI SHALL provide an OCR threshold slider (default 50 chars/page, range 10-200) and a blank threshold slider (default 10 chars, range 1-100).
3. WHEN the user changes any configuration parameter, THE Batch_Loader_UI SHALL re-fetch the Discovery_Preview to update the cost estimate and file counts.
4. THE Batch_Loader_UI SHALL validate that batch_size is a positive integer and source_prefixes contains at least one non-empty prefix before enabling the "Start Batch" button.

### Requirement 4: Start Batch Endpoint

**User Story:** As an investigator, I want to click "Start Batch" to kick off batch processing from the browser, so that I do not need SSH access or CLI tools to run a batch.

#### Acceptance Criteria

1. WHEN the user clicks "Start Batch", THE Batch_Loader_UI SHALL send a POST /batch-loader/start request with the configured parameters: case_id, batch_size, sub_batch_size, source_prefixes, enable_entity_resolution, ocr_threshold, and blank_threshold.
2. THE Batch_Loader_API SHALL validate all parameters, create a new Batch_Session with a unique batch_id, initialize batch_progress.json in S3 with status "discovery", and return the batch_id to the frontend.
3. THE Batch_Loader_API SHALL begin asynchronous batch processing: run discovery to select the batch files, then proceed through extraction, filtering, sub-batch ingestion, SFN polling, and entity resolution phases.
4. IF a batch is already in progress for the same case_id, THEN THE Batch_Loader_API SHALL return a 409 Conflict error and THE Batch_Loader_UI SHALL display a message indicating a batch is already running with a link to the Live Progress tab.
5. WHEN the batch starts successfully, THE Batch_Loader_UI SHALL automatically switch to the "Live Progress" tab and begin polling for status updates.


### Requirement 5: Real-Time Progress Tracking

**User Story:** As an investigator, I want to watch batch processing progress in real time from the browser, so that I can monitor extraction, ingestion, and entity resolution phases without checking CLI output.

#### Acceptance Criteria

1. THE Batch_Loader_API SHALL expose a GET /batch-loader/status endpoint that accepts a case_id query parameter and returns the current Batch_Progress_Store contents from S3: batch_id, status (discovery, extracting, filtering, ingesting, polling_sfn, entity_resolution, completed, failed, paused), current_phase, phase_progress (items_completed / items_total for the current phase), overall_progress (files_processed / batch_size), elapsed_time, and per-phase statistics.
2. THE Progress_Poller SHALL poll the status endpoint every 5 seconds while a batch is in the "extracting", "filtering", "ingesting", or "polling_sfn" phase, and every 15 seconds during the "entity_resolution" phase.
3. THE Batch_Loader_UI SHALL display a multi-phase progress visualization showing: a phase indicator bar (discovery → extraction → filtering → ingestion → SFN polling → entity resolution → complete), a numeric progress counter for the current phase, and a running total of documents processed.
4. THE Batch_Loader_UI SHALL display real-time statistics during processing: extraction method breakdown (PyPDF2 vs Textract vs failed), blank filter count, sub-batches sent, SFN executions triggered, SFN succeeded/failed counts.
5. WHEN the batch status changes to "completed", THE Progress_Poller SHALL stop polling and THE Batch_Loader_UI SHALL display a completion summary with final statistics and a link to view the batch manifest.
6. WHEN the batch status changes to "failed" or "paused", THE Batch_Loader_UI SHALL display the error reason and, for "paused" status (failure threshold exceeded), provide a "Resume" button.
7. THE Batch_Loader_API SHALL update the Batch_Progress_Store in S3 after each sub-batch completes, after each SFN execution reaches a terminal state, and after entity resolution finishes.

### Requirement 6: Batch Manifest Viewer

**User Story:** As an investigator, I want to view the detailed manifest for any completed batch showing per-file results, so that I can audit which files succeeded, failed, were blank, or were quarantined.

#### Acceptance Criteria

1. THE Batch_Loader_API SHALL expose a GET /batch-loader/manifests endpoint that accepts a case_id query parameter and returns a list of available batch manifests with summary statistics (batch_id, batch_number, started_at, completed_at, total_files, succeeded, failed, blank_filtered, quarantined).
2. THE Batch_Loader_API SHALL expose a GET /batch-loader/manifests/{batch_id} endpoint that returns the full manifest JSON for a specific batch, including per-file entries.
3. THE Batch_Loader_UI SHALL display the manifest list as a table with sortable columns and, when a manifest is selected, show the per-file details in a scrollable table with columns: S3 Key, Extraction Method, Char Count, Blank, Pipeline Status, SFN ARN, Error.
4. THE Manifest_Viewer SHALL provide filter controls to show only files matching a specific pipeline_status (succeeded, failed, blank_filtered, quarantined) or extraction_method (pypdf2, textract, failed).
5. THE Manifest_Viewer SHALL display a summary bar at the top of the per-file table showing counts for each status category and a pie or bar chart of the status distribution.


### Requirement 7: Quarantine Viewer

**User Story:** As an investigator, I want to view all quarantined files across batches with their failure reasons, so that I can investigate persistent failures and decide whether to retry or permanently exclude files.

#### Acceptance Criteria

1. THE Batch_Loader_API SHALL expose a GET /batch-loader/quarantine endpoint that accepts a case_id query parameter and returns the full quarantine list from quarantine.json in S3: for each entry, the s3_key, reason, failed_at timestamp, retry_count, and batch_number.
2. THE Quarantine_Viewer SHALL display quarantined files in a sortable table with columns: S3 Key, Failure Reason, Failed At, Retry Count, Batch Number.
3. THE Quarantine_Viewer SHALL display a summary card at the top showing: total quarantined count, breakdown by failure reason category (extraction_failed, pipeline_failed, timeout), and the most recent quarantine timestamp.
4. THE Quarantine_Viewer SHALL provide a search/filter input to filter quarantined files by S3 key substring or failure reason.

### Requirement 8: Batch History from Ingestion Ledger

**User Story:** As an investigator, I want to view the history of all batch loads from the ingestion ledger, so that I can see cumulative progress and statistics across all batches.

#### Acceptance Criteria

1. THE Batch_Loader_API SHALL expose a GET /batch-loader/history endpoint that accepts a case_id query parameter and returns all batch load entries from the Processing_Ledger for that case, plus the current batch_progress.json cumulative statistics.
2. THE Batch_History SHALL display batch entries in a reverse-chronological table with columns: Batch ID, Timestamp, Source Files, Blanks Skipped, Docs Sent, SFN Succeeded, SFN Failed, Textract OCR Count, Entity Resolution Result, and Estimated Cost.
3. THE Batch_History SHALL display a cumulative statistics card at the top showing: total files discovered, total processed, total remaining, total blanks filtered, total quarantined, total estimated cost, and current cursor position from batch_progress.json.
4. WHEN the user clicks a batch entry in the history table, THE Batch_Loader_UI SHALL navigate to the Manifest Viewer for that batch.

### Requirement 9: Lambda Handler and API Gateway Integration

**User Story:** As a developer, I want the batch loader endpoints served by a Lambda handler integrated with the existing API Gateway, so that the frontend can call them using the same API URL and CORS configuration as all other endpoints.

#### Acceptance Criteria

1. THE Batch_Loader_API SHALL be implemented as a new Lambda handler (batch_loader_handler.py) following the same dispatch pattern used by pipeline_config.py, with a dispatch_handler function that routes requests based on HTTP method and resource path.
2. THE Batch_Loader_API SHALL be registered in the API Gateway definition (api_definition.yaml) under the /batch-loader/* path prefix with Lambda proxy integration.
3. THE Batch_Loader_API SHALL handle CORS preflight OPTIONS requests and include CORS headers in all responses, consistent with the existing response_helper.py pattern.
4. THE Batch_Loader_API SHALL import and reuse the existing batch_loader modules (discovery, cost_estimator, manifest, quarantine, ledger_integration) for reading S3 state, rather than reimplementing that logic.
5. WHEN the start endpoint initiates long-running batch processing, THE Batch_Loader_API SHALL return immediately with the batch_id and process asynchronously, updating the Batch_Progress_Store in S3 as processing proceeds.

### Requirement 10: Error Handling and Edge Cases

**User Story:** As an investigator, I want clear error messages and graceful handling of edge cases in the batch loader UI, so that I understand what went wrong and can take corrective action.

#### Acceptance Criteria

1. IF the Batch_Loader_API cannot reach S3 to read batch state, THEN THE Batch_Loader_API SHALL return a 503 Service Unavailable error with a descriptive message and THE Batch_Loader_UI SHALL display a retry prompt.
2. IF the user attempts to start a batch with a batch_size larger than the number of unprocessed files, THEN THE Batch_Loader_API SHALL accept the request and process all remaining files as a partial batch (consistent with the existing CLI behavior).
3. WHEN the Progress_Poller receives a network error or timeout, THE Batch_Loader_UI SHALL display a "Connection lost — retrying" indicator and continue polling with exponential backoff up to 60 seconds.
4. IF the batch processing encounters a failure rate exceeding the configured threshold (default 10%), THEN THE Batch_Loader_API SHALL set the batch status to "paused" in the Batch_Progress_Store and THE Batch_Loader_UI SHALL display the failure details with a "Resume" button.
5. THE Batch_Loader_UI SHALL disable the "Start Batch" button and show a spinner while the start request is in flight, preventing duplicate batch submissions.