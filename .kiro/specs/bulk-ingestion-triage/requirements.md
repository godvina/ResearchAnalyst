# Requirements: Bulk Ingestion & Triage

## Introduction

Extends the existing matter-collection-hierarchy to support massive bulk data loads (500TB+) from customers like DOJ. Introduces Customer as a first-class entity (extending Organization), a Matter/Case distinction, AI-powered document classification with auto-routing, multi-modal file processing (documents, images, audio, video, spreadsheets, emails), flexible ingestion modes (auto-classify, pre-assigned, hybrid), a wizard-driven pipeline configuration for media-specific processing (Rekognition, Transcribe, Neptune bulk loader), a human triage queue for ambiguous documents, deduplication, and chain-of-custody tracking. Follows industry best practices from eDiscovery platforms (Relativity, Nuix, Concordance) for bulk evidence processing at scale. The full hierarchy becomes: Customer → Matter → Case → Collection → Document.

## Glossary

- **Customer**: A first-class tenant entity that extends/renames Organization. Represents a real-world client (e.g., DOJ). A Customer has many Matters and Cases. All data is isolated per Customer.
- **Matter**: A broader investigation or legal proceeding (e.g., "Epstein Investigation"). Can span multiple Cases, involve multiple subjects, and last years. A Matter belongs to one Customer and can contain multiple Cases.
- **Case**: A specific filed legal action with a docket number (e.g., "Case No. 23-CR-00456 United States v. Epstein"). Has formal court filings, a judge, parties, and a lifecycle. A Case belongs to exactly one Matter.
- **Bulk_Ingestion_Job**: A tracked unit of work representing a large-scale data delivery from a Customer. Tracks total files, processed count, classified count, triage count, error count, throughput rate, and estimated completion time.
- **Staging_Area**: A temporary holding zone where raw bulk data lands before any Matter/Case assignment occurs.
- **AI_Classifier**: The Bedrock-powered AI subsystem that reads each document and extracts case numbers, matter references, document types, and key entities.
- **Auto_Router**: The subsystem that matches AI-extracted identifiers to existing Matters/Cases, auto-creates new Matters or Cases when new references are discovered, and routes documents accordingly.
- **Triage_Queue**: A queue of documents that the AI_Classifier could not confidently classify, presented to human investigators for manual assignment.
- **Confidence_Score**: A float between 0.0 and 1.0 representing the AI_Classifier's certainty in a classification result.
- **Docket_Number**: A court-assigned identifier for a Case (e.g., "23-CR-00456").
- **Ingestion_Mode**: The classification strategy for a Bulk Ingestion Job — either "auto_classify" (AI routes docs to discovered Matters/Cases), "pre_assigned" (all docs go to a specified Matter/Case), or "hybrid" (pre-assign to a Matter, AI sub-classifies into Cases within it).
- **Media_Type**: The broad category of a file — document (PDF, DOCX, TXT), image (JPG, PNG, TIFF), audio (MP3, WAV, M4A), video (MP4, MOV, AVI), spreadsheet (XLSX, CSV), email (EML, MSG, PST), or database (MDB, SQL dumps).
- **Processing_Pipeline**: The set of processing steps configured for a Bulk Ingestion Job, determined by the media types detected. Different media types require different processing chains (e.g., Textract for PDFs, Rekognition for images/video, Transcribe for audio).
- **Pipeline_Wizard**: The guided configuration UI that detects media types in a bulk load and prompts the operator to configure the appropriate processing services (Rekognition collections, Transcribe settings, Neptune bulk loader CSV format, etc.).

## Requirements

### Requirement 1: Customer as First-Class Entity

**User Story:** As a platform operator, I want Customer to be a first-class entity that extends Organization, so that the system models real-world clients like DOJ with proper data isolation.

#### Acceptance Criteria

1. THE System SHALL store customers by extending the existing organizations table with additional fields: customer_code (unique short identifier), primary_contact, contract_tier, and onboarded_at.
2. THE System SHALL map the existing Organization model to Customer, preserving all existing org_id references and backward compatibility.
3. WHEN any data operation occurs, THE System SHALL enforce tenant isolation so that data belonging to one Customer is inaccessible to another Customer.
4. THE System SHALL support multiple concurrent bulk ingestions from the same Customer without data corruption or cross-job interference.

### Requirement 2: Matter and Case Distinction

**User Story:** As an investigator, I want Matters and Cases to be distinct entities with a parent-child relationship, so that I can model real-world legal structures where one investigation spans multiple court cases.

#### Acceptance Criteria

1. THE System SHALL extend the existing matters table with a parent_type field distinguishing Matters from Cases.
2. THE System SHALL store Cases with: case_id (UUID PK), matter_id FK (parent Matter), docket_number, case_title, judge, parties (JSONB), filing_date, case_status, and court_jurisdiction.
3. WHEN a Case is created, THE System SHALL validate that the referenced matter_id exists and belongs to the same Customer.
4. THE System SHALL enforce that a Case belongs to exactly one Matter, while a Matter can contain zero or more Cases.
5. THE System SHALL maintain the full hierarchy: Customer → Matter → Case → Collection → Document.
6. WHEN a Matter is deleted or archived, THE System SHALL cascade the status change to all child Cases.

### Requirement 3: Bulk Ingestion Job Creation and Tracking

**User Story:** As a data manager, I want to create a Bulk Ingestion Job when a customer delivers a large dataset, so that I can track the entire load from start to finish.

#### Acceptance Criteria

1. THE System SHALL store Bulk Ingestion Jobs with: job_id (UUID PK), customer_id FK, job_name, source_description, status, total_files, processed_count, classified_count, triage_count, error_count, created_at, started_at, completed_at.
2. WHEN a Bulk Ingestion Job is created, THE System SHALL set its status to "created" and total_files to the count of files in the staging area.
3. THE System SHALL compute throughput_rate as processed_count divided by elapsed seconds since started_at.
4. THE System SHALL compute estimated_completion_time based on throughput_rate and remaining unprocessed files.
5. Bulk Ingestion Job status SHALL follow the state machine: created → staging → processing → classifying → completing → completed | failed.
6. THE System SHALL support multiple concurrent Bulk Ingestion Jobs for the same Customer, each with independent tracking counters.

### Requirement 4: Bulk Ingestion Staging Area

**User Story:** As a data manager, I want raw bulk data to land in a staging area before any Matter/Case assignment, so that the system can process and classify documents without prematurely routing them.

#### Acceptance Criteria

1. WHEN a Customer delivers raw data, THE System SHALL write files to a staging S3 prefix: orgs/{customer_id}/bulk-staging/{job_id}/raw/.
2. THE System SHALL create document records in the documents table with matter_id and case_id set to NULL, linked only to the Bulk Ingestion Job.
3. WHEN all files are staged, THE System SHALL transition the Bulk Ingestion Job status from "created" to "staging" and then to "processing".
4. THE System SHALL track each staged document's processing state independently: staged → parsing → classifying → routed | triage | error.

### Requirement 5: AI Document Classification

**User Story:** As a data manager, I want the system to use AI to automatically classify each document by extracting case numbers, matter references, document types, and key entities, so that documents can be auto-routed to the correct Matter/Case.

#### Acceptance Criteria

1. WHEN a staged document is processed, THE AI_Classifier SHALL extract: case numbers (e.g., "Case No. 23-CR-00456", docket numbers), matter references (investigation names, matter numbers), document type (court_filing, email, financial_record, photo, deposition, law_enforcement_report, correspondence, contract, transcript, miscellaneous), and key entities (people, organizations, dates, locations).
2. THE AI_Classifier SHALL return a Confidence_Score between 0.0 and 1.0 for each extracted identifier.
3. THE AI_Classifier SHALL use the existing Bedrock integration (EntityExtractionService) extended with case-number and matter-reference extraction prompts.
4. IF the AI_Classifier encounters a document it cannot parse (corrupted, encrypted, unsupported format), THEN THE System SHALL mark the document as "error" and increment the Bulk Ingestion Job error_count.
5. THE AI_Classifier SHALL process documents in parallel using the SQS + Lambda fleet architecture described in the 500TB ingestion architecture.

### Requirement 6: Auto-Routing of Classified Documents

**User Story:** As a data manager, I want the system to automatically route classified documents to the correct Matter/Case based on extracted identifiers, so that the bulk of documents are organized without human intervention.

#### Acceptance Criteria

1. WHEN the AI_Classifier extracts a docket number matching an existing Case, THE Auto_Router SHALL assign the document to that Case and its parent Matter.
2. WHEN the AI_Classifier extracts a matter reference matching an existing Matter, THE Auto_Router SHALL assign the document to that Matter.
3. WHEN the AI_Classifier extracts a docket number that does not match any existing Case, THE Auto_Router SHALL auto-create a new Case under the most relevant Matter (or a default "Unassigned" Matter) and assign the document to the new Case.
4. WHEN the AI_Classifier extracts a matter reference that does not match any existing Matter, THE Auto_Router SHALL auto-create a new Matter under the Customer and assign the document to the new Matter.
5. THE Auto_Router SHALL apply a configurable confidence threshold (default 0.8) below which documents are sent to the Triage_Queue instead of being auto-routed.
6. WHEN a document is auto-routed, THE System SHALL increment the Bulk Ingestion Job classified_count.
7. THE Auto_Router SHALL create a Collection within the target Matter/Case for each Bulk Ingestion Job, grouping auto-routed documents by their destination.

### Requirement 7: Triage Queue for Ambiguous Documents

**User Story:** As an investigator, I want a triage queue for documents that the AI could not confidently classify, so that I can manually review and assign them.

#### Acceptance Criteria

1. WHEN a document's highest Confidence_Score is below the configured threshold, THE System SHALL add the document to the Triage_Queue.
2. WHEN a document has conflicting classifications (multiple possible Matters/Cases with similar confidence), THE System SHALL add the document to the Triage_Queue.
3. THE Triage_Queue SHALL store for each item: triage_id, document_id, job_id, ai_suggestions (JSONB array of {matter_id, case_id, confidence, reasoning}), document_type, extracted_entities (JSONB), status, assigned_matter_id, assigned_case_id, assigned_by, assigned_at, created_at.
4. THE System SHALL support triage item statuses: pending, assigned, new_matter, new_case, irrelevant, duplicate.
5. WHEN a document is added to the Triage_Queue, THE System SHALL increment the Bulk Ingestion Job triage_count.

### Requirement 8: Triage Queue Operations

**User Story:** As an investigator, I want to view triaged documents with AI suggestions and assign them to Matters/Cases, so that no document is left unclassified.

#### Acceptance Criteria

1. THE System SHALL provide a paginated list of triage items filtered by job_id, status, and document_type.
2. THE System SHALL display each triage item with: a document preview (first 5000 characters of parsed text), the AI_Classifier's top suggestions with Confidence_Scores and reasoning, and extracted entities.
3. WHEN an investigator assigns a triage item to an existing Matter/Case, THE System SHALL move the document to the target Matter/Case and update the triage item status to "assigned".
4. WHEN an investigator creates a new Matter from a triage item, THE System SHALL create the Matter under the Customer and assign the document to the new Matter, updating the triage item status to "new_matter".
5. WHEN an investigator creates a new Case from a triage item, THE System SHALL create the Case under a specified Matter and assign the document to the new Case, updating the triage item status to "new_case".
6. WHEN an investigator marks a triage item as irrelevant, THE System SHALL update the triage item status to "irrelevant" and exclude the document from analysis.
7. WHEN an investigator marks a triage item as duplicate, THE System SHALL update the triage item status to "duplicate", link the document to the original, and exclude the duplicate from analysis.

### Requirement 9: Bulk Ingestion Job Monitoring

**User Story:** As a data manager, I want real-time visibility into the progress of each Bulk Ingestion Job, so that I can monitor throughput and identify issues early.

#### Acceptance Criteria

1. THE System SHALL expose a job status endpoint returning: job_id, status, total_files, processed_count, classified_count, triage_count, error_count, throughput_rate, estimated_completion_time, started_at, elapsed_time.
2. THE System SHALL update processed_count, classified_count, triage_count, and error_count atomically as each document completes processing.
3. WHEN a Bulk Ingestion Job's error_count exceeds a configurable threshold (default 5% of total_files), THE System SHALL flag the job with a warning status.
4. WHEN all documents in a Bulk Ingestion Job are processed (processed_count equals total_files), THE System SHALL transition the job status to "completing" and then "completed".
5. THE System SHALL provide a per-job breakdown of documents by classification outcome: auto-routed by Matter, auto-routed by Case, sent to triage, errored.

### Requirement 10: Concurrent Bulk Ingestion Isolation

**User Story:** As a platform operator, I want multiple concurrent bulk ingestions from the same customer to run independently, so that one job's failure does not affect another.

#### Acceptance Criteria

1. THE System SHALL isolate each Bulk Ingestion Job's staging area under a unique S3 prefix: orgs/{customer_id}/bulk-staging/{job_id}/raw/.
2. THE System SHALL use separate SQS message groups or queues per Bulk Ingestion Job to prevent cross-job message interference.
3. IF one Bulk Ingestion Job fails, THEN THE System SHALL leave other concurrent jobs for the same Customer unaffected.
4. THE System SHALL prevent duplicate document processing across concurrent jobs by tracking document hashes per Customer.

### Requirement 11: Schema Extension (Non-Breaking)

**User Story:** As a platform operator, I want the existing matter-collection-hierarchy schema extended rather than replaced, so that existing data and services continue to work.

#### Acceptance Criteria

1. THE System SHALL add a cases table with: case_id (UUID PK), matter_id FK, org_id FK, docket_number, case_title, judge, parties (JSONB), filing_date, case_status, court_jurisdiction, created_at, last_activity.
2. THE System SHALL add a bulk_ingestion_jobs table with all fields specified in Requirement 3.
3. THE System SHALL extend the existing triage_queue table with job_id FK, ai_suggestions (JSONB), and extracted_entities (JSONB) columns.
4. THE System SHALL add job_id and case_id columns to the documents table.
5. THE existing organizations, matters, collections, documents, and promotion_snapshots tables SHALL remain structurally intact.
6. ALL existing API endpoints SHALL continue to function without modification.

### Requirement 12: API Endpoints for Bulk Ingestion

**User Story:** As a developer, I want clean API endpoints for bulk ingestion, job monitoring, and triage operations.

#### Acceptance Criteria

1. THE System SHALL provide: POST /customers/{id}/bulk-ingestion-jobs to create a job, GET /bulk-ingestion-jobs/{id} to get job status, GET /bulk-ingestion-jobs/{id}/documents to list documents with classification outcomes.
2. THE System SHALL provide: GET /bulk-ingestion-jobs/{id}/triage to list triage items, POST /triage/{id}/assign to assign a triage item, POST /triage/{id}/create-matter to create a Matter from triage, POST /triage/{id}/create-case to create a Case from triage, POST /triage/{id}/mark-irrelevant, POST /triage/{id}/mark-duplicate.
3. THE System SHALL provide: GET /customers/{id}/matters/{mid}/cases to list Cases under a Matter, POST /customers/{id}/matters/{mid}/cases to create a Case, GET /cases/{id} to get Case detail.
4. ALL bulk ingestion and triage endpoints SHALL enforce Customer-level tenant isolation.

### Requirement 13: Multi-Modal File Processing

**User Story:** As a data manager, I want the system to handle all file types in a bulk load — documents, images, audio, video, spreadsheets, emails — so that every piece of evidence is processed appropriately regardless of format.

#### Acceptance Criteria

1. WHEN files are staged, THE System SHALL detect each file's Media_Type based on extension and MIME type, categorizing into: document (PDF, DOCX, DOC, TXT, RTF, HTML), image (JPG, JPEG, PNG, TIFF, TIF, GIF, BMP), audio (MP3, WAV, M4A, AAC, FLAC, OGG), video (MP4, MOV, AVI, MKV, WMV), spreadsheet (XLSX, XLS, CSV, TSV), email (EML, MSG, PST, MBOX), database (MDB, ACCDB, SQL).
2. THE System SHALL route each file to the appropriate processing chain based on Media_Type: documents → Textract/parser + Bedrock entity extraction, images → Rekognition (face detection, label detection, OCR via Textract) + metadata extraction, audio → Transcribe → Bedrock entity extraction on transcript, video → Rekognition Video (face search, label detection, shot detection) + Transcribe for audio track → Bedrock entity extraction, spreadsheets → tabular parser + Bedrock entity extraction on cell contents, emails → email parser (headers, body, attachments) with recursive processing of attachments.
3. THE System SHALL track per-job media type counts: document_count, image_count, audio_count, video_count, spreadsheet_count, email_count, other_count.
4. THE System SHALL store extracted content uniformly regardless of source media type: parsed_text (from OCR, transcription, or direct parsing), extracted_entities, embeddings, and source_media_type.
5. WHEN processing emails with attachments, THE System SHALL recursively process each attachment as a separate document linked to the parent email, preserving the email thread context.
6. WHEN a PDF is staged, THE System SHALL test readability by attempting direct text extraction; IF the extracted text is empty or below a configurable character threshold (default 50 characters per page), THE System SHALL classify the PDF as "scanned/image-based" and route it through Textract OCR before entity extraction.
7. THE System SHALL enforce a strict processing order per document: (a) media type detection → (b) content extraction (Textract OCR for scanned docs, Transcribe for audio/video, direct parse for native text) → (c) entity extraction via Bedrock on extracted text → (d) classification and routing to Matter/Case → (e) embedding generation → (f) Neptune graph loading. Each step SHALL depend on the output of the previous step and SHALL NOT begin until its predecessor completes.
8. WHEN a document requires multiple extraction services (e.g., a video needs both Rekognition Video for visual analysis and Transcribe for audio), THE System SHALL run those sub-steps in parallel and merge results before proceeding to entity extraction.
9. THE Pipeline_Wizard SHALL present the detected scanned-PDF percentage to the operator and recommend enabling Textract OCR if scanned PDFs exceed a configurable threshold (default 10% of document-type files).

### Requirement 14: Flexible Ingestion Modes

**User Story:** As a data manager, I want to choose whether the system auto-classifies documents across Matters/Cases or assigns everything to a pre-specified Matter/Case, so that I can handle both multi-case bulk dumps and single-case targeted loads.

#### Acceptance Criteria

1. WHEN creating a Bulk Ingestion Job, THE System SHALL accept an ingestion_mode parameter: "auto_classify", "pre_assigned", or "hybrid".
2. WHEN ingestion_mode is "auto_classify", THE System SHALL run the full AI classification and auto-routing pipeline (Requirements 5-6), discovering and creating Matters/Cases as needed.
3. WHEN ingestion_mode is "pre_assigned", THE System SHALL skip AI classification for Matter/Case routing and assign all documents directly to the specified target_matter_id and optional target_case_id. Entity extraction and document type classification SHALL still occur.
4. WHEN ingestion_mode is "hybrid", THE System SHALL pre-assign all documents to a specified target_matter_id but use AI to sub-classify documents into Cases within that Matter, auto-creating Cases when new docket numbers are discovered.
5. THE System SHALL default to "auto_classify" if no ingestion_mode is specified.
6. WHEN ingestion_mode is "pre_assigned" or "hybrid", THE System SHALL validate that the target_matter_id (and target_case_id if provided) exists and belongs to the Customer.

### Requirement 15: Pipeline Wizard for Media-Specific Configuration

**User Story:** As a data manager, I want a guided wizard that detects what media types are in my bulk load and prompts me to configure the right processing services, so that I don't have to manually figure out what AWS services to enable.

#### Acceptance Criteria

1. WHEN a Bulk Ingestion Job is created and files are staged, THE Pipeline_Wizard SHALL scan a sample of staged files (up to 1000) to detect the distribution of Media_Types present.
2. THE Pipeline_Wizard SHALL present the detected media type breakdown to the operator with recommended processing configurations for each type.
3. WHEN images are detected, THE Pipeline_Wizard SHALL prompt the operator to configure Rekognition: enable/disable face detection, enable/disable face search (with option to create or select a Rekognition collection), enable/disable label detection, enable/disable OCR via Textract, set minimum confidence thresholds.
4. WHEN audio files are detected, THE Pipeline_Wizard SHALL prompt the operator to configure Transcribe: select language(s), enable/disable speaker diarization, enable/disable custom vocabulary, select output format.
5. WHEN video files are detected, THE Pipeline_Wizard SHALL prompt the operator to configure Rekognition Video: enable/disable face search, enable/disable shot detection, enable/disable label detection, plus Transcribe settings for the audio track.
6. THE Pipeline_Wizard SHALL prompt the operator to configure Neptune bulk loader settings: select entity types to extract, configure relationship types, set the CSV bulk load format (nodes CSV columns, edges CSV columns), and specify the target Neptune subgraph label.
7. THE Pipeline_Wizard SHALL save the complete pipeline configuration as a JSONB pipeline_config on the Bulk Ingestion Job record, which the processing Lambda fleet reads at runtime.
8. THE Pipeline_Wizard SHALL provide sensible defaults for all settings so that an operator can accept defaults and start processing immediately.

### Requirement 16: Deduplication and Near-Duplicate Detection

**User Story:** As an investigator, I want the system to detect duplicate and near-duplicate documents during bulk ingestion, so that the same evidence isn't counted or analyzed multiple times.

#### Acceptance Criteria

1. THE System SHALL compute a SHA-256 hash for every staged file and detect exact duplicates within the same Customer's data.
2. WHEN an exact duplicate is detected, THE System SHALL link the duplicate to the original document, mark it as "duplicate" in the documents table, and skip redundant processing.
3. THE System SHALL compute a content-based similarity score (using embedding cosine similarity) for text documents to detect near-duplicates (threshold configurable, default 0.95).
4. WHEN a near-duplicate is detected, THE System SHALL flag it in the Triage_Queue with the original document reference and similarity score, allowing an investigator to confirm or override.
5. THE System SHALL track deduplication statistics per Bulk Ingestion Job: exact_duplicate_count, near_duplicate_count.

### Requirement 17: Chain of Custody and Audit Trail

**User Story:** As a legal professional, I want every document's provenance tracked from the moment it enters the system through classification and routing, so that chain of custody is maintained for court admissibility.

#### Acceptance Criteria

1. THE System SHALL record a chain_of_custody event log for each document: ingestion timestamp, source job_id, original filename, original file path within the bulk delivery, SHA-256 hash at ingestion, every classification decision (AI or human), every routing/reassignment action with actor and timestamp.
2. THE System SHALL store chain_of_custody as an append-only JSONB array on the document record — entries can be added but never modified or deleted.
3. THE System SHALL record the Bates number range (if applicable) or production number for documents that arrive with existing numbering from the producing party.
4. ALL triage actions (assign, create-matter, create-case, mark-irrelevant, mark-duplicate) SHALL be recorded in the chain_of_custody with the acting user's identity and timestamp.
