# Requirements Document

## Introduction

This feature downloads and ingests approximately 25,000 pre-OCR'd text pages from the HuggingFace dataset `ishumilin/epstein-files-ocr-datasets-1-8-early-release` into the existing investigative intelligence platform. The dataset contains 42,182 page-level Markdown files covering Datasets 1-8. Since DS1-5 are already loaded in the system (~345K docs in Epstein Main), only DS6-8 pages (~25K net new pages) are ingested.

This is a text-only ingestion — no images, no OCR processing. Pages are grouped into document-level records where possible, inserted into the Aurora `documents` table for the Epstein Main case (`7f05e8d5-4492-4f19-8894-25367606db96`), entity extraction is run via Bedrock, and extracted entities are synced to the Neptune knowledge graph. Target: ~$5 Bedrock cost, ~1 hour total runtime.

All changes extend existing code — nothing is replaced.

## Glossary

- **HF_Dataset**: The HuggingFace dataset `ishumilin/epstein-files-ocr-datasets-1-8-early-release`, containing 42,182 page-level OCR files in Markdown format (172 MB total, CC0 license)
- **Page_File**: A single Markdown file from HF_Dataset named `page_N.md`, containing the OCR text of one scanned page from the Epstein document releases
- **Dataset_Tag**: The dataset number (1-8) identifying which DOJ release a Page_File belongs to, derived from the file path or metadata in HF_Dataset
- **DS1_5_Pages**: Page_Files belonging to Datasets 1 through 5, which overlap with documents already loaded in the Epstein Main case and must be filtered out
- **DS6_8_Pages**: Page_Files belonging to Datasets 6 through 8, representing the ~25,000 net new pages to be ingested
- **Document_Record**: A row in the Aurora `documents` table containing grouped page text, source metadata, and a reference to the Epstein Main case
- **Page_Grouping**: The process of combining consecutive Page_Files that belong to the same source document into a single Document_Record, using filename prefix patterns or sequential page numbering
- **Epstein_Main_Case**: The existing case record in Aurora with `case_id` = `7f05e8d5-4492-4f19-8894-25367606db96`, currently containing 345,898 documents and 77,900 entities
- **HF_Loader_Script**: A new Python script (`scripts/load_huggingface_text.py`) that orchestrates the download, filtering, grouping, and ingestion pipeline
- **Aurora_DB**: The Aurora PostgreSQL database accessed via RDS Proxy, containing the `documents`, `entities`, and `case_files` tables
- **Entity_Extraction_Service**: The existing `EntityExtractionService` class (`src/services/entity_extraction_service.py`) that uses Bedrock Claude Haiku to extract named entities from document text
- **Neptune_Graph**: The Amazon Neptune knowledge graph storing entity nodes and relationship edges for each case
- **Bedrock_LLM**: Amazon Bedrock Claude Haiku (`anthropic.claude-3-haiku-20240307-v1:0`) used for entity extraction at ~$0.00025 per 1K input tokens
- **Ingestion_Batch**: A group of Document_Records processed together in a single database transaction, sized to stay within Lambda timeout and memory constraints
- **Progress_Tracker**: A JSON file (`scripts/hf_ingestion_progress.json`) that records which pages have been processed, enabling resume after interruption
- **Case_Statistics**: The `document_count`, `entity_count`, and `relationship_count` columns on the `case_files` table that must be updated after ingestion completes

## Requirements

### Requirement 1: Download HuggingFace Dataset with Streaming

**User Story:** As a data engineer, I want to download the HuggingFace OCR dataset using streaming, so that the full 172 MB dataset does not need to be stored locally before processing begins.

#### Acceptance Criteria

1. THE HF_Loader_Script SHALL download Page_Files from HF_Dataset using the HuggingFace `datasets` library streaming mode.
2. WHEN streaming is unavailable or fails, THE HF_Loader_Script SHALL fall back to a full download of HF_Dataset to a local cache directory.
3. THE HF_Loader_Script SHALL log the total number of Page_Files discovered in HF_Dataset before filtering begins.
4. IF the HuggingFace API returns an authentication error or dataset-not-found error, THEN THE HF_Loader_Script SHALL log a descriptive error message and exit with a non-zero exit code.
5. THE HF_Loader_Script SHALL accept a `--dry-run` flag that downloads and counts pages without writing to Aurora_DB or triggering entity extraction.

### Requirement 2: Filter Out DS1-5 Pages

**User Story:** As a data engineer, I want DS1-5 pages automatically filtered out during ingestion, so that already-loaded documents are not duplicated in the Epstein Main case.

#### Acceptance Criteria

1. THE HF_Loader_Script SHALL identify each Page_File's Dataset_Tag from the file path or metadata fields in HF_Dataset.
2. WHEN a Page_File has a Dataset_Tag of 1, 2, 3, 4, or 5, THE HF_Loader_Script SHALL skip the Page_File and increment a `skipped_ds1_5` counter.
3. WHEN a Page_File has a Dataset_Tag of 6, 7, or 8, THE HF_Loader_Script SHALL include the Page_File for ingestion processing.
4. THE HF_Loader_Script SHALL log the count of skipped DS1_5_Pages and included DS6_8_Pages after filtering completes.
5. IF a Page_File's Dataset_Tag cannot be determined, THEN THE HF_Loader_Script SHALL log a warning with the filename and skip the Page_File.

### Requirement 3: Group Pages into Document-Level Records

**User Story:** As a data engineer, I want page-level files grouped into document-level records where possible, so that the Aurora documents table contains coherent multi-page documents rather than individual page fragments.

#### Acceptance Criteria

1. THE HF_Loader_Script SHALL group consecutive Page_Files that share the same document prefix (the filename portion before the page number suffix) into a single Document_Record.
2. WHEN grouping pages, THE HF_Loader_Script SHALL concatenate the Markdown text of grouped pages in page-number order, separated by a page break marker (`\n\n---\n\n`).
3. WHEN a Page_File cannot be matched to a document prefix group, THE HF_Loader_Script SHALL create a standalone Document_Record containing only that single page's text.
4. THE HF_Loader_Script SHALL store the original Page_File names in the `source_metadata` JSONB field of each Document_Record as a `pages` array.
5. THE HF_Loader_Script SHALL set the `source_filename` field of each Document_Record to the document prefix (or the original Page_File name for standalone pages).
6. THE HF_Loader_Script SHALL log the total number of Document_Records created and the average pages per document after grouping completes.

### Requirement 4: Ingest Documents into Aurora

**User Story:** As a data engineer, I want grouped documents inserted into the Aurora documents table for the Epstein Main case, so that the new text is searchable and available for analysis.

#### Acceptance Criteria

1. THE HF_Loader_Script SHALL insert each Document_Record into the Aurora `documents` table with `case_file_id` set to the Epstein_Main_Case UUID (`7f05e8d5-4492-4f19-8894-25367606db96`).
2. THE HF_Loader_Script SHALL insert documents in Ingestion_Batches of 500 records per database transaction.
3. WHEN inserting a Document_Record, THE HF_Loader_Script SHALL populate: `source_filename` (document name), `raw_text` (concatenated page text), `source_metadata` (JSONB with `pages` array, `dataset_tag`, and `source` set to `"huggingface"`), and `indexed_at` (current timestamp).
4. IF a database transaction fails, THEN THE HF_Loader_Script SHALL log the error with the batch range, roll back the failed transaction, and continue with the next Ingestion_Batch.
5. THE HF_Loader_Script SHALL update the Progress_Tracker after each successful Ingestion_Batch with the last processed page identifier.
6. WHEN the `--dry-run` flag is set, THE HF_Loader_Script SHALL log the number of Document_Records that would be inserted without executing database writes.

### Requirement 5: Run Entity Extraction on New Documents

**User Story:** As a data engineer, I want entity extraction run on all newly ingested documents via Bedrock, so that people, organizations, locations, and dates are identified for the knowledge graph.

#### Acceptance Criteria

1. WHEN a Document_Record is successfully inserted into Aurora_DB, THE HF_Loader_Script SHALL invoke the Entity_Extraction_Service to extract entities from the document's `raw_text`.
2. THE HF_Loader_Script SHALL use the existing `EntityExtractionService` class with Bedrock_LLM model `anthropic.claude-3-haiku-20240307-v1:0`.
3. THE HF_Loader_Script SHALL process entity extraction in batches of 50 documents, with a 1-second delay between batches to stay within Bedrock throttling limits.
4. WHEN entity extraction completes for a document, THE HF_Loader_Script SHALL insert extracted entities into the Aurora `entities` table with the correct `case_file_id` and `document_id` references.
5. IF Bedrock_LLM returns a throttling error (HTTP 429), THEN THE HF_Loader_Script SHALL retry with exponential backoff starting at 5 seconds, up to 3 retries.
6. IF entity extraction fails for a document after retries, THEN THE HF_Loader_Script SHALL log the document_id and error, skip the document, and continue processing.
7. THE HF_Loader_Script SHALL log a running total of entities extracted every 100 documents.

### Requirement 6: Sync Extracted Entities to Neptune Knowledge Graph

**User Story:** As a data engineer, I want newly extracted entities synced to the Neptune knowledge graph, so that the graph-based analysis features reflect the new data.

#### Acceptance Criteria

1. WHEN entity extraction completes for all Ingestion_Batches, THE HF_Loader_Script SHALL invoke the Neptune entity sync process for the Epstein_Main_Case.
2. THE HF_Loader_Script SHALL use the existing Lambda-based sync mechanism (`action: sync_neptune_to_aurora` on the CaseFiles Lambda) to sync entities from Aurora to Neptune.
3. WHEN the Neptune sync Lambda invocation returns a success response, THE HF_Loader_Script SHALL log the count of Neptune entities synced and Aurora rows upserted.
4. IF the Neptune sync Lambda invocation fails or times out, THEN THE HF_Loader_Script SHALL log the error and print a manual recovery command: `python scripts/sync_neptune_to_aurora.py --case-id 7f05e8d5-4492-4f19-8894-25367606db96`.

### Requirement 7: Update Case Statistics

**User Story:** As a data engineer, I want the Epstein Main case document and entity counts updated after ingestion, so that the UI displays accurate totals.

#### Acceptance Criteria

1. WHEN all Ingestion_Batches and entity extraction complete, THE HF_Loader_Script SHALL query Aurora_DB for the current `COUNT(*)` of documents and entities for the Epstein_Main_Case.
2. THE HF_Loader_Script SHALL update the `case_files` table row for the Epstein_Main_Case with the new `document_count` and `entity_count` values.
3. THE HF_Loader_Script SHALL log the before and after counts for documents and entities.
4. WHEN the `--dry-run` flag is set, THE HF_Loader_Script SHALL display the projected new counts without updating the database.

### Requirement 8: Resume Support After Interruption

**User Story:** As a data engineer, I want the ingestion script to resume from where it left off if interrupted, so that I do not need to re-process pages that were already ingested.

#### Acceptance Criteria

1. THE HF_Loader_Script SHALL write the Progress_Tracker file (`scripts/hf_ingestion_progress.json`) after each successful Ingestion_Batch, recording: `last_page_processed`, `documents_inserted`, `entities_extracted`, `timestamp`, and `status`.
2. WHEN the HF_Loader_Script starts and a Progress_Tracker file exists with `status` = `"in_progress"`, THE HF_Loader_Script SHALL resume from the `last_page_processed` position, skipping already-ingested pages.
3. WHEN all pages are processed, THE HF_Loader_Script SHALL update the Progress_Tracker with `status` = `"completed"`.
4. THE HF_Loader_Script SHALL accept a `--reset` flag that deletes the Progress_Tracker file and starts ingestion from the beginning.

### Requirement 9: Ingestion Summary and Documentation Update

**User Story:** As a data engineer, I want a clear summary printed after ingestion and the data inventory plan updated, so that the team knows the current state of the data.

#### Acceptance Criteria

1. WHEN ingestion completes, THE HF_Loader_Script SHALL print a summary table showing: total pages scanned, DS1-5 pages skipped, DS6-8 pages ingested, documents created, entities extracted, Neptune entities synced, estimated Bedrock cost, and elapsed time.
2. THE HF_Loader_Script SHALL accept a `--estimate-cost` flag that calculates and displays the projected Bedrock entity extraction cost based on the total text size of DS6_8_Pages without running extraction.
3. WHEN ingestion completes successfully, THE HF_Loader_Script SHALL print a reminder to update `docs/data-inventory-and-ingestion-plan.md` with the new counts and mark Phase 2 as complete.

### Requirement 10: CLI Interface and Configuration

**User Story:** As a data engineer, I want a clear CLI interface with sensible defaults, so that I can run the ingestion with a single command or customize parameters as needed.

#### Acceptance Criteria

1. THE HF_Loader_Script SHALL accept the following CLI arguments: `--case-id` (default: Epstein_Main_Case UUID), `--batch-size` (default: 500), `--extraction-batch-size` (default: 50), `--dry-run`, `--reset`, `--estimate-cost`, and `--skip-entity-extraction`.
2. THE HF_Loader_Script SHALL be executable via: `python scripts/load_huggingface_text.py`.
3. WHEN the `--skip-entity-extraction` flag is set, THE HF_Loader_Script SHALL insert documents into Aurora_DB without running entity extraction or Neptune sync.
4. THE HF_Loader_Script SHALL validate that the specified `case-id` exists in the `case_files` table before beginning ingestion.
5. IF the specified `case-id` does not exist in Aurora_DB, THEN THE HF_Loader_Script SHALL log an error message and exit with a non-zero exit code.
