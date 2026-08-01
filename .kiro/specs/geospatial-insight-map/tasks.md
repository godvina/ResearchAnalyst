# Implementation Plan: Geospatial Insight Map

## Overview

Add an interactive Leaflet.js map panel to the Pattern Library drill-down, showing geographic coordinates generated on-demand by Bedrock Claude Haiku. The backend implements a new `level_coordinates.py` handler mirroring the existing `level_summary.py` pattern. The frontend renders markers on an OpenStreetMap-tiled Leaflet map below the AI Insight panel.

## Tasks

- [ ] 1. Create coordinate prompt builder service
  - [ ] 1.1 Create `src/services/coordinate_prompt_builder.py` with `CoordinatePromptBuilder` class
    - Implement `build_prompt(level, context_key, taxonomy_data)` returning `{system, messages, max_tokens}` dict
    - Implement `_gather_context(level, context_key, taxonomy_data)` to extract node name, description, and domain context
    - Define `COORDINATE_SYSTEM_PROMPT` constant instructing Bedrock to return 3-8 sites as JSON array with keys: name, lat, lng, description
    - Define `CRIME_INSTRUCTION` and `ANCIENT_MYSTERIES_INSTRUCTION` domain-specific constants
    - Select domain-appropriate instructions based on the taxonomy node's domain
    - _Requirements: 1.4, 1.5, 1.6, 9.1_

  - [ ]* 1.2 Write property test for domain-aware prompt construction
    - **Property 1: Domain-aware prompt construction**
    - Generate random taxonomy node dicts (varying domain, name, description), invoke `CoordinatePromptBuilder.build_prompt()`, assert prompt contains node name + description + domain-appropriate instructions
    - **Validates: Requirements 1.4, 1.5, 1.6, 9.1**

- [ ] 2. Implement coordinate response parsing and validation
  - [ ] 2.1 Add parsing and validation functions to `src/lambdas/api/level_coordinates.py`
    - Implement `_parse_coordinate_response(raw_text: str) -> list[dict]` — strips markdown fencing/preamble, parses JSON array
    - Implement `_validate_coordinate(obj: dict) -> bool` — checks lat ∈ [-90, 90], lng ∈ [-180, 180], non-empty name and description (≤200 chars)
    - Implement count enforcement: return empty array if fewer than 3 valid sites, pass through 3-8 sites
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 1.8_

  - [ ]* 2.2 Write property test for coordinate validation
    - **Property 2: Coordinate validation filters invalid entries**
    - Generate random lists of coordinate dicts with lat/lng values spanning [-200, 200], run through `_validate_coordinate()` filter, assert only valid ones survive
    - **Validates: Requirements 9.2, 9.3**

  - [ ]* 2.3 Write property test for markdown-tolerant JSON parsing
    - **Property 3: Markdown-tolerant JSON parsing**
    - Generate random valid JSON arrays, wrap in various markdown patterns (```json ... ```, preamble + JSON, bare JSON), feed to `_parse_coordinate_response()`, assert correct extraction. Also generate random non-JSON strings, assert empty result
    - **Validates: Requirements 9.4, 9.5**

  - [ ]* 2.4 Write property test for result count enforcement
    - **Property 4: Result count enforcement**
    - Generate random validated coordinate lists of length 0-10, apply count enforcement, assert empty for <3 and passthrough for 3-8
    - **Validates: Requirements 1.1, 1.8**

- [ ] 3. Implement the coordinate handler module
  - [ ] 3.1 Create `src/lambdas/api/level_coordinates.py` with GET handler
    - Implement `get_coordinates_handler(event, context)` mirroring `get_summary_handler` pattern
    - Add input validation: level must be in {domain, typology, method, signature, precedent_case}, context_key must be non-empty and ≤256 chars
    - Implement cache-first flow: check cache with `geo:` prefixed key → if hit, return cached coordinates
    - Implement rate limiting: call `check_and_increment()` on shared `SummaryRateLimiter` singleton
    - If rate limited + stale cache ≤24h: serve stale with `is_throttled: true`
    - If rate limited + no cache: return 429 with Retry-After header
    - Implement Bedrock invocation via `_invoke_bedrock()` with same client config (10s read timeout, 5s connect timeout, max_attempts=1)
    - Parse response, validate coordinates, enforce count, store in cache with `geo:` prefix
    - Return JSON response with: coordinates, generated_at, is_cached, is_stale, is_throttled, taxonomy_level
    - Log Bedrock invocations with context_key, token counts, and latency_ms
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.6, 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 3.2 Implement `invalidate_coordinates_handler(event, context)` in the same module
    - POST endpoint to invalidate cached coordinates by path prefix or all `geo:`-prefixed entries
    - Mirror the existing `invalidate_handler` pattern from `level_summary.py`
    - _Requirements: 2.5_

  - [ ]* 3.3 Write property test for input validation
    - **Property 6: Input validation rejects invalid parameters**
    - Generate random strings (including valid levels for negative testing), call handler with them, assert appropriate HTTP status codes (400 for invalid level, 400 for empty/oversized context_key)
    - **Validates: Requirements 6.3, 6.4**

  - [ ]* 3.4 Write property test for API response schema completeness
    - **Property 7: API response schema completeness**
    - Generate valid coordinate sets, run through full handler (mocked Bedrock), assert response contains all required fields: coordinates (array), generated_at (string), is_cached (boolean), is_throttled (boolean), taxonomy_level (string). Each coordinate object has: name (string), lat (number), lng (number), description (string)
    - **Validates: Requirements 6.2, 1.2**

- [ ] 4. Checkpoint - Ensure backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Register coordinate routes in the dispatcher
  - [ ] 5.1 Add `/pattern-library/coordinates/` route block to `src/lambdas/api/case_files.py`
    - Insert route matching BEFORE the existing `/pattern-library/summary/` block
    - Handle `POST /pattern-library/coordinates/invalidate` → `invalidate_coordinates_handler`
    - Handle `GET /pattern-library/coordinates/{level}/{context_key}` → `get_coordinates_handler`
    - Extract level and context_key from path parts (same pattern as summary routes)
    - Return 404 for unmatched methods
    - _Requirements: 6.1_

  - [ ]* 5.2 Write unit tests for coordinate route dispatch
    - Test that GET requests route to `get_coordinates_handler`
    - Test that POST invalidate routes to `invalidate_coordinates_handler`
    - Test that invalid paths return 404
    - _Requirements: 6.1_

- [ ] 6. Implement cache round-trip with geo: prefix
  - [ ] 6.1 Verify `SummaryCacheManager` works with `geo:` prefixed keys (no code changes expected)
    - Confirm that `store_summary()` and `get_cached()` function correctly when `context_key` starts with `geo:`
    - Add any necessary documentation comments if behavior is implicit
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 6.2 Write property test for cache round-trip
    - **Property 5: Cache round-trip preserves coordinate data**
    - Generate random coordinate arrays, serialize + store via `SummaryCacheManager` with `geo:` prefix, retrieve, assert equality
    - **Validates: Requirements 2.1**

- [ ] 7. Checkpoint - Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Add Leaflet map panel to frontend
  - [ ] 8.1 Add map panel HTML and CSS to `src/frontend/pattern-library.html`
    - Add Leaflet.js CSS link from unpkg CDN in the `<head>` section
    - Add map panel HTML below the AI Insight panel div: container, header (🗺️ Geographic Context label, status span, toggle button), body with `#leafletMap` div (height: 350px)
    - Add CSS styles for `.map-panel`, `.map-panel-header`, `.map-panel-body`, `.map-label`, `.map-status`, `.map-toggle-btn` matching the existing AI Insight panel aesthetic
    - Default panel to `display:none` (shown when coordinates load)
    - _Requirements: 4.1, 4.5, 5.1_

  - [ ] 8.2 Add Leaflet.js script and map rendering JavaScript
    - Load Leaflet.js from unpkg CDN (script tag before map logic)
    - Implement `renderMap(coordinates)` — initializes Leaflet map, adds OpenStreetMap tile layer, places markers with popups (name + description), auto-fits bounds with padding
    - Implement `toggleMapPanel()` — toggles panel body visibility, updates button label (Show Map / Hide Map)
    - Implement `triggerMapCoordinates()` — called alongside `triggerAiSummary()` on navigation, fetches coordinates and renders map
    - Implement `fetchCoordinates(level, contextKey)` — mirrors `fetchSummary()` pattern, calls GET endpoint, handles errors, shows loading state
    - Handle empty coordinate set: display "No geographic data available for this node" message
    - Handle throttled response: show "Throttled" status indicator
    - Handle network errors: show dismissible error message without disrupting taxonomy content
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7, 5.1, 5.2, 5.3, 5.4, 5.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 8.3 Write property test for marker-to-coordinate bijection (fast-check)
    - **Property 8: Marker-to-coordinate bijection**
    - Generate random coordinate arrays (3-8 items), call `renderMap()` logic, assert marker count matches and positions correspond to lat/lng of coordinate objects
    - **Validates: Requirements 4.2**

- [ ] 9. Wire navigation to trigger map coordinates
  - [ ] 9.1 Integrate `triggerMapCoordinates()` into the Pattern Library navigation flow
    - Call `triggerMapCoordinates()` in the same places `triggerAiSummary()` is called (drill-down navigation handlers)
    - Use the same context_key construction logic as the AI Insight panel (domain_id/typology_id/method_id path format)
    - Reset map panel to expanded state on navigation change
    - Hide map panel when at top-level domains view with no specific node selected
    - _Requirements: 8.1, 8.2, 5.4, 5.5_

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend uses Python (pytest + hypothesis); Frontend property tests use fast-check (JavaScript)
- The existing `SummaryCacheManager` and `SummaryRateLimiter` require no modifications — only reuse with `geo:` prefixed keys
- Leaflet.js and OpenStreetMap tiles require no API keys

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "2.3", "2.4"] },
    { "id": 2, "tasks": ["3.1", "3.2"] },
    { "id": 3, "tasks": ["3.3", "3.4", "5.1", "6.1"] },
    { "id": 4, "tasks": ["5.2", "6.2", "8.1"] },
    { "id": 5, "tasks": ["8.2"] },
    { "id": 6, "tasks": ["8.3", "9.1"] }
  ]
}
```
