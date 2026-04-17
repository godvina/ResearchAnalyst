# Requirements Document

## Introduction

The Configurable Pipeline feature introduces per-case pipeline configuration for the DOJ Investigative Case Management platform. Each case (customer) has different document types, entity types, and processing needs. This feature allows investigators to customize every step of the ingestion pipeline — entity extraction prompts, entity types, confidence thresholds, chunk sizes, graph load strategies, embedding models, and more — on a per-case basis while inheriting sensible system-wide defaults.

The feature includes a sample-and-compare workflow for iteratively tuning pipeline configuration against sample documents before committing to a full batch run, a visual config editor embedded in the investigator.html interface, pipeline monitoring with entity quality metrics, config versioning with rollback, and config portability across environments. The system is designed for production scale at 500TB across multiple cases running in GovCloud.

## Glossary

- **Platform**: The DOJ Investigative Case Management platform — the complete serverless system including Aurora, Neptune, OpenSearch, Step Functions, Lambda, S3, Bedrock, API Gateway, and frontend interfaces
- **Case_File**: A logical investigation container representing a single case/customer, stored in the Aurora case_files table, with its own S3 prefix, Neptune subgraph, and now its own Pipeline_Config
- **Pipeline_Config**: A JSON document stored in Aurora that defines all configurable parameters for a case's ingestion pipeline. Each case has at most one active Pipeline_Config that overrides the System_Default_Config
- **System_Default_Config**: A platform-wide JSON configuration document that provides default values for all pipeline parameters. Applied to any case that has not defined overrides for a given parameter
- **Config_Version**: An immutable snapshot of a Pipeline_Config at a point in time, identified by a monotonically increasing version number. Pipeline runs are tagged with the Config_Version they used
- **Effective_Config**: The result of deep-merging the System_Default_Config with a case's Pipeline_Config overrides. This is the configuration actually used at pipeline execution time
- **Pipeline_Step**: One stage in the ingestion pipeline (Parse, Extract, Embed, Graph_Load, Store_Artifact), each reading its parameters from the Effective_Config
- **Sample_Run**: A pipeline execution against a small subset of documents (10-20) used to evaluate entity extraction quality before committing to a full batch
- **Config_Editor**: A visual interface embedded in investigator.html that displays pipeline steps as a flow diagram and allows editing of each step's configuration
- **Config_Template**: A preset Pipeline_Config for common case types (antitrust, criminal, financial fraud) that can be applied as a starting point
- **Entity_Quality_Metrics**: Quantitative measures of extraction quality including entity count, type distribution, average confidence, and noise ratio
- **Ingestion_Pipeline**: The Step Functions orchestration that processes documents through Parse, Extract, Embed, Graph_Load, and Store_Artifact steps
- **Confidence_Threshold**: A float value between 0.0 and 1.0 that filters extracted entities below the threshold, reducing noise in the knowledge graph
- **Normalization_Rules**: A set of rules in the Pipeline_Config that control how extracted entity names are canonicalized (e.g., case folding, alias merging, abbreviation expansion)

## Requirements

### Requirement 1: Pipeline Configuration Data Model

**User Story:** As a platform operator, I want a structured configuration model stored alongside case metadata in Aurora, so that each case's pipeline behavior is explicitly defined and auditable.

#### Acceptance Criteria

1. THE Platform SHALL store Pipeline_Config records in an Aurora table with columns: config_id (UUID), case_id (FK to case_files), version (integer), config_json (JSONB), created_at (timestamp), created_by (text), and is_active (boolean)
2. THE Platform SHALL store exactly one System_Default_Config record in an Aurora table with columns: config_id (UUID), version (integer), config_json (JSONB), created_at (timestamp), and created_by (text)
3. THE Pipeline_Config config_json document SHALL contain sections keyed by Pipeline_Step name: "parse", "extract", "embed", "graph_load", and "store_artifact"
4. THE "parse" section SHALL support parameters: pdf_method (string), ocr_enabled (boolean), and table_extraction_enabled (boolean)
5. THE "extract" section SHALL support parameters: prompt_template (string), entity_types (list of strings), llm_model_id (string), chunk_size_chars (integer), confidence_threshold (float 0.0-1.0), and relationship_inference_enabled (boolean)
6. THE "embed" section SHALL support parameters: embedding_model_id (string), search_tier (string), and opensearch_settings (object)
7. THE "graph_load" section SHALL support parameters: load_strategy (string: "bulk_csv" or "gremlin"), batch_size (integer), and normalization_rules (object)
8. THE "store_artifact" section SHALL support parameters: artifact_format (string) and include_raw_text (boolean)

### Requirement 2: Configuration Inheritance and Merging

**User Story:** As a platform operator, I want new cases to automatically use sensible defaults while allowing any parameter to be overridden per case, so that configuration is minimal for standard cases and flexible for specialized ones.

#### Acceptance Criteria

1. WHEN a new Case_File is created with no Pipeline_Config, THE Platform SHALL use the System_Default_Config for all pipeline parameters
2. WHEN a Case_File has a Pipeline_Config, THE Platform SHALL compute the Effective_Config by deep-merging the System_Default_Config with the case's Pipeline_Config, where case-level values override system defaults at the leaf key level
3. WHEN a key is present in the System_Default_Config but absent from the case's Pipeline_Config, THE Platform SHALL use the System_Default_Config value for that key in the Effective_Config
4. WHEN the System_Default_Config is updated, THE Platform SHALL apply the updated defaults to all cases that have not overridden the changed parameters
5. THE Platform SHALL provide an API endpoint that returns the computed Effective_Config for a given Case_File, showing which values are inherited and which are overridden
6. IF a Pipeline_Config contains a key not recognized by the Platform, THEN THE Platform SHALL reject the configuration update and return a validation error listing the unrecognized keys

### Requirement 3: Configuration Versioning

**User Story:** As an investigator, I want every configuration change to be versioned and linked to pipeline runs, so that I can understand which settings produced which results and roll back if needed.

#### Acceptance Criteria

1. WHEN a Pipeline_Config is created or updated for a Case_File, THE Platform SHALL create a new Config_Version with a monotonically increasing version number and store the previous version as inactive
2. WHEN the Ingestion_Pipeline executes for a Case_File, THE Platform SHALL tag the pipeline run record with the Config_Version number that was active at execution start
3. WHEN an investigator requests a rollback to a previous Config_Version, THE Platform SHALL create a new Config_Version whose config_json matches the target version's content
4. THE Platform SHALL provide an API endpoint that lists all Config_Versions for a Case_File, including version number, created_at timestamp, and created_by identifier
5. THE Platform SHALL provide an API endpoint that returns the config_json for any specific Config_Version of a Case_File
6. THE Platform SHALL retain all Config_Versions for the lifetime of the Case_File and not delete historical versions

### Requirement 4: Pipeline Step Configuration Integration

**User Story:** As a platform developer, I want each pipeline step to read its parameters from the case's Effective_Config at execution time, so that per-case customization flows through the entire pipeline without code changes to individual steps.

#### Acceptance Criteria

1. WHEN the Parse Pipeline_Step executes, THE Parse step SHALL read pdf_method, ocr_enabled, and table_extraction_enabled from the "parse" section of the Effective_Config
2. WHEN the Extract Pipeline_Step executes, THE Extract step SHALL read prompt_template, entity_types, llm_model_id, chunk_size_chars, confidence_threshold, and relationship_inference_enabled from the "extract" section of the Effective_Config
3. WHEN the Embed Pipeline_Step executes, THE Embed step SHALL read embedding_model_id, search_tier, and opensearch_settings from the "embed" section of the Effective_Config
4. WHEN the Graph_Load Pipeline_Step executes, THE Graph_Load step SHALL read load_strategy, batch_size, and normalization_rules from the "graph_load" section of the Effective_Config
5. WHEN the Store_Artifact Pipeline_Step executes, THE Store_Artifact step SHALL read artifact_format and include_raw_text from the "store_artifact" section of the Effective_Config
6. THE Platform SHALL resolve the Effective_Config once at the start of a pipeline execution and pass the resolved config to all Pipeline_Steps, so that config changes during execution do not affect the running pipeline
7. THE Platform SHALL cache the resolved Effective_Config in the Lambda execution environment to avoid repeated Aurora queries within the same pipeline execution


### Requirement 5: Sample-and-Compare Workflow

**User Story:** As an investigator, I want to run the pipeline on a small sample of documents, review the results, tweak the configuration, and compare before-and-after results side by side, so that I can tune entity extraction quality before committing to a full batch run.

#### Acceptance Criteria

1. WHEN an investigator initiates a Sample_Run, THE Platform SHALL accept a list of 1-50 document identifiers and execute the full Ingestion_Pipeline against only those documents using the case's current Effective_Config
2. WHEN a Sample_Run completes, THE Platform SHALL store the run results (extracted entities, relationships, entity quality metrics) as a named snapshot associated with the Config_Version used
3. WHEN an investigator requests a comparison between two Sample_Run snapshots, THE Platform SHALL return a side-by-side diff showing: entities added, entities removed, entities changed (confidence or type), relationship changes, and aggregate Entity_Quality_Metrics for each snapshot
4. WHEN an investigator modifies the Pipeline_Config and re-runs the sample, THE Platform SHALL execute a new Sample_Run with the updated Effective_Config and store a new snapshot
5. WHEN an investigator is satisfied with sample results, THE Platform SHALL allow the investigator to lock the current Config_Version and initiate a full batch pipeline run using that locked configuration
6. THE Platform SHALL track each Sample_Run with a unique run_id, the Config_Version used, the document identifiers processed, start time, end time, and status (running, completed, failed)

### Requirement 6: Visual Configuration Editor

**User Story:** As an investigator, I want a visual editor in the investigator.html interface that shows the pipeline as a flow diagram and lets me click any step to edit its configuration, so that I can understand and modify the pipeline without writing raw JSON.

#### Acceptance Criteria

1. THE Config_Editor SHALL display the pipeline steps (Parse, Extract, Embed, Graph_Load, Store_Artifact) as a connected visual flow diagram in the investigator.html interface
2. WHEN an investigator clicks a Pipeline_Step in the flow diagram, THE Config_Editor SHALL open an editing panel showing the configurable parameters for that step with current values from the Effective_Config
3. THE Config_Editor SHALL visually distinguish parameters that are inherited from the System_Default_Config versus parameters that are overridden by the case's Pipeline_Config
4. THE Config_Editor SHALL provide a "Reset to Default" button for each parameter and for each Pipeline_Step section that removes the case-level override and reverts to the System_Default_Config value
5. THE Config_Editor SHALL provide a JSON editor view with syntax highlighting for investigators who prefer to edit the raw Pipeline_Config JSON directly
6. THE Config_Editor SHALL provide Config_Template presets for common case types (antitrust, criminal, financial_fraud) that populate the Pipeline_Config with recommended values for that case type
7. WHEN an investigator saves changes in the Config_Editor, THE Platform SHALL validate the configuration, create a new Config_Version, and display a confirmation with the new version number

### Requirement 7: Pipeline Monitoring Dashboard

**User Story:** As an investigator, I want a real-time dashboard showing pipeline execution status, entity quality metrics, processing speed, error rates, and cost estimates per case, so that I can monitor pipeline health and make informed configuration decisions.

#### Acceptance Criteria

1. THE Platform SHALL display real-time pipeline execution status for each Case_File, showing the current Pipeline_Step, documents processed, documents remaining, and elapsed time
2. THE Platform SHALL compute and display Entity_Quality_Metrics for each pipeline run: total entity count, entity count by type, average confidence score, and noise ratio (entities below Confidence_Threshold divided by total entities before filtering)
3. THE Platform SHALL compute and display processing speed metrics: documents processed per minute and average entities extracted per document
4. THE Platform SHALL display error rates per pipeline run: count of failed documents, failure rate percentage, and failure details including the Pipeline_Step where each failure occurred and the error message
5. THE Platform SHALL compute and display estimated Bedrock cost per pipeline run based on the number of Bedrock API invocations, the LLM model used, and the total input/output token count
6. WHEN an investigator views the comparison view, THE Platform SHALL display Entity_Quality_Metrics from two Sample_Run snapshots side by side with delta values highlighted

### Requirement 8: Configuration Validation

**User Story:** As a platform operator, I want the system to validate pipeline configurations before they are saved, so that invalid configurations do not cause pipeline failures at execution time.

#### Acceptance Criteria

1. WHEN a Pipeline_Config is submitted for creation or update, THE Platform SHALL validate that confidence_threshold is a float between 0.0 and 1.0 inclusive
2. WHEN a Pipeline_Config is submitted for creation or update, THE Platform SHALL validate that chunk_size_chars is a positive integer between 500 and 100000
3. WHEN a Pipeline_Config is submitted for creation or update, THE Platform SHALL validate that entity_types contains only values from the Platform's supported EntityType enumeration
4. WHEN a Pipeline_Config is submitted for creation or update, THE Platform SHALL validate that load_strategy is one of "bulk_csv" or "gremlin"
5. WHEN a Pipeline_Config is submitted for creation or update, THE Platform SHALL validate that llm_model_id and embedding_model_id reference Bedrock model identifiers available in the deployment region
6. IF validation fails, THEN THE Platform SHALL return a structured error response listing all validation failures with the field path and reason for each failure

### Requirement 9: Configuration Portability

**User Story:** As a platform operator, I want to export and import pipeline configurations between environments (dev, staging, production, GovCloud), so that tested configurations can be promoted without manual re-entry.

#### Acceptance Criteria

1. THE Platform SHALL provide an API endpoint that exports a Case_File's active Pipeline_Config as a standalone JSON document including a metadata header with the source case_id, config_version, and export timestamp
2. THE Platform SHALL provide an API endpoint that imports a Pipeline_Config JSON document into a target Case_File, creating a new Config_Version with the imported configuration
3. WHEN importing a Pipeline_Config, THE Platform SHALL validate the imported configuration against the same rules applied to manual edits before creating the Config_Version
4. THE Platform SHALL provide an API endpoint that exports the System_Default_Config as a standalone JSON document
5. THE Platform SHALL provide an API endpoint that imports a System_Default_Config JSON document, creating a new version of the system defaults

### Requirement 10: Production Scale and Isolation

**User Story:** As a platform operator, I want pipeline configuration to be resolved efficiently and isolated from running executions, so that the system performs well at 500TB scale and configuration changes do not disrupt in-flight processing.

#### Acceptance Criteria

1. THE Platform SHALL resolve the Effective_Config with a single Aurora query joining the System_Default_Config and the case's active Pipeline_Config, completing within 50 milliseconds
2. WHEN a Pipeline_Config is updated while a pipeline execution is in progress for the same Case_File, THE running execution SHALL continue using the Effective_Config resolved at its start time and not be affected by the update
3. THE Platform SHALL cache the resolved Effective_Config in Lambda memory for the duration of a single pipeline execution to avoid redundant database queries across Pipeline_Steps
4. THE Platform SHALL not introduce any AWS service dependencies outside the existing stack (Aurora, Neptune, OpenSearch, Step Functions, Lambda, S3, Bedrock, API Gateway) to maintain GovCloud compatibility
5. WHEN multiple Case_Files execute pipelines concurrently, THE Platform SHALL resolve each case's Effective_Config independently with no cross-case contention

### Requirement 11: Per-Step Pipeline Monitoring with Drill-Down

**User Story:** As an investigator or platform operator, I want to see each pipeline step as a visual card showing its status, and click any step to see detailed metrics, configuration, and processing results for that step, so that I can monitor pipeline health at a glance and drill into specific steps when issues arise.

#### Acceptance Criteria

1. THE Platform SHALL display the pipeline as a series of clickable step cards in the investigator.html interface, with one card per Pipeline_Step: Upload/Collection, Parse/Text Extraction, Entity Extraction (Bedrock), Embedding Generation (Bedrock), Vector Indexing (OpenSearch), Knowledge Graph (Neptune), and RAG Knowledge Base (Bedrock KB)
2. EACH step card SHALL display: step name, AWS service used, a brief description of what the step does, current status indicator (idle, running, completed, error), and a "Click for processing status" link
3. WHEN an investigator clicks a step card, THE Platform SHALL open a detail overlay panel showing:
   - Service status (Active/Inactive) with item count (e.g., "48,247 Vectors Indexed")
   - Key metrics displayed as large stat cards: item count, dimensions/parameters, average latency, estimated monthly cost
   - Configuration & Settings section showing the current Effective_Config values for that step (service name, region, model ID, collection type, etc.)
   - Recent processing history: last 5 pipeline runs with document count, duration, success/failure count
   - Error log: last 10 errors for this step with timestamp, document ID, and error message
4. THE step detail overlay SHALL display metrics that are specific to each step type:
   - Parse step: documents parsed, average parse time, OCR usage count, table extraction count
   - Extract step: entities extracted, entity type distribution, average confidence, LLM model used, total tokens consumed, estimated Bedrock cost
   - Embed step: embeddings generated, embedding dimensions, average embed time, embedding model used
   - Vector Index step: vectors indexed, index size, average query latency, collection cost
   - Graph Load step: nodes loaded, edges loaded, load strategy used (bulk_csv/gremlin), load duration, bulk load status
   - RAG KB step: knowledge base sync status, document count, last sync time
5. THE step detail overlay SHALL include the Configuration & Settings section showing the Effective_Config values for that step, with visual indicators showing which values are inherited from the System_Default_Config versus overridden by the case's Pipeline_Config
6. THE step detail overlay SHALL include an "Edit Configuration" button that opens the Config_Editor pre-focused on that step's configuration section
7. WHEN a pipeline is actively running, THE step cards SHALL update their status indicators in near-real-time (polling every 10 seconds) to show which step is currently executing, which have completed, and which are pending

### Requirement 12: Pipeline Step Processing Results and Quality Feedback

**User Story:** As an investigator tuning a pipeline configuration, I want to see the actual processing results from each step (extracted entities, generated embeddings, loaded graph nodes) so that I can evaluate whether the configuration is producing good results before running the full batch.

#### Acceptance Criteria

1. WHEN the Entity Extraction step completes for a Sample_Run, THE Platform SHALL display the extracted entities grouped by type with confidence scores, allowing the investigator to visually assess extraction quality
2. WHEN the Knowledge Graph step completes for a Sample_Run, THE Platform SHALL display the loaded node count and edge count, and provide a link to view the resulting graph in the Knowledge Graph section
3. WHEN the Vector Indexing step completes for a Sample_Run, THE Platform SHALL display the number of vectors indexed and allow the investigator to run a test search query against the indexed sample
4. THE Platform SHALL compute a "Pipeline Quality Score" for each Sample_Run based on: entity extraction confidence average, entity type diversity, relationship density (edges per node), and noise ratio — displayed as a single 0-100 score with breakdown
5. WHEN an investigator compares two Sample_Runs, THE Platform SHALL highlight quality score improvements or regressions for each metric, making it clear whether a configuration change improved or degraded results


### Requirement 13: Image and Video Analysis Pipeline Step (Amazon Rekognition)

**User Story:** As an investigator, I want the pipeline to automatically analyze photos and videos in case files using Amazon Rekognition, extracting faces, objects, text, scenes, and matching faces against watchlists, so that visual evidence is searchable and connected to the knowledge graph alongside document-derived entities.

#### Acceptance Criteria

1. THE Pipeline SHALL include an optional Rekognition Pipeline_Step that processes image files (JPEG, PNG, TIFF) and video files (MP4, MOV) uploaded to a case's S3 prefix
2. THE Rekognition step SHALL perform facial detection and return bounding boxes, confidence scores, and facial attributes (age range, gender, emotions) for each detected face
3. THE Rekognition step SHALL perform facial comparison against a configurable watchlist collection (per-case or shared), returning match confidence and the matched identity name
4. THE Rekognition step SHALL perform object and scene detection, returning labels with confidence scores (e.g., "weapon: 0.95", "currency: 0.88", "vehicle: 0.92")
5. THE Rekognition step SHALL perform text detection (OCR) on images, extracting visible text with bounding boxes and confidence
6. WHEN Rekognition identifies a face matching a watchlist entry, THE Platform SHALL create a person entity in the Neptune knowledge graph linked to the source image document, the matched identity, and any co-occurring entities from the same image
7. WHEN Rekognition detects objects or scenes, THE Platform SHALL create entity nodes for significant objects (weapons, drugs, vehicles, currency, electronics) and link them to the source image document in the knowledge graph
8. THE Rekognition step SHALL be configurable per case via the Pipeline_Config with parameters: enabled (boolean), watchlist_collection_id (string), min_face_confidence (float), min_object_confidence (float), detect_text (boolean), detect_moderation_labels (boolean)
9. THE Platform SHALL store Rekognition results as JSON artifacts in S3 alongside text extraction artifacts, and index detected text and labels in OpenSearch for keyword search
10. THE Rekognition step SHALL support processing existing Rekognition output from external sources (e.g., pre-processed Rekognition results in S3) by importing the JSON results directly into the entity extraction and graph loading steps
11. THE Pipeline_Config "rekognition" section SHALL support parameters: enabled, watchlist_collection_id, min_face_confidence (0.0-1.0), min_object_confidence (0.0-1.0), detect_text (boolean), detect_moderation_labels (boolean), video_segment_length_seconds (integer)

### Requirement 14: Investigative Case Assistant Chatbot

**User Story:** As an investigator, I want a persistent AI chatbot panel in the investigator interface that understands my case context, can answer questions about case evidence, help me explore connections, compare findings with external sources, and assist with investigative analysis — so that I have an always-available AI partner that accelerates my investigation.

#### Acceptance Criteria

1. THE Platform SHALL display a collapsible chatbot panel on the right side of the investigator.html interface, accessible from any tab, that maintains conversation history for the duration of the session
2. THE chatbot SHALL have access to the currently selected case's data including: all indexed documents (via OpenSearch search), the knowledge graph (via Neptune queries), extracted entities, pattern discovery results, and pipeline configuration
3. WHEN an investigator asks a question about case evidence, THE chatbot SHALL use RAG (Retrieval-Augmented Generation) to search the case's OpenSearch index, retrieve relevant document passages, and generate an answer citing specific documents and page references
4. WHEN an investigator asks about entity connections, THE chatbot SHALL query the Neptune knowledge graph to find paths between entities and explain the connections in natural language
5. THE chatbot SHALL support document attachment — an investigator can drag-and-drop or upload a new document into the chat, and the chatbot SHALL extract text, identify entities, and compare them against existing case entities, highlighting matches and new information
6. THE chatbot SHALL support "compare with external" queries — when an investigator pastes text or a URL, the chatbot SHALL compare the external content against case evidence and highlight overlaps, contradictions, and new leads
7. THE chatbot SHALL maintain investigative context across the conversation — if the investigator is viewing a specific entity profile or graph filter, the chatbot SHALL be aware of that context and tailor responses accordingly
8. THE chatbot SHALL support investigative commands including:
   - "Summarize this case" — generate a case brief from all evidence
   - "Who is [person]?" — entity profile with all connections and document references
   - "Find connections between [entity A] and [entity B]" — graph path analysis
   - "What documents mention [topic]?" — targeted search with excerpts
   - "Flag this as suspicious" — add an investigator note/tag to an entity or document
   - "Generate a timeline" — chronological sequence of events from case evidence
   - "What's missing?" — AI analysis of gaps in the evidence
   - "Draft a subpoena list" — suggest entities/documents for legal process based on evidence gaps
9. THE chatbot SHALL display source citations for every factual claim, linking to the specific document, entity, or graph query that supports the statement
10. THE chatbot SHALL support multi-turn conversation with memory — follow-up questions reference previous answers without requiring the investigator to repeat context
11. THE chatbot backend SHALL use Amazon Bedrock with the case's configured LLM model (from Pipeline_Config), with the OpenSearch index and Neptune graph as tool sources for RAG
12. THE chatbot SHALL log all conversations to Aurora for audit trail purposes, associating each conversation with the case_id, user_id, and timestamp
13. THE chatbot panel SHALL include a "Share Finding" button that captures the current chat exchange and adds it as a finding/note attached to the case, visible to other investigators on the same case


### Requirement 15: Pipeline Configuration Wizard — Customer Intake Form

**User Story:** As a consultant or solutions architect, I want a guided questionnaire that I can complete during a customer meeting or send as a form, where the answers automatically generate an optimized pipeline configuration, cost estimate, and deployment plan — so that I can configure a new customer's pipeline in minutes without deep technical knowledge.

#### Acceptance Criteria

1. THE Platform SHALL provide a "New Case Setup Wizard" accessible from the investigator.html interface that presents a multi-section guided questionnaire
2. THE wizard SHALL collect answers across 6 sections:
   - **Data Profile**: total volume (TB), document count, file formats (checkboxes: PDF searchable, PDF scanned, Word, Excel, Email, Text, HTML, Images, Video, Audio), percentage scanned vs digital, average page count, languages
   - **Investigation Type**: case type (dropdown: antitrust, criminal, financial, drug trafficking, public corruption, civil rights, national security, environmental, tax), investigation goals (multi-select: people connections, financial flow, communication patterns, property ownership, corporate structures, timeline, geographic patterns), known subject count, single vs multi-case
   - **Visual Evidence**: photo count estimate, video hours estimate, facial recognition needed (yes/no), watchlist available (yes/no), object detection needed (yes/no), handwritten OCR needed (yes/no)
   - **Search & Analysis**: concurrent users, search type (keyword/semantic/both), cross-case importance (critical/nice-to-have/not needed), ingestion mode (real-time/batch), latency requirement
   - **Environment & Compliance**: AWS region, data classification, data residency, monthly budget range, one-time processing budget range
   - **Integration**: existing system integration, SSO needed, audit logging, export format
   - **Frontend & User Scale**: expected concurrent users (1-50 small, 50-500 medium, 500-10000 large), user roles (investigators, attorneys, managers, analysts), frontend deployment preference (static S3+CloudFront, React SPA, or embedded in existing portal), authentication method (Cognito, SAML/SSO, existing IAM), real-time collaboration needed (yes/no)
3. WHEN the wizard is completed, THE Platform SHALL automatically generate:
   - A Pipeline_Config JSON optimized for the customer's answers (entity types, extraction prompt, chunk size, confidence threshold, search tier, graph strategy, Rekognition settings, embedding model)
   - A cost estimate breakdown (Textract, Bedrock entity extraction, Bedrock embeddings, OpenSearch monthly, Neptune monthly, S3 storage, Lambda compute, Rekognition)
   - A processing time estimate (hours for initial load, ongoing ingestion rate)
   - A recommended architecture summary (which AWS services are needed, sizing recommendations)
4. THE wizard SHALL map investigation type to a Config_Template as a starting point, then refine based on specific answers (e.g., antitrust + financial flow → add account_number and financial_amount entity types, increase confidence threshold)
5. THE wizard SHALL generate a shareable summary document (HTML or PDF) that can be emailed to the customer, containing: the questionnaire answers, the generated pipeline config, the cost estimate, and the architecture recommendation
6. THE wizard SHALL support "quick mode" where only the 5 most critical questions are asked (data volume, document count, file formats, investigation type, and AWS region) and reasonable defaults are applied for everything else
7. THE wizard SHALL support saving partial progress — a consultant can start the form, save it, and return later to complete it
8. THE wizard SHALL include an "AI Assist" button that, given the investigation type and a brief description, uses Bedrock to suggest optimal entity types, extraction prompt customizations, and relationship types specific to that investigation domain
9. WHEN the generated Pipeline_Config is accepted, THE Platform SHALL automatically create a new Case_File with the generated config applied, ready for document upload and pipeline execution
10. THE wizard SHALL display a visual preview of the pipeline flow diagram showing which steps are enabled/disabled based on the answers (e.g., Rekognition step shown only if images/video are present, Textract shown only if scanned documents exist)


### Requirement 16: AI-Powered Cost Estimation from Customer Intake

**User Story:** As a consultant, I want the Pipeline Configuration Wizard to automatically generate a detailed cost estimate based on the customer's answers and current AWS public pricing, broken down by service, one-time processing vs monthly running costs, and with optimization recommendations — so that I can present a credible budget to the customer during the same meeting.

#### Acceptance Criteria

1. WHEN the wizard questionnaire is completed, THE Platform SHALL compute a detailed cost estimate using the customer's data profile (volume, document count, file formats, image/video counts) and the generated Pipeline_Config settings
2. THE cost estimate SHALL include a one-time processing cost breakdown by service:
   - **Amazon Textract**: pages × $1.50/1000 pages (only if scanned documents exist, calculated from document count × avg pages × scanned percentage)
   - **Amazon Bedrock Entity Extraction**: documents × avg chunks per doc × cost per invocation (model-specific: Haiku $0.25/M input tokens, Sonnet $3/M, Nova Pro $0.80/M)
   - **Amazon Bedrock Embeddings**: documents × cost per embedding (Titan Embed $0.10/M tokens)
   - **Amazon Rekognition Images**: image count × $1/1000 images for detection + $0.10/face comparison (only if images exist and Rekognition enabled)
   - **Amazon Rekognition Video**: video hours × $0.10/min for label detection + $0.10/min for face detection (only if video exists)
   - **AWS Lambda Compute**: total invocations × avg duration × memory × Lambda pricing
   - **Amazon S3 Storage**: total data volume × $0.023/GB/month
3. THE cost estimate SHALL include a monthly running cost breakdown:
   - **Amazon OpenSearch Serverless**: OCU count × $0.24/OCU/hour × 730 hours (OCU count derived from data volume and search tier)
   - **Amazon Neptune Serverless**: NCU count × $0.22/NCU/hour × 730 hours (NCU count derived from entity/relationship count estimates)
   - **Amazon Aurora Serverless v2**: ACU count × $0.12/ACU/hour × 730 hours
   - **Amazon S3 Storage**: ongoing storage cost
   - **Amazon Bedrock Knowledge Base**: if RAG enabled, sync cost estimate
   - **API Gateway + Lambda**: estimated monthly API call volume × cost
4. THE cost estimate SHALL include optimization recommendations that reduce cost, such as:
   - "Use Bedrock Batch Inference for entity extraction to save ~50% ($X savings)"
   - "Use PyPDF2 instead of Textract for searchable PDFs to save $X"
   - "Reduce OpenSearch OCU by using standard tier for cases under 1M documents"
   - "Use Haiku instead of Sonnet for entity extraction to save $X with minimal quality impact"
5. THE cost estimate SHALL display three tiers: Economy (minimum viable, lowest cost), Recommended (balanced quality and cost), and Premium (maximum quality, highest throughput) — each with different model selections, concurrency levels, and service tiers
6. THE cost estimate SHALL be presented as a visual table in the wizard UI with service icons, per-service costs, subtotals for one-time and monthly, and a grand total
7. THE cost estimate SHALL include a "Cost vs Quality" chart showing how different confidence thresholds, model selections, and processing options affect both cost and expected entity quality score
8. THE Platform SHALL use a pricing data file (JSON) that can be updated when AWS pricing changes, rather than hardcoding prices — enabling the estimate to stay current without code changes
9. THE cost estimate SHALL be included in the shareable summary document (HTML/PDF) generated by the wizard, formatted for customer presentation with AWS service logos and clear line items
10. THE Platform SHALL track actual costs during pipeline execution (via CloudWatch metrics and Bedrock usage) and compare them against the wizard's estimate, displaying the variance in the monitoring dashboard — enabling the consultant to refine estimates for future customers


### Requirement 17: Case Assessment Dashboard — Investigator Command View

**User Story:** As a senior investigator or supervising attorney, I want to see an immediate case health assessment when I open a case — showing case strength, evidence gaps, key subjects, critical leads, resource recommendations, and timeline — so that I can make informed decisions about where to focus limited investigative resources and whether to pursue, escalate, or close the case.

#### Acceptance Criteria

1. WHEN an investigator selects a case, THE Platform SHALL display a Case Assessment Dashboard as the first section above the search bar, showing an AI-generated case overview
2. THE dashboard SHALL display a Case Strength Score (0-100) computed from: evidence volume, entity density, relationship density, document corroboration rate, and cross-case connection count — with a visual gauge and color coding (red 0-30, yellow 31-60, green 61-100)
3. THE dashboard SHALL display an Evidence Coverage section showing which investigative elements have supporting evidence and which have gaps, presented as a checklist with status indicators:
   - People identified (count + status)
   - Organizations mapped (count + status)
   - Financial connections documented (count + status)
   - Communication patterns established (count + status)
   - Physical evidence cataloged (count + status)
   - Timeline established (date range + completeness)
   - Geographic scope mapped (location count + status)
4. THE dashboard SHALL display a Key Subjects section showing the top persons of interest ranked by connection density in the knowledge graph, with entity type icons, connection count, and document reference count
5. THE dashboard SHALL display a Critical Leads section with AI-identified entities or patterns that appear significant but lack follow-up documentation — these are the "investigate next" recommendations
6. THE dashboard SHALL display a Resource Recommendation section with AI-generated guidance on where to focus analyst time, formatted as actionable bullet points (e.g., "Subpoena financial records for Company X — 3 unexplained transactions detected", "Interview Person Y — appears in 12 documents but no statement on file")
7. THE dashboard SHALL display a Case Timeline showing key events in chronological order, derived from date entities in the knowledge graph, with evidence density indicators per time period
8. THE dashboard SHALL include a "Generate Case Brief" button that produces a comprehensive AI-generated case summary document suitable for presenting to a supervising attorney or for case review meetings
9. THE dashboard metrics SHALL update automatically when new documents are ingested or new pipeline runs complete
10. THE dashboard SHALL be computed from actual case data (Neptune graph metrics, OpenSearch document counts, entity extraction results) — not hardcoded or simulated


### Requirement 18: Case Portfolio Dashboard — Manager View

**User Story:** As a supervising attorney or section chief managing hundreds of cases, I want a portfolio dashboard that shows all cases grouped by status, priority, and category with key metrics at a glance — so that I can allocate investigative resources effectively, identify bottlenecks, and make informed decisions about which cases to pursue, escalate, or close.

#### Acceptance Criteria

1. THE Platform SHALL provide a Case Portfolio Dashboard as a dedicated landing page (or tab) that displays all cases in a structured, filterable view — replacing the simple sidebar list for users managing more than 20 cases
2. THE dashboard SHALL display summary statistics at the top: total active cases, cases by status (active/investigating/indexed/archived), total documents across all cases, total entities extracted, and cases requiring attention (stalled, overdue, or with evidence gaps)
3. THE dashboard SHALL support grouping cases by:
   - **Status**: Created, Ingesting, Indexed, Investigating, Archived, Error
   - **Priority**: Critical, High, Medium, Low (user-assignable)
   - **Category**: Case type (antitrust, criminal, financial, etc.)
   - **Assigned Team**: Which investigator/team is responsible
   - **Age**: Cases opened this week, this month, this quarter, older
   - **Evidence Strength**: Cases grouped by Case Strength Score ranges (strong 61-100, moderate 31-60, weak 0-30)
4. THE dashboard SHALL display each case as a card showing: case name, status badge, priority indicator, document count, entity count, Case Strength Score, assigned investigator(s), days since last activity, and a mini progress bar showing pipeline completion
5. THE dashboard SHALL support sorting by: case name, creation date, last activity, document count, entity count, Case Strength Score, priority
6. THE dashboard SHALL support filtering by: status, priority, category, assigned team, date range, search tier, minimum Case Strength Score
7. THE dashboard SHALL include a "Cases Requiring Attention" section that automatically surfaces:
   - Cases with no activity in 30+ days (stalled)
   - Cases with pipeline errors (failed ingestion)
   - Cases with low Case Strength Score but high document volume (evidence not being extracted effectively)
   - Cases approaching statute of limitations (if configured)
   - Cases with cross-case entity matches that haven't been investigated
8. THE dashboard SHALL include a Resource Allocation view showing: investigator workload (cases per person), case distribution by team, and a drag-and-drop interface for reassigning cases between investigators
9. THE dashboard SHALL include a "Portfolio Analytics" section with charts: cases opened/closed over time, average case duration, evidence processing throughput, cost per case, and Case Strength Score distribution
10. WHEN a manager clicks a case card, THE Platform SHALL navigate to that case's detailed view (Case Assessment Dashboard + search + graph)
11. THE dashboard SHALL support bulk actions: assign priority to multiple cases, reassign cases to a different investigator, archive multiple cases, export case list to CSV

### Requirement 19: Investigator Workbench — Personal Case View

**User Story:** As an investigator managing my assigned cases, I want a personal workbench that shows only my cases organized by what needs my attention next — with AI-prioritized task lists, upcoming deadlines, and quick access to my most active investigations — so that I can manage my caseload efficiently without a manager telling me what to do next.

#### Acceptance Criteria

1. THE Platform SHALL provide an Investigator Workbench view that shows only cases assigned to the current user, organized by urgency and next action needed
2. THE workbench SHALL display a "Today's Priority" section at the top with AI-generated recommendations for which cases to work on today, based on: recent evidence additions, pending leads, approaching deadlines, and cross-case matches discovered overnight
3. THE workbench SHALL organize cases into swim lanes:
   - **Needs Immediate Action**: Cases with new cross-case matches, failed pipeline runs, or new evidence uploaded
   - **Active Investigation**: Cases the investigator is currently working on
   - **Awaiting Response**: Cases waiting for subpoena returns, witness interviews, or external data
   - **Review & Close**: Cases ready for supervisory review or closure recommendation
4. THE workbench SHALL display a personal activity feed showing: recent searches performed, entities investigated, documents reviewed, findings added, and drill-down sessions — enabling the investigator to pick up where they left off
5. THE workbench SHALL include a "My Findings" section where the investigator can see all notes, tags, and findings they've added across all their cases — searchable and filterable
6. THE workbench SHALL include quick-action buttons for each case: "Continue Investigation" (opens where they left off), "Add Finding", "Request Resources", "Recommend Closure"
7. THE workbench SHALL display workload metrics: total assigned cases, cases worked this week, average time per case, and a personal productivity trend

### Requirement 20: Document Evidence Viewer with S3 Source Access

**User Story:** As an investigator reviewing case evidence in the drill-down panel, I want to click a document and view the original source file (PDF, image, Word doc) directly from S3 in my browser, so that I can review the actual evidence artifact — not just extracted text — and verify the accuracy of entity extraction and text parsing.

#### Acceptance Criteria

1. WHEN an investigator drills down to a document in the entity profile (Level 4 — Document Evidence), THE Platform SHALL display a "View Original Document" button that opens the original source file from S3 in a new browser tab
2. THE Platform SHALL provide an API endpoint `GET /case-files/{id}/documents/{docId}/download` that generates a time-limited pre-signed S3 URL for the requested document
3. THE pre-signed URL SHALL expire after 15 minutes and SHALL grant read-only access to the specific document file
4. THE Platform SHALL resolve the document's S3 key by looking up the document_id in Aurora to find the source_filename and s3_key, falling back to the convention `cases/{case_id}/raw/{filename}` if the s3_key is not stored
5. THE Platform SHALL support viewing all ingested file types: PDF, Word (DOCX), Excel (XLSX), plain text, HTML, images (JPEG, PNG, TIFF), and video (MP4, MOV) — the browser handles rendering based on Content-Type
6. THE document viewer button SHALL display the filename and a visual indicator of the file type (PDF icon, image icon, etc.)
7. IF the document is not found in S3, THE Platform SHALL display a clear error message indicating the file is unavailable rather than showing a broken link
8. THE Platform SHALL not require the investigator to have direct S3 access — the pre-signed URL is generated server-side by the Lambda execution role which has S3 read permissions


### Requirement 21: Phased Video Processing Strategy

**User Story:** As a senior investigator managing limited resources, I want to control when and how video evidence is processed — starting with documents and photos to build context, then processing video only when I have specific subjects to look for — so that I don't waste budget on unfocused video analysis and instead use video evidence strategically to confirm or deny investigative hypotheses.

#### Acceptance Criteria

1. THE Pipeline_Config "rekognition" section SHALL support a `video_processing_mode` parameter with values: "skip" (default — don't process video), "faces_only" (run only face detection/matching against watchlist), "targeted" (face + label detection on investigator-flagged videos only), "full" (all detections on all videos)
2. WHEN `video_processing_mode` is "skip", THE Rekognition step SHALL ignore all video files (MP4, MOV) and process only images — this is the default for initial case ingestion to keep costs low
3. WHEN `video_processing_mode` is "faces_only", THE Rekognition step SHALL run only `start_face_detection` and `search_faces_by_image` (watchlist matching) on video files, skipping label detection — this mode is for Phase 2 when a watchlist of known subjects has been built from document/photo analysis
4. WHEN `video_processing_mode` is "targeted", THE Rekognition step SHALL process only videos that have been explicitly flagged by an investigator for analysis (via a `flagged_for_video_analysis` tag on the document record) — this mode enables selective processing of specific surveillance footage
5. WHEN `video_processing_mode` is "full", THE Rekognition step SHALL run all available detections (face detection, face matching, label detection, text detection) on all video files — this mode is for comprehensive pre-trial evidence processing
6. THE Pipeline Configuration Wizard SHALL include a "Video Processing Priority" question with options: "Process with initial load" (sets mode to "full"), "Process after document analysis" (sets mode to "skip" initially, with guidance to upgrade later), "Process on demand only" (sets mode to "targeted")
7. THE Cost Estimation Service SHALL compute video processing costs separately from image costs, showing the investigator the cost impact of each video_processing_mode so they can make an informed budget decision
8. THE Platform SHALL support changing `video_processing_mode` at any time via the Config Editor, allowing investigators to upgrade from "skip" to "faces_only" or "targeted" as the investigation progresses and context is built
9. THE Case Assessment Dashboard SHALL include a "Video Evidence Status" indicator showing: total video files in the case, how many have been processed, which mode was used, and a recommendation on whether video processing would add investigative value based on the current entity graph density


### Requirement 22: One-Click Deployment Package Generator

**User Story:** As a consultant deploying this platform for a new customer, I want the wizard to generate a complete, self-contained deployment package (CloudFormation template + Lambda code zip + frontend) that the customer can deploy in their AWS account with zero coding — so that I can hand off a working system after a single discovery meeting without requiring the customer to have AWS development expertise.

#### Acceptance Criteria

1. WHEN the wizard questionnaire is completed and the generated Pipeline_Config is accepted, THE Platform SHALL provide a "Generate Deployment Package" button that produces a downloadable deployment bundle
2. THE deployment bundle SHALL contain:
   - A parameterized CloudFormation YAML template that creates the complete infrastructure stack: VPC (with private subnets, NAT Gateway, VPC endpoints), Aurora Serverless v2 (with RDS Proxy), Neptune Serverless, OpenSearch Serverless (with AOSS-managed VPC endpoint), Lambda functions (14+), Step Functions state machine, API Gateway, S3 buckets, IAM roles and policies, Secrets Manager secret, and an S3-hosted static website with CloudFront distribution for the frontend
   - A Lambda code zip (`lambda-code.zip`) containing all `src/` code, uploaded to a deployment S3 bucket
   - The `investigator.html` frontend with the API Gateway URL injected at deploy time via a CloudFormation custom resource
   - The generated Pipeline_Config as a CloudFormation parameter default, automatically seeded into Aurora as the system default config on first deploy
   - The `config/aws_pricing.json` pricing data file bundled with the Lambda code
3. THE CloudFormation template SHALL accept only 5 required parameters for deployment:
   - `EnvironmentName` (string, default "prod") — prefix for all resource names
   - `AdminEmail` (string) — for SNS notifications and initial Cognito user
   - `VpcCidr` (string, default "10.0.0.0/16") — VPC CIDR block
   - `DeploymentBucketName` (string) — S3 bucket where the Lambda code zip is uploaded
   - `LambdaCodeKey` (string, default "deployments/lambda-code.zip") — S3 key for the Lambda code zip
4. THE CloudFormation template SHALL output:
   - `InvestigatorURL` — the CloudFront URL for the investigator frontend
   - `ApiGatewayURL` — the API Gateway endpoint URL
   - `S3DataBucket` — the S3 bucket name for case data uploads
   - `AuroraClusterEndpoint` — for database administration
   - `NeptuneClusterEndpoint` — for graph database administration
5. THE deployment bundle SHALL include a `DEPLOYMENT_GUIDE.md` with step-by-step instructions (with screenshots placeholders) covering: prerequisites (AWS account, permissions), uploading the Lambda code zip to S3, deploying the CloudFormation stack via AWS Console, verifying the deployment, and accessing the investigator URL
6. THE CloudFormation template SHALL include a custom resource Lambda that runs on stack creation to: create the Aurora database schema (all tables from the migration script), seed the system default Pipeline_Config, and upload the frontend HTML to the S3 website bucket with the API Gateway URL injected
7. THE Platform SHALL support generating deployment packages for both commercial AWS regions and GovCloud — the template SHALL not use any services unavailable in GovCloud
8. THE wizard SHALL also offer a "Download CDK App" option for technical customers who prefer CDK — this packages the existing `infra/cdk/` directory with the generated Pipeline_Config pre-configured
9. THE deployment package generator SHALL be accessible from the wizard results page and from the shareable summary document — the consultant can generate the package during the meeting or email it to the customer afterward
10. THE CloudFormation template SHALL include CloudWatch alarms for: Lambda error rates, Aurora CPU utilization, Neptune query latency, Step Functions execution failures, and API Gateway 5xx error rates — providing production monitoring out of the box


### Requirement 23: AI-Powered Document Classification and Case Routing

**User Story:** As a platform operator ingesting a bulk document dump (e.g., 500TB from a subpoena or raid) where files are not pre-organized by case, I want the pipeline to automatically classify each document and route it to the correct case — using AI to read the first pages, extract case numbers, and match to existing cases or suggest new ones — so that millions of unorganized files can be ingested without manual sorting.

#### Acceptance Criteria

1. THE Pipeline SHALL include an optional Document Classification step that runs BEFORE entity extraction, reading the first 2-3 pages of each document to determine case assignment
2. THE classification step SHALL support three routing modes configurable in the Pipeline_Config:
   - **folder_based** (default): Documents are pre-organized in S3 folders per case — no classification needed
   - **metadata_routing**: Extract case numbers from filenames, PDF metadata, or Bates number patterns using configurable regex patterns
   - **ai_classification**: Use Bedrock (Haiku) to read the first 2 pages and classify the document by case type, extract case numbers, and match to existing cases
3. WHEN using metadata_routing, THE Platform SHALL accept a configurable case_number_pattern regex (e.g., `\d{4}-AT-\d{5}` for antitrust) and scan filenames, PDF metadata fields (author, subject, keywords), and the first page text for matches
4. WHEN using ai_classification, THE Platform SHALL send the first 5,000 characters of each document to Bedrock Haiku with a prompt that includes the list of existing case names/numbers from Aurora, and return: case_number (if found), case_category, confidence, and routing_reason
5. WHEN a document matches an existing case (by case number or AI classification with confidence > 0.8), THE Platform SHALL automatically route it to that case's S3 prefix and associate it with the case in Aurora
6. WHEN a document does not match any existing case, THE Platform SHALL place it in a "triage" queue visible in the investigator UI, where an investigator can manually assign it to an existing case or create a new case
7. THE Platform SHALL support a "classify sample" mode where the first 100 documents are classified and the results are shown to the investigator for review before committing to a full bulk classification run
8. THE Pipeline Configuration Wizard SHALL include a "Document Organization" question with options: Pre-organized by case (folder_based), Has case numbers in filenames/headers (metadata_routing), Mixed/unorganized (ai_classification), Unknown (run sample first)
9. THE wizard SHALL also ask for the case number format pattern when metadata_routing is selected
10. THE cost estimation SHALL include the classification step cost: ~$0.0001 per document for Haiku classification of first 2 pages, shown separately from entity extraction cost


### Requirement 24: Advanced Knowledge Graph Interaction and Multi-Entity Analysis

**User Story:** As an investigator exploring the knowledge graph, I want to click any entity to see a focused neighborhood graph with AI-generated investigative questions and key insights, and I want to Ctrl+click multiple entities to analyze their relationships — so that I can quickly understand entity connections, identify anomalies, and investigate multi-entity relationships without manually cross-referencing documents.

#### Acceptance Criteria

1. WHEN an investigator clicks an entity node in the knowledge graph, THE Platform SHALL display a drill-down panel containing: entity intelligence profile, AI investigative intelligence brief (via Bedrock), a focused connection graph (ego graph) showing the entity and its 1-hop neighbors, AI investigative questions (top 3), key insights (prioritized anomaly detection), connected entities list, and document evidence
2. THE focused connection graph (ego graph) SHALL render the clicked entity as a centered, larger node with its direct neighbors arranged around it in a radial layout, color-coded by entity type, with edge labels showing relationship types
3. THE ego graph SHALL be interactive — double-clicking a neighbor node SHALL navigate to that entity's drill-down profile, enabling the investigator to "walk" the graph
4. THE AI Investigative Questions section SHALL display up to 3 questions generated from the entity's local graph topology, detecting: entity density anomalies (many documents but few connections or vice versa), bridge entities connecting multiple entity types, co-occurrence patterns with key persons, and organizational/geographic patterns
5. EACH AI Investigative Question SHALL be clickable, expanding to show: contextual analysis explaining why the pattern is significant, and a recommended investigator action
6. THE Key Insights section SHALL display prioritized anomaly detections including: evidence gaps (graph connections without document support), strong corroboration (multiple independent documents confirming connections), unusual entity clustering (many entities in few documents), network hub identification (high-connectivity entities), and cross-category bridge detection
7. EACH Key Insight SHALL be color-coded by priority (red=HIGH, yellow=MEDIUM, green=CONFIRMED) and clickable to expand detailed analysis with investigative guidance
8. WHEN an investigator Ctrl+clicks (or Cmd+clicks on Mac) entity nodes in the knowledge graph, THE Platform SHALL add each node to a multi-select set (maximum 5 entities) with visual highlighting (blue border) on selected nodes
9. WHEN 2 or more entities are multi-selected, THE Platform SHALL display a floating toolbar at the bottom of the graph showing: selected count, entity names, an "Analyze Selection" button, and a "Clear" button
10. WHEN the investigator clicks "Analyze Selection", THE Platform SHALL open a relationship analysis panel showing: a relationship subgraph (only selected entities + shared connections), shared connections list (entities connected to 2+ selected entities), co-occurring documents (documents mentioning 2+ selected entities), and an AI relationship hypothesis
11. THE relationship subgraph SHALL visually distinguish: selected entities (larger, blue-bordered), shared connections (standard size), direct connections between selected entities (red edges labeled "direct"), and indirect connections through shared entities (blue edges)
12. THE AI relationship hypothesis SHALL be generated from the computed shared connections and document co-occurrences, describing the nature of the relationship and recommending investigative next steps
13. THE Platform SHALL limit multi-select to 5 entities maximum and display a notification if the investigator attempts to select more


### Requirement 25: Interactive Timeline Analysis View

**User Story:** As a prosecutor preparing for trial, I want to see all case events, entity appearances, and document dates plotted on an interactive timeline — so that I can identify temporal patterns, gaps in activity, sequences of events, and build a chronological narrative of the case.

#### Acceptance Criteria

1. THE Platform SHALL provide a "Timeline" tab in the investigator interface that displays all date entities from the knowledge graph as events on a horizontal, scrollable timeline
2. EACH timeline event SHALL display: the date, connected entities (persons, organizations, locations), the source document(s), and a brief description extracted from the document context
3. THE timeline SHALL support zooming from year-level overview down to day-level detail, with smooth transitions between zoom levels
4. THE timeline SHALL color-code events by entity type: person events (red), organization events (orange), location events (green), financial events (yellow), legal/court events (blue)
5. THE timeline SHALL highlight temporal clusters — periods with unusually high event density — with a visual density indicator bar above the timeline
6. THE timeline SHALL detect and highlight temporal gaps — periods with no activity that are surrounded by active periods — as these often indicate concealment or changes in behavior
7. WHEN an investigator clicks a timeline event, THE Platform SHALL show the connected entities and source document in a detail panel, with a link to drill down into the entity or view the original document
8. THE timeline SHALL support filtering by entity type, specific entity name, date range, and document source
9. THE Platform SHALL provide an "AI Timeline Analysis" button that uses Bedrock to generate a narrative summary of the chronological sequence of events, highlighting significant patterns, gaps, and escalation/de-escalation trends
10. THE timeline SHALL support overlaying multiple entity timelines for comparison — e.g., show Person A's timeline alongside Person B's to identify when they were active in the same periods or locations


### Requirement 26: Automated Investigative Report Generation

**User Story:** As a prosecutor or supervising attorney, I want to generate formal investigative reports, prosecution memos, and case summaries with one click — pulling from all case evidence, entity analysis, and AI insights — so that I can produce court-ready documents without manually compiling information from multiple sources.

#### Acceptance Criteria

1. THE Platform SHALL provide a "Generate Report" button accessible from the case assessment dashboard and the investigator workbench
2. THE Platform SHALL support generating multiple report types: Case Summary Brief, Prosecution Memo, Investigation Status Report, Entity Profile Dossier, Evidence Inventory, and Subpoena Recommendation List
3. EACH report SHALL be generated by Bedrock using the case's actual data: entities from Neptune, document references from OpenSearch, entity relationships, timeline events, AI insights, and investigator findings/notes
4. THE Case Summary Brief SHALL include: case overview, key subjects with connection counts, evidence summary by type, timeline of key events, case strength assessment, and recommended next steps
5. THE Prosecution Memo SHALL include: statement of facts (chronological), elements of the offense mapped to evidence, witness/document list, anticipated defenses with counter-evidence, and sentencing considerations
6. THE Entity Profile Dossier SHALL include: comprehensive profile of a selected entity with all connections, document references, timeline of appearances, associated entities, and AI-generated risk assessment
7. EACH generated report SHALL include source citations linking every factual claim to the specific document, entity, or graph query that supports it — enabling the reader to verify any statement
8. THE Platform SHALL render reports as formatted HTML viewable in the browser, with an option to export as PDF or Word document
9. THE Platform SHALL store generated reports in Aurora associated with the case, allowing investigators to retrieve, compare, and share previous reports
10. THE report generation SHALL use the case's configured LLM model from the Pipeline_Config, defaulting to Claude Sonnet for highest quality output


### Requirement 27: AI Hypothesis Testing

**User Story:** As an investigator building a theory of the case, I want to state a hypothesis in natural language and have the AI evaluate it against all available evidence — identifying supporting evidence, contradicting evidence, and gaps — so that I can systematically test investigative theories before committing resources.

#### Acceptance Criteria

1. THE Platform SHALL provide a "Test Hypothesis" input in the investigator interface where the investigator can type a hypothesis in natural language (e.g., "Epstein used Company X to funnel money to Location Y through Account Z")
2. WHEN a hypothesis is submitted, THE Platform SHALL use Bedrock to decompose the hypothesis into testable claims (e.g., "Epstein is connected to Company X", "Company X has financial transactions", "Transactions involve Location Y")
3. FOR EACH testable claim, THE Platform SHALL search the case evidence (OpenSearch documents + Neptune graph) and classify the evidence as: SUPPORTED (evidence found), CONTRADICTED (conflicting evidence found), UNVERIFIED (no evidence found either way), or PARTIALLY SUPPORTED (some evidence but incomplete)
4. THE Platform SHALL display a hypothesis evaluation dashboard showing: overall confidence score (0-100), each claim with its evidence status, supporting documents with relevant excerpts, contradicting documents with relevant excerpts, and evidence gaps that need to be filled
5. THE Platform SHALL highlight evidence gaps as investigative leads — "To verify claim X, you would need: financial records from Company X for 2005-2008, or testimony from Person Y"
6. THE Platform SHALL allow investigators to save hypotheses and their evaluations, track how the evidence status changes as new documents are ingested, and compare multiple competing hypotheses
7. THE Platform SHALL support "What if" scenarios — "If we obtain Document X, how would it change the hypothesis evaluation?" — by allowing investigators to add hypothetical evidence and see the impact
8. THE hypothesis evaluation SHALL use RAG to search for both supporting and contradicting evidence, avoiding confirmation bias by explicitly searching for counter-evidence
9. THE Platform SHALL generate a "Hypothesis Report" summarizing the evaluation, suitable for inclusion in prosecution memos or case review presentations


### Requirement 28: Geospatial Map View

**User Story:** As an investigator analyzing geographic patterns in case evidence, I want to see all location entities plotted on an interactive map with connections to associated persons, organizations, and events — so that I can identify geographic clusters, travel patterns, jurisdictional boundaries, and location-based evidence gaps.

#### Acceptance Criteria

1. THE Platform SHALL provide a "Map" tab in the investigator interface that displays an interactive map (using Leaflet.js with OpenStreetMap tiles) with all location entities from the knowledge graph plotted as markers
2. EACH map marker SHALL be color-coded by the type of activity at that location: person residence (blue), organization headquarters (orange), event location (red), financial transaction location (green), property/asset (yellow)
3. WHEN an investigator clicks a map marker, THE Platform SHALL display a popup showing: location name, connected entities (persons, organizations, events), document references, and a link to drill down into the location entity
4. THE map SHALL draw connection lines between locations that share common entities — e.g., if Person A appears at both Location X and Location Y, draw a line between them labeled with the person's name
5. THE map SHALL support a "Travel Pattern" mode that shows the chronological movement of a selected person between locations, with dated arrows showing the sequence and direction of travel
6. THE map SHALL support filtering by: entity type, specific person, date range, and activity type
7. THE map SHALL display a heat map overlay option showing geographic density of case activity — highlighting areas with the most evidence concentration
8. THE Platform SHALL attempt to geocode location entities using their names (city, state, country) and cache the coordinates in Aurora for subsequent renders
9. THE map SHALL support overlaying jurisdictional boundaries (federal districts, state lines) to help prosecutors identify venue and jurisdiction issues
10. THE Platform SHALL provide an "AI Geographic Analysis" button that uses Bedrock to analyze the geographic patterns and generate insights about: geographic clustering, travel patterns, jurisdictional implications, and location-based evidence gaps


### Requirement 29: Document Tagging, Annotation, and Evidence Chain

**User Story:** As an investigator reviewing case documents, I want to highlight passages, tag them with evidentiary categories, add annotations, and link them to entities — so that I can build a structured evidence chain that maps specific document passages to elements of the offense, and so that other investigators and prosecutors can see my analysis when they review the same documents.

#### Acceptance Criteria

1. WHEN an investigator views a document in the drill-down panel, THE Platform SHALL allow the investigator to select a text passage and create an annotation with: a highlight color, a tag category, a free-text note, and optional entity links
2. THE Platform SHALL support the following tag categories: "Evidence of Offense" (red), "Corroborating Evidence" (green), "Contradicting Evidence" (orange), "Witness Statement" (blue), "Financial Record" (yellow), "Communication" (purple), "Suspicious Activity" (red outline), and custom user-defined tags
3. EACH annotation SHALL be stored in Aurora associated with the document_id, case_id, user_id, the character offset range of the highlighted passage, the tag category, the note text, linked entity names, and a timestamp
4. WHEN a document is viewed, THE Platform SHALL render all existing annotations as colored highlights over the document text, with hover tooltips showing the tag, note, and author
5. THE Platform SHALL provide an "Annotations" sidebar panel that lists all annotations for the current document, filterable by tag category and author, with click-to-scroll-to functionality
6. THE Platform SHALL provide a case-wide "Evidence Board" view that aggregates all annotations across all documents, grouped by tag category — enabling prosecutors to see all "Evidence of Offense" passages in one view regardless of which document they came from
7. EACH annotation SHALL support linking to one or more entities from the knowledge graph — when an annotation is linked to an entity, it appears in that entity's drill-down profile under a "Tagged Evidence" section
8. THE Platform SHALL support annotation threads — other investigators can reply to an annotation with their own notes, creating a discussion thread attached to a specific document passage
9. THE Platform SHALL log all annotation activity in the audit trail (investigator_activity table) for chain of custody purposes, recording who created, modified, or deleted each annotation and when
10. THE Platform SHALL provide an "AI Auto-Tag" button that uses Bedrock to scan a document and suggest annotations — identifying passages that appear to be evidence of specific offense elements, financial transactions, witness statements, or suspicious activity — which the investigator can accept, modify, or reject
11. THE Platform SHALL support exporting all annotations for a case as a structured report (HTML or CSV) suitable for discovery production or court filing, with document references and page numbers
