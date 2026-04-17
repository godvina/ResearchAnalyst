# Requirements Document

## Introduction

The Geospatial Evidence Map transforms the existing basic Leaflet.js map in the Investigator UI into a professional-grade investigative mapping tool. The current map plots location entities as static circle markers using a hardcoded geocoding lookup of ~15 well-known locations. This feature extends the map with travel pattern visualization (dotted lines between locations), heat map overlays showing activity density, drill-down detail panels for each location, AI-powered geographic analysis, expanded geocoding coverage, and cross-case geographic pattern detection. All changes extend the existing investigator.html — no working code is rewritten or replaced.

## Glossary

- **Evidence_Map**: The Leaflet.js-based interactive map component within the Investigator UI that displays location entities and their relationships from case data
- **Geocoding_Service**: A backend module that resolves location entity names to latitude/longitude coordinates using an expanded lookup table and fuzzy matching against known locations
- **Travel_Line**: A dotted polyline drawn on the Evidence_Map between two location markers to represent a person's movement or connection between those locations, derived from person-location relationship edges in the graph
- **Heat_Layer**: A Leaflet heat map overlay on the Evidence_Map that visualizes the density of entity activity (relationship count) at each geocoded location
- **Drill_Down_Panel**: A side panel or expanded popup displayed when a user clicks a location marker, showing detailed entity connections, document references, and relationship context for that location
- **Geographic_Insight**: An AI-generated analysis of spatial patterns in case data, including clustering, travel frequency, jurisdiction mapping, and anomaly detection
- **Location_Entity**: A row in the Aurora entities table with entity_type = 'location' and an associated case_file_id
- **Person_Location_Edge**: A relationship row or Neptune graph edge connecting a person entity to a location entity within a case
- **Cross_Case_Location**: A location entity name that appears in the entities table across two or more distinct case_file_id values

## Requirements

### Requirement 1: Expanded Geocoding Resolution

**User Story:** As an investigator, I want all location entities in my case to be plotted on the map, so that I get a complete geographic picture rather than only the ~15 hardcoded locations.

#### Acceptance Criteria

1. THE Geocoding_Service SHALL maintain a curated lookup table of at least 200 location-to-coordinate mappings covering common investigative locations (US cities, international capitals, islands, airports, known addresses)
2. WHEN a Location_Entity canonical_name does not match any entry in the curated lookup table, THE Geocoding_Service SHALL attempt fuzzy matching by normalizing the name (lowercase, strip punctuation, remove state/country suffixes) and comparing against the lookup table
3. WHEN fuzzy matching produces a match with a similarity score above 0.8, THE Geocoding_Service SHALL return the matched coordinates
4. WHEN a Location_Entity cannot be resolved by the curated lookup or fuzzy matching, THE Geocoding_Service SHALL return a null coordinate and THE Evidence_Map SHALL exclude that location from rendering
5. THE Geocoding_Service SHALL expose a REST endpoint (POST /case-files/{id}/geocode) that accepts a list of location names and returns coordinates for each
6. FOR ALL location names that resolve to coordinates, geocoding the same name twice SHALL produce identical coordinates (deterministic property)

### Requirement 2: Travel Pattern Visualization

**User Story:** As an investigator, I want to see dotted lines on the map showing travel connections between locations for a selected person, so that I can visualize movement patterns like travel to an island.

#### Acceptance Criteria

1. WHEN a user selects a person from the person filter dropdown, THE Evidence_Map SHALL draw Travel_Lines between all locations connected to that person via Person_Location_Edges
2. THE Evidence_Map SHALL render each Travel_Line as a dashed polyline with directional arrow markers indicating the relationship direction
3. WHEN a user hovers over a Travel_Line, THE Evidence_Map SHALL display a tooltip showing the person name, source location, destination location, and relationship type
4. WHEN the user selects "All Persons" in the filter, THE Evidence_Map SHALL remove all Travel_Lines from the map
5. WHILE travel mode is active, THE Evidence_Map SHALL color-code Travel_Lines by person using distinct colors when multiple persons are selected or visible
6. THE Evidence_Map SHALL retrieve travel connection data from the existing /case-files/{id}/patterns endpoint using the graph edges between person and location nodes

### Requirement 3: Heat Map Overlay

**User Story:** As an investigator, I want a heat map overlay showing the density of activity at each location, so that I can quickly identify geographic hotspots in the case.

#### Acceptance Criteria

1. WHEN the user activates the heat map toggle, THE Evidence_Map SHALL render a Heat_Layer overlay where intensity at each geocoded location is proportional to the total relationship count (number of edges connected to that Location_Entity)
2. THE Heat_Layer SHALL use a color gradient from cool (blue, low activity) to hot (red, high activity)
3. WHEN the heat map toggle is deactivated, THE Evidence_Map SHALL remove the Heat_Layer and restore the standard circle marker view
4. THE Heat_Layer SHALL update dynamically when the user changes the person filter, showing heat only for locations connected to the selected person
5. THE Evidence_Map SHALL load the Leaflet.heat plugin from CDN to render the Heat_Layer

### Requirement 4: Location Drill-Down Detail

**User Story:** As an investigator, I want to click on a location pin and see detailed information about all entities, relationships, and documents connected to that location, so that I can investigate a specific geographic area in depth.

#### Acceptance Criteria

1. WHEN a user clicks a location marker on the Evidence_Map, THE Drill_Down_Panel SHALL display a detailed view containing: the location name, all connected person entities, all connected organization entities, all connected event entities, and the total relationship count
2. THE Drill_Down_Panel SHALL group connected entities by entity type (persons, organizations, events, other) with counts for each group
3. WHEN the Drill_Down_Panel is open, THE Drill_Down_Panel SHALL list up to 10 source documents that mention the location, retrieved from the entity_document_links table via a backend query
4. WHEN a user clicks a document reference in the Drill_Down_Panel, THE Drill_Down_Panel SHALL navigate to or highlight that document in the evidence viewer
5. THE Drill_Down_Panel SHALL display a mini relationship graph showing the location node and its immediate neighbors (1-hop) using a simple force-directed layout or structured list
6. IF the backend query for drill-down data fails, THEN THE Drill_Down_Panel SHALL display an error message with the failure reason and a retry button
7. THE Evidence_Map SHALL expose drill-down data via a new REST endpoint (POST /case-files/{id}/map/location-detail) that accepts a location entity name and returns connected entities, relationships, and document references

### Requirement 5: AI Geographic Insights

**User Story:** As an investigator, I want AI-generated analysis of geographic patterns in my case, so that I can identify clusters, unusual travel patterns, and jurisdictional considerations without manual analysis.

#### Acceptance Criteria

1. WHEN the user clicks the AI geographic analysis button, THE Evidence_Map SHALL send all geocoded locations with their connection counts and person associations to the backend for AI analysis
2. THE Geographic_Insight engine SHALL use the Bedrock Haiku model (anthropic.claude-3-haiku-20240307-v1:0) to generate analysis covering: geographic clustering of activity, high-frequency travel corridors, jurisdictional observations (state/federal/international), and anomalous location patterns
3. THE Evidence_Map SHALL display the AI analysis results in a formatted panel overlaid on or adjacent to the map, with sections for each insight category
4. WHEN AI analysis is in progress, THE Evidence_Map SHALL display a loading indicator with the text "Analyzing geographic patterns..."
5. IF the AI analysis request fails, THEN THE Evidence_Map SHALL display an error message and allow the user to retry
6. THE Geographic_Insight engine SHALL include the specific location names and person names in the analysis prompt so the output references actual case entities

### Requirement 6: Cross-Case Geographic Patterns

**User Story:** As an investigator, I want to see which locations in my case also appear in other cases, so that I can identify geographic overlaps that may indicate broader patterns.

#### Acceptance Criteria

1. WHEN the user activates the cross-case overlay toggle, THE Evidence_Map SHALL query the entities table for Cross_Case_Locations that share a canonical_name with entity_type = 'location' across different case_file_id values
2. THE Evidence_Map SHALL visually distinguish Cross_Case_Locations from single-case locations using a different marker style (double-ring or contrasting color)
3. WHEN a user clicks a Cross_Case_Location marker, THE Drill_Down_Panel SHALL display the list of case names where that location appears, in addition to the standard drill-down detail
4. THE Evidence_Map SHALL retrieve cross-case location data via a new REST endpoint (POST /map/cross-case-locations) that accepts a case_file_id and returns locations shared with other cases along with the overlapping case identifiers
5. IF no Cross_Case_Locations exist for the current case, THEN THE Evidence_Map SHALL display a brief notification indicating no cross-case geographic overlaps were found

### Requirement 7: Professional Map UX and Controls

**User Story:** As an investigator, I want a polished, professional map interface with intuitive controls, so that the tool feels like top-tier investigative software.

#### Acceptance Criteria

1. THE Evidence_Map SHALL display a control panel with clearly labeled toggle buttons for: Heat Map, Travel Lines, Cross-Case Overlay, and AI Analysis
2. THE Evidence_Map SHALL display a legend panel showing the meaning of marker colors, marker sizes, Travel_Line styles, and Heat_Layer gradient
3. WHEN the map loads, THE Evidence_Map SHALL auto-fit the map bounds to encompass all plotted location markers with appropriate padding
4. THE Evidence_Map SHALL display a location count badge showing the number of geocoded locations out of total Location_Entities (e.g., "47/52 locations mapped")
5. WHEN the user double-clicks a location marker, THE Evidence_Map SHALL zoom the map to that location at zoom level 12 and open the Drill_Down_Panel
6. THE Evidence_Map SHALL support a fullscreen toggle that expands the map to fill the browser viewport
7. THE Evidence_Map SHALL maintain the dark theme consistent with the existing CARTO dark tile layer and the Investigator UI color scheme

### Requirement 8: AI Insight Cards

**User Story:** As an investigator, I want to see AI-generated insight summaries directly on the map next to each location marker, so that I can immediately understand the investigative significance of each location without clicking.

#### Acceptance Criteria

1. WHEN the map loads, THE Evidence_Map SHALL display an AI Insight Card next to each location marker containing: the location name, a role classification (Hub or Node based on connection count), the top 2 connected person names, and a contextual "so what" summary
2. THE AI Insight Card SHALL classify locations with 5 or more connections as "Hub" and others as "Node"
3. THE "so what" summary SHALL describe the investigative significance based on the types and counts of connected entities (e.g., "Key coordination point — 5 persons, 3 orgs intersect here")
4. THE AI Insight Cards SHALL be semi-transparent dark-themed overlays that are always visible without requiring hover or click interaction
5. THE AI Insight Cards SHALL not interfere with marker click events for drill-down

### Requirement 9: Entity Geo-Drill (Graph-to-Map Navigation)

**User Story:** As an investigator, I want to select an entity from the network graph and see its geographic footprint on the map, so that I can understand the spatial dimension of a specific person or organization's activity.

#### Acceptance Criteria

1. WHEN a user clicks "Show on Map" from an entity card in the network graph drill-down, THE Evidence_Map SHALL filter to show only locations connected to that specific entity
2. THE Evidence_Map SHALL draw travel arcs between the filtered locations showing the entity's geographic reach
3. THE Evidence_Map SHALL display an AI narrative summarizing the entity's geographic pattern (e.g., "Subject traveled between NY and Virgin Islands across 47 documents")
4. THE Evidence_Map SHALL provide a "Back to Full Map" button to restore the case-wide view
5. THE Entity Geo-Drill SHALL work for persons, organizations, and any entity type that has location connections in the graph

### Requirement 10: Static Professional Markers

**User Story:** As an investigator, I want map markers that are stable, professional, and easy to click, so that the map feels like a serious investigative tool rather than a flashy animation.

#### Acceptance Criteria

1. THE Evidence_Map SHALL render location markers as static circle markers with NO animation, pulsing, or scaling effects
2. THE Evidence_Map markers SHALL use color coding: red (#fc8181) for Hub locations (5+ connections), blue (#4a9eff) for Node locations
3. THE Evidence_Map SHALL auto-fit zoom tightly to encompass only the plotted markers with minimal padding, eliminating unnecessary ocean or empty space
4. THE Evidence_Map SHALL support click events on markers to open the drill-down panel reliably

### Requirement 11: Entity Photo Avatars on Knowledge Graph

**User Story:** As an investigator, I want to see photo avatars or initials on person nodes in the knowledge graph, so that the graph looks like a professional investigation wall and I can visually identify key subjects at a glance.

#### Acceptance Criteria

1. THE Knowledge Graph SHALL render person entity nodes with color-coded initial avatars (e.g., "JE" for Jeffrey Epstein) using inline SVG data URIs for known key figures
2. THE Knowledge Graph SHALL support a toggle button ("📷 Photos") that switches between three display modes: initials (default), evidence photos (from Rekognition face crops), and plain dots
3. WHEN evidence face photos are available for a person entity in S3, THE Knowledge Graph SHALL render those as circular image nodes using presigned S3 URLs
4. THE entity photo system SHALL work across all graph views: main graph, focused ego graph, drill-down SVG radial graph, thread network mini graph, multi-select analysis graph, and entity neighborhood graph
5. THE initial avatar colors SHALL be distinct per person to aid visual identification

### Requirement 12: Rekognition Face Crop Pipeline (Future)

**User Story:** As an investigator, I want the system to automatically extract and store face thumbnails from evidence photos during Rekognition processing, so that identified persons can be displayed with their actual face on the investigation graph.

#### Acceptance Criteria

1. DURING Rekognition image processing, WHEN a face is detected with confidence >= 90%, THE system SHALL crop the bounding box region from the source image and save a 100x100px JPEG thumbnail
2. THE face crop SHALL be stored at `s3://bucket/cases/{case_id}/face-crops/{entity_name}/{hash}.jpg`
3. THE face crop S3 key SHALL be stored as a vertex property (`face_thumbnail_url`) on the corresponding Neptune entity node
4. A new API endpoint (GET /case-files/{id}/entity-photos) SHALL return a mapping of entity names to presigned S3 URLs for face thumbnails
5. THE frontend SHALL fetch entity photos on graph load and use them for `circularImage` nodes when the photo display mode is active
6. WHEN multiple face crops exist for the same entity, THE system SHALL select the highest-confidence crop as the primary thumbnail

### Requirement 13: Video Intelligence — Tiered Analysis (Future)

**User Story:** As an investigator, I want the system to process video evidence at multiple depth levels, so that I can quickly identify which videos contain relevant content and then dive deeper into specific segments.

#### Acceptance Criteria

1. Tier 1 (Automated Triage): THE ingestion pipeline SHALL run Rekognition `StartLabelDetection` and `StartFaceDetection` on video files to flag timestamps with investigatively relevant content (persons, weapons, vehicles, documents, currency)
2. Tier 1 results SHALL be stored as structured metadata in S3 (`cases/{case_id}/video-analysis/{filename}.json`) with timestamp ranges, detected labels, and confidence scores
3. Tier 2 (On-Demand Deep Dive): WHEN an investigator clicks "Analyze Deeper" on a flagged video, THE system SHALL run `StartCelebrityRecognition`, `StartContentModeration`, and extract key frames at flagged timestamps
4. Tier 2 key frames SHALL be stored in S3 and linked to the video entity in Neptune with timestamp metadata
5. Tier 3 (Human Review): THE UI SHALL present flagged video segments with start/end timestamps, allowing the investigator to play just the relevant clip with AI-generated annotations overlaid
6. THE video analysis results SHALL feed into the entity graph — persons detected in video SHALL create edges to the video document entity with timestamp metadata

### Requirement 14: Audio Intelligence — Transcription and Speaker Analysis (Future)

**User Story:** As an investigator, I want audio and video files to be transcribed with speaker identification, so that I can search spoken content and identify who said what.

#### Acceptance Criteria

1. THE ingestion pipeline SHALL support Amazon Transcribe for speech-to-text on audio files (.mp3, .wav, .m4a) and video files (.mp4, .mov)
2. THE transcription output SHALL include speaker diarization (Speaker 0, Speaker 1, etc.) with timestamps
3. THE transcribed text SHALL be indexed in OpenSearch alongside document text, enabling semantic search across spoken content
4. WHEN a known entity name is mentioned in a transcript, THE system SHALL create an edge in Neptune linking the speaker segment to the mentioned entity
5. THE UI SHALL display transcripts with speaker labels, timestamps, and clickable segments that jump to the audio/video playback position
6. THE system SHALL flag segments where multiple key entities are mentioned together as high-priority investigative leads
