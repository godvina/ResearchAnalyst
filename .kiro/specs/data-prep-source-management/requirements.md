# Requirements Document

## Introduction

The Data Prep & Source Management feature adds a data preparation stage to the batch loader UI. Currently the batch loader only scans the `pdfs/` and `bw-documents/` prefixes (~8K files) and has no visibility into the full S3 bucket contents — including 5 zip archives (DataSet8–12) containing ~331K PDFs total. Users must manually extract zips via scripts and have no way to see the complete data lifecycle from the UI.

This feature provides full source bucket visibility, UI-driven zip extraction, multi-prefix scanning with user-selectable prefixes, and improved cost estimates that account for the ~40% blank page rate observed in production.

## Glossary

- **Source_Bucket**: The S3 bucket `doj-cases-974220725866-us-east-1` containing raw source data (PDFs, zip archives, and processed outputs).
- **Data_Lake_Bucket**: The S3 bucket `research-analyst-data-lake-974220725866` storing processed data, manifests, and batch state.
- **Source_Browser**: The new UI section in batch-loader.html that displays all S3 prefixes, file counts, sizes, and types within the Source_Bucket.
- **Zip_Extractor**: The backend service that streams zip archives from S3, decompresses them, and uploads extracted PDFs to a target prefix in the Source_Bucket.
- **Cost_Estimator**: The existing module (`scripts/batch_loader/cost_estimator.py`) that calculates estimated AWS costs for batch processing, enhanced to account for blank page filtering.
- **Pipeline_Dashboard**: The UI section showing the complete data lifecycle from source archives through ingestion.
- **Prefix_Selector**: The UI component allowing users to select which S3 prefixes to scan for unprocessed PDF files.
- **Blank_Page_Rate**: The configurable ratio (default 40%) of documents expected to be blank/near-empty, used to adjust cost estimates downward.
- **Batch_Loader_Handler**: The Lambda handler (`src/lambdas/api/batch_loader_handler.py`) that serves all `/batch-loader/*` API endpoints.
- **Extraction_Job**: A long-running zip extraction operation tracked with a unique job ID, progress percentage, and status.

## Requirements

### Requirement 1: Source Bucket Inventory

**User Story:** As a batch operator, I want to see all S3 prefixes in the source bucket with file counts, sizes, and types, so that I know exactly what data is available before starting batch processing.

#### Acceptance Criteria

1. WHEN the Source_Browser tab is opened, THE Batch_Loader_Handler SHALL return a list of all top-level prefixes in the Source_Bucket with the following metadata per prefix: total object count, total size in bytes, count of PDF files, and count of zip archive files.
2. THE Source_Browser SHALL display a summary row showing: total files in the Source_Bucket, total extracted PDFs ready for processing, count of already-processed files, and count of remaining unprocessed files.
3. WHEN a prefix contains zip archives, THE Source_Browser SHALL display each zip file name, size, and estimated file count (from zip central directory metadata) as a distinct row within that prefix.
4. WHEN the user clicks a refresh button, THE Source_Browser SHALL re-fetch the prefix inventory from the Source_Bucket and update all displayed counts and sizes.
5. IF the Source_Bucket is unreachable or the ListObjects call fails, THEN THE Source_Browser SHALL display an error message with the specific S3 error code and a retry button.

### Requirement 2: Zip Extraction from UI

**User Story:** As a batch operator, I want to select zip archives in the UI and extract their contents to the `pdfs/` prefix, so that I can prepare data for batch processing without running manual scripts.

#### Acceptance Criteria

1. WHEN the user selects one or more zip archives and clicks the extract button, THE Batch_Loader_Handler SHALL create an Extraction_Job and return a job ID to the Source_Browser.
2. WHILE an Extraction_Job is running, THE Source_Browser SHALL poll the job status and display: job ID, source zip file name, extraction progress as a percentage, files extracted so far, total files expected, and elapsed time.
3. THE Zip_Extractor SHALL stream each zip archive from S3, decompress entries in memory, and upload each extracted PDF to the `pdfs/` prefix in the Source_Bucket using the original filename from the archive.
4. IF a zip archive exceeds the Lambda 300-second timeout or 512MB memory limit, THEN THE Zip_Extractor SHALL split the extraction into chunked jobs that each process a subset of entries from the zip central directory, resuming from the last successfully extracted entry.
5. IF an individual file within a zip archive fails to extract or upload, THEN THE Zip_Extractor SHALL log the failure with the file name and error reason, skip the file, and continue extracting remaining files.
6. WHEN an Extraction_Job completes, THE Zip_Extractor SHALL write a completion record to S3 containing: job ID, source zip key, total files extracted, total files skipped, total bytes uploaded, and duration in seconds.
7. IF a zip archive has already been fully extracted (completion record exists), THEN THE Source_Browser SHALL display the archive as "Already Extracted" and disable the extract button for that archive.
8. WHEN duplicate filenames exist across multiple zip archives being extracted, THE Zip_Extractor SHALL prefix the extracted filename with the dataset name (e.g., `DataSet11_filename.pdf`) to prevent overwrites.

### Requirement 3: Blank-Adjusted Cost Estimates

**User Story:** As a batch operator, I want cost estimates that account for the ~40% blank page rate, so that I get realistic cost projections before committing to a batch run.

#### Acceptance Criteria

1. THE Cost_Estimator SHALL accept a configurable `blank_page_rate` parameter (float between 0.0 and 1.0, default 0.40) that represents the expected proportion of blank documents in the batch.
2. WHEN a cost estimate is calculated, THE Cost_Estimator SHALL produce two estimates: a gross estimate (all files as if none are blank) and a net estimate (after applying the blank_page_rate reduction to Textract OCR, Bedrock entity extraction, Bedrock embedding, and Neptune write costs).
3. THE Source_Browser SHALL display both the gross and net cost estimates side by side, with the blank_page_rate percentage shown between them.
4. WHEN the user adjusts the blank_page_rate slider in the UI, THE Source_Browser SHALL recalculate and display updated net cost estimates without making a new API call.
5. THE Cost_Estimator SHALL return the gross estimate, net estimate, blank_page_rate used, and per-component cost breakdown (Textract, Bedrock entity, Bedrock embedding, Neptune) for both gross and net in a single response object.

### Requirement 4: Full Pipeline Visibility

**User Story:** As a batch operator, I want to see the complete data lifecycle from source archives through ingestion, so that I understand exactly where my data is in the pipeline at each stage.

#### Acceptance Criteria

1. THE Pipeline_Dashboard SHALL display the data lifecycle as a visual flow: Source Archives (zips) → Extract → Raw PDFs → Blank Filter → Ingestion Pipeline, with file counts at each stage.
2. WHEN the Pipeline_Dashboard is loaded, THE Batch_Loader_Handler SHALL return counts for each stage: number of zip archives in the Source_Bucket, number of extracted PDFs pending processing, number of blank-filtered documents (from historical batch manifests), and number of documents successfully ingested.
3. WHEN a batch is in progress, THE Pipeline_Dashboard SHALL update stage counts in real time by polling the batch status endpoint every 5 seconds.
4. THE Pipeline_Dashboard SHALL display which S3 prefixes are currently selected for scanning, with the ability to navigate to the Prefix_Selector to change the selection.
5. IF any pipeline stage has zero files, THEN THE Pipeline_Dashboard SHALL display that stage as empty with a grey indicator rather than hiding the stage.

### Requirement 5: Multi-Prefix Scanning

**User Story:** As a batch operator, I want to select which S3 prefixes to scan for unprocessed files, so that I can control exactly which data sources are included in batch processing.

#### Acceptance Criteria

1. WHEN the Source_Browser loads, THE Batch_Loader_Handler SHALL return a list of all prefixes in the Source_Bucket that contain at least one PDF file, each with its PDF count.
2. THE Prefix_Selector SHALL display checkboxes for each available prefix, with `pdfs/` and `bw-documents/` checked by default.
3. WHEN the user changes the prefix selection and clicks Preview Batch, THE Batch_Loader_Handler SHALL scan only the selected prefixes for unprocessed files and return the discovery results scoped to those prefixes.
4. WHEN the user starts a batch, THE Batch_Loader_Handler SHALL pass the selected prefixes to the batch processing pipeline as the `source_prefixes` configuration parameter.
5. THE Prefix_Selector SHALL display the unprocessed file count next to each prefix checkbox, updating when the selection changes and a new preview is run.
6. IF no prefixes are selected, THEN THE Prefix_Selector SHALL disable the Preview Batch and Start Batch buttons and display a message indicating at least one prefix is required.
