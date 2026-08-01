# Implementation Plan: Typology Subgraph Pipeline

## Overview

Pre-computed typology subgraph pipeline that replaces real-time Neptune graph traversal for large cases (100K+ entities). The system extracts typology-specific subgraphs asynchronously via Step Functions, scores them against prosecution patterns using OpenSearch k-NN and Bedrock, stores results in Aurora, and serves pre-computed data at page-load time with sub-second latency.

## Tasks

- [ ] 1. Database schema and migration
  - [ ] 1.1 Create Aurora migration for typology pipeline tables
    - Create `src/db/migrations/021_typology_subgraph_pipeline.sql`
    - Define tables: `typology_precomputed_results`, `typology_precomputed_summary`, `typology_summary_graph`, `pipeline_executions`
    - Add indexes: `idx_typology_results_case`, `idx_typology_results_stale`, `idx_pipeline_exec_case`
    - Include UNIQUE constraints for upsert semantics and pipeline locking
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 9.1, 10.1, 10.2_

  - [ ]* 1.2 Write unit tests for migration SQL validity
    - Validate that migration can be applied to a fresh database
    - Verify constraint behavior (unique, default values)
    - _Requirements: 4.2, 10.2_

- [ ] 2. Typology query definitions and shared utilities
  - [ ] 2.1 Create typology query configuration module
    - Create `src/services/typology_query_definitions.py`
    - Define `TYPOLOGY_QUERIES` dictionary with all 11 modules × 6 sub-categories
    - Each entry specifies: entity_types, relationship_filter, indicators, query_template (Gremlin)
    - Include entity-type-to-typology mapping (`TYPE_TO_TYPOLOGY`) for staleness detection
    - _Requirements: 2.1, 2.2, 7.3_

  - [ ] 2.2 Create pipeline shared utilities module
    - Create `src/services/typology_pipeline_utils.py`
    - Implement `get_case_entity_count(case_id)` — query Aurora for entity count
    - Implement `mark_stale_typologies(case_id, new_entity_types)` — set is_stale flags
    - Implement `get_stale_typologies(case_id)` — return list of stale typology_module_ids
    - Import DB connection from `src/db/connection.py`
    - _Requirements: 1.1, 7.1, 7.2, 7.3, 8.1_

  - [ ]* 2.3 Write unit tests for typology query definitions and utilities
    - Test TYPE_TO_TYPOLOGY mapping completeness (all entity types mapped)
    - Test mark_stale_typologies with mock DB
    - Test entity count threshold logic
    - _Requirements: 2.2, 7.3, 8.1_

- [ ] 3. Pipeline Lambda functions — Threshold and Lock
  - [ ] 3.1 Implement threshold_check Lambda
    - Create `src/lambdas/pipeline/threshold_check.py`
    - Query Aurora for case entity_count
    - Return `{ is_large_case, case_id, entity_count, typology_modules: [...] }`
    - Check staleness: if existing results have `is_stale=True`, include only affected modules (incremental mode)
    - If all typologies stale or no existing results, include all 11 modules (full mode)
    - _Requirements: 1.1, 7.2, 7.4, 8.1, 8.3, 8.4_

  - [ ] 3.2 Implement acquire_pipeline_lock Lambda
    - Create `src/lambdas/pipeline/acquire_lock.py`
    - INSERT into `pipeline_executions` with status='running', trigger_source from event
    - Use `ON CONFLICT DO NOTHING` + row-count check for lock semantics
    - Raise `LockConflict` exception if another execution is in progress for this case
    - _Requirements: 10.1, 10.2, 9.1_

  - [ ] 3.3 Implement release_pipeline_lock Lambda
    - Create `src/lambdas/pipeline/release_lock.py`
    - UPDATE `pipeline_executions` row: status='completed', completed_at=NOW()
    - Record per_typology_timing JSONB from state machine context
    - Handle failure case: status='failed' with error_message
    - _Requirements: 9.1, 10.1_

  - [ ]* 3.4 Write unit tests for threshold and lock Lambdas
    - Test threshold returns is_large_case=False for small cases
    - Test lock acquisition succeeds on first attempt
    - Test lock raises LockConflict when duplicate
    - Test release updates status correctly
    - _Requirements: 1.1, 10.1_

- [ ] 4. Checkpoint — Validate foundation layers
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Pipeline Lambda functions — Extraction and Scoring
  - [ ] 5.1 Implement extract_subgraph Lambda
    - Create `src/lambdas/pipeline/extract_subgraph.py`
    - Input: `{ case_id, typology_module_id, sub_categories: [...] }`
    - For each sub-category, build and execute targeted Gremlin query using `TYPOLOGY_QUERIES` config
    - Use Neptune HTTP API via existing `src/db/neptune.py` connection pattern
    - Apply 300s timeout per query; catch timeout and log, continue to next sub-category
    - Return: `{ typology_id, sub_categories: [{ id, entities: [...], edges: [...], entity_count }] }`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 5.2 Implement score_typology Lambda
    - Create `src/lambdas/pipeline/score_typology.py`
    - Input: extracted subgraph for one typology
    - Step 1: Run flag scoring using existing `SexTraffickingTypologyEngine._score_category()` pattern from `src/services/sex_trafficking_typology.py`
    - Step 2: Embed evidence summary via Titan Embed v2, query OpenSearch `typology-patterns` index with k-NN
    - Step 3: Classify match_strength (Strong ≥ 0.80, Moderate ≥ 0.60, Weak < 0.60)
    - Step 4: For Strong/Moderate, invoke Bedrock Claude Haiku for narrative synthesis (30s timeout)
    - Step 5: If Bedrock fails, store result with `synthesis_status='pending'`
    - Write results to `typology_precomputed_results` table (UPSERT on case_id + typology + sub_category)
    - Write aggregated score to `typology_precomputed_summary` table
    - Return: `{ typology_id, overall_score, sub_category_scores, match_strength, key_entities, narrative }`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.3, 4.4_

  - [ ]* 5.3 Write unit tests for extract and score Lambdas
    - Mock Neptune responses and verify subgraph extraction output format
    - Mock OpenSearch k-NN and verify score classification
    - Test Bedrock timeout handling (synthesis_status='pending')
    - _Requirements: 2.3, 3.2, 3.5_

- [ ] 6. Pipeline Lambda functions — Summary Graph
  - [ ] 6.1 Implement build_summary_graph Lambda
    - Create `src/lambdas/pipeline/build_summary_graph.py`
    - Read all typology results for the case from `typology_precomputed_results`
    - Identify Hub_Nodes: entities appearing in 2+ typology subgraphs
    - Limit to 30-50 hub nodes by ranking on cross-typology participation count
    - Query Neptune for direct edges between hub entities (bounded query)
    - Annotate each node with typology participation list and match_strength values
    - Store to `typology_summary_graph` table as vis.js-compatible JSON (nodes + edges)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 6.2 Write unit tests for summary graph construction
    - Test hub node selection logic (entities in 2+ typologies)
    - Test node limit enforcement (30-50 max)
    - Test vis.js JSON output format
    - _Requirements: 6.1, 6.2, 6.5_

- [ ] 7. OpenSearch typology-patterns index
  - [ ] 7.1 Create OpenSearch index definition and seed script
    - Create `src/db/seeds/typology_patterns_index.py`
    - Define index mapping with knn_vector field (dimension 1536, hnsw, cosinesimil)
    - Include fields: typology_module_id, sub_category_id, pattern_text, embedding, source, severity
    - Implement seed function to embed prosecution patterns from existing `TYPOLOGY_CATEGORIES` indicators
    - Use Titan Embed v2 to generate embeddings for each pattern description
    - Use existing `src/services/opensearch_serverless_backend.py` connection pattern
    - _Requirements: 3.1_

  - [ ]* 7.2 Write unit test for index creation and seeding
    - Verify index mapping structure matches k-NN requirements
    - Test pattern embedding generation with mock Bedrock
    - _Requirements: 3.1_

- [ ] 8. Checkpoint — Validate all Lambda functions
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Step Functions state machine and EventBridge trigger
  - [ ] 9.1 Create Step Functions state machine definition
    - Create `infra/step_functions/typology_subgraph_pipeline.json`
    - Define states: ThresholdCheck → IsLargeCase → AcquireLock → ExtractSubgraphs (Map, maxConcurrency=3) → ScoreTypologies (Map, maxConcurrency=3) → BuildSummaryGraph → ReleaseLock → PipelineComplete
    - Add Choice state for small case skip
    - Add Catch on AcquireLock for LockConflict → PipelineAlreadyRunning (Succeed)
    - Add error handling: on any state failure → ReleaseLock with status='failed'
    - _Requirements: 1.1, 1.2, 2.5, 10.1_

  - [ ] 9.2 Create EventBridge rule for pipeline trigger
    - Add EventBridge rule definition to CDK or CloudFormation
    - Pattern: match `ingestion.complete` event source
    - Target: Step Functions state machine with case_id from event detail
    - Ensure rule triggers within 60 seconds of ingestion completion
    - _Requirements: 1.1, 1.3_

  - [ ] 9.3 Add CDK constructs for pipeline infrastructure
    - Create `infra/cdk/stacks/typology_pipeline_stack.py` (or add to existing stack)
    - Define 6 Lambda functions with appropriate IAM roles (Neptune read, Aurora read/write, OpenSearch read, Bedrock invoke)
    - Define Step Functions state machine resource
    - Define EventBridge rule resource
    - Set Lambda timeout to 300s for extraction/scoring, 60s for threshold/lock/release
    - Set memory to 1024MB for extraction and scoring Lambdas
    - _Requirements: 1.1, 1.2, 2.3_

- [ ] 10. API endpoint — Serve pre-computed results
  - [ ] 10.1 Implement GET /case-files/{id}/typology-precomputed endpoint
    - Create `src/lambdas/api/typology_precomputed.py`
    - Query `typology_precomputed_summary` for all typology scores for the case (single query)
    - Query `typology_summary_graph` for the summary graph
    - Return `{ precomputed: bool, typologies: [...], summary_graph: {...}, any_stale: bool }`
    - Return `{ precomputed: false, reason: "no_results" }` if no data exists
    - Ensure response time < 500ms (simple Aurora SELECT queries)
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 10.2 Modify GET /case-files/{id}/investigator-analysis for pre-computed path
    - Edit `src/lambdas/api/investigator_analysis.py`
    - Before existing command center compute, check entity_count against threshold
    - If above threshold and pre-computed data exists, build response from Aurora (no Neptune/Bedrock)
    - If above threshold but no pre-computed data, fall through to existing time-budgeted logic
    - Add `any_stale` indicator in response when serving pre-computed data
    - _Requirements: 5.1, 5.3, 8.2, 8.3_

  - [ ] 10.3 Implement pipeline health status endpoint
    - Add health check logic to `src/lambdas/api/pipeline_status.py` (existing file)
    - Return last execution time, status, current step for a given case_id
    - Report `in_progress` with step identifier when pipeline is running
    - _Requirements: 9.3, 9.4_

  - [ ] 10.4 Add API Gateway route definitions
    - Update `infra/api_gateway/api_definition.yaml` with new route: `GET /case-files/{id}/typology-precomputed`
    - Wire to Lambda integration
    - _Requirements: 5.1_

  - [ ]* 10.5 Write unit tests for API endpoints
    - Test precomputed endpoint returns correct format with mock data
    - Test investigator-analysis pre-computed path branching
    - Test health status reports in_progress during execution
    - _Requirements: 5.2, 5.3, 9.3, 9.4_

- [ ] 11. Frontend changes — Pre-computed data rendering
  - [ ] 11.1 Modify typology-lens.js to try pre-computed first
    - Edit `src/frontend/typology-lens.js`
    - In the data loading function, call `GET /case-files/{id}/typology-precomputed` first
    - If `precomputed: true`, call `_renderPrecomputedTypology()` and return
    - If `precomputed: false`, fall through to existing live computation path
    - Display staleness indicator when `any_stale: true` (yellow badge or banner)
    - _Requirements: 5.1, 5.4, 8.1, 8.2_

  - [ ] 11.2 Implement pre-computed typology rendering function
    - Add `_renderPrecomputedTypology(data)` to `src/frontend/typology-lens.js`
    - Render typology cards with scores, match_strength badges, key entities, and narratives
    - Match existing UI patterns from live rendering (reuse card/panel structure)
    - _Requirements: 5.1, 5.2_

  - [ ] 11.3 Implement Summary Graph panel in Command Center
    - Add `renderSummaryGraph(graphData)` function to `src/frontend/typology-lens.js`
    - Use vis.js (already loaded) to render hub nodes and edges
    - Color nodes by dominant typology match_strength
    - Size nodes by number of typologies they participate in
    - Edge labels show relationship type and typology source
    - _Requirements: 6.4, 6.5_

- [ ] 12. Incremental staleness marking integration
  - [ ] 12.1 Add staleness marking hook to ingestion pipeline
    - Edit `src/services/ingestion_service_v2.py` (or the appropriate ingestion completion handler)
    - After successful ingestion, call `mark_stale_typologies(case_id, new_entity_types)`
    - Determine affected entity types from the newly ingested documents
    - If case crosses the entity threshold due to new ingestion, emit event for full pipeline trigger
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.4_

  - [ ]* 12.2 Write unit tests for staleness integration
    - Test that ingestion marks correct typologies as stale
    - Test threshold crossing triggers full pipeline
    - _Requirements: 7.1, 7.4, 8.4_

- [ ] 13. Monitoring and observability
  - [ ] 13.1 Add CloudWatch alarms and pipeline failure handling
    - Configure CloudWatch alarm on Step Functions execution failure
    - Include case_id, failed step, and error message in alarm notification
    - Add error recording in release_lock Lambda for failed executions
    - _Requirements: 9.2, 1.3_

- [ ] 14. Final checkpoint — End-to-end validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The pipeline Lambda functions are in `src/lambdas/pipeline/` (new subdirectory) to separate from API handlers
- All Lambda functions reuse existing connection patterns from `src/db/connection.py` and `src/services/opensearch_serverless_backend.py`
- The scoring Lambda reuses logic from `src/services/sex_trafficking_typology.py` for flag evaluation
- Frontend changes maintain backward compatibility — small cases continue using the existing live path
- Migration numbering follows existing pattern (021 is next available)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "7.1"] },
    { "id": 2, "tasks": ["2.3", "3.1", "3.2", "3.3", "7.2"] },
    { "id": 3, "tasks": ["3.4", "5.1"] },
    { "id": 4, "tasks": ["5.2", "6.1"] },
    { "id": 5, "tasks": ["5.3", "6.2", "9.1"] },
    { "id": 6, "tasks": ["9.2", "9.3", "10.1", "10.2", "10.3"] },
    { "id": 7, "tasks": ["10.4", "10.5", "11.1"] },
    { "id": 8, "tasks": ["11.2", "11.3", "12.1"] },
    { "id": 9, "tasks": ["12.2", "13.1"] }
  ]
}
```
