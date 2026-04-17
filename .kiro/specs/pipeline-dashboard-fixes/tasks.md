# Implementation Plan: Pipeline Dashboard Fixes

## Overview

Incremental implementation of six pipeline dashboard enhancements: backend changes to `PipelineStatusService` (multi-prefix S3, multi-index OpenSearch, workload tier, throughput/minute), followed by frontend changes to `investigator.html` (docs/minute display, step detail overlay, workload tier label, production target projection). Property-based tests validate correctness properties from the design document.

## Tasks

- [x] 1. Implement backend multi-prefix S3 counting and workload tier classification
  - [x] 1.1 Refactor `_get_s3_stats` to check multiple S3 prefixes and aggregate counts
    - Modify `src/services/pipeline_status_service.py` method `_get_s3_stats`
    - Check prefixes: `cases/{id}/raw/`, `cases/{id}/documents/`, `epstein_files/`
    - Use paginated `list_objects_v2` with `MaxKeys=1000` per page
    - Add 25-second timeout guard to stay within API Gateway's 29s limit
    - Return `total_objects` as aggregate, `matched_prefixes` list for non-zero prefixes
    - Handle per-prefix errors gracefully (log warning, skip, continue)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 1.2 Write property test for S3 multi-prefix count aggregation
    - **Property 4: S3 multi-prefix count aggregation**
    - **Validates: Requirements 4.1, 4.2**
    - Create `tests/unit/test_pipeline_status_service.py`
    - Generate random counts per prefix, verify sum equals `total_objects`

  - [ ]* 1.3 Write property test for S3 matched prefixes accuracy
    - **Property 5: S3 matched prefixes accuracy**
    - **Validates: Requirements 4.4**
    - Generate random prefix results, verify `matched_prefixes` contains exactly non-zero prefixes

  - [x] 1.4 Add `_classify_workload_tier` method and integrate into `_assess_health`
    - Add new method `_classify_workload_tier(total_source_files)` to `PipelineStatusService`
    - Return `{"tier": "Small|Medium|Large|Enterprise", "range": "...", "recommendation": "..."}`
    - Boundaries: Small (<100), Medium (100–10K), Large (10K–100K), Enterprise (100K+)
    - Modify `_assess_health` to accept `total_source_files`, call `_classify_workload_tier`
    - Add `workload_tier` and `tier_range` to health response
    - Add tier-specific recommendation text to recommendations list
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 1.5 Write property test for workload tier classification
    - **Property 6: Workload tier classification correctness**
    - **Validates: Requirements 5.1, 5.6**
    - Generate random non-negative integers, verify tier assignment matches boundary rules

- [x] 2. Implement backend multi-index OpenSearch and throughput per minute
  - [x] 2.1 Refactor `_get_opensearch_stats` for multi-index fallback
    - Modify `src/services/pipeline_status_service.py` method `_get_opensearch_stats`
    - Try index formats in order: `case_{id_underscored}`, `case-{id}`, `{id}`
    - If all return 0 or error, fall back to `GET /_cat/indices?format=json` discovery
    - Return `doc_count`, `index` (matched), and `attempted_indices` on failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 2.2 Write property test for OpenSearch multi-index resolution
    - **Property 3: OpenSearch multi-index first-non-zero resolution**
    - **Validates: Requirements 3.1, 3.2, 3.3**
    - Generate random lists of (index, count) pairs, verify first non-zero is returned

  - [x] 2.3 Add `throughput_per_minute` to `get_status` summary response
    - Modify `get_status` in `src/services/pipeline_status_service.py`
    - Compute `throughput_per_minute = round(throughput_per_hour / 60, 1)`
    - Add field to summary dict
    - _Requirements: 1.4_

  - [ ]* 2.4 Write property test for throughput per minute computation
    - **Property 1: Throughput per minute computation**
    - **Validates: Requirements 1.1, 1.4**
    - Generate random floats for throughput_per_hour, verify `round(val / 60, 1)` matches

- [x] 3. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement frontend docs/minute display and workload tier label
  - [x] 4.1 Update throughput card in `loadPipelineMonitor` to show docs/minute
    - Modify `src/frontend/investigator.html` `loadPipelineMonitor` function
    - Display both `throughput_per_hour` and `throughput_per_minute` in the throughput card
    - Show "0" for both when throughput is 0
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 4.2 Display workload tier label in AI Health card
    - Modify the AI Health card rendering in `loadPipelineMonitor`
    - Show `workload_tier` label from health response
    - _Requirements: 5.7_

- [x] 5. Implement step card click detail overlay
  - [x] 5.1 Add `onclick` handlers to step cards and implement `showStepDetail` function
    - Add `onclick` handler to each step card calling `showStepDetail(step)`
    - Implement `showStepDetail(step)` function in `src/frontend/investigator.html`
    - Populate `.monitor-overlay` with step name, service, metric, status, detail text
    - Show activity log section with status and progress percentage
    - Show per-step AI recommendations based on status
    - Running steps show progress % and estimated time remaining
    - Error steps highlight in red with CloudWatch log suggestion
    - Close on overlay background click or close button
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 6. Implement production target projection calculator
  - [x] 6.1 Add production target input and `updateProjection` function
    - Add "Production Target" input field below step cards in `src/frontend/investigator.html`
    - Implement `updateProjection()` function
    - Compute serial time: `target / throughput_per_hour`
    - Compute parallel time: `target / (throughput_per_hour * 50)`
    - Format as human-readable string (hours/days)
    - Handle zero throughput with informational message
    - Update projection in real-time as user types (oninput event)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 6.2 Write property test for production target projection computation
    - **Property 7: Production target projection computation**
    - **Validates: Requirements 6.2, 6.3, 6.4**
    - Generate random positive target and throughput values
    - Verify serial = target/throughput and parallel = target/(throughput*50)

- [x] 7. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` library for Python backend properties
- Frontend property (Property 2: Step detail overlay completeness) is validated via manual testing of the overlay
- No new API routes or Lambda functions needed — all changes are additive to existing response
- Checkpoints ensure incremental validation after backend and full implementation
