# Implementation Plan: Configurable Pipeline

## Overview

This plan implements per-case pipeline configuration for the DOJ Investigative Case Management platform across 19 requirements. Tasks are grouped by functional area: core config data model and services (Req 1-4), sample-and-compare workflow (Req 5), visual editor and monitoring frontend (Req 6-7, 11-12), validation and portability (Req 8-9), production scale (Req 10), Rekognition pipeline step (Req 13), investigative chatbot (Req 14), pipeline wizard and cost estimation (Req 15-16), and dashboards/workbench (Req 17-19). All code is Python (Lambda/services) and HTML/JS (investigator.html frontend). Property-based tests use `hypothesis`.

## Tasks

- [x] 1. Aurora schema and Pydantic models for pipeline configuration
  - [x] 1.1 Create Aurora migration script with all pipeline config tables
    - Create `scripts/migrations/001_pipeline_config_tables.sql` with CREATE TABLE statements for: `system_default_config`, `pipeline_configs`, `pipeline_runs`, `pipeline_step_results`, `sample_run_snapshots`
    - Include all indexes, constraints, partial unique constraints for `is_active`
    - Include `ALTER TABLE case_files` additions for priority, assigned_to, case_category, last_activity_at, strength_score columns (Req 18)
    - Include `chat_conversations` table (Req 14), `investigator_findings` and `investigator_activity` tables (Req 19)
    - _Requirements: 1.1, 1.2, 14.12, 18.8, 19.4, 19.5_

  - [x] 1.2 Create Pydantic models for pipeline configuration
    - Create `src/models/pipeline_config.py` with: `PipelineConfig`, `ConfigVersion`, `EffectiveConfig`, `SampleRun`, `QualityScore`, `SampleRunComparison`, `ValidationError`, `StepDetail`, `PipelineRunSummary`, `PipelineRunMetrics`, `PipelineStatus`
    - Include `ParseConfig`, `ExtractConfig`, `EmbedConfig`, `GraphLoadConfig`, `StoreArtifactConfig`, `RekognitionConfig` section models
    - Include `CostEstimate`, `CaseAssessment`, `ChatMessage`, `Finding`, `WorkbenchCase` models for Req 13-19
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 13.11_

  - [ ]* 1.3 Write unit tests for Pydantic models
    - Test serialization/deserialization of all models
    - Test default values and field validation
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [x] 2. Config Resolution Service and deep merge logic (Req 2)
  - [x] 2.1 Implement ConfigResolutionService
    - Create `src/services/config_resolution_service.py` with `resolve_effective_config`, `get_system_default`, `get_case_override`, and `deep_merge` methods
    - `resolve_effective_config` executes a single Aurora query joining `system_default_config` and `pipeline_configs` for the case, then calls `deep_merge`
    - `deep_merge` recursively merges dicts; override replaces base at leaf level; lists replaced wholesale
    - Return `EffectiveConfig` with `origins` dict annotating each leaf key as "system_default" or "case_override"
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 2.2 Write property test: deep merge preserves base keys and overrides leaf values
    - **Property 1: Deep merge preserves base keys and overrides leaf values**
    - Generate random nested dicts for system default and case override; verify (a) base-only keys preserved, (b) override keys take override value, (c) no extra keys
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [ ]* 2.3 Write property test: deep merge with empty override is identity
    - **Property 2: Deep merge with empty override is identity**
    - Generate random valid system default configs; verify `deep_merge(default, {})` equals default
    - **Validates: Requirements 2.1**

  - [ ]* 2.4 Write property test: origin annotations correctly classify inherited vs overridden
    - **Property 10: Origin annotations correctly classify inherited vs overridden**
    - Generate random configs with mixed inherited/overridden keys; verify origins dict labels each leaf correctly
    - **Validates: Requirements 2.5, 11.5**

  - [ ]* 2.5 Write property test: removing a case override reverts to system default
    - **Property 17: Removing a case override reverts to system default**
    - Generate configs with overrides, remove a field, re-resolve, verify field reverts to system default value
    - **Validates: Requirements 6.4**

  - [ ]* 2.6 Write property test: concurrent config resolution is independent per case
    - **Property 19: Concurrent config resolution is independent per case**
    - Generate two cases with different overrides; resolve both; verify each reflects its own override merged with shared default
    - **Validates: Requirements 10.5**

- [x] 3. Config Validation Service (Req 8)
  - [x] 3.1 Implement ConfigValidationService
    - Create `src/services/config_validation_service.py` with `validate` method and per-section validators: `_validate_parse`, `_validate_extract`, `_validate_embed`, `_validate_graph_load`, `_validate_store_artifact`, `_check_unknown_keys`
    - Validate: confidence_threshold in [0.0, 1.0], chunk_size_chars in [500, 100000], entity_types from EntityType enum, load_strategy in {"bulk_csv", "gremlin"}, pdf_method in {"text", "ocr", "hybrid"}, artifact_format in {"json", "jsonl"}
    - Validate Rekognition section: min_face_confidence and min_object_confidence in [0.0, 1.0], video_segment_length_seconds > 0
    - Collect all errors (not fail-fast) and return list of `ValidationError`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.6_

  - [ ]* 3.2 Write property test: config validation accepts valid and rejects invalid configs
    - **Property 3: Config validation accepts valid configs and rejects invalid ones**
    - Generate random valid configs (all fields in range) → expect empty error list; generate random invalid configs (at least one field out of range) → expect non-empty error list with correct field_path
    - **Validates: Requirements 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

  - [ ]* 3.3 Write property test: config templates produce valid configs
    - **Property 16: Config templates produce valid configs**
    - For each template (antitrust, criminal, financial_fraud), apply template and run validation → expect zero errors
    - **Validates: Requirements 6.6**

- [x] 4. Pipeline Config Service with versioning (Req 3)
  - [x] 4.1 Implement PipelineConfigService
    - Create `src/services/pipeline_config_service.py` with: `create_or_update_config`, `get_active_config`, `list_versions`, `get_version`, `rollback_to_version`, `export_config`, `import_config`, `apply_template`
    - `create_or_update_config`: validate via ConfigValidationService, deactivate previous active version, insert new version with incremented version number
    - `rollback_to_version`: create new version with content of target version
    - `export_config`: return config_json with metadata header (source case_id, config_version, export timestamp)
    - `import_config`: validate imported config, create new version
    - `apply_template`: look up template from `CONFIG_TEMPLATES` dict, create new version
    - Include `CONFIG_TEMPLATES` dict with antitrust, criminal, financial_fraud presets
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 6.6, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 4.2 Write property test: config version numbers are monotonically increasing
    - **Property 4: Config version numbers are monotonically increasing**
    - Generate random sequences of N config updates for a case; verify version numbers form strictly increasing sequence
    - **Validates: Requirements 3.1, 3.4, 3.6**

  - [ ]* 4.3 Write property test: config rollback round-trip
    - **Property 5: Config rollback round-trip**
    - Generate version history, rollback to random version K, verify new version's config_json equals version K's config_json and version number > previous max
    - **Validates: Requirements 3.3, 3.5**

  - [ ]* 4.4 Write property test: config export/import round-trip
    - **Property 6: Config export/import round-trip**
    - Generate valid config, export, import into different case, verify config_json equality
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [ ]* 4.5 Write property test: system default export/import round-trip
    - **Property 7: System default export/import round-trip**
    - Export active system default, import, verify config_json equality
    - **Validates: Requirements 9.4, 9.5**

- [x] 5. Checkpoint — Core config services
  - Ensure all tests pass, ask the user if questions arise.


- [x] 6. Pipeline step config integration and Step Functions modification (Req 4, 10)
  - [x] 6.1 Create config resolution Lambda for Step Functions
    - Create `src/lambdas/ingestion/resolve_config_handler.py` — Lambda that receives `case_id`, calls `ConfigResolutionService.resolve_effective_config`, returns effective_config JSON
    - This Lambda is invoked as the first step in the Step Functions state machine
    - _Requirements: 4.6, 4.7, 10.1, 10.2, 10.3_

  - [x] 6.2 Modify existing pipeline step Lambdas to read from effective_config
    - Update `src/lambdas/ingestion/embed_handler.py` to read embedding_model_id, search_tier, opensearch_settings from `event["effective_config"]["embed"]`
    - Update `src/lambdas/ingestion/graph_load_handler.py` to read load_strategy, batch_size, normalization_rules from `event["effective_config"]["graph_load"]`
    - Update `src/services/entity_extraction_service.py` to accept extract config params (prompt_template, entity_types, llm_model_id, chunk_size_chars, confidence_threshold, relationship_inference_enabled) from effective_config
    - Add fallback to hardcoded defaults when effective_config is not present (backward compatibility)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 6.3 Update Step Functions ASL definition
    - Modify `infra/step_functions/ingestion_pipeline.json` to add `ResolveConfig` as the first Task step, passing `$.case_id` and storing result in `$.effective_config`
    - Update all subsequent step parameters to pass `$.effective_config` to each Lambda
    - Add `sample_mode` and `document_ids` support for sample runs
    - _Requirements: 4.6, 5.1_

  - [ ]* 6.4 Write property test: pipeline execution uses snapshotted config
    - **Property 8: Pipeline execution uses snapshotted config**
    - Verify that the effective_config stored in pipeline_runs record equals the resolved config at execution start
    - **Validates: Requirements 3.2, 4.6, 10.2**

  - [ ]* 6.5 Write property test: each pipeline step reads exactly its named section
    - **Property 9: Each pipeline step reads exactly its named section**
    - For each step name in {"parse", "extract", "embed", "graph_load", "store_artifact"}, verify the step reads only from `effective_config[step_name]`
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

- [x] 7. Sample Run Service and quality scoring (Req 5, 12)
  - [x] 7.1 Implement SampleRunService
    - Create `src/services/sample_run_service.py` with: `start_sample_run`, `get_sample_run`, `list_sample_runs`, `compare_runs`, `compute_quality_score`
    - `start_sample_run`: validate 1-50 document IDs, resolve effective config, start Step Functions execution with `sample_mode: true` and restricted document list, insert pipeline_runs record
    - `compare_runs`: load two snapshots, compute entities_added/removed/changed, relationship_changes, quality deltas
    - `compute_quality_score`: weighted formula — confidence_avg (0.35), type_diversity (0.20), relationship_density (0.25), noise_ratio_score (0.20)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ]* 7.2 Write property test: quality score is deterministic and bounded
    - **Property 11: Quality score is deterministic and bounded**
    - Generate random entity lists with confidence scores and relationships; verify score in [0, 100], deterministic, breakdown components each in [0, 100] and weighted sum equals overall
    - **Validates: Requirements 12.4**

  - [ ]* 7.3 Write property test: quality score comparison deltas are correct
    - **Property 12: Quality score comparison deltas are correct**
    - Generate two QualityScore values; verify delta for each metric equals B.metric - A.metric
    - **Validates: Requirements 7.6, 12.5**

  - [ ]* 7.4 Write property test: entity quality metrics are correctly computed
    - **Property 13: Entity quality metrics are correctly computed**
    - Generate entity lists with confidence scores and threshold; verify noise_ratio, avg_confidence, entity_type_counts
    - **Validates: Requirements 7.2**

  - [ ]* 7.5 Write property test: sample run snapshot comparison diff is correct
    - **Property 15: Sample run snapshot comparison diff is correct**
    - Generate two entity lists; verify added + removed + unchanged accounts for all entities in both lists
    - **Validates: Requirements 5.3**

  - [ ]* 7.6 Write property test: sample run processes exactly the specified documents
    - **Property 18: Sample run processes exactly the specified documents**
    - Generate list of 1-50 document IDs; verify pipeline_runs record contains exactly those IDs and document_count matches
    - **Validates: Requirements 5.1, 5.6**

  - [ ]* 7.7 Write property test: entity grouping by type is exhaustive
    - **Property 20: Entity grouping by type is exhaustive**
    - Generate entity list; group by type; verify total count equals original list length, each entity in exactly one group
    - **Validates: Requirements 12.1**

- [x] 8. Pipeline Monitoring Service (Req 7, 11)
  - [x] 8.1 Implement PipelineMonitoringService
    - Create `src/services/pipeline_monitoring_service.py` with: `get_pipeline_status`, `get_run_metrics`, `list_runs`, `get_step_details`
    - `get_pipeline_status`: query pipeline_runs + pipeline_step_results for current execution status, docs processed/remaining, elapsed time
    - `get_run_metrics`: aggregate entity quality metrics, processing speed, error rates, cost estimate from pipeline_runs and pipeline_step_results
    - `get_step_details`: per-step metrics (parse: docs parsed, avg parse time; extract: entities extracted, type distribution, tokens, cost; embed: embeddings generated; graph_load: nodes/edges loaded; etc.), config values with origin annotations, recent runs, error log
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ]* 8.2 Write property test: Bedrock cost estimation is deterministic
    - **Property 14: Bedrock cost estimation is deterministic**
    - Generate random model_id, input_tokens, output_tokens; verify cost = input_tokens * input_rate + output_tokens * output_rate, deterministic
    - **Validates: Requirements 7.5**

  - [ ]* 8.3 Write unit tests for PipelineMonitoringService
    - Test step detail metrics computation for each step type
    - Test error rate calculation, docs_per_minute, avg_entities_per_doc
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 9. Checkpoint — Services complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. API Lambda handlers for pipeline config endpoints (Req 1-9)
  - [x] 10.1 Create pipeline config API Lambda handler
    - Create `src/lambdas/api/pipeline_config.py` with handlers for all 19 pipeline config endpoints:
      - GET/PUT `/case-files/{id}/pipeline-config` — get effective config, update config
      - GET `/case-files/{id}/pipeline-config/versions`, GET `/case-files/{id}/pipeline-config/versions/{v}` — list/get versions
      - POST `/case-files/{id}/pipeline-config/rollback` — rollback
      - POST `/case-files/{id}/pipeline-config/export`, POST `/case-files/{id}/pipeline-config/import` — export/import
      - POST `/case-files/{id}/pipeline-config/template` — apply template
      - POST/GET `/case-files/{id}/sample-runs`, GET `/case-files/{id}/sample-runs/{run_id}`, POST `/case-files/{id}/sample-runs/compare`
      - GET `/case-files/{id}/pipeline-runs`, GET `/case-files/{id}/pipeline-runs/{run_id}`, GET `/case-files/{id}/pipeline-runs/{run_id}/steps/{step}`
      - GET/PUT `/system/default-config`, POST `/system/default-config/export`, POST `/system/default-config/import`
    - Each handler delegates to the appropriate service (PipelineConfigService, SampleRunService, PipelineMonitoringService, ConfigResolutionService)
    - Return structured error responses for validation failures (HTTP 400), not found (HTTP 404), server errors (HTTP 500/503)
    - _Requirements: 1.1, 1.2, 2.5, 3.4, 3.5, 5.1, 5.3, 7.1, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 10.2 Update API Gateway definition
    - Add all new routes to `infra/api_gateway/api_definition.yaml` for pipeline config, sample runs, pipeline runs, system default config endpoints
    - _Requirements: 2.5, 3.4, 3.5, 9.1, 9.2, 9.4, 9.5_

  - [ ]* 10.3 Write unit tests for pipeline config API handlers
    - Test correct HTTP status codes, request validation, CORS headers
    - Test error response structure for validation failures
    - _Requirements: 8.6, 2.5, 3.4_

- [x] 11. Rekognition pipeline step (Req 13)
  - [x] 11.1 Implement Rekognition handler Lambda
    - Create `src/lambdas/ingestion/rekognition_handler.py` with `RekognitionHandler` class
    - `handler`: check if rekognition enabled in effective_config, list media files (JPEG, PNG, TIFF, MP4, MOV) from case S3 prefix, process each
    - `_process_image`: call Rekognition detect_faces, detect_labels, detect_text; filter by min_face_confidence and min_object_confidence
    - `_process_video`: start async video analysis jobs (start_label_detection, start_face_detection), poll for completion with segment support
    - `_results_to_entities`: convert Rekognition detections to entity format for graph loader — create person entities for face matches, object entities for significant detections (weapons, drugs, vehicles, currency, electronics)
    - Support importing pre-processed Rekognition JSON from `s3://bucket/cases/{case_id}/rekognition-output/`
    - Store Rekognition results as JSON artifacts in S3, index detected text and labels in OpenSearch
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10, 13.11_

  - [x] 11.2 Add Rekognition step to Step Functions pipeline
    - Update `infra/step_functions/ingestion_pipeline.json` to add Rekognition Choice + Task step after Parse, before Extract
    - Choice state checks `$.effective_config.rekognition.enabled`; if true → RekognitionStep, if false → skip to Extract
    - _Requirements: 13.1_

  - [x] 11.3 Add Rekognition config validation to ConfigValidationService
    - Add `_validate_rekognition` method to `src/services/config_validation_service.py`
    - Validate: min_face_confidence in [0.0, 1.0], min_object_confidence in [0.0, 1.0], video_segment_length_seconds > 0
    - _Requirements: 13.8, 13.11_

  - [ ]* 11.4 Write unit tests for Rekognition handler
    - Test image processing with mock Rekognition responses
    - Test video processing with async job polling
    - Test entity conversion from Rekognition results
    - Test skip behavior when rekognition disabled
    - Test import of pre-processed Rekognition JSON
    - _Requirements: 13.1, 13.2, 13.4, 13.5, 13.10_

- [x] 12. Checkpoint — Backend services and Lambdas complete
  - Ensure all tests pass, ask the user if questions arise.


- [x] 13. Investigative chatbot backend (Req 14)
  - [x] 13.1 Implement Chat Lambda handler
    - Create `src/lambdas/api/chat.py` with `ChatHandler` class
    - `handle`: classify intent (question, command, comparison), retrieve context via RAG (OpenSearch search + Neptune graph query), build prompt with case context, invoke Bedrock, extract citations, log conversation to Aurora
    - Support investigative commands: summarize, who is, connections between, documents mention, flag, timeline, what's missing, subpoena list — route to specialized handlers
    - POST `/case-files/{id}/chat` — send message, get AI response with citations
    - GET `/case-files/{id}/chat/history` — get conversation history
    - POST `/case-files/{id}/chat/share` — share finding from chat
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.7, 14.8, 14.9, 14.10, 14.11, 14.12, 14.13_

  - [x] 13.2 Implement ChatService with RAG and graph integration
    - Create `src/services/chat_service.py` with: `_search_documents` (OpenSearch RAG retrieval), `_query_graph` (Neptune entity/path queries), `_build_prompt` (assemble system prompt + case context + retrieved context + conversation history), `_invoke_bedrock` (call Bedrock with case's configured LLM model), `_extract_citations` (link response claims to source documents)
    - Implement command handlers: `_handle_summarize`, `_handle_who_is`, `_handle_connections`, `_handle_documents_mention`, `_handle_flag`, `_handle_timeline`, `_handle_whats_missing`, `_handle_subpoena_list`
    - _Requirements: 14.3, 14.4, 14.5, 14.6, 14.8, 14.9, 14.10, 14.11_

  - [x] 13.3 Add chat API routes to API Gateway
    - Add POST `/case-files/{id}/chat`, GET `/case-files/{id}/chat/history`, POST `/case-files/{id}/chat/share` to `infra/api_gateway/api_definition.yaml`
    - _Requirements: 14.1_

  - [ ]* 13.4 Write unit tests for ChatService
    - Test intent classification for each command type
    - Test prompt building with case context and retrieved context
    - Test citation extraction from Bedrock responses
    - Test conversation history management
    - _Requirements: 14.3, 14.8, 14.9, 14.10_

- [x] 14. Pipeline Configuration Wizard backend (Req 15)
  - [x] 14.1 Implement WizardService
    - Create `src/services/wizard_service.py` with: `generate_config`, `estimate_cost`, `generate_summary`, `save_progress`, `load_progress`
    - `generate_config`: map wizard answers to Pipeline_Config — start with template based on investigation_type, adjust entity_types based on goals, set pdf_method based on file formats, enable rekognition if images/video, set search_tier based on volume, set graph_load strategy based on doc count
    - Include AI-assisted config generation via Bedrock for custom extraction prompts based on investigation type
    - Support quick mode (5 questions only) with intelligent defaults
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.6, 15.7, 15.8, 15.9, 15.10_

  - [x] 14.2 Create Wizard API Lambda handler
    - Create `src/lambdas/api/wizard.py` with handlers:
      - POST `/wizard/generate-config` — generate Pipeline_Config from answers
      - POST `/wizard/estimate-cost` — generate cost estimate
      - POST `/wizard/create-case` — create case with generated config
      - GET `/wizard/templates` — list available config templates
      - POST `/wizard/export-summary` — generate shareable HTML summary
      - POST `/wizard/save-progress` — save partial wizard state
      - GET `/wizard/load-progress/{id}` — load saved wizard state
    - Add routes to `infra/api_gateway/api_definition.yaml`
    - _Requirements: 15.1, 15.3, 15.5, 15.7, 15.9_

  - [ ]* 14.3 Write unit tests for WizardService
    - Test config generation for each investigation type
    - Test quick mode defaults
    - Test template mapping from investigation type
    - _Requirements: 15.3, 15.4, 15.6_

- [x] 15. AI-Powered Cost Estimation Service (Req 16)
  - [x] 15.1 Create AWS pricing data file
    - Create `config/aws_pricing.json` with externalized pricing for: Textract, Bedrock (Sonnet, Haiku, Nova Pro, Titan Embed), OpenSearch Serverless OCUs, Neptune Serverless NCUs, Aurora Serverless ACUs, Rekognition (images, face comparison, video), S3, Lambda, API Gateway
    - _Requirements: 16.8_

  - [x] 15.2 Implement CostEstimationService
    - Create `src/services/cost_estimation_service.py` with: `estimate`, `_compute_one_time`, `_compute_monthly`, `_suggest_optimizations`, `_compute_tiers`
    - `_compute_one_time`: Textract (pages × rate, only if scanned), Bedrock extraction (docs × chunks × model rate), Bedrock embeddings, Rekognition images/video, Lambda compute, S3 storage
    - `_compute_monthly`: OpenSearch OCUs (derived from volume + tier), Neptune NCUs (derived from entity/relationship estimates), Aurora ACUs, S3, API Gateway + Lambda
    - `_suggest_optimizations`: generate cost reduction recommendations (batch inference, PyPDF2 vs Textract, tier reduction, Haiku vs Sonnet)
    - `_compute_tiers`: Economy (Haiku, standard tier), Recommended (Sonnet, balanced), Premium (max quality)
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.8_

  - [ ]* 15.3 Write unit tests for CostEstimationService
    - Test one-time cost computation with known inputs
    - Test monthly cost computation
    - Test tier generation (economy, recommended, premium)
    - Test optimization recommendations
    - _Requirements: 16.2, 16.3, 16.4, 16.5_

- [x] 16. Case Assessment Service (Req 17)
  - [x] 16.1 Implement CaseAssessmentService
    - Create `src/services/case_assessment_service.py` with: `get_assessment`, `generate_brief`, `_compute_strength_score`, `_identify_critical_leads`, `_generate_resource_recommendations`
    - `_compute_strength_score`: deterministic 0-100 from evidence volume (20), entity density (20), relationship density (20), document corroboration (20), cross-case connections (20)
    - `_identify_critical_leads`: query Neptune for high-connectivity entities with low document coverage
    - `_generate_resource_recommendations`: use Bedrock to generate actionable bullet points from case data
    - Evidence coverage checklist: query Neptune for entity type counts vs expected types for case category
    - Key subjects: top 10 persons by degree centrality in Neptune
    - Case timeline: date entities sorted chronologically with document density per period
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.10_

  - [x] 16.2 Create Assessment API Lambda handler
    - Create `src/lambdas/api/assessment.py` with handlers:
      - GET `/case-files/{id}/assessment` — get case assessment dashboard data
      - POST `/case-files/{id}/assessment/brief` — generate AI case brief
    - Add routes to `infra/api_gateway/api_definition.yaml`
    - _Requirements: 17.1, 17.8_

  - [ ]* 16.3 Write unit tests for CaseAssessmentService
    - Test strength score computation with known metrics
    - Test evidence coverage checklist generation
    - _Requirements: 17.2, 17.3, 17.10_

- [x] 17. Portfolio Dashboard and Workbench backends (Req 18, 19)
  - [x] 17.1 Implement PortfolioService
    - Create `src/services/portfolio_service.py` with: `get_summary`, `list_cases` (filtered, sorted, paginated), `set_priority`, `assign_case`, `bulk_action`, `get_analytics`, `get_attention_cases`
    - `get_summary`: aggregate stats — total active, by status, total docs, total entities, cases requiring attention
    - `get_attention_cases`: cases with no activity 30+ days, pipeline errors, low strength + high docs, cross-case matches uninvestigated
    - `get_analytics`: cases opened/closed over time, avg duration, processing throughput, cost per case, strength distribution
    - Support grouping by status, priority, category, assigned team, age, evidence strength
    - Support sorting by name, creation date, last activity, doc count, entity count, strength score, priority
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8, 18.9, 18.10, 18.11_

  - [x] 17.2 Implement WorkbenchService
    - Create `src/services/workbench_service.py` with: `get_my_cases`, `get_daily_priorities`, `get_activity_feed`, `get_findings`, `add_finding`, `get_metrics`
    - `get_my_cases`: cases where assigned_to matches user, grouped into swim lanes (needs action, active, awaiting, review & close)
    - `get_daily_priorities`: AI-generated via Bedrock based on recent evidence additions, pending leads, deadlines, cross-case matches
    - `get_activity_feed`: recent searches, entity views, findings from investigator_activity table
    - `get_findings`: all investigator notes/findings across cases from investigator_findings table
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

  - [x] 17.3 Create Portfolio and Workbench API Lambda handlers
    - Create `src/lambdas/api/portfolio.py` with handlers for: GET `/portfolio/summary`, GET `/portfolio/cases`, PUT `/portfolio/cases/{id}/priority`, PUT `/portfolio/cases/{id}/assign`, POST `/portfolio/bulk-action`, GET `/portfolio/analytics`, GET `/portfolio/attention`
    - Create `src/lambdas/api/workbench.py` with handlers for: GET `/workbench/my-cases`, GET `/workbench/priorities`, GET `/workbench/activity`, GET/POST `/workbench/findings`, GET `/workbench/metrics`
    - Add all routes to `infra/api_gateway/api_definition.yaml`
    - _Requirements: 18.1, 18.8, 18.11, 19.1, 19.4, 19.5, 19.6_

  - [ ]* 17.4 Write unit tests for PortfolioService and WorkbenchService
    - Test case filtering, sorting, grouping logic
    - Test attention case detection rules
    - Test swim lane assignment logic
    - _Requirements: 18.3, 18.5, 18.6, 18.7, 19.3_

- [x] 18. Checkpoint — All backend services and APIs complete
  - Ensure all tests pass, ask the user if questions arise.


- [x] 19. Visual Config Editor frontend (Req 6)
  - [x] 19.1 Implement pipeline flow diagram and config editor tab in investigator.html
    - Add "Pipeline Config" tab to `src/frontend/investigator.html`
    - Render pipeline flow diagram: 5 step cards (Parse → Extract → Embed → Graph Load → Store Artifact) connected by arrows, each showing step name and status
    - Click step card → slide-out panel with form fields for that step's parameters, populated from Effective_Config API response
    - Each field shows "inherited" badge (gray) or "overridden" badge (blue) based on `origins` dict
    - "Reset to Default" button per field and per section — removes case override for that field
    - JSON editor toggle with syntax highlighting (textarea with basic highlighting)
    - Template selector dropdown (antitrust, criminal, financial_fraud) — calls apply_template API
    - Save button → PUT `/pipeline-config`, show confirmation toast with new version number
    - Version history panel — list versions with rollback button per version
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 19.2 Write unit tests for config editor API client functions
    - Test API client functions for get/update config, list versions, rollback, apply template
    - _Requirements: 6.2, 6.7_

- [x] 20. Pipeline Monitoring Dashboard frontend (Req 7, 11, 12)
  - [x] 20.1 Implement monitoring dashboard tab in investigator.html
    - Add "Pipeline Monitor" tab to `src/frontend/investigator.html`
    - Pipeline step cards row: Upload → Parse → Extract → Embed → Vector Index → Knowledge Graph → RAG KB
    - Each card shows: step name, AWS service, status indicator (idle/running/completed/error), "Click for status" link
    - Click card → detail overlay with: service status + item count stat, key metrics as large stat cards (item count, dimensions, latency, cost), Configuration & Settings section showing Effective_Config values with inherited/overridden indicators, recent processing history (last 5 runs), error log (last 10 errors)
    - Step-specific metrics per design: Parse (docs parsed, avg parse time, OCR count), Extract (entities, type distribution, confidence, tokens, cost), Embed (embeddings, dimensions, avg time), Vector Index (vectors, index size, query latency), Graph Load (nodes, edges, strategy, duration), RAG KB (sync status, doc count, last sync)
    - "Edit Configuration" button in overlay → opens Config Editor pre-focused on that step
    - Real-time polling every 10 seconds when pipeline is running — update step card status indicators
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [x] 21. Sample-and-Compare UI frontend (Req 5, 12)
  - [x] 21.1 Implement sample run and comparison UI in investigator.html
    - Add "Sample & Compare" section within the Pipeline Config tab
    - Document selector: multi-select from case documents (max 50), "Run Sample" button
    - Progress indicator during sample run execution
    - Results panel: entity list grouped by type with confidence bars, relationship count, Pipeline Quality Score (0-100) with breakdown chart (confidence_avg, type_diversity, relationship_density, noise_ratio_score)
    - Compare mode: select two sample runs → side-by-side snapshots with diff highlighting (added=green, removed=red, changed=yellow)
    - Quality score delta display: per-metric improvement/regression indicators
    - Link to view resulting graph in Knowledge Graph section (Req 12.2)
    - Test search query input for vector index results (Req 12.3)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 22. Investigative Chatbot frontend (Req 14)
  - [x] 22.1 Implement chatbot panel in investigator.html
    - Add collapsible chatbot panel on right side of `src/frontend/investigator.html`, accessible from any tab
    - Chat message list with user/AI message bubbles, markdown rendering for AI responses
    - Input box with send button, support for multi-turn conversation
    - Citation links in AI responses that open document drill-down when clicked
    - "Share Finding" button per AI response — calls POST `/chat/share` to save as case finding
    - Context indicator showing current entity/graph filter being used as chat context
    - Support document drag-and-drop/upload into chat for inline analysis (Req 14.5)
    - Maintain conversation history for session duration, send conversation_id with each message
    - _Requirements: 14.1, 14.5, 14.6, 14.7, 14.9, 14.10, 14.13_

- [x] 23. Pipeline Configuration Wizard frontend (Req 15, 16)
  - [x] 23.1 Implement wizard multi-step form in investigator.html
    - Add "New Case Setup" wizard accessible from investigator.html (button in case list or dedicated tab)
    - 6-section guided questionnaire: Data Profile, Investigation Type, Visual Evidence, Search & Analysis, Environment & Compliance, Integration
    - Each section as a step with next/back navigation and progress indicator
    - Quick mode toggle — shows only 5 critical questions (volume, doc count, formats, investigation type, region)
    - "AI Assist" button — sends investigation type + description to Bedrock, populates suggested entity types and prompt customizations
    - Save progress button — persists partial wizard state for later completion
    - _Requirements: 15.1, 15.2, 15.6, 15.7, 15.8, 15.10_

  - [x] 23.2 Implement wizard results and cost estimation display
    - On wizard completion: call POST `/wizard/generate-config` and POST `/wizard/estimate-cost`
    - Display generated Pipeline_Config as visual pipeline flow diagram showing enabled/disabled steps
    - Display cost estimate as visual table: service icons, per-service costs, one-time subtotal, monthly subtotal, grand total
    - Display three tiers (Economy, Recommended, Premium) with different model/tier selections
    - Display "Cost vs Quality" scatter chart showing cost/quality trade-offs for different configurations
    - Display optimization recommendations as actionable cards
    - "Accept & Create Case" button → POST `/wizard/create-case`
    - "Export Summary" button → POST `/wizard/export-summary` → download shareable HTML document
    - _Requirements: 15.3, 15.5, 15.9, 15.10, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.9_

- [x] 24. Case Assessment Dashboard frontend (Req 17)
  - [x] 24.1 Implement case assessment dashboard in investigator.html
    - Display as first section when investigator selects a case, above the search bar
    - Case Strength Score: visual gauge (0-100) with color coding (red 0-30, yellow 31-60, green 61-100)
    - Evidence Coverage checklist: people, organizations, financial connections, communication patterns, physical evidence, timeline, geographic scope — each with count + status indicator
    - Key Subjects section: top 10 persons by connection density, with entity type icons, connection count, document reference count
    - Critical Leads section: AI-identified high-connectivity entities with low document coverage
    - Resource Recommendations: AI-generated actionable bullet points
    - Case Timeline: chronological events from date entities with evidence density per period
    - "Generate Case Brief" button → POST `/assessment/brief` → display/download comprehensive AI summary
    - Auto-refresh when new documents ingested or pipeline runs complete
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.10_

- [x] 25. Case Portfolio Dashboard frontend (Req 18)
  - [x] 25.1 Implement portfolio dashboard tab in investigator.html
    - Add "Portfolio" tab visible for manager role or when case count > 20
    - Summary bar: active cases, by status, total docs, total entities, cases requiring attention
    - Filter controls: status, priority, category, team, date range, search tier, min strength score
    - Group by controls: status, priority, category, assigned team, age, evidence strength
    - Sort by controls: name, creation date, last activity, doc count, entity count, strength score, priority
    - Case cards: name, status badge, priority indicator, doc count, entity count, strength score, assigned investigator, days since last activity, mini pipeline progress bar
    - Click card → navigate to case assessment dashboard
    - "Cases Requiring Attention" section: stalled (30+ days), pipeline errors, low strength + high docs, cross-case matches uninvestigated
    - Resource allocation view: investigator workload, case distribution by team, drag-and-drop reassignment
    - Portfolio analytics: cases over time chart, strength distribution chart, avg duration, throughput, cost per case
    - Bulk actions: assign priority, reassign, archive, export CSV
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8, 18.9, 18.10, 18.11_

- [x] 26. Investigator Workbench frontend (Req 19)
  - [x] 26.1 Implement workbench tab in investigator.html
    - Add "My Workbench" tab showing only cases assigned to current user
    - "Today's Priority" section: AI-generated recommendations from GET `/workbench/priorities`
    - Swim lanes: Needs Immediate Action, Active Investigation, Awaiting Response, Review & Close — populated from GET `/workbench/my-cases`
    - Quick-action buttons per case: "Continue Investigation", "Add Finding", "Request Resources", "Recommend Closure"
    - Recent Activity feed: searches, entity views, findings from GET `/workbench/activity`
    - "My Findings" section: searchable/filterable list of all notes and findings across cases from GET `/workbench/findings`
    - Add Finding form: finding type (note, suspicious, lead, evidence_gap, recommendation), title, content, entity/document refs
    - Workload metrics: total assigned, cases worked this week, avg time per case, productivity trend
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

- [x] 27. Checkpoint — All frontend components complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 28. CDK infrastructure updates
  - [x] 28.1 Update CDK stack for new Lambdas and resources
    - Update `infra/cdk/stacks/research_analyst_stack.py` to add:
      - Lambda functions: resolve_config_handler, pipeline_config API, chat API, wizard API, assessment API, portfolio API, workbench API, rekognition_handler
      - IAM permissions: Rekognition (detect_faces, detect_labels, detect_text, start_label_detection, start_face_detection, get_label_detection, get_face_detection), Bedrock invoke_model for chat service
      - API Gateway routes for all new endpoints
      - Aurora schema migration execution (or document manual migration step)
    - Ensure all resources are GovCloud compatible — no services outside existing stack (Aurora, Neptune, OpenSearch, Step Functions, Lambda, S3, Bedrock, API Gateway, Rekognition)
    - _Requirements: 10.4, 13.1_

  - [ ]* 28.2 Write unit tests for CDK stack additions
    - Test that new Lambda functions are created with correct handlers and permissions
    - Test API Gateway routes are properly configured
    - _Requirements: 10.4_

- [x] 29. Integration wiring and end-to-end validation
  - [x] 29.1 Wire all services together and verify end-to-end flows
    - Verify config resolution → pipeline execution → step config reading flow works end-to-end
    - Verify sample run → snapshot → comparison flow
    - Verify config editor → save → version creation → rollback flow
    - Verify wizard → generate config → create case → pipeline execution flow
    - Verify chatbot → RAG search → graph query → Bedrock response flow
    - Verify portfolio → case card → assessment dashboard navigation
    - Verify workbench → findings → activity feed flow
    - Ensure all API endpoints are properly routed and return expected responses
    - _Requirements: 4.6, 5.1, 5.3, 6.7, 14.3, 15.9, 18.10, 19.1_

  - [ ]* 29.2 Write integration tests for critical flows
    - Test config resolution end-to-end: create system default, create case override, resolve effective config, verify merge
    - Test sample run workflow: create config, run sample, verify snapshot, modify config, run again, compare
    - Test pipeline execution with custom config: verify each step received correct parameters
    - _Requirements: 2.1, 2.2, 4.6, 5.1, 5.3_

- [ ] 30. S3 Document Evidence Viewer (Req 20)
  - [x] 30.1 Add document download API endpoint to case_files Lambda
    - Add `GET /case-files/{id}/documents/{docId}/download` handler to `src/lambdas/api/case_files.py`
    - Look up document's `source_filename` and `s3_key` from Aurora `documents` table
    - Generate pre-signed S3 URL with 15-minute expiry via `s3.generate_presigned_url`
    - Fall back to convention `cases/{case_id}/raw/{filename}` if s3_key not stored
    - Return `{download_url, filename, s3_key, expires_in}` response
    - **ALREADY IMPLEMENTED** — deployed to Lambda
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.8_

  - [x] 30.2 Add "View Original Document" button to Level 4 drill-down in investigator.html
    - Add "📥 View Original Document from S3" button in `renderL4` function above document content
    - `_openOriginalDoc(docId)` calls the download API and opens pre-signed URL in new tab
    - Display filename and file type indicator
    - Show error alert if document not found
    - **ALREADY IMPLEMENTED** — in investigator.html
    - _Requirements: 20.1, 20.5, 20.6, 20.7_

  - [ ] 30.3 Add API Gateway route for document download endpoint
    - Add `GET /case-files/{id}/documents/{docId}/download` route to `infra/api_gateway/api_definition.yaml`
    - Configure CORS OPTIONS handler for the new route
    - **ALREADY DEPLOYED** — route added via scripts/add_doc_download_route.py
    - _Requirements: 20.2_

- [ ] 31. Phased Video Processing Mode (Req 21)
  - [ ] 31.1 Update Rekognition handler with video_processing_mode logic
    - Update `src/lambdas/ingestion/rekognition_handler.py` handler to check `config.get("video_processing_mode", "skip")` and route video processing accordingly
    - Add `_process_video_faces_only` function that runs only face detection (no labels)
    - Add `_get_flagged_videos` function that queries Aurora for documents flagged for video analysis
    - Skip all video files when mode is "skip" (default)
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

  - [ ] 31.2 Update config validation and Pydantic models for video_processing_mode
    - Add `video_processing_mode` to `RekognitionConfig` in `src/models/pipeline_config.py` with default "skip"
    - Add validation in `ConfigValidationService._validate_rekognition` for valid values: {"skip", "faces_only", "targeted", "full"}
    - _Requirements: 21.1, 21.8_

  - [ ] 31.3 Update wizard and cost estimation for video processing modes
    - Add "Video Processing Priority" question to wizard questionnaire mapping in `src/services/wizard_service.py`
    - Update `src/services/cost_estimation_service.py` to compute video costs separately per mode
    - _Requirements: 21.6, 21.7_

- [ ] 32. One-Click Deployment Package Generator (Req 22)
  - [ ] 32.1 Create DeploymentGenerator service
    - Create `src/services/deployment_generator.py` with `generate_bundle`, `_render_cfn_template`, `_package_lambda_code`, `_generate_deployment_guide`, `_create_init_lambda_code`
    - The CFN template renders from a base template at `infra/cfn/base_template.yaml` with string substitution for wizard answers (service sizing, Pipeline_Config defaults, enabled/disabled services)
    - Package `src/` directory into `lambda-code.zip`
    - Generate `DEPLOYMENT_GUIDE.md` with step-by-step instructions
    - Upload bundle to S3, return pre-signed download URL
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7_

  - [ ] 32.2 Create base CloudFormation template
    - Create `infra/cfn/base_template.yaml` — parameterized CloudFormation template with all resources: VPC, Aurora, Neptune, OpenSearch, Lambda functions, Step Functions, API Gateway, S3, CloudFront, IAM roles, CloudWatch alarms, SNS, custom resource for schema init + frontend injection
    - Template accepts 5 parameters: EnvironmentName, AdminEmail, VpcCidr, DeploymentBucketName, LambdaCodeKey
    - Outputs: InvestigatorURL, ApiGatewayURL, S3DataBucket, AuroraEndpoint, NeptuneEndpoint
    - Include schema init custom resource Lambda inline
    - _Requirements: 22.2, 22.3, 22.4, 22.6, 22.7, 22.10_

  - [ ] 32.3 Create deployment package API endpoint
    - Add `POST /wizard/generate-deployment` handler to `src/lambdas/api/wizard.py`
    - Add route to `infra/api_gateway/api_definition.yaml`
    - _Requirements: 22.1, 22.9_

  - [ ] 32.4 Add CDK app download option
    - Add `POST /wizard/download-cdk` handler that packages `infra/cdk/` with generated Pipeline_Config
    - _Requirements: 22.8_

- [x] 34. AI-Powered Document Classification and Case Routing (Req 23)
  - [x] 34.1 Create Pydantic models for classification config and results
    - Add `ClassificationConfig`, `ClassificationResult`, `RoutingOutcome`, `TriageQueueItem` to `src/models/pipeline_config.py`
    - `ClassificationConfig`: routing_mode (default "folder_based"), case_number_pattern, ai_model_id, confidence_threshold (0.8), max_preview_chars (5000), classify_sample_size (100)
    - `ClassificationResult`: document_id, matched_case_id, case_number, case_category, confidence, routing_reason, routing_mode
    - `RoutingOutcome`: action ("assigned"/"triage"/"skipped"), case_id, triage_reason
    - `TriageQueueItem`: triage_id, document_id, filename, classification_result, suggested_case_id, confidence, status, assigned_case_id, assigned_by, created_at
    - _Requirements: 23.1, 23.2, 23.4, 23.5, 23.6_

  - [x] 34.2 Create DocumentClassificationService
    - Create `src/services/document_classification_service.py` with `classify`, `route_document`, `get_triage_queue`, `assign_from_triage`, `create_case_from_triage`
    - `_classify_folder_based`: extract case from S3 folder structure
    - `_classify_metadata`: apply `case_number_pattern` regex to filename → PDF metadata → first page text (first match wins)
    - `_classify_ai`: truncate text to `max_preview_chars`, fetch existing cases from Aurora, call Bedrock Haiku, parse response into ClassificationResult
    - `route_document`: if matched_case_id and confidence > threshold → assign to case; else → add to triage_queue
    - `get_triage_queue`: list pending triage items with pagination
    - `assign_from_triage`: update triage item status, associate document with case
    - `create_case_from_triage`: create new case_files row, assign document, update triage status
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6_

  - [x] 34.3 Create Classification Lambda handler
    - Create `src/lambdas/ingestion/classification_handler.py` with `handler(event, context)`
    - Read `effective_config.classification` from event payload
    - If routing_mode is "folder_based", return skipped result immediately
    - Otherwise, instantiate DocumentClassificationService, call classify + route_document
    - Return classification_result dict with action, case_id, confidence, case_category, routing_reason
    - _Requirements: 23.1, 23.2_

  - [x] 34.4 Update Step Functions ASL with classification step
    - Modify `infra/step_functions/ingestion_pipeline.json` to insert `ClassifyDocument` state between `ParseDocument` and `ExtractEntities` in the per-document Map iterator
    - Change `ParseDocument.Next` from `"ExtractEntities"` to `"ClassifyDocument"`
    - `ClassifyDocument` passes case_id, document_id, parse_result, effective_config to the classification Lambda
    - Add standard retry (3 attempts, exponential backoff) and catch → LogDocumentFailure
    - _Requirements: 23.1_

  - [x] 34.5 Update config validation for classification section
    - Add `"classification"` to `_VALID_SECTIONS` in `src/services/config_validation_service.py`
    - Add `_CLASSIFICATION_KEYS` set and `_validate_classification` method
    - Validate routing_mode ∈ {"folder_based", "metadata_routing", "ai_classification"}
    - Validate confidence_threshold in [0.0, 1.0]
    - Validate case_number_pattern is a valid regex (compile test)
    - Validate max_preview_chars in [100, 50000], classify_sample_size in [1, 10000]
    - _Requirements: 23.2, 23.3_

  - [x] 34.6 Create triage_queue Aurora table and API endpoints
    - Add `triage_queue` table DDL (triage_id, document_id, filename, s3_key, classification_json, suggested_case_id, confidence, status, assigned_case_id, assigned_by, assigned_at, created_at)
    - Add `GET /triage-queue`, `POST /triage-queue/{docId}/assign`, `POST /triage-queue/{docId}/create-case` handlers to `src/lambdas/api/pipeline_config.py`
    - Add routes to `infra/api_gateway/api_definition.yaml`
    - _Requirements: 23.6_

  - [x] 34.7 Update wizard with Document Organization question
    - Add "Document Organization" question mapping in `src/services/wizard_service.py` `generate_config`
    - Map: pre_organized → folder_based, has_case_numbers → metadata_routing, mixed_unorganized → ai_classification, unknown → ai_classification with classify_sample_size=100
    - When metadata_routing selected, include `case_number_pattern` from answers
    - _Requirements: 23.8, 23.9_

  - [x] 34.8 Update cost estimation with classification costs
    - Add classification cost computation to `src/services/cost_estimation_service.py` `_compute_one_time`
    - Only compute when routing_mode is "ai_classification"
    - Formula: ~2500 input tokens + ~100 output tokens per doc at Haiku pricing
    - Show as separate "classification" line item
    - _Requirements: 23.10_

  - [x] 34.9 Add triage queue UI to investigator.html
    - Add "Triage Queue" section accessible from pipeline monitoring area in `src/frontend/investigator.html`
    - Show pending count badge, list of unclassified documents with filename, suggested case, confidence, routing reason
    - "Assign to Case" dropdown, "Create New Case" button, "View Document" link per item
    - Filter by confidence, date, suggested case
    - _Requirements: 23.6, 23.7_

  - [ ] 34.10 *Unit tests for classification service and config validation
    - Create `tests/unit/test_document_classification_service.py`
    - Test metadata regex extraction with various patterns and document sources
    - Test routing decision at confidence boundary (exactly 0.8)
    - Test triage queue CRUD operations
    - Test config validation accepts valid classification configs and rejects invalid ones
    - Test wizard mapping for all 4 document_organization options
    - Test cost estimation formula for ai_classification mode
    - Property tests for Properties 21-26 using hypothesis (min 100 iterations each)
    - _Requirements: 23.2, 23.3, 23.4, 23.5, 23.6, 23.8, 23.9, 23.10_

- [x] 33. Final checkpoint — Full feature complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical boundaries
- Property tests validate universal correctness properties from the design document (Properties 1-26)
- Unit tests validate specific examples and edge cases
- All code is Python for backend (Lambda/services) and HTML/JS for frontend (investigator.html)
- The design uses Python throughout — no pseudocode language selection needed
- GovCloud compatibility is maintained: no AWS services outside the existing stack + Rekognition


- [x] 35. Interactive Timeline Analysis View (Req 25)
  - [x] 35.1 Implement Timeline tab frontend in investigator.html
    - Add "Timeline" tab with vis.js Timeline component, density bar, entity/type filters, event detail panel, AI analysis button
    - Query `/patterns` API with `{graph: true}` to get date entities and connections
    - Color-code events by entity type, detect temporal clusters and gaps
    - Click event → show connected entities and source documents
    - "AI Analysis" button → send timeline data to chat API for Bedrock narrative
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9, 25.10_

- [x] 36. Automated Report Generation (Req 26)
  - [x] 36.1 Create ReportGenerationService backend
    - Created `src/services/report_generation_service.py` with 5 report types (case_summary, prosecution_memo, entity_dossier, evidence_inventory, subpoena_list)
    - Bedrock prompt templates with citation format, case data gathering, report storage in Aurora
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5, 26.6, 26.7, 26.10_

  - [x] 36.2 Create Reports API Lambda handler
    - Create `src/lambdas/api/reports.py` with `POST /case-files/{id}/reports/generate` and `GET /case-files/{id}/reports`
    - Add routes to API Gateway definition
    - _Requirements: 26.1, 26.8, 26.9_

  - [x] 36.3 Add report generation UI to investigator.html
    - "Generate Report" button in case assessment dashboard
    - Report type selector dropdown, generation progress indicator
    - Report viewer with formatted HTML, print/export button
    - Previous reports list with date and type
    - _Requirements: 26.1, 26.2, 26.8_

- [x] 37. AI Hypothesis Testing (Req 27)
  - [x] 37.1 Create HypothesisTestingService backend
    - Created `src/services/hypothesis_testing_service.py` with decompose → evaluate → confidence scoring
    - Bedrock-powered claim decomposition and evidence classification
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.8_

  - [x] 37.2 Create Hypothesis API Lambda handler
    - Create `POST /case-files/{id}/hypothesis/evaluate` and `GET /case-files/{id}/hypotheses`
    - _Requirements: 27.1, 27.6_

  - [x] 37.3 Add hypothesis testing UI to investigator.html
    - "Test Hypothesis" input field in investigator interface
    - Evaluation dashboard with claim cards (SUPPORTED/CONTRADICTED/UNVERIFIED)
    - Overall confidence gauge, evidence gaps as investigative leads
    - Saved hypotheses list
    - _Requirements: 27.1, 27.4, 27.5, 27.6, 27.9_

- [x] 38. Geospatial Map View (Req 28)
  - [x] 38.1 Implement Map tab frontend in investigator.html
    - Added "Map" tab with Leaflet.js (CDN), dark CARTO tiles, location markers from Neptune
    - Person filter, marker popups with connected entities, geocoding lookup table
    - _Requirements: 28.1, 28.2, 28.3, 28.6, 28.8_

  - [ ] 38.2 Add travel pattern and heat map modes
    - Travel pattern: select person → show chronological movement with dated arrows
    - Heat map overlay showing geographic density
    - AI geographic analysis button
    - _Requirements: 28.4, 28.5, 28.7, 28.9, 28.10_

- [x] 39. Document Tagging and Annotation (Req 29)
  - [x] 39.1 Create AnnotationService backend
    - Create `src/services/annotation_service.py` with CRUD, evidence board aggregation, AI auto-tag
    - Aurora table: document_annotations
    - _Requirements: 29.1, 29.2, 29.3, 29.6, 29.9, 29.10_

  - [x] 39.2 Create Annotations API Lambda handler
    - `POST/GET /case-files/{id}/documents/{docId}/annotations`
    - `GET /case-files/{id}/evidence-board`
    - `POST /case-files/{id}/documents/{docId}/auto-tag`
    - _Requirements: 29.1, 29.5, 29.6, 29.10_

  - [x] 39.3 Add annotation UI to document viewer in investigator.html
    - Text selection → annotation creation dialog (tag, note, entity links)
    - Colored highlights rendered on document text
    - Annotations sidebar panel, evidence board view
    - AI auto-tag button
    - _Requirements: 29.1, 29.2, 29.4, 29.5, 29.6, 29.7, 29.10, 29.11_
