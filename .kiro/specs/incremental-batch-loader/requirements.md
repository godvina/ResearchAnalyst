# Requirements: Incremental Batch Loader

## Introduction

Processes the remaining ~326K raw PDFs through the existing DOJ document analysis pipeline in manageable test batches of 5-6K documents. Builds on the proven Phase 1/Phase 2 loading pattern (scripts/phase1_load_ds15.py, scripts/phase2_load_ds11.py) but automates batch discovery, text extraction with OCR fallback, progress tracking, and entity resolution at batch boundaries. The loader is CLI-driven (Python script), idempotent (picks up where it left off), cost-aware (estimates before each batch), and designed to scale entity resolution from O(n²) to O(n) via a canonical entity index. All loads target the existing Epstein Combined case (ed0b6c27) and are tracked in the ingestion ledger (scripts/ingestion_ledger.json).

## Glossary

- **Batch_Loader**: The CLI Python script that orchestrates end-to-end batch processing: discovery, extraction, filtering, ingestion, entity resolution, and ledger updates.
- **Batch**: A configurable group of raw PDF files (default 5,000-6,000) processed as a single unit of work through the full pipeline.
- **Processing_Ledger**: The existing ingestion_ledger.json file extended with per-batch tracking entries, cursor position, and cumulative statistics.
- **Cursor**: A persistent marker (S3 key or offset) indicating the last processed file, enabling the Batch_Loader to resume from where it left off.
- **Text_Extractor**: The subsystem that attempts PyPDF2 direct text extraction first, then falls back to Textract OCR for scanned/image-based PDFs.
- **Blank_Filter**: The subsystem that discards documents with fewer than a configurable character threshold (default 10 characters) after text extraction.
- **Extraction_Cache**: Pre-extracted text JSONs saved to S3 so that text extraction never runs twice for the same source PDF.
- **Canonical_Entity_Index**: A persistent lookup table (keyed by normalized entity name + type) that enables O(n) entity dedup at ingestion time instead of O(n²) pairwise comparison.
- **Batch_Manifest**: A JSON file listing all source PDF keys, their extraction status, and pipeline outcome for a single batch, stored alongside the batch ledger entry.
- **Quarantine_Queue**: A set of persistently failed documents (failed extraction or pipeline ingestion after retries) excluded from future batches.
- **Cost_Estimator**: The subsystem that calculates estimated AWS costs (Textract OCR, Bedrock entity extraction, Neptune writes) before a batch runs.
- **Dry_Run_Mode**: A mode where the Batch_Loader previews what would be processed, estimated costs, and expected outcomes without making any changes.
- **Ingest_API**: The existing REST endpoint (POST /case-files/{case_id}/ingest) that triggers Step Functions for entity extraction, embedding, and Neptune graph loading.
- **Step_Functions_Pipeline**: The existing AWS Step Functions state machine that processes ingested documents through Bedrock entity extraction, embedding generation, and Neptune graph loading.

## Requirements

### Requirement 1: Batch Discovery and Cursor-Based Resumption

**User Story:** As a data engineer, I want the batch loader to automatically discover the next N unprocessed raw PDFs from S3 and resume from where the last batch left off, so that no document is processed twice and no document is skipped.

#### Acceptance Criteria

1. WHEN the Batch_Loader starts, THE Batch_Loader SHALL list all raw PDF keys under the configured S3 prefixes (pdfs/ and bw-documents/ in the source bucket) and exclude any keys already recorded in the Processing_Ledger or Extraction_Cache.
2. THE Batch_Loader SHALL persist a Cursor (the S3 key of the last file included in the previous batch) in the Processing_Ledger so that subsequent runs resume from the next unprocessed file.
3. WHEN the Batch_Loader resumes after a partial or failed run, THE Batch_Loader SHALL skip all files whose S3 keys appear in completed batch manifests or the Quarantine_Queue.
4. THE Batch_Loader SHALL accept a configurable batch_size parameter (default 5,000) controlling how many raw PDFs to include in a single batch.
5. WHEN fewer unprocessed files remain than the configured batch_size, THE Batch_Loader SHALL process all remaining files as a final partial batch.
6. THE Batch_Loader SHALL generate a Batch_Manifest JSON listing every source PDF key, its extraction status, and pipeline outcome, saved to S3 alongside the batch ledger entry.

### Requirement 2: Text Extraction with OCR Fallback

**User Story:** As a data engineer, I want the batch loader to extract text from raw PDFs using PyPDF2 first and fall back to Textract OCR for scanned documents, so that both native-text and image-based PDFs are processed correctly.

#### Acceptance Criteria

1. WHEN a raw PDF is processed, THE Text_Extractor SHALL attempt PyPDF2 direct text extraction first.
2. WHEN PyPDF2 extraction yields fewer than a configurable character threshold (default 50 characters per page), THE Text_Extractor SHALL classify the PDF as scanned and submit it to AWS Textract for OCR.
3. WHEN Textract OCR completes, THE Text_Extractor SHALL combine the OCR output into a single text string for the document.
4. THE Text_Extractor SHALL save the extracted text as a JSON file to the Extraction_Cache in S3 (under a textract-output/batch_{batch_id}/ prefix) so that re-runs skip already-extracted files.
5. IF a PDF cannot be read by PyPDF2 (corrupted or encrypted), THEN THE Text_Extractor SHALL log the error, mark the file in the Batch_Manifest as "extraction_failed", and continue processing the remaining files in the batch.
6. THE Text_Extractor SHALL record the extraction method used (pypdf2 or textract) and character count in the Batch_Manifest for each file.

### Requirement 3: Blank Document Filtering

**User Story:** As a data engineer, I want truly blank documents filtered out before they enter the ingestion pipeline, so that pipeline resources and costs are not wasted on empty content.

#### Acceptance Criteria

1. WHEN text extraction completes for a document, THE Blank_Filter SHALL discard documents with fewer than a configurable character threshold (default 10 characters of non-whitespace text).
2. THE Blank_Filter SHALL record each filtered document in the Batch_Manifest with status "blank_filtered" and the extracted character count.
3. THE Batch_Loader SHALL report the blank-to-valid ratio for each batch in the batch summary, consistent with the ~40-55% blank rate observed in prior loads.

### Requirement 4: Pipeline Ingestion via Existing Ingest API

**User Story:** As a data engineer, I want non-blank extracted text sent through the existing ingest API in sub-batches, so that the proven Step Functions pipeline (Bedrock entity extraction, embedding, Neptune graph load) processes each document.

#### Acceptance Criteria

1. WHEN a batch of non-blank documents is ready, THE Batch_Loader SHALL send documents to the Ingest_API (POST /case-files/{case_id}/ingest) in sub-batches of a configurable size (default 50 documents per API call), matching the pattern used in phase1_load_ds15.py and phase2_load_ds11.py.
2. THE Batch_Loader SHALL target the existing Epstein Combined case (ed0b6c27) by default, with the case_id configurable via CLI parameter.
3. THE Batch_Loader SHALL record each Step_Functions_Pipeline execution ARN returned by the Ingest_API in the Batch_Manifest.
4. THE Batch_Loader SHALL wait for all Step_Functions_Pipeline executions in the current batch to reach a terminal state (SUCCEEDED, FAILED, TIMED_OUT, ABORTED) before proceeding to entity resolution.
5. WHEN polling Step Functions status, THE Batch_Loader SHALL use exponential backoff starting at 30 seconds, capped at 5 minutes between polls.
6. THE Batch_Loader SHALL insert a configurable delay (default 2 seconds) between sub-batch API calls to avoid throttling the Ingest_API.

### Requirement 5: Entity Resolution at Batch Boundaries

**User Story:** As a data engineer, I want entity resolution to run automatically after each batch completes, so that duplicate entities are merged incrementally rather than accumulating into an unmanageable O(n²) problem at the end.

#### Acceptance Criteria

1. WHEN all Step_Functions_Pipeline executions for a batch complete successfully, THE Batch_Loader SHALL trigger entity resolution on the target case using the existing entity resolution endpoint (POST /case-files/{case_id}/entity-resolution).
2. THE Batch_Loader SHALL run entity resolution in no-LLM mode (fuzzy matching only) for speed at scale, consistent with the approach validated in Phase 2.
3. THE Batch_Loader SHALL record entity resolution results (clusters merged, nodes dropped, edges relinked, errors) in the Processing_Ledger for each batch.
4. IF entity resolution fails, THEN THE Batch_Loader SHALL log the error and continue to the next batch, marking entity resolution as "failed" in the ledger entry for that batch.

### Requirement 6: Scalable Entity Resolution via Canonical Entity Index

**User Story:** As a data engineer, I want entity resolution to use a canonical entity index for O(n) dedup instead of O(n²) pairwise comparison, so that resolution remains fast as the graph grows to 300K+ documents.

#### Acceptance Criteria

1. THE Batch_Loader SHALL maintain a Canonical_Entity_Index — a persistent JSON or DynamoDB table mapping normalized entity names to their canonical form, keyed by (normalized_name, entity_type).
2. WHEN entity resolution runs after a batch, THE Batch_Loader SHALL first check new entities against the Canonical_Entity_Index for known matches before performing pairwise comparison among unmatched entities only.
3. WHEN a new merge cluster is confirmed, THE Batch_Loader SHALL update the Canonical_Entity_Index with all aliases pointing to the canonical name.
4. THE Batch_Loader SHALL partition entity comparison by entity_type so that persons are only compared to persons, organizations to organizations, and so on, consistent with the existing EntityResolutionService.find_candidates behavior.
5. THE Canonical_Entity_Index SHALL persist across batch runs so that entity knowledge accumulates over time.

### Requirement 7: Error Handling, Retry, and Quarantine

**User Story:** As a data engineer, I want failed documents retried automatically and persistently failing documents quarantined, so that transient errors are recovered and bad files do not block batch progress.

#### Acceptance Criteria

1. WHEN a document fails text extraction or pipeline ingestion, THE Batch_Loader SHALL retry the document up to a configurable number of times (default 3 retries) with exponential backoff.
2. WHEN a document fails all retry attempts, THE Batch_Loader SHALL add the document's S3 key to the Quarantine_Queue with the failure reason and timestamp.
3. THE Quarantine_Queue SHALL persist across batch runs so that quarantined documents are excluded from future batch discovery.
4. THE Batch_Loader SHALL report quarantined document counts in the batch summary and cumulative totals in the Processing_Ledger.
5. IF more than a configurable percentage of documents in a batch fail (default 10%), THEN THE Batch_Loader SHALL pause processing and prompt the operator to investigate before continuing.

### Requirement 8: Cost Estimation and Dry-Run Mode

**User Story:** As a data engineer, I want to see estimated AWS costs before each batch runs and have a dry-run mode that previews processing without making changes, so that I can budget and validate before committing resources.

#### Acceptance Criteria

1. WHEN the Batch_Loader starts (or when --dry-run is specified), THE Cost_Estimator SHALL calculate estimated costs for the batch: Textract OCR cost (estimated scanned PDF count × $0.001/page × estimated pages), Bedrock entity extraction cost (non-blank doc count × ~$0.004/doc), and Neptune/OpenSearch write costs.
2. THE Cost_Estimator SHALL use the observed blank rate from prior batches (stored in the Processing_Ledger) to estimate the non-blank document count for cost projection.
3. WHEN --dry-run is specified, THE Batch_Loader SHALL list the files that would be processed, display the cost estimate, show the expected batch manifest, and exit without modifying any state.
4. THE Batch_Loader SHALL display the cost estimate at the start of each batch and require --confirm (or an interactive prompt) before proceeding with actual processing.

### Requirement 9: Processing Ledger Integration

**User Story:** As a data engineer, I want every batch recorded in the existing ingestion ledger with a full audit trail, so that I have a single source of truth for all data loads across the project.

#### Acceptance Criteria

1. WHEN a batch completes, THE Batch_Loader SHALL append a load entry to the Processing_Ledger (scripts/ingestion_ledger.json) with: load_id (batch_{batch_number}), timestamp, source prefixes, source_files_total, blanks_skipped, docs_sent_to_pipeline, sfn_executions count, sfn_succeeded count, sfn_failed count, entity_resolution_result, textract_ocr_count, extraction_method_breakdown (pypdf2 vs textract), cost_actual (if measurable), and notes.
2. THE Batch_Loader SHALL update the running_total_s3_docs for the target case in the Processing_Ledger after each batch.
3. THE Batch_Loader SHALL update Aurora document counts (via the existing update_case_doc_counts.py pattern) after each batch so the UI reflects current totals.
4. THE Batch_Loader SHALL maintain a separate batch_progress.json file tracking: total_files_discovered, total_processed, total_remaining, current_batch_number, cursor position, cumulative_blanks, cumulative_quarantined, and cumulative_cost.

### Requirement 10: CLI Interface and Configuration

**User Story:** As a data engineer, I want a clean CLI interface with sensible defaults and overridable parameters, so that I can run batches with minimal configuration or fine-tune behavior as needed.

#### Acceptance Criteria

1. THE Batch_Loader SHALL accept the following CLI parameters: --batch-size (default 5000), --case-id (default ed0b6c27), --sub-batch-size (default 50), --dry-run (preview only), --confirm (skip interactive prompt), --no-entity-resolution (skip entity resolution), --max-batches (limit number of batches to run, default 1), --ocr-threshold (characters per page below which Textract is used, default 50), --blank-threshold (characters below which a doc is blank, default 10), --source-prefixes (S3 prefixes to scan, default pdfs/ and bw-documents/).
2. THE Batch_Loader SHALL print a progress summary after each sub-batch: documents sent, Step Functions executions triggered, running totals.
3. WHEN --max-batches is greater than 1, THE Batch_Loader SHALL process multiple consecutive batches in a single run, with entity resolution between each batch.
4. THE Batch_Loader SHALL print a final summary after all batches complete: total documents processed, total blanks filtered, total quarantined, total cost estimate, entity resolution summary, and next-batch cursor position.

### Requirement 11: Batch Manifest and Auditability

**User Story:** As a data engineer, I want a detailed manifest for every batch showing exactly which files were processed and their outcomes, so that I can audit and debug any issues.

#### Acceptance Criteria

1. THE Batch_Loader SHALL generate a Batch_Manifest JSON file for each batch containing: batch_id, batch_number, started_at, completed_at, source_prefix, and for each file: s3_key, file_size_bytes, extraction_method (pypdf2/textract/failed), extracted_char_count, blank_filtered (boolean), pipeline_status (sent/succeeded/failed/quarantined), sfn_execution_arn, and error_message (if any).
2. THE Batch_Loader SHALL save each Batch_Manifest to S3 under a configurable prefix (default: batch-manifests/{case_id}/batch_{number}.json) and locally under scripts/batch_manifests/.
3. THE Batch_Manifest SHALL enable reconstruction of exactly what happened in any batch without re-running the batch.
