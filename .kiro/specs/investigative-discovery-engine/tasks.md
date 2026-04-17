# Implementation Plan: Investigative Discovery Engine

## Overview

Replace the Patterns tab with a two-lens Discovery experience: "Did You Know" (AI narrative discoveries via Bedrock) and "Anomaly Radar" (statistical anomaly detection). Implementation proceeds backend-first (model registry → migrations → services → API handlers), then frontend (tab replacement → card layouts → sparklines → state management).

## Tasks

- [x] 1. Create Bedrock model registry config file
  - [x] 1.1 Create `config/bedrock_models.json` with model entries
    - Define JSON structure with model_id, provider, type, speed, depth, fedramp_level, and notes for each model
    - Include GovCloud (FedRAMP High) models: Titan Text Premier, Titan Text Express, Claude Sonnet 4.5, Claude 3.7 Sonnet, Claude 3.5 Sonnet, Claude 3 Haiku, Llama3 8B, Llama3 70B, Titan Embed v2
    - Include Commercial (FedRAMP Moderate) additional models: Nova Pro, Nova Lite, Nova Micro, Claude Sonnet 4, Mistral Large, AI21 Jamba
    - Include qualifying logic metadata: region → compliance level mapping
    - _Requirements: 1.5, 12.2_

- [x] 2. Aurora database migrations
  - [x] 2.1 Create `src/db/migrations/015_discovery_engine.sql`
    - Create `discovery_feedback` table with columns: feedback_id (UUID PK), discovery_id (UUID), case_id (UUID), user_id (VARCHAR 255), rating (SMALLINT CHECK -1/1), discovery_type (VARCHAR 50), content_hash (VARCHAR 64), created_at (TIMESTAMPTZ)
    - Create index `idx_discovery_feedback_case` on case_id
    - Create `discovery_history` table with columns: discovery_id (UUID PK), case_id (UUID), batch_number (INTEGER), discoveries (JSONB), created_at (TIMESTAMPTZ)
    - Create index `idx_discovery_history_case` on case_id
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 3. Implement DiscoveryEngineService
  - [x] 3.1 Create `src/services/discovery_engine_service.py` with data models and service class
    - Define Discovery, DiscoveryBatch dataclasses matching design data models
    - Implement `__init__` accepting aurora_cm, bedrock_client, neptune_endpoint, pattern_svc, ai_engine, default_model_id
    - Load SUPPORTED_MODELS from `config/bedrock_models.json` at init
    - Implement `generate_discoveries(case_id, user_id, model_id)` orchestrating: model validation, history exclusion query, feedback query, context gathering, prompt building, Bedrock invocation, JSON parsing, batch storage
    - Implement `_gather_case_context(case_id)` querying Aurora (documents, entities, temporal distribution) and Neptune (top entities by centrality via PatternDiscoveryService methods, 2-hop neighborhoods)
    - Implement `_build_prompt(case_id, context, feedback, exclusions)` with INVESTIGATOR_PERSONA, context injection, feedback preferences pattern from Req 2.4, and exclusion list
    - Implement `_generate_fallback_discoveries(case_id, context)` generating 2+ discoveries from graph statistics with narrative framing when Bedrock fails
    - Implement `submit_feedback(case_id, user_id, discovery_id, rating, discovery_type, content_hash)` inserting into discovery_feedback table
    - Implement `_get_previous_discovery_hashes(case_id)` and `_get_feedback(case_id)` query helpers
    - Ensure batch always contains exactly 5 discoveries (pad with fallback if Bedrock returns fewer)
    - Generate content_hash as SHA-256 of narrative text for dedup
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.4, 11.1, 11.2, 11.3, 12.2, 12.3, 13.1_

  - [ ]* 3.2 Write property test: Discovery batch size invariant (Property 1)
    - **Property 1: Discovery batch size invariant**
    - Generate random case contexts (entity counts 0–100, document counts 0–500). Mock Bedrock to return valid JSON arrays of varying lengths (0–10). Verify batch always contains exactly 5 discoveries.
    - **Validates: Requirements 1.1**

  - [ ]* 3.3 Write property test: Discovery exclusion across batches (Property 2)
    - **Property 2: Discovery exclusion across batches**
    - Generate random sets of content_hashes (0–50). Mock Bedrock to return discoveries with random content. Verify no new discovery's content_hash appears in the exclusion set.
    - **Validates: Requirements 2.1, 11.3**

  - [ ]* 3.4 Write property test: Feedback round-trip storage (Property 3)
    - **Property 3: Feedback round-trip storage**
    - Generate random feedback submissions (random UUIDs, ratings from {-1, 1}, random discovery_types, random content_hashes). Submit and query back. Verify all fields match.
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 3.5 Write property test: Feedback incorporation in generation prompt (Property 4)
    - **Property 4: Feedback incorporation in generation prompt**
    - Generate random feedback records (0–20 records, mix of +1/-1 ratings). Build prompt. Verify prompt contains feedback references when feedback exists.
    - **Validates: Requirements 2.3, 3.4**

  - [ ]* 3.6 Write property test: Fallback discoveries on Bedrock failure (Property 13)
    - **Property 13: Fallback discoveries on Bedrock failure**
    - Generate random case contexts, force Bedrock failure. Verify at least 2 fallback discoveries with valid discovery_type, non-empty narrative, and confidence in [0.0, 1.0].
    - **Validates: Requirements 13.1**

  - [ ]* 3.7 Write unit tests for DiscoveryEngineService
    - Test generate_discoveries with mocked Bedrock returning valid JSON, verify 5 discoveries returned
    - Test fallback path when Bedrock raises exception
    - Test submit_feedback stores and retrieves correctly
    - Test exclusion logic prevents duplicate content_hashes across batches
    - Test model_id validation falls back to default for invalid model
    - _Requirements: 1.1, 2.1, 3.2, 3.3, 11.1, 11.2, 13.1_

- [x] 4. Checkpoint — Verify DiscoveryEngineService
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement AnomalyDetectionService
  - [x] 5.1 Create `src/services/anomaly_detection_service.py` with data models and service class
    - Define Anomaly, AnomalyReport dataclasses matching design data models
    - Implement `__init__` accepting aurora_cm, neptune_endpoint, neptune_port
    - Implement `detect_anomalies(case_id)` orchestrating all 5 detectors with independent try/except, collecting computed_dimensions and failed_dimensions
    - Implement `_detect_temporal_anomalies(case_id)`: query Aurora for document counts by month/quarter, compute z-scores, flag |z| > 2.0, return data_points for sparkline
    - Implement `_detect_network_anomalies(case_id)`: query Neptune for entities bridging disconnected clusters (structural holes), reuse graph query patterns from PatternDiscoveryService
    - Implement `_detect_frequency_anomalies(case_id)`: query Aurora for entity/term frequency distributions, flag count > mean + 2*std_dev
    - Implement `_detect_coabsence_anomalies(case_id)`: query Neptune for entity sets co-occurring in all sources except one, identify missing source
    - Implement `_detect_volume_anomalies(case_id)`: query Aurora for entity type ratios, compare against expected distribution, flag >2 std dev deviations
    - Ensure anomaly descriptions are factual statistical statements only (no narrative framing, no "Did you know")
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 8.2, 8.4, 12.1, 13.2_

  - [ ]* 5.2 Write property test: Anomaly dimension completeness (Property 5)
    - **Property 5: Anomaly dimension completeness**
    - Generate random dimension failure combinations (subsets of 5 dimensions). Verify computed ∪ failed = {temporal, network, frequency, co_absence, volume}, and all anomaly types ∈ computed.
    - **Validates: Requirements 5.1, 13.2**

  - [ ]* 5.3 Write property test: Temporal anomaly z-score correctness (Property 6)
    - **Property 6: Temporal anomaly z-score correctness**
    - Generate random time series (3–24 periods, counts 0–100). Compute z-scores independently. Verify detector flags exactly the periods where |z| > 2.0.
    - **Validates: Requirements 5.2**

  - [ ]* 5.4 Write property test: Network structural hole detection (Property 7)
    - **Property 7: Network structural hole detection**
    - Generate random graphs with planted structural holes (entity connecting 2+ disconnected clusters). Verify detection. Also generate fully-connected neighborhoods and verify no false positives.
    - **Validates: Requirements 5.3**

  - [ ]* 5.5 Write property test: Frequency outlier detection (Property 8)
    - **Property 8: Frequency outlier detection**
    - Generate random frequency distributions (5–100 entities, counts 1–1000). Compute mean + 2*std_dev independently. Verify detector flags exactly the outliers.
    - **Validates: Requirements 5.4**

  - [ ]* 5.6 Write property test: Co-absence anomaly detection (Property 9)
    - **Property 9: Co-absence anomaly detection**
    - Generate random entity-document co-occurrence matrices with planted co-absence patterns. Verify detection of the missing source.
    - **Validates: Requirements 5.5**

  - [ ]* 5.7 Write property test: Volume ratio deviation detection (Property 10)
    - **Property 10: Volume ratio deviation detection**
    - Generate random entity type count distributions. Compute ratio deviations independently. Verify detector flags exactly the significant deviations.
    - **Validates: Requirements 5.6**

  - [ ]* 5.8 Write property test: Zero-overlap — no narrative in anomaly descriptions (Property 12)
    - **Property 12: Zero-overlap — no narrative in anomaly descriptions**
    - Generate random anomaly descriptions from the detector (using random input data). Verify none contain narrative framing patterns ("Did you know", subjective assessments, AI-generated prose).
    - **Validates: Requirements 8.4, 6.1, 6.4**

  - [ ]* 5.9 Write unit tests for AnomalyDetectionService
    - Test each of the 5 dimension detectors with known data sets
    - Test partial failure handling (one dimension fails, others succeed)
    - Test empty case (no documents/entities) returns empty anomalies list
    - Test z-score computation accuracy with known values
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 13.2_

- [x] 6. Checkpoint — Verify AnomalyDetectionService
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Add API handlers and route wiring
  - [x] 7.1 Add discovery and anomaly handlers to `src/lambdas/api/investigator_analysis.py`
    - Add `_build_discovery_engine()` helper to construct DiscoveryEngineService with aurora_cm, bedrock, neptune_ep, pattern_svc, ai_engine
    - Add `_build_anomaly_service()` helper to construct AnomalyDetectionService with aurora_cm, neptune_ep
    - Implement `discoveries_handler(event, context)`: extract case_id from pathParameters, user_id and model_id from body, call generate_discoveries, return DiscoveryBatch JSON
    - Implement `discovery_feedback_handler(event, context)`: extract case_id from pathParameters, discovery_id/rating/discovery_type/content_hash from body, call submit_feedback, return {status: ok}
    - Implement `anomalies_handler(event, context)`: extract case_id from pathParameters, call detect_anomalies, return AnomalyReport JSON
    - Add all three routes to `dispatch_handler` routes dict
    - _Requirements: 1.1, 2.1, 3.2, 3.3, 5.1, 13.1, 13.2, 13.3_

  - [x] 7.2 Add route matching in `src/lambdas/api/case_files.py`
    - Add `"/discoveries"` and `"/anomalies"` to the existing investigator-analysis routing `any(seg in path ...)` block
    - _Requirements: 1.1, 5.1_

  - [ ]* 7.3 Write unit tests for API handlers
    - Test discoveries_handler with mocked DiscoveryEngineService
    - Test discovery_feedback_handler with valid and invalid payloads
    - Test anomalies_handler with mocked AnomalyDetectionService
    - Test missing case_id returns 400
    - Test error paths return 500 with descriptive error
    - _Requirements: 13.1, 13.2, 13.3_

- [x] 8. Checkpoint — Verify backend API end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Frontend — Replace Patterns tab with Discovery tab
  - [x] 9.1 Replace Patterns tab in `src/frontend/investigator.html`
    - Replace the Patterns tab label in the main `.tabs` bar with "🔍 Discovery" and update onclick to `showTab('discovery')`
    - Replace the `rh-patterns` sub-panel button in the Research Hub sub-nav with "🔍 Discovery"
    - Create `tab-discovery` content div with two-section layout: `#discovery-dyk` (top) and `#discovery-anomalies` (bottom)
    - Add model selector dropdown at top of Discovery layout with options from bedrock_models.json (Claude Haiku, Claude Sonnet, Nova Pro, Nova Lite)
    - Persist model selection in `localStorage` keyed by case_id
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 10. Frontend — Did You Know cards with feedback
  - [x] 10.1 Implement Did You Know card rendering and interaction
    - Implement `loadDiscoveries(caseId)` function: POST to `/case-files/{id}/discoveries` with user_id and model_id from selector, render Discovery_Cards
    - Render each Discovery_Card with: narrative text, 👍 button, 👎 button, "Save to Case" button
    - Implement `submitDiscoveryFeedback(discoveryId, rating, discoveryType, contentHash)`: POST to `/case-files/{id}/discoveries/feedback`
    - Implement "Show me 5 more" button calling `loadDiscoveries` again (appends new batch)
    - Implement card click → `DrillDown.openEntity()` for primary entity in the discovery
    - Implement "Save to Case" → call existing FindingsService endpoint to persist discovery
    - Ensure Discovery_Cards display narrative text only, no raw statistical values
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 3.1, 3.2, 3.3, 4.1, 4.2, 8.1, 8.3, 10.1_

- [x] 11. Frontend — Anomaly Radar cards with sparklines
  - [x] 11.1 Implement Anomaly Radar card rendering with inline SVG sparklines
    - Implement `loadAnomalies(caseId)` function: GET `/case-files/{id}/anomalies`, render Anomaly_Cards
    - Render each Anomaly_Card with: concise factual description, inline SVG sparkline, "Investigate" button, "Save to Case" button
    - Implement `renderSparkline(dataPoints, anomalyMetadata)`: generate inline `<svg>` polyline scaled to 120×30 viewport, highlight anomaly points in red
    - Implement "Investigate" button routing: entity drilldown for network/co_absence anomalies, evidence library for temporal/frequency/volume anomalies
    - Implement "Save to Case" → call existing FindingsService endpoint to persist anomaly
    - Show computed_dimensions and failed_dimensions indicators
    - Ensure Anomaly_Cards contain no AI-generated narrative text or "Did you know" framing
    - _Requirements: 5.1, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 8.2, 8.4, 10.2, 13.2_

  - [ ]* 11.2 Write property test: Investigate routing by anomaly type (Property 11)
    - **Property 11: Investigate routing by anomaly type**
    - For all anomaly_type values in {temporal, network, frequency, co_absence, volume}, verify routing returns "entity_drilldown" for network and co_absence, "evidence_library" for temporal, frequency, and volume.
    - **Validates: Requirements 7.1, 7.2**

- [x] 12. Frontend — CSS styles, error handling, and empty states
  - [x] 12.1 Add CSS styles and error/empty state handling
    - Add CSS styles for Discovery_Cards (narrative card styling, feedback button states, active/inactive)
    - Add CSS styles for Anomaly_Cards (compact card styling, sparkline container, investigate button)
    - Add CSS styles for model selector dropdown
    - Implement error handling: warning banner when Bedrock unavailable (Req 13.1), partial dimension indicators (Req 13.2), empty state messages for each section (Req 13.3)
    - Implement feedback button state management (highlight selected, disable re-click)
    - _Requirements: 9.3, 9.4, 13.1, 13.2, 13.3_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (13 properties total)
- Unit tests validate specific examples and edge cases
- The design uses Python throughout — no language selection needed
- Frontend is a single-file HTML app with inline JavaScript (no build step)
