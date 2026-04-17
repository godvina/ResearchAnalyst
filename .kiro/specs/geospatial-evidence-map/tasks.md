# Implementation Plan: Geospatial Evidence Map

## Overview

Extend the existing Investigator UI map and backend services to provide expanded geocoding, travel pattern visualization, heat map overlays, location drill-down, AI geographic insights, and cross-case geographic overlap detection. All backend changes are Lambda code updates — no CDK deploy or migrations needed. Frontend changes extend existing stubs in investigator.html.

## Tasks

- [x] 1. Create GeocodingService with curated lookup and fuzzy matching
  - [x] 1.1 Create `src/services/geocoding_service.py` with `GeocodingService` class
    - Implement `CURATED_LOCATIONS` dict with 200+ location-to-coordinate mappings (US cities, international capitals, islands, airports, known addresses)
    - Implement `_normalize(name)` — lowercase, strip punctuation, remove state/country suffixes
    - Implement `_fuzzy_match(normalized)` using `difflib.SequenceMatcher` with 0.8 threshold, tie-break alphabetically
    - Implement `geocode(names)` — resolve list of names via exact lookup then fuzzy match, return `{name: {lat, lng} | None}`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [ ]* 1.2 Write property tests for GeocodingService normalization and geocoding
    - **Property 1: Normalization produces lowercase punctuation-free output**
    - **Property 2: Fuzzy match threshold determines resolution**
    - **Property 3: Geocoding determinism**
    - **Property 9: Geocode response counts are consistent**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.6, 1.5**
    - Create `tests/unit/test_geocoding_service.py`

  - [ ]* 1.3 Write unit tests for GeocodingService
    - Test curated lookup has >= 200 entries (Req 1.1)
    - Test exact match returns correct coordinates
    - Test fuzzy match above 0.8 resolves, below 0.8 returns None
    - Test unresolvable name returns None
    - Test determinism — same name twice yields same result
    - _Requirements: 1.1, 1.3, 1.4, 1.6_

- [x] 2. Add geocode and map endpoints to case_files.py dispatcher
  - [x] 2.1 Add geocode handler and route in `src/lambdas/api/investigator_analysis.py`
    - Add `geocode_handler(event, context)` — parse `locations` list from body, call `GeocodingService.geocode()`, return `{geocoded, unresolved, total, resolved}`
    - _Requirements: 1.5, 7.4_

  - [x] 2.2 Add location-detail handler in `src/lambdas/api/investigator_analysis.py`
    - Add `location_detail_handler(event, context)` — parse `location_name` from body, query Aurora `entities`/`relationships`/`entity_document_links` tables, query Neptune 1-hop neighbors via `get_entity_neighborhood`, return grouped entities (persons, organizations, events, other), up to 10 documents, and neighbors list
    - Handle Neptune unreachable gracefully — return partial result with `neighbors: []`
    - Return 404 for non-existent location entity
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.7_

  - [x] 2.3 Add AI map analysis handler in `src/lambdas/api/investigator_analysis.py`
    - Add `ai_map_analysis_handler(event, context)` — parse locations data from body, call `InvestigatorAIEngine.analyze_geography()`, return structured analysis
    - Handle Bedrock timeout (504) and throttle (429) errors
    - _Requirements: 5.1, 5.5_

  - [x] 2.4 Add cross-case locations handler in `src/lambdas/api/investigator_analysis.py`
    - Add `cross_case_locations_handler(event, context)` — call `GeocodingService.cross_case_locations()`, return shared locations with case names and counts
    - Return 404 for invalid case_file_id, return empty list when no overlaps found
    - _Requirements: 6.1, 6.4, 6.5_

  - [x] 2.5 Wire new routes into `case_files.py` mega-dispatcher and `investigator_analysis.py` dispatch_handler
    - Add path matching for `/geocode`, `/map/location-detail`, `/map/ai-analysis` under `/case-files/{id}/` in `case_files.py` to route to `investigator_analysis` dispatch
    - Add path matching for `/map/cross-case-locations` in `case_files.py`
    - Add route entries in `investigator_analysis.py` `dispatch_handler` routes dict
    - _Requirements: 1.5, 4.7, 6.4_


- [x] 3. Extend InvestigatorAIEngine with geography methods
  - [x] 3.1 Add `get_location_detail()` method to `InvestigatorAIEngine` in `src/services/investigator_ai_engine.py`
    - Query Aurora `entities` table for the location entity by canonical_name and case_file_id
    - Query `relationships` table for all edges involving that entity, group connected entities by type (persons, organizations, events, other)
    - Query `entity_document_links` for up to 10 documents mentioning the location
    - Call `get_entity_neighborhood()` for 1-hop Neptune neighbors, catch Neptune errors gracefully
    - Return structured dict matching the design schema
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [x] 3.2 Add `analyze_geography()` method to `InvestigatorAIEngine` in `src/services/investigator_ai_engine.py`
    - Build prompt that includes all location names, person names, coordinates, and connection counts
    - Call `_invoke_bedrock()` with model `anthropic.claude-3-haiku-20240307-v1:0`
    - Parse response into sections: clustering, travel_corridors, jurisdictional, anomalies
    - _Requirements: 5.2, 5.6_

  - [x] 3.3 Add `cross_case_locations()` method to `GeocodingService` in `src/services/geocoding_service.py`
    - Query Aurora `entities` table for locations with same canonical_name across different case_file_ids
    - Join with `case_files` table to get case names
    - Return list of `{location, cases: [{case_id, case_name}], case_count}`
    - _Requirements: 6.1, 6.3_

  - [ ]* 3.4 Write property tests for location detail and AI analysis
    - **Property 6: Location detail returns grouped entities with document limit**
    - **Property 7: AI geographic prompt includes entity names and covers all categories**
    - **Property 8: Cross-case locations include all overlapping cases**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5, 5.2, 5.6, 6.1, 6.3**

  - [ ]* 3.5 Write unit tests for backend handlers
    - Test geocode endpoint returns correct response shape (Req 1.5)
    - Test location detail 404 for non-existent location (Req 4.6)
    - Test AI analysis sends correct payload structure (Req 5.1)
    - Test AI analysis error returns retry-able response (Req 5.5)
    - Test cross-case endpoint returns empty list when no overlaps (Req 6.5)

- [x] 4. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Extend frontend loadMap() to use backend geocoding
  - [x] 5.1 Extend `loadMap()` in `src/frontend/investigator.html` to call `/geocode` endpoint
    - After fetching nodes/edges from `/patterns`, collect location entity names
    - Call `POST /case-files/{id}/geocode` with the location names list
    - Replace hardcoded `geoLookup` usage with the returned `geocoded` coordinates
    - Keep existing marker rendering logic, just swap coordinate source
    - Display location count badge showing "X/Y locations mapped" (resolved vs total)
    - Auto-fit map bounds to encompass all plotted markers with padding
    - _Requirements: 1.5, 7.3, 7.4_

  - [x] 5.2 Implement `toggleTravelMode()` in `src/frontend/investigator.html`
    - Replace stub with real implementation
    - When person selected in filter, draw dashed polylines between locations connected to that person via graph edges
    - Add directional arrow markers on polylines
    - Add hover tooltip showing person name, source, destination, relationship type
    - Color-code lines by person when multiple visible
    - When "All Persons" selected, remove all travel lines
    - Store travel line layer for toggle on/off
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 5.3 Write property test for travel line extraction
    - **Property 4: Travel line extraction from graph edges**
    - **Validates: Requirements 2.1**

- [x] 6. Implement heat map overlay in frontend
  - [x] 6.1 Implement `toggleMapHeat()` in `src/frontend/investigator.html`
    - Replace stub with real implementation
    - Load Leaflet.heat plugin from CDN (`unpkg.com/leaflet.heat`) on first activation, matching existing Leaflet CDN loading pattern
    - Create heat layer from geocoded locations with intensity proportional to relationship count
    - Use blue-to-red gradient
    - Toggle on/off, removing heat layer when deactivated
    - Update heat data when person filter changes (show only filtered person's locations)
    - Handle CDN load failure with toast "Heat map plugin unavailable"
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 6.2 Write property test for heat map data filtering
    - **Property 5: Heat map data reflects filtered relationship counts**
    - **Validates: Requirements 3.1, 3.4**

- [x] 7. Implement location drill-down and AI analysis in frontend
  - [x] 7.1 Implement `showLocationDrillDown(locationName)` in `src/frontend/investigator.html`
    - Call `POST /case-files/{id}/map/location-detail` with location name
    - Display side panel or expanded popup with: location name, connected entities grouped by type (persons, organizations, events, other), relationship count, up to 10 source documents, 1-hop neighbor list
    - Make document references clickable to navigate to evidence viewer
    - Show error message with retry button on failure
    - Wire to marker click event
    - Wire double-click to zoom level 12 + open drill-down
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 7.5_

  - [x] 7.2 Implement `aiMapAnalysis()` in `src/frontend/investigator.html`
    - Replace stub with real implementation
    - Collect all geocoded locations with connection counts and person associations
    - Call `POST /case-files/{id}/map/ai-analysis`
    - Display loading indicator "Analyzing geographic patterns..."
    - Show results in formatted panel with sections: clustering, travel corridors, jurisdictional, anomalies
    - Show error with retry button on failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.3 Implement `toggleCrossCaseOverlay()` in `src/frontend/investigator.html`
    - Call `POST /map/cross-case-locations` with current case_file_id
    - Render cross-case locations with distinct marker style (double-ring or contrasting color)
    - On click, show overlapping case names in drill-down panel alongside standard detail
    - Show notification toast when no cross-case overlaps found
    - Toggle on/off
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 8. Build professional map controls and UX
  - [x] 8.1 Implement `buildMapControls()` and map UX polish in `src/frontend/investigator.html`
    - Add control panel with labeled toggle buttons: Heat Map, Travel Lines, Cross-Case Overlay, AI Analysis
    - Add legend panel showing marker colors/sizes, travel line styles, heat gradient meaning
    - Add fullscreen toggle that expands map to fill viewport
    - Maintain dark theme consistent with CARTO dark tiles and Investigator UI color scheme
    - _Requirements: 7.1, 7.2, 7.6, 7.7_

- [x] 9. Final checkpoint — All features integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All backend changes are Lambda code updates — no CDK deploy or new migrations needed
- Per lessons-learned.md: EXTEND existing code, never rewrite working modules
- Frontend extends existing stubs: `loadMap()`, `toggleMapHeat()`, `toggleTravelMode()`, `aiMapAnalysis()`
- New routes are added to the existing `case_files.py` mega-dispatcher and `investigator_analysis.py` sub-dispatcher
- Property tests use `hypothesis` library, tagged with feature and property number
- Bedrock model: `anthropic.claude-3-haiku-20240307-v1:0`

- [x] 10. Entity Photo Avatars on Knowledge Graph (Req 11)
  - [x] 10.1 Add ENTITY_PHOTOS map with SVG initial avatars for key Epstein case figures
  - [x] 10.2 Add `_nodeWithPhoto()` helper and `toggleEntityPhotos()` function
  - [x] 10.3 Add 📷 Photos toggle button to Knowledge Graph section header
  - [x] 10.4 Apply photo rendering to all graph views (main, ego, drill-down SVG, mini, multi-select, neighborhood)

- [ ]* 11. Rekognition Face Crop Pipeline (Req 12 — Future)
  - [ ]* 11.1 Extend `rekognition_handler.py` to crop face bounding boxes from source images during processing
  - [ ]* 11.2 Save 100x100px JPEG thumbnails to `s3://bucket/cases/{case_id}/face-crops/{entity_name}/{hash}.jpg`
  - [ ]* 11.3 Store `face_thumbnail_url` as Neptune vertex property on person entities
  - [ ]* 11.4 Create API endpoint `GET /case-files/{id}/entity-photos` returning entity→presigned URL mapping
  - [ ]* 11.5 Update frontend to fetch and render face photos in "evidence photo" display mode

- [ ]* 12. Video Intelligence — Tiered Analysis (Req 13 — Future)
  - [ ]* 12.1 Tier 1: Add video label/face detection to ingestion pipeline with timestamp metadata storage
  - [ ]* 12.2 Tier 1: Store structured video analysis results in S3 (`video-analysis/{filename}.json`)
  - [ ]* 12.3 Tier 2: Add "Analyze Deeper" button in UI triggering celebrity recognition + key frame extraction
  - [ ]* 12.4 Tier 2: Store key frames in S3 linked to video entity in Neptune with timestamps
  - [ ]* 12.5 Tier 3: Build video segment player UI with AI annotations and timestamp navigation
  - [ ]* 12.6 Link video-detected persons to entity graph with timestamp edges

- [ ]* 13. Audio Intelligence — Transcription and Speaker Analysis (Req 14 — Future)
  - [ ]* 13.1 Add Amazon Transcribe integration for audio/video files in ingestion pipeline
  - [ ]* 13.2 Implement speaker diarization output parsing and storage
  - [ ]* 13.3 Index transcribed text in OpenSearch for semantic search across spoken content
  - [ ]* 13.4 Create Neptune edges from transcript entity mentions to speaker segments
  - [ ]* 13.5 Build transcript viewer UI with speaker labels, timestamps, and audio/video playback sync
  - [ ]* 13.6 Flag high-priority segments where multiple key entities co-occur in speech
