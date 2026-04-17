# Implementation Plan: Investigative Timeline

## Overview

Replace the existing basic vis.js timeline in the Investigator UI with a full-featured chronological reconstruction tool. Backend adds TimelineService + TimelineHandler following the PatternDiscoveryService/patterns.py pattern. Frontend replaces the Timeline tab with swim lanes, clustering, gap analysis, event type markers, and AI analysis. All backend changes are Lambda code updates routed through case_files.py dispatch_handler.

## Tasks

- [x] 1. Create TimelineService with event extraction, clustering, and gap detection
  - [x] 1.1 Create `src/services/timeline_service.py` with `TimelineService` class
    - Implement `__init__(self, aurora_conn: ConnectionManager, bedrock_client)` matching PatternDiscoveryService pattern
    - Implement `_neptune_query(query)` helper using Neptune HTTP API (urllib.request, not gremlinpython WebSocket) — same pattern as `_neptune_query` in patterns.py
    - Implement `_extract_events(case_id)` — query Neptune for date entities with `g.V().hasLabel('Entity_{case_id}').has('entity_type','date')` projecting name, neighbors, neighbor_types; query Aurora entities table for document co-occurrences; build TimelineEvent dicts
    - Implement `_normalize_date(date_str)` — parse various date formats (ISO 8601, MM/DD/YYYY, YYYY-MM-DD, natural language dates) into ISO 8601 strings; return None for unparseable dates with logger.warning
    - Implement `_infer_event_type(connected_entity_types)` — deterministic inference following the design rules: person+location→travel, person+financial_amount→financial_transaction, person+person→meeting, person+phone_number/email→communication, organization+legal→legal_proceeding, metadata dates→document_creation, fallback→other
    - Implement `_get_source_snippets(case_id, date_str, document_ids)` — query OpenSearch for text surrounding date mentions, truncate snippets to 200 chars
    - Implement `_cluster_events(events, window_hours)` — group events within temporal proximity sharing common entities; window=0 disables clustering; return ActivityCluster dicts
    - Implement `_detect_gaps(events, entity_names, threshold_days)` — find per-entity temporal gaps exceeding threshold; return GapInterval dicts with event_before_id and event_after_id
    - Implement `reconstruct_timeline(case_id, clustering_window_hours=48, gap_threshold_days=30)` — orchestrate extraction, clustering, gap detection; sort events ascending by timestamp; return full response dict with events, clusters, gaps, summary
    - Implement `generate_ai_analysis(case_id, events, gaps)` — send timeline data to Bedrock Claude for temporal pattern analysis; return structured analysis dict with chronological_patterns, escalation_trends, clustering_significance, gap_interpretation, cross_entity_coordination, recommended_followups
    - Handle Neptune timeout gracefully — return partial results with warning flag
    - Handle missing/deleted source documents — include reference with snippet=null and status="source_unavailable"
    - Handle empty case (no date entities) — return empty arrays with zero-count summary
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 3.1, 3.2, 3.5, 3.6, 4.1, 4.4, 4.5, 5.1, 5.2, 5.3, 5.6, 5.7, 7.1, 7.2, 7.6_

  - [ ]* 1.2 Write unit tests for TimelineService in `tests/unit/test_timeline_service.py`
    - Test event type inference for each entity type combination (person+location→travel, person+financial_amount→financial_transaction, person+person→meeting, person+phone_number→communication, fallback→other)
    - Test date normalization for various formats (ISO 8601, MM/DD/YYYY, YYYY-MM-DD)
    - Test unparseable date exclusion with logger.warning (Req 1.5)
    - Test clustering with window=0 disables clustering (Req 3.6)
    - Test missing document handling returns "source_unavailable" (Req 4.5)
    - Test empty case returns empty arrays with zero-count summary
    - Test AI analysis response structure contains all required sections (Req 7.2)
    - Test events are sorted ascending by timestamp
    - Test gap detection returns correct gap_days calculation
    - Mock Neptune HTTP API, Aurora ConnectionManager, OpenSearch, and Bedrock
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 3.6, 4.5, 5.1, 5.2, 5.3, 7.2_

- [x] 2. Create TimelineHandler with REST endpoints
  - [x] 2.1 Create `src/lambdas/api/timeline_handler.py` with dispatch_handler
    - Implement `dispatch_handler(event, context)` with `@with_access_control` decorator following patterns.py pattern
    - Route POST `/case-files/{id}/timeline` to `timeline_handler` function
    - Route POST `/case-files/{id}/timeline/ai-analysis` to `ai_analysis_handler` function
    - Handle OPTIONS with CORS headers
    - Implement `timeline_handler(event, context)` — parse case_id from pathParameters, parse clustering_window_hours and gap_threshold_days from body with defaults, validate inputs, construct TimelineService, call reconstruct_timeline, return success_response
    - Implement `ai_analysis_handler(event, context)` — parse case_id, events, and gaps from body, construct TimelineService, call generate_ai_analysis, return success_response
    - Validate case_file_id format (UUID) — return 400 VALIDATION_ERROR if invalid
    - Validate clustering_window_hours is non-negative integer — return 400 if invalid
    - Validate gap_threshold_days is positive integer — return 400 if invalid
    - Return 404 NOT_FOUND for non-existent case file
    - Return 500 AI_ANALYSIS_ERROR for Bedrock failures
    - Handle Neptune query failure — return 200 with empty events and warning
    - _Requirements: 1.6, 5.6, 7.6, 9.1, 9.2, 9.5_

  - [ ]* 2.2 Write unit tests for TimelineHandler in `tests/unit/test_timeline_handler.py`
    - Test invalid case_file_id returns 400
    - Test OPTIONS returns CORS headers
    - Test valid timeline request returns 200 with events and gaps arrays (Req 9.3)
    - Test valid ai-analysis request returns 200 with analysis sections
    - Test invalid clustering_window_hours returns 400
    - Test invalid gap_threshold_days returns 400
    - Test non-existent case file returns 404
    - Mock TimelineService for all handler tests
    - _Requirements: 1.6, 5.6, 9.1, 9.2, 9.3, 9.5_

- [x] 3. Wire timeline routes into case_files.py dispatch_handler
  - [x] 3.1 Add timeline route to `src/lambdas/api/case_files.py` dispatch_handler
    - Add route block BEFORE the `/patterns` catch-all and BEFORE the case file CRUD catch-all:
      ```python
      if "/timeline" in path and "/case-files/" in path:
          from lambdas.api.timeline_handler import dispatch_handler as tl_dispatch
          return tl_dispatch(event, context)
      ```
    - Place after the `/top-patterns` route and before the `/patterns` route
    - _Requirements: 1.6, 5.6, 9.1, 9.2_

- [x] 4. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Replace frontend Timeline tab in investigator.html
  - [x] 5.1 Replace Timeline tab HTML structure in `src/frontend/investigator.html`
    - Replace existing `#tab-timeline` content with new layout: view mode toggle (flat/swim lane/cluster), entity picker multi-select, event type filter dropdown, zoom controls (+/- buttons), density bar, summary badge (event count, entity count, cluster count, gap count), main timeline canvas area, event detail panel, gap markers area, AI Analysis button and results panel, event type legend panel
    - Maintain dark theme (#0f1923 background, #48bb78 accent, #e2e8f0 text)
    - Add CSS for swim lanes, cluster markers, gap hatched overlays, event type icons/colors, density bar, legend panel
    - _Requirements: 2.1, 2.5, 2.6, 3.3, 5.4, 6.1, 6.2, 8.1, 8.4, 8.5, 8.6_

  - [x] 5.2 Replace `loadTimeline()` function in `src/frontend/investigator.html`
    - Call `POST /case-files/{id}/timeline` with clustering_window_hours and gap_threshold_days from UI controls
    - Parse response events, clusters, gaps, summary
    - Render events on timeline canvas with event type markers (📞 purple, 🤝 green, 💰 yellow, ✈️ blue, ⚖️ red, 📄 gray, 📎 muted)
    - Render density bar showing event frequency distribution
    - Render summary badge with counts
    - Auto-fit time range to encompass all events with padding
    - Default to flat timeline view
    - Default entity picker to top 5 entities by event count
    - _Requirements: 1.6, 1.7, 6.1, 6.5, 8.2, 8.3, 8.5_

  - [x] 5.3 Implement swim lane rendering in `src/frontend/investigator.html`
    - Render horizontal lanes per selected entity with entity name labels
    - Color-code lanes by entity type (person: #fc8181, organization: #f6ad55, location: #90cdf4)
    - Display events in their respective entity lanes
    - Draw connector lines for events involving multiple swim lane entities
    - Shared time axis across all lanes for vertical alignment
    - Re-render on entity picker changes without full page reload
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 5.4 Implement clustering UI and gap visualization in `src/frontend/investigator.html`
    - Render Activity_Clusters as expandable markers showing event count and date range
    - On cluster click, expand to reveal individual events
    - Render Gap_Intervals as hatched/semi-transparent overlays on swim lanes
    - On gap click, show detail panel with gap duration, bounding events, and AI hypothesis placeholder
    - _Requirements: 3.3, 3.4, 5.4, 5.5_

  - [x] 5.5 Implement event detail panel and document linking in `src/frontend/investigator.html`
    - On event marker click, show detail panel with: timestamp, event type, associated entities, source documents with snippets
    - Make document references clickable to navigate to document search view
    - Show "source unavailable" indicator for missing documents
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [x] 5.6 Implement AI analysis panel and view controls in `src/frontend/investigator.html`
    - Replace existing `aiTimelineAnalysis()` function
    - On AI Analysis button click, call `POST /case-files/{id}/timeline/ai-analysis` with current events and gaps
    - Show loading indicator "Analyzing temporal patterns..."
    - Display results in formatted panel with sections: chronological patterns, escalation trends, clustering significance, gap interpretation, cross-entity coordination, recommended follow-ups
    - Show error message with retry button on failure
    - Implement view mode toggle (flat/swim lane/cluster) switching
    - Implement event type filter multi-select dropdown
    - Implement zoom controls (+/- buttons, mouse wheel)
    - Implement keyboard navigation: left/right arrows pan, +/- zoom, Escape closes panels
    - _Requirements: 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.7_

- [x] 6. Checkpoint — Frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Property-based tests for timeline correctness
  - [ ]* 7.1 Write property test for event reconstruction structure
    - **Property 1: Event reconstruction produces well-structured events**
    - Generate random date entities with connections using Hypothesis strategies
    - Verify each event has non-empty event_id, valid ISO 8601 timestamp, event_type from allowed set, non-empty entities list with name/type, snippets ≤ 200 chars
    - **Validates: Requirements 1.1, 1.2, 4.1**
    - Create `tests/unit/test_timeline_properties.py`

  - [ ]* 7.2 Write property test for event type inference
    - **Property 2: Event type inference follows entity type rules**
    - Generate random entity type combinations using Hypothesis
    - Verify inference matches design rules deterministically
    - **Validates: Requirements 1.3, 6.5**

  - [ ]* 7.3 Write property test for date normalization round-trip
    - **Property 3: Date normalization produces valid ISO 8601**
    - Generate parseable date strings using Hypothesis
    - Verify normalized output is valid ISO 8601; re-normalizing produces same string
    - **Validates: Requirements 1.4**

  - [ ]* 7.4 Write property test for chronological ordering
    - **Property 4: Events are sorted in ascending chronological order**
    - Generate random event sets using Hypothesis
    - Verify events[i].timestamp <= events[i+1].timestamp for all consecutive pairs
    - **Validates: Requirements 1.7, 9.4**

  - [ ]* 7.5 Write property test for clustering invariants
    - **Property 5: Clustering groups temporally proximate events sharing entities**
    - Generate random events with timestamps and entities using Hypothesis
    - Verify all cluster events are within window_hours of at least one other, share at least one entity, have valid metadata
    - **Validates: Requirements 3.1, 3.2, 3.5**

  - [ ]* 7.6 Write property test for gap detection
    - **Property 6: Gap detection identifies intervals exceeding threshold**
    - Generate random event sequences per entity using Hypothesis
    - Verify gap_days equals difference between gap_end and gap_start, gap_days >= threshold, all fields present
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 7.7 Write property test for gap boundary invariant
    - **Property 7: Gap boundary invariant**
    - Generate random event sequences using Hypothesis
    - Verify gap_start equals timestamp of event_before_id, gap_end equals timestamp of event_after_id, gap_start < gap_end
    - **Validates: Requirements 5.7**

- [ ] 8. Integration tests for timeline routing chain
  - [ ]* 8.1 Write integration tests in `tests/unit/test_timeline_handler.py`
    - Test: invoke `dispatch_handler` from case_files.py with realistic API Gateway proxy event for `POST /case-files/{uuid}/timeline` — verify response status is not 404 and not 500 (Req 9.1)
    - Test: invoke `dispatch_handler` with realistic event for `POST /case-files/{uuid}/timeline/ai-analysis` — verify response status is not 404 and not 500 (Req 9.2)
    - Test: verify timeline response contains `events` array and `gaps` array (Req 9.3)
    - Test: verify events are sorted ascending by timestamp (Req 9.4)
    - Test: verify invalid case_file_id returns 400 (Req 9.5)
    - Mock Neptune, Aurora, OpenSearch, Bedrock at service level; exercise full dispatch_handler → timeline_handler → TimelineService chain
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 9. Final checkpoint — All features integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All backend changes are Lambda code updates — no CDK deploy or new migrations needed
- Follow patterns.py / PatternDiscoveryService as the reference for handler+service structure
- Neptune queries use HTTP API (urllib.request), not gremlinpython WebSocket
- Aurora queries use ConnectionManager cursor pattern
- OpenSearch queries for source snippets around date mentions
- Bedrock model: anthropic.claude-3-haiku-20240307-v1:0
- Frontend replaces existing loadTimeline/showTimelineDetail/renderTimelineDensity/filterTimeline/aiTimelineAnalysis functions
- Property tests use `hypothesis` library with minimum 100 iterations, tagged with feature and property number
- Each property test references its design document property number
