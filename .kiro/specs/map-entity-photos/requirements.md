# Requirements Document

## Introduction

This feature adds two capabilities to the investigator UI: (1) entity face crop photos on geospatial map markers, and (2) a full evidence gallery view. The map tab currently shows location nodes as circle markers with insight cards, but does not display the person entities visually on the markers. The network graph already successfully renders entity photos using the `entity-photos` API and base64 data URIs — this feature applies the same pattern to map markers. The evidence gallery provides a new tab where investigators can browse all case evidence visually (documents, images, videos), click into any item to see its graph associations, an AI summary, and related evidence — following the same AI drill-down pattern used by the existing entity intelligence, evidence triage, and investigative leads views.

## Glossary

- **Map_Tab**: The existing geospatial map view in `investigator.html` (tab id `tab-map`) that renders location entities on a Leaflet map with circle markers, travel lines, and insight cards.
- **Map_Marker**: A Leaflet circle marker or custom div marker placed on the Map_Tab at the geocoded coordinates of a location entity.
- **Entity_Photos_API**: The existing `GET /case-files/{id}/entity-photos` endpoint that returns entity name → base64 data URI mappings for face crop thumbnails.
- **Image_Evidence_API**: The existing `GET /case-files/{id}/image-evidence` endpoint that returns paginated image evidence with Rekognition labels and face crop metadata.
- **Evidence_Gallery**: A new tab or section in the investigator UI that displays all evidence items for a case as a visual gallery with filtering and detail views.
- **Evidence_Detail_Panel**: A slide-out panel shown when an investigator clicks an evidence item in the Evidence_Gallery, displaying graph associations, AI summary, and related evidence.
- **AI_Evidence_Summary**: A Bedrock-generated investigative analysis of a single evidence item, following the same prompt and response pattern as the existing entity intelligence AI drill-down.
- **Evidence_Summary_API**: A new `POST /case-files/{id}/evidence-summary` endpoint that generates an AI investigative summary for a specific evidence item.
- **Person_Avatar**: A circular thumbnail (32×32px) showing a person entity's face crop photo, or initials with entity-type color coding as fallback.
- **Neptune_Graph**: The Amazon Neptune graph database storing entities, documents, and their relationships.
- **Investigator_AI_Engine**: The existing service (`investigator_ai_engine.py`) that orchestrates AI analysis using Bedrock.
- **Dispatch_Handler**: The central Lambda router in `case_files.py` that routes all API requests to the correct sub-handler.

## Requirements

### Requirement 1: Display Person Entity Avatars on Map Markers

**User Story:** As an investigator, I want to see face photos of persons associated with a location directly on the map marker, so that I can visually identify who is connected to each location at a glance.

#### Acceptance Criteria

1. WHEN the Map_Tab renders a location marker that has connected person entities, THE Map_Tab SHALL display Person_Avatar thumbnails adjacent to or overlaid on the Map_Marker for each connected person (up to 4 persons).
2. WHEN a connected person entity has a face crop photo available from the Entity_Photos_API, THE Map_Tab SHALL render the Person_Avatar as a circular 32×32px image using the base64 data URI.
3. WHEN a connected person entity has no face crop photo available, THE Map_Tab SHALL render the Person_Avatar as a circular 32×32px element displaying the person's initials with the person entity-type color (`#fc8181` background).
4. WHEN a location has more than 4 connected person entities, THE Map_Tab SHALL display the first 4 Person_Avatars and a "+N" overflow indicator showing the count of additional persons.
5. THE Map_Tab SHALL fetch entity photos from the Entity_Photos_API using the same `fetchEntityPhotos()` function and `ENTITY_PHOTOS` cache already used by the network graph visualization.

### Requirement 2: Map Marker Tooltip with Entity Details

**User Story:** As an investigator, I want to hover over a map marker and see the names and types of all connected entities, so that I can quickly assess a location's significance without clicking.

#### Acceptance Criteria

1. WHEN an investigator hovers over a Map_Marker, THE Map_Tab SHALL display a tooltip showing the location name, the count of connected entities, and a list of connected person names (up to 6).
2. WHEN the tooltip lists a person entity that has a face crop photo, THE tooltip SHALL display a small Person_Avatar (20×20px) next to the person's name.
3. WHEN an investigator clicks a Person_Avatar on a Map_Marker or in the tooltip, THE Map_Tab SHALL open the existing Drill_Down_Panel for that person entity.

### Requirement 3: Evidence Gallery Tab with Visual Grid

**User Story:** As an investigator, I want a dedicated evidence gallery view showing all case evidence as visual thumbnails, so that I can browse and assess evidence visually rather than through text lists.

#### Acceptance Criteria

1. THE Evidence_Gallery SHALL be accessible as a new tab labeled "📸 Evidence" in the investigator UI tab bar.
2. WHEN the Evidence_Gallery tab is activated, THE Evidence_Gallery SHALL fetch evidence items from the Image_Evidence_API and display them as a responsive grid of thumbnail cards.
3. THE Evidence_Gallery SHALL display each evidence item as a card containing: a thumbnail preview (image preview for images, document icon for PDFs, video icon for videos), the filename, the evidence type badge, and the count of associated graph entities.
4. THE Evidence_Gallery SHALL support filtering by evidence type using toggle buttons for "All", "Documents", "Images", and "Videos".
5. WHEN no evidence items match the active filter, THE Evidence_Gallery SHALL display an empty state message indicating no matching evidence was found.

### Requirement 4: Evidence Detail Panel with Graph Associations

**User Story:** As an investigator, I want to click on any evidence item and see which graph entities it is associated with, so that I can understand the investigative context of each piece of evidence.

#### Acceptance Criteria

1. WHEN an investigator clicks an evidence item in the Evidence_Gallery, THE Evidence_Detail_Panel SHALL open as a slide-out panel on the right side of the screen.
2. THE Evidence_Detail_Panel SHALL display the evidence item's filename, type, file size, and a larger preview (image render for images, document metadata for PDFs, video player for videos).
3. THE Evidence_Detail_Panel SHALL query the Neptune_Graph for all entities associated with the evidence item's source document and display them as clickable entity tags grouped by entity type (persons, organizations, locations).
4. WHEN an investigator clicks an entity tag in the Evidence_Detail_Panel, THE Evidence_Detail_Panel SHALL open the existing Drill_Down_Panel for that entity.
5. IF the evidence item has no associated graph entities, THEN THE Evidence_Detail_Panel SHALL display a message indicating no entity associations were found.

### Requirement 5: AI Evidence Summary in Detail Panel

**User Story:** As an investigator, I want an AI-generated investigative summary for each evidence item, so that I can quickly understand the significance of a piece of evidence without reading the full document.

#### Acceptance Criteria

1. WHEN the Evidence_Detail_Panel opens for an evidence item, THE Evidence_Detail_Panel SHALL call the Evidence_Summary_API to generate an AI_Evidence_Summary.
2. THE AI_Evidence_Summary SHALL include: a 2-3 sentence investigative significance assessment, a list of key entities mentioned, a list of investigative questions raised by the evidence, and a priority rating (high, medium, low).
3. THE Evidence_Summary_API SHALL use the same Bedrock invocation pattern (Claude Haiku model, temperature 0.3, max_tokens 1024) as the existing entity intelligence AI drill-down in `patterns.py`.
4. WHILE the AI_Evidence_Summary is loading, THE Evidence_Detail_Panel SHALL display a loading spinner with the text "Generating AI analysis...".
5. IF the Bedrock invocation fails or times out, THEN THE Evidence_Detail_Panel SHALL display a fallback message "AI analysis unavailable — review evidence manually" and log the error.

### Requirement 6: Evidence Summary API Endpoint

**User Story:** As a frontend developer, I want a backend endpoint that generates AI summaries for evidence items, so that the Evidence_Detail_Panel can request analysis on demand.

#### Acceptance Criteria

1. WHEN a POST request is made to `/case-files/{id}/evidence-summary` with a JSON body containing `document_id` and `evidence_type`, THE Evidence_Summary_API SHALL return a JSON response with the AI_Evidence_Summary.
2. THE Evidence_Summary_API SHALL retrieve the document's text content from Aurora and its entity associations from the Neptune_Graph to build the Bedrock prompt context.
3. THE Evidence_Summary_API SHALL return a JSON response containing `significance` (string), `key_entities` (list of objects with name and type), `investigative_questions` (list of objects with question and quick_answer), `recommended_actions` (list of strings), and `priority` (string: high, medium, or low).
4. IF the specified document_id does not exist in the case, THEN THE Evidence_Summary_API SHALL return a 404 error with error code "DOCUMENT_NOT_FOUND".
5. THE Dispatch_Handler SHALL route `POST /case-files/{id}/evidence-summary` requests to the Evidence_Summary_API handler, placed before the catch-all case file routes in the routing chain.

### Requirement 7: Related Evidence in Detail Panel

**User Story:** As an investigator, I want to see evidence items related to the one I'm viewing, so that I can follow investigative threads across multiple pieces of evidence.

#### Acceptance Criteria

1. WHEN the Evidence_Detail_Panel displays an evidence item, THE Evidence_Detail_Panel SHALL show a "Related Evidence" section listing up to 8 evidence items that share at least one graph entity with the current item.
2. THE Evidence_Detail_Panel SHALL determine related evidence by querying the Neptune_Graph for documents connected to the same entities as the current evidence item.
3. WHEN an investigator clicks a related evidence item, THE Evidence_Detail_Panel SHALL navigate to that evidence item's detail view, updating the panel content.
4. IF no related evidence items are found, THEN THE Evidence_Detail_Panel SHALL display a message indicating no related evidence was found.

### Requirement 8: Evidence Summary API Routing and Integration Test

**User Story:** As a developer, I want the evidence-summary endpoint properly routed and integration-tested, so that the deployment does not break existing routes.

#### Acceptance Criteria

1. THE Dispatch_Handler SHALL include a routing rule for `POST /case-files/{id}/evidence-summary` that matches the path pattern `/evidence-summary` within `/case-files/` paths.
2. WHEN a dispatch_handler integration test sends a realistic API Gateway proxy event with path `/case-files/{test-uuid}/evidence-summary` and httpMethod `POST`, THE Dispatch_Handler SHALL route to the evidence_summary_handler and return a status code that is not 404.
3. WHEN a dispatch_handler integration test sends a realistic API Gateway proxy event with path `/case-files/{test-uuid}/entity-photos` and httpMethod `GET`, THE Dispatch_Handler SHALL route to the entity_photos_handler and return a status code that is not 404.
4. WHEN a dispatch_handler integration test sends a realistic API Gateway proxy event with path `/case-files/{test-uuid}/image-evidence` and httpMethod `GET`, THE Dispatch_Handler SHALL route to the image_evidence_handler and return a status code that is not 404.

### Requirement 9: Map Entity Photo Loading and Caching

**User Story:** As an investigator, I want entity photos on the map to load efficiently without redundant API calls, so that the map renders quickly even with many location markers.

#### Acceptance Criteria

1. WHEN the Map_Tab loads and entity photos have already been fetched for the current case (via the network graph or a previous map load), THE Map_Tab SHALL reuse the cached `ENTITY_PHOTOS` object without making an additional API call.
2. WHEN the Map_Tab loads and entity photos have not been fetched for the current case, THE Map_Tab SHALL call `fetchEntityPhotos()` once before rendering markers.
3. WHEN a new case is selected, THE Map_Tab SHALL clear the cached entity photos and re-fetch from the Entity_Photos_API on the next map load.
