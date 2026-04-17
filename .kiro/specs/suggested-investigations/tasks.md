# Implementation Plan: Suggested Investigations

## Overview

Implement automatic research lead generation that triggers after case file ingestion. The feature adds three graph signal analyses (Entity Connection Count, Community Detection, Betweenness Centrality), combines results into ranked suggestions with Bedrock-generated explanations, stores them in Aurora, and displays them on the Case Detail page with dismiss and sub-case creation actions.

## Tasks

- [ ] 1. Create data models and Aurora schema
  - [ ] 1.1 Create Pydantic models for Suggestion and SuggestionSet
    - Create `src/models/suggestion.py` with `Suggestion` and `SuggestionSet` models as defined in the design
    - Add `SignalSource` enum with values: `entity_connection_count`, `community_detection`, `betweenness_centrality`
    - Register new models in `src/models/__init__.py`
    - _Requirements: 1.6, 5.1_

  - [ ] 1.2 Create Aurora migration SQL for suggestion tables
    - Create `suggestion_sets` table with `suggestion_set_id`, `case_file_id` (FK to case_files), `top_n`, `generated_at`, `message` columns
    - Create `suggestions` table with all fields from design: `suggestion_id`, `suggestion_set_id` (FK), `rank`, `title`, `signal_source` (CHECK constraint), `composite_score` (CHECK 0-1), `explanation`, `entity_names` (JSONB), `entity_fingerprint`, `dismissed`, `dismissed_at`, `created_at`
    - Add UNIQUE constraint on `suggestion_sets(case_file_id)` for one-active-set-per-case
    - Add indexes: `idx_suggestion_sets_case`, `idx_suggestions_set`, `idx_suggestions_fingerprint`, `idx_suggestions_dismissed`
    - _Requirements: 5.1, 5.3, 6.2_

- [ ] 2. Implement SuggestionService core
  - [ ] 2.1 Create SuggestionService with signal analysis methods
    - Create `src/services/suggestion_service.py` with `SuggestionService` class
    - Implement `_compute_connection_counts(case_id)` — query Neptune for entity nodes ranked by total edge count, reusing traversal patterns from `PatternDiscoveryService._discover_centrality_patterns`
    - Implement `_detect_communities(case_id)` — traverse case subgraph for connected components ranked by member count × density, reusing patterns from `PatternDiscoveryService._discover_community_patterns`
    - Implement `_compute_betweenness_centrality(case_id)` — approximate betweenness centrality via sampled shortest paths, reusing patterns from `PatternDiscoveryService._discover_path_patterns`
    - Each signal method returns results sorted descending by its respective score
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.2 Write property test: Signal result ordering (Property 1)
    - **Property 1: Signal result ordering**
    - **Validates: Requirements 1.3, 1.4, 1.5**

  - [ ] 2.3 Implement combine, deduplicate, and score logic
    - Implement `_combine_and_score()` with weights: connection=0.35, community=0.30, centrality=0.35
    - Implement `_entity_fingerprint()` — SHA-256 hash of sorted entity names
    - Deduplicate by entity fingerprint, order by composite score descending
    - _Requirements: 1.6_

  - [ ]* 2.4 Write property test: Combined list deduplication and ordering (Property 2)
    - **Property 2: Combined suggestion list is deduplicated and ordered by composite score**
    - **Validates: Requirements 1.6**

  - [ ] 2.5 Implement Bedrock explanation generation with fallback
    - Implement `_generate_explanation(suggestion)` — call Bedrock with entity names, types, signal source, composite score
    - For community detection suggestions, include community member names and internal relationship count in prompt
    - For betweenness centrality suggestions, include bridged topic group names in prompt
    - Implement `_fallback_explanation(suggestion)` — structured string with entity names, signal source, and score when Bedrock fails
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 2.6 Write property test: Bedrock prompt context (Property 3)
    - **Property 3: Bedrock prompt contains all required context for the signal source**
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 2.7 Write property test: Fallback explanation fields (Property 4)
    - **Property 4: Fallback explanation contains required fields**
    - **Validates: Requirements 2.5**

- [ ] 3. Implement SuggestionService storage and retrieval
  - [ ] 3.1 Implement generate_suggestions orchestration method
    - Implement `generate_suggestions(case_id, top_n)` — run all three signals, combine, generate explanations, store in Aurora
    - Handle < 2 entities case: return empty suggestion set with "Insufficient data" message
    - On regeneration (UPSERT), delete old suggestion_set and create new one, preserving dismissals by entity fingerprint
    - _Requirements: 1.1, 1.7, 5.1, 5.3, 6.4_

  - [ ]* 3.2 Write property test: At most one suggestion set per case (Property 8)
    - **Property 8: At most one suggestion set per case file**
    - **Validates: Requirements 5.3**

  - [ ]* 3.3 Write property test: Suggestion set storage round trip (Property 7)
    - **Property 7: Suggestion set storage round trip**
    - **Validates: Requirements 5.1, 5.4**

  - [ ] 3.4 Implement get_suggestion_set and get_visible_suggestions
    - Implement `get_suggestion_set(case_id)` — retrieve cached suggestion set from Aurora, return None if not generated
    - Implement `get_visible_suggestions(case_id)` — return non-dismissed suggestions, limited to top_n
    - _Requirements: 3.3, 5.2_

  - [ ]* 3.5 Write property test: Visible suggestions respect top-N (Property 5)
    - **Property 5: Visible suggestions respect top-N limit**
    - **Validates: Requirements 3.3**

  - [ ] 3.6 Implement dismiss_suggestion
    - Implement `dismiss_suggestion(case_id, suggestion_id)` — mark suggestion as dismissed in Aurora, set `dismissed_at` timestamp
    - Return 404 for non-existent suggestion_id
    - Idempotent for already-dismissed suggestions
    - _Requirements: 6.2, 6.3_

  - [ ]* 3.7 Write property test: Dismissed suggestions excluded from visible list (Property 9)
    - **Property 9: Dismissed suggestions are excluded from visible list**
    - **Validates: Requirements 6.2, 6.3**

  - [ ]* 3.8 Write property test: Dismissals persist across regeneration (Property 10)
    - **Property 10: Dismissals persist across suggestion set regeneration**
    - **Validates: Requirements 6.4**

- [ ] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Create Lambda handlers
  - [ ] 5.1 Create generate_suggestions_handler Lambda
    - Create `src/lambdas/ingestion/generate_suggestions_handler.py`
    - Instantiate `SuggestionService` with `NeptuneConnectionManager`, `ConnectionManager`, and Bedrock client
    - Accept `{"case_id": "..."}` from Step Functions, call `generate_suggestions`, return `{"suggestion_set_id": "...", "suggestion_count": N}`
    - _Requirements: 1.1_

  - [ ] 5.2 Create suggestions API Lambda
    - Create `src/lambdas/api/suggestions.py` with `suggestions_handler`
    - Route `GET /case-files/{id}/suggestions` → call `get_visible_suggestions`, return suggestions list with generation timestamp
    - Route `POST /case-files/{id}/suggestions/{sid}/dismiss` → call `dismiss_suggestion`
    - Handle error cases: no suggestion set (return message), non-existent suggestion (404), already dismissed (idempotent)
    - _Requirements: 3.1, 3.4, 6.1, 6.2, 6.5_

  - [ ]* 5.3 Write unit tests for Lambda handlers
    - Test generate_suggestions_handler with mocked SuggestionService
    - Test suggestions API handler routing (GET, POST dismiss)
    - Test error cases: 404 for missing suggestion, empty suggestion set message
    - _Requirements: 1.1, 3.4, 6.2_

- [ ] 6. Update Step Functions and CDK infrastructure
  - [ ] 6.1 Update Step Functions ASL definition
    - Modify `infra/step_functions/ingestion_pipeline.json`: change `UpdateCaseStatusIndexed.Next` from `PipelineComplete` to `GenerateSuggestions`
    - Add `GenerateSuggestions` state with `${GenerateSuggestionsLambdaArn}` resource, retry config (2 attempts, 3s, 2x backoff), and Catch routing to `PipelineComplete` (non-fatal)
    - _Requirements: 1.1_

  - [ ] 6.2 Update CDK stack with new Lambda and API Gateway routes
    - Add `generate_suggestions` Lambda to `_create_ingestion_lambdas` in `infra/cdk/stacks/research_analyst_stack.py`
    - Add `suggestions` Lambda to `_create_api_lambdas`
    - Add `GenerateSuggestionsLambdaArn` to `definition_substitutions` in `_create_state_machine`
    - Grant Bedrock invoke permissions to `generate_suggestions` Lambda
    - Add API Gateway routes: `GET /case-files/{id}/suggestions`, `POST /case-files/{id}/suggestions/{sid}/dismiss`
    - _Requirements: 1.1, 3.1, 6.1_

- [ ] 7. Implement frontend integration
  - [ ] 7.1 Add suggestion API functions to api_client.py
    - Add `get_suggestions(case_id)` → `GET /case-files/{case_id}/suggestions`
    - Add `dismiss_suggestion(case_id, suggestion_id)` → `POST /case-files/{case_id}/suggestions/{suggestion_id}/dismiss`
    - _Requirements: 3.1, 6.1_

  - [ ] 7.2 Update case_detail.py with Suggested Investigations section
    - Add "Suggested Investigations" section below case metadata in `src/frontend/pages/case_detail.py`
    - Display generation timestamp, each suggestion with rank, title, signal badge, composite score, and explanation
    - Add "Create Sub-Case" button per suggestion — calls existing `drill_down()` with suggestion title as topic_name, explanation as description, and entity_names
    - Add "Dismiss" button per suggestion — calls `dismiss_suggestion()` and reruns page
    - Handle states: no suggestion set ("Suggestions not yet available"), empty set ("Insufficient data"), all dismissed ("All suggestions reviewed")
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.2, 5.4, 6.1, 6.2, 6.5_

  - [ ]* 7.3 Write property test: Sub-case creation data (Property 6)
    - **Property 6: Sub-case creation from suggestion passes correct data**
    - **Validates: Requirements 4.2, 4.3**

- [ ] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Neptune and Aurora dependencies are mocked in all tests
- The design uses Python throughout — all code examples use Python with hypothesis for property-based tests
