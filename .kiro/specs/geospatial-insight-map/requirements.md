# Requirements Document

## Introduction

Add an interactive geospatial map panel to the Pattern Library's drill-down view in the Research Analyst / Investigative Intelligence platform. The map appears below the existing AI Insight panel when a user navigates to any taxonomy level (Domain, Typology, Method, Signature, Precedent Case). Map coordinates are generated on-demand by Amazon Bedrock (Claude Haiku), cached in Aurora using the same pattern as AI summaries, and rendered via Leaflet.js with OpenStreetMap tiles. The feature supports both Crime Typology and Ancient Mysteries domains.

## Glossary

- **Map_Panel**: The interactive geospatial map UI component displayed below the AI Insight panel at each taxonomy level in the Pattern Library drill-down view
- **Coordinate_Service**: The backend service that generates geographic coordinates via Bedrock and manages coordinate caching in Aurora
- **Taxonomy_Node**: A specific item at any level of the Pattern Library hierarchy (Domain, Typology, Method, Signature, or Precedent Case)
- **Marker**: A visual indicator placed on the Map_Panel at a specific latitude/longitude representing a geographic site relevant to the current Taxonomy_Node
- **Bedrock_Client**: The Amazon Bedrock Runtime client configured to invoke Claude Haiku for coordinate generation
- **Coordinate_Cache**: The Aurora database table storing previously generated coordinate sets to avoid redundant Bedrock calls
- **Rate_Limiter**: The existing rate limiting mechanism that caps Bedrock invocations to 60 per clock hour across all features (summaries and coordinates combined)
- **Leaflet_Map**: The Leaflet.js map instance rendered using OpenStreetMap tile layers loaded from CDN
- **Toggle_Button**: The Show Map / Hide Map button that allows users to collapse or expand the Map_Panel

## Requirements

### Requirement 1: Coordinate Generation via Bedrock

**User Story:** As a research analyst, I want geographic coordinates generated for the current taxonomy node, so that I can visualize where relevant patterns, cases, or sites are located on a map.

#### Acceptance Criteria

1. WHEN a user navigates to a Taxonomy_Node, THE Coordinate_Service SHALL invoke the Bedrock_Client to generate between 3 and 8 geographic site objects relevant to that Taxonomy_Node
2. THE Coordinate_Service SHALL include in each site object a latitude (decimal degrees), a longitude (decimal degrees), a site name (string), and a brief description (one sentence)
3. THE Coordinate_Service SHALL use the Claude Haiku model (anthropic.claude-3-haiku-20240307-v1:0) for coordinate generation
4. THE Coordinate_Service SHALL include the Taxonomy_Node's name, description, and domain context in the prompt sent to the Bedrock_Client
5. WHEN the Taxonomy_Node belongs to the Crime Typology domain, THE Coordinate_Service SHALL instruct the Bedrock_Client to identify cities or regions where precedent cases or pattern instances occurred
6. WHEN the Taxonomy_Node belongs to the Ancient Mysteries domain, THE Coordinate_Service SHALL instruct the Bedrock_Client to identify actual archaeological or historical sites (pyramids, temples, ley line endpoints, geological formations)
7. THE Coordinate_Service SHALL return coordinates with a precision tolerance of approximately 10 kilometers for ancient sites and named cities
8. IF the Bedrock_Client returns fewer than 3 sites or an unparseable response, THEN THE Coordinate_Service SHALL return an empty coordinate set and log a warning

### Requirement 2: Coordinate Caching

**User Story:** As a platform operator, I want coordinate results cached in Aurora, so that redundant Bedrock calls are avoided and response times stay fast for repeated views.

#### Acceptance Criteria

1. WHEN the Coordinate_Service generates a coordinate set for a Taxonomy_Node, THE Coordinate_Cache SHALL store the result keyed by the node's context_key
2. WHEN a coordinate request arrives for a context_key that exists in the Coordinate_Cache and has not expired, THE Coordinate_Service SHALL return the cached result without invoking the Bedrock_Client
3. THE Coordinate_Cache SHALL expire entries after 7 days from generation time
4. WHEN a cached entry has expired but is less than 24 hours past expiry, THE Coordinate_Service SHALL serve the stale entry if the Rate_Limiter blocks regeneration
5. WHEN the taxonomy data is re-indexed, THE Coordinate_Cache SHALL invalidate all coordinate entries for the affected path prefix
6. IF a cache write fails, THEN THE Coordinate_Service SHALL log the error and still return the generated coordinates to the caller

### Requirement 3: Rate Limiting

**User Story:** As a platform operator, I want coordinate generation to share the existing Bedrock rate limit, so that total Bedrock costs and API usage remain controlled.

#### Acceptance Criteria

1. THE Coordinate_Service SHALL count each Bedrock invocation for coordinates toward the same 60-invocations-per-clock-hour limit used by AI summaries
2. WHEN the Rate_Limiter has reached 60 invocations in the current clock hour, THE Coordinate_Service SHALL not invoke the Bedrock_Client for new coordinate generation
3. WHEN the Rate_Limiter blocks coordinate generation and a stale cached entry exists (less than 24 hours past expiry), THE Coordinate_Service SHALL return the stale entry with an is_throttled flag set to true
4. WHEN the Rate_Limiter blocks coordinate generation and no usable cached entry exists, THE Coordinate_Service SHALL return a 429 response with a Retry-After header indicating seconds until the next clock hour

### Requirement 4: Map Rendering

**User Story:** As a research analyst, I want an interactive map displayed in the Pattern Library drill-down, so that I can visually explore the geographic context of patterns and cases.

#### Acceptance Criteria

1. WHEN coordinate data is available for the current Taxonomy_Node, THE Map_Panel SHALL render a Leaflet_Map with OpenStreetMap tiles loaded from a public CDN
2. THE Map_Panel SHALL place one Marker at each coordinate returned by the Coordinate_Service
3. WHEN all Markers are placed, THE Leaflet_Map SHALL auto-zoom and auto-center to fit all Markers within the visible map area with appropriate padding
4. WHEN a user clicks or hovers over a Marker, THE Map_Panel SHALL display a popup or tooltip showing the site name and brief description
5. THE Map_Panel SHALL appear below the AI Insight panel in the drill-down view at every taxonomy level (Domain, Typology, Method, Signature, Precedent Case)
6. THE Map_Panel SHALL display a loading indicator while coordinates are being fetched from the Coordinate_Service
7. IF the Coordinate_Service returns an empty coordinate set, THEN THE Map_Panel SHALL display a message stating that no geographic data is available for the current node

### Requirement 5: Map Toggle

**User Story:** As a research analyst, I want to show or hide the map panel, so that I can focus on other content when the map is not needed.

#### Acceptance Criteria

1. THE Toggle_Button SHALL be rendered with the label "Show Map" when the Map_Panel is collapsed and "Hide Map" when the Map_Panel is expanded
2. WHEN a user clicks the Toggle_Button while the Map_Panel is expanded, THE Map_Panel SHALL collapse and hide all map content
3. WHEN a user clicks the Toggle_Button while the Map_Panel is collapsed, THE Map_Panel SHALL expand and display the Leaflet_Map with its current markers
4. THE Map_Panel SHALL default to the expanded state when coordinate data is first loaded for a Taxonomy_Node
5. WHEN a user navigates to a different Taxonomy_Node, THE Map_Panel SHALL reset to the expanded state and load new coordinates

### Requirement 6: API Endpoint

**User Story:** As a frontend developer, I want a dedicated API endpoint for coordinate retrieval, so that the map panel can fetch geographic data independently from the summary endpoint.

#### Acceptance Criteria

1. THE Coordinate_Service SHALL expose a GET endpoint at /pattern-library/coordinates/{level}/{context_key}
2. WHEN a valid request is received, THE Coordinate_Service SHALL return a JSON response containing: coordinates (array of site objects), generated_at (ISO 8601 timestamp), is_cached (boolean), is_throttled (boolean), and taxonomy_level (string)
3. WHEN the level path parameter is not one of domain, typology, method, signature, or precedent_case, THE Coordinate_Service SHALL return a 400 response with error code INVALID_TAXONOMY_LEVEL
4. WHEN the context_key path parameter is empty or exceeds 256 characters, THE Coordinate_Service SHALL return a 400 response with a descriptive error message
5. THE Coordinate_Service SHALL include CORS headers in all responses to allow requests from the frontend origin

### Requirement 7: Bedrock Client Configuration

**User Story:** As a platform operator, I want the Bedrock client for coordinates configured identically to summaries, so that timeout and retry behavior is consistent and predictable.

#### Acceptance Criteria

1. THE Bedrock_Client SHALL be configured with a read_timeout of 10 seconds
2. THE Bedrock_Client SHALL be configured with a connect_timeout of 5 seconds
3. THE Bedrock_Client SHALL be configured with max_attempts of 1 (no retries)
4. IF the Bedrock_Client invocation exceeds the read_timeout, THEN THE Coordinate_Service SHALL return a 503 response with error code GENERATION_FAILED
5. THE Coordinate_Service SHALL log each Bedrock invocation with the context_key, prompt token count, completion token count, and latency in milliseconds

### Requirement 8: Frontend Integration

**User Story:** As a research analyst, I want the map panel to load automatically when I navigate through the Pattern Library, so that geographic context is always available without extra clicks.

#### Acceptance Criteria

1. WHEN the Pattern Library drill-down navigation changes to a new Taxonomy_Node, THE Map_Panel SHALL automatically fetch coordinates from the Coordinate_Service for the new node
2. THE Map_Panel SHALL use the same context_key construction logic as the AI Insight panel (domain_id/typology_id/method_id path format)
3. THE Map_Panel SHALL load the Leaflet.js library and CSS from a public CDN (unpkg or cdnjs)
4. THE Map_Panel SHALL load OpenStreetMap tiles without requiring an API key
5. WHEN the Coordinate_Service returns is_throttled as true, THE Map_Panel SHALL display a "Throttled" status indicator
6. WHEN a network error occurs during coordinate fetch, THE Map_Panel SHALL display a dismissible error message without disrupting the rest of the Pattern Library view

### Requirement 9: Coordinate Response Parsing

**User Story:** As a developer, I want Bedrock's coordinate output parsed reliably, so that malformed responses do not crash the map or produce invalid markers.

#### Acceptance Criteria

1. THE Coordinate_Service SHALL instruct the Bedrock_Client to return coordinates as a JSON array of objects with keys: name, lat, lng, description
2. THE Coordinate_Service SHALL validate that each lat value is between -90 and 90 and each lng value is between -180 and 180
3. IF any coordinate object fails validation, THEN THE Coordinate_Service SHALL exclude that object from the result set and log a warning
4. IF the Bedrock_Client returns text that cannot be parsed as valid JSON, THEN THE Coordinate_Service SHALL return an empty coordinate set and log an error
5. THE Coordinate_Service SHALL strip any markdown fencing or preamble text before attempting JSON parsing of the Bedrock response
