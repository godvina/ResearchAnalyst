# Implementation Plan: Timeline Intelligence Upgrade

## Overview

Upgrade the existing investigative timeline by modifying three files: `src/services/timeline_service.py` (5 new methods + clustering fix), `src/lambdas/api/timeline_handler.py` (noise_cutoff_year parameter), and `src/frontend/investigator.html` (UI improvements). All changes are in-place modifications to existing code — no new files except optional test files.

## Tasks

- [x] 1. Add display label computation and noise date filtering to TimelineService
  - [x] 1.1 Add `_compute_display_label` static method to `TimelineService` in `src/services/timeline_service.py`
    - Implement the label composition: top 2 entity names + formatted date ("Mar 15, 2019")
    - Truncate entity names exceeding 25 characters to 22 chars + "..."
    - Fall back to event_type label + date when no entities present
    - _Requirements: 5.1, 5.2, 5.4, 5.5_

  - [ ]* 1.2 Write property test for `_compute_display_label`
    - **Property 5: Display label composition**
    - **Validates: Requirements 5.1, 5.2, 5.4, 5.5**

  - [x] 1.3 Add `_filter_noise_dates` method to `TimelineService` in `src/services/timeline_service.py`
    - Build year histogram from event timestamps
    - Find the largest contiguous block of active years (Density_Cluster) where no gap between consecutive active years exceeds 5 years
    - Set auto cutoff to Density_Cluster start year minus 20
    - If all events fall within a 20-year window, apply no filtering
    - Accept optional `noise_cutoff_year` parameter for manual override
    - Return `(relevant_events, noise_events)` tuple
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.8_

  - [ ]* 1.4 Write property tests for `_filter_noise_dates`
    - **Property 1: Noise filtering partition invariant**
    - **Property 2: Manual cutoff override**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

  - [x] 1.5 Add `_compute_relevant_range` method to `TimelineService` in `src/services/timeline_service.py`
    - Sort event timestamps ascending
    - Slide a window of size ceil(len * 0.8) to find the smallest span
    - Return `{"start": iso, "end": iso}` or None if fewer than 3 events
    - _Requirements: 2.2, 2.3_

  - [ ]* 1.6 Write property test for `_compute_relevant_range`
    - **Property 3: Relevant date range contains at least 80% of events**
    - **Validates: Requirements 2.2, 2.3**

- [ ] 2. Checkpoint — Verify new service methods
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add phase detection, narrative header, and fix clustering in TimelineService
  - [x] 3.1 Add `_detect_phases` method to `TimelineService` in `src/services/timeline_service.py`
    - Return empty list for fewer than 5 events
    - Divide timeline into temporal thirds, analyze event type distribution per third
    - Assign phase labels from fixed vocabulary: "Pre-Criminal Activity", "Early Activity", "Escalation", "Peak Activity", "Active Criminal Period", "Investigation Phase", "Legal Proceedings", "Post-Resolution"
    - Each phase gets: phase_id (UUID), label, start, end, description, event_count
    - _Requirements: 3.1, 3.2, 3.3, 3.6_

  - [ ]* 3.2 Write property test for `_detect_phases`
    - **Property 4: Phase detection structure and vocabulary**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.6**

  - [x] 3.3 Add `_generate_narrative_header` method to `TimelineService` in `src/services/timeline_service.py`
    - Build a lightweight Bedrock prompt with event count, time span, entity counts by type, top event types, phase labels
    - Set max_tokens to 150 for fast response
    - On Bedrock failure, return a template-based fallback string containing event count and time span
    - _Requirements: 4.1, 4.2, 4.5_

  - [ ]* 3.4 Write property test for narrative header fallback
    - **Property 9: Fallback narrative contains event data**
    - **Validates: Requirements 4.5**

  - [x] 3.5 Fix `_cluster_events` method in `src/services/timeline_service.py`
    - Add document co-occurrence check: if two events share a source document ID, treat as related
    - Add tight temporal fallback: cluster events within `window_hours / 2` even without entity or document overlap
    - Log cluster count at INFO level after clustering
    - Log WARNING with diagnostics if 0 clusters for 10+ events
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 3.6 Write property tests for clustering fix
    - **Property 6: Clustering produces clusters for temporally close events**
    - **Property 7: Document co-occurrence enables clustering**
    - **Validates: Requirements 9.1, 9.3**

- [ ] 4. Checkpoint — Verify phase detection and clustering fix
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Wire new methods into `reconstruct_timeline` and update handler
  - [x] 5.1 Update `reconstruct_timeline` in `src/services/timeline_service.py`
    - Add `noise_cutoff_year` parameter
    - Call `_compute_display_label` for each event during extraction
    - Call `_filter_noise_dates` after extraction, split into relevant + noise
    - Sort and cluster on relevant events only
    - Run `_detect_gaps` on relevant events only
    - Call `_compute_relevant_range` on relevant events
    - Call `_detect_phases` on relevant events
    - Call `_generate_narrative_header` with relevant events, range, and phases
    - Add to response: `filtered_noise_events`, `noise_filter_summary`, `relevant_range`, `phases`, `narrative_header`
    - _Requirements: 1.1, 1.4, 1.5, 2.2, 2.3, 3.1, 4.1, 9.2, 10.1, 10.4_

  - [ ]* 5.2 Write property test for noise exclusion from downstream processing
    - **Property 8: Noise events excluded from downstream processing**
    - **Validates: Requirements 9.2, 10.1, 10.4**

  - [x] 5.3 Update `timeline_handler.py` to parse `noise_cutoff_year`
    - Parse optional `noise_cutoff_year` from request body
    - Validate: must be integer, must not be in the future
    - Return 400 VALIDATION_ERROR for invalid values
    - Pass to `reconstruct_timeline`
    - _Requirements: 1.3_

  - [ ]* 5.4 Write unit tests for handler noise_cutoff_year validation
    - Test invalid noise_cutoff_year returns 400
    - Test valid noise_cutoff_year passes through to service
    - Test response contains new fields
    - _Requirements: 1.3_

- [ ] 6. Checkpoint — Verify end-to-end backend pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend: default swim lane view, narrative header, and noise toggle
  - [x] 7.1 Change default view to swim lanes in `src/frontend/investigator.html`
    - Change `tlCurrentView = 'flat'` to `tlCurrentView = 'swimlane'`
    - Update view toggle buttons so "Swim Lanes" has the `active` class by default
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 7.2 Add narrative header banner in `src/frontend/investigator.html`
    - Add `<div id="tlNarrativeHeader">` above the density bar
    - Style: accent color (#48bb78), 14px font, padding 10px
    - Show "Generating investigative summary..." placeholder on load
    - Populate with `data.narrative_header` from response
    - Compute fallback from event data on failure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 7.3 Add noise date toggle in `src/frontend/investigator.html`
    - Add toggle switch in controls row: "Show noise dates"
    - Store `tlNoiseEvents` and `tlNoiseFilterSummary` from response in `loadTimeline`
    - When enabled, merge `filtered_noise_events` into display with muted styling (opacity 0.4, dashed border)
    - When disabled (default), show only relevant events
    - Maintain current viewport when toggling (no re-fit)
    - _Requirements: 1.6, 1.7, 2.4_

- [x] 8. Frontend: quick zoom, phase bands, compact layout, and improved labels
  - [x] 8.1 Add quick zoom preset buttons in `src/frontend/investigator.html`
    - Add 4 buttons next to zoom controls: "1Y", "5Y", "Dense", "All"
    - "Dense" uses `relevant_range` from response
    - "1Y" / "5Y" compute from the latest event timestamp
    - "All" fits to full range including noise
    - Highlight active preset with #48bb78
    - Deselect active preset on manual zoom/pan
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 8.2 Add phase band rendering in `src/frontend/investigator.html`
    - Render phases as horizontal colored bands behind event markers
    - Each phase category gets a distinct semi-transparent background color
    - Hover tooltip shows phase description and event count
    - _Requirements: 3.4, 3.5_

  - [x] 8.3 Apply compact layout changes in `src/frontend/investigator.html`
    - Change `.tl-canvas` from `min-height: 420px` to `min-height: 200px; max-height: 500px`
    - AI panel renders directly below canvas with 8px gap
    - Collapsed AI panel shows single-line "AI Analysis ▸" bar (40px height)
    - Stack density bar, canvas, and AI panel with max 8px spacing
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 8.4 Use `display_label` from response for event markers in `src/frontend/investigator.html`
    - Update `tlEventMarkerHTML` to use `evt.display_label` if available
    - Fall back to existing label logic when `display_label` is absent
    - Set `.tl-event-label` to `max-width: 200px; font-size: 11px; white-space: normal;`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 8.5 Auto-fit viewport to relevant range on load in `src/frontend/investigator.html`
    - In `loadTimeline`, if `relevant_range` is present, compute zoom/pan to fit that range with 5% padding
    - When "Show noise dates" is toggled on, maintain current viewport
    - _Requirements: 2.1, 2.4_

- [ ] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All changes modify existing files — no new service classes or handlers
- No CDK deploy needed — all changes are Lambda code updates
- Property tests use the `hypothesis` library (already in project dependencies)
- Each task references specific requirements for traceability
