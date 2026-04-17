# Design Document: Geospatial Evidence Map

## Overview

This feature transforms the existing basic Leaflet.js map in the Investigator UI into a professional-grade investigative mapping tool. The current map (investigator.html ~line 3122-3230) plots location entities as static circle markers using a hardcoded `geoLookup` of ~15 well-known locations. This design extends that code — without rewriting it — to add:

1. A backend `GeocodingService` with 200+ curated locations and fuzzy matching
2. Travel pattern visualization (dashed polylines between person-connected locations)
3. Heat map overlay (Leaflet.heat plugin) showing activity density
4. Location drill-down detail panel with connected entities and documents
5. AI geographic insights via Bedrock Haiku
6. Cross-case geographic overlap detection
7. Professional map controls, legend, and fullscreen toggle

All backend logic lives in a new `geocoding_service.py` module and new methods on `InvestigatorAIEngine`. Three new REST endpoints are added to the existing `case_files.py` mega-dispatcher. The frontend extends the existing `loadMap()`, `toggleMapHeat()`, `toggleTravelMode()`, and `aiMapAnalysis()` stub functions in `investigator.html`.

## Architecture

```mermaid
graph TD
    subgraph Frontend [investigator.html]
        A[loadMap - extended] -->|POST /case-files/{id}/geocode| B
        A -->|POST /case-files/{id}/patterns| C
        D[toggleMapHeat] -->|uses geocoded data| A
        E[toggleTravelMode] -->|uses graph edges| A
        F[aiMapAnalysis] -->|POST /case-files/{id}/map/ai-analysis| G
        H[drillDown click] -->|POST /case-files/{id}/map/location-detail| I
        J[crossCaseToggle] -->|POST /map/cross-case-locations| K
    end

    subgraph Lambda [case_files.py dispatcher]
        B[geocode handler]
        G[AI analysis handler]
        I[location detail handler]
        K[cross-case handler]
        C[patterns handler - existing]
    end

    subgraph Services
        B --> L[GeocodingService]
        G --> M[InvestigatorAIEngine.analyze_geography]
        I --> N[InvestigatorAIEngine.get_location_detail]
        K --> O[GeocodingService.cross_case_locations]
    end

    subgraph Data
        L --> P[Curated lookup dict - 200+ entries]
        M --> Q[Bedrock Haiku]
        N --> R[Aurora entities + relationships + entity_document_links]
        O --> R
        N --> S[Neptune graph - 1-hop neighbors]
    end
```

### Request Flow

1. `loadMap()` calls the existing `/patterns` endpoint (graph=true) to get nodes and edges — unchanged.
2. `loadMap()` then calls the new `POST /case-files/{id}/geocode` with the list of location entity names. The backend `GeocodingService` resolves each name to coordinates via curated lookup + fuzzy matching.
3. The frontend plots markers using the returned coordinates instead of the hardcoded `geoLookup`.
4. Toggle buttons activate heat map, travel lines, cross-case overlay, and AI analysis — each calling their respective endpoints or using already-loaded data.

### Key Design Decisions

- **No external geocoding API**: We use a curated lookup table + fuzzy matching rather than calling Google/Mapbox geocoding APIs. This avoids API key management, cost, latency, and network dependencies in Lambda. The 200+ entry table covers common investigative locations. Unresolvable locations are gracefully excluded.
- **Fuzzy matching via SequenceMatcher**: Python's `difflib.SequenceMatcher` provides sufficient fuzzy matching for location name normalization without adding dependencies. Threshold of 0.8 balances precision vs recall.
- **Leaflet.heat from CDN**: The heat map plugin is loaded from `unpkg.com` CDN on demand, matching the existing pattern for loading Leaflet itself.
- **Extend, don't rewrite**: Per lessons-learned.md, the existing `loadMap()` function body is preserved. New code is added after it or in new functions that the existing code calls.

## Components and Interfaces

### 1. GeocodingService (`src/services/geocoding_service.py`) — NEW

```python
class GeocodingService:
    """Resolves location entity names to lat/lng coordinates."""

    # Class-level curated lookup: dict[str, tuple[float, float]]
    CURATED_LOCATIONS: dict[str, tuple[float, float]]  # 200+ entries

    def geocode(self, names: list[str]) -> dict[str, dict]:
        """Resolve a list of location names to coordinates.
        
        Returns: {name: {"lat": float, "lng": float} | None}
        """

    def _normalize(self, name: str) -> str:
        """Lowercase, strip punctuation, remove state/country suffixes."""

    def _fuzzy_match(self, normalized: str) -> tuple[str, float] | None:
        """Find best match in CURATED_LOCATIONS above 0.8 threshold."""

    def cross_case_locations(self, case_id: str, aurora_cm) -> list[dict]:
        """Query entities table for locations shared across cases.
        
        Returns: [{"location": str, "cases": [{"case_id": str, "case_name": str}], "count": int}]
        """
```

### 2. InvestigatorAIEngine — EXTENDED (new methods only)

```python
# Added to existing InvestigatorAIEngine class:

def get_location_detail(self, case_id: str, location_name: str) -> dict:
    """Return connected entities, relationships, and documents for a location.
    
    Returns: {
        "location": str,
        "connected_entities": {"persons": [...], "organizations": [...], "events": [...], "other": [...]},
        "relationship_count": int,
        "documents": [{"document_id": str, "title": str, "mention_count": int}],  # up to 10
        "neighbors": [{"name": str, "type": str, "relationship": str}]  # 1-hop from Neptune
    }
    """

def analyze_geography(self, case_id: str, locations_data: list[dict]) -> dict:
    """Send geocoded location data to Bedrock Haiku for geographic analysis.
    
    Args:
        locations_data: [{"name": str, "lat": float, "lng": float, 
                         "connection_count": int, "persons": [str]}]
    
    Returns: {
        "clustering": str,
        "travel_corridors": str,
        "jurisdictional": str,
        "anomalies": str,
        "raw_analysis": str
    }
    """
```

### 3. API Handlers — NEW routes in case_files.py dispatcher

| Endpoint | Method | Handler | Description |
|---|---|---|---|
| `/case-files/{id}/geocode` | POST | `geocode_handler` | Resolve location names to coordinates |
| `/case-files/{id}/map/location-detail` | POST | `location_detail_handler` | Drill-down data for a location |
| `/case-files/{id}/map/ai-analysis` | POST | `ai_map_analysis_handler` | AI geographic insights |
| `/map/cross-case-locations` | POST | `cross_case_locations_handler` | Locations shared across cases |

All handlers follow the existing pattern: extract `case_id` from `pathParameters`, parse JSON body, call service, return via `success_response`/`error_response`.

### 4. Frontend Extensions (`investigator.html`) — EXTENDED

New/replaced functions:
- `loadMap()` — extended to call `/geocode` endpoint instead of using hardcoded `geoLookup`
- `toggleMapHeat()` — replaced stub with Leaflet.heat toggle
- `toggleTravelMode()` — replaced stub with dashed polyline rendering from graph edges
- `aiMapAnalysis()` — replaced stub with Bedrock analysis call and result panel
- `showLocationDrillDown(locationName)` — new function for click-to-detail
- `toggleCrossCaseOverlay()` — new function for cross-case markers
- `buildMapControls()` — new function for control panel, legend, fullscreen

## Data Models

### Geocode Request/Response

```json
// POST /case-files/{id}/geocode
// Request:
{"locations": ["New York", "Palm Beach", "Virgin Islands", "Unknown Place"]}

// Response:
{
  "geocoded": {
    "New York": {"lat": 40.7128, "lng": -74.006},
    "Palm Beach": {"lat": 26.7056, "lng": -80.0364},
    "Virgin Islands": {"lat": 18.3358, "lng": -64.8963}
  },
  "unresolved": ["Unknown Place"],
  "total": 4,
  "resolved": 3
}
```

### Location Detail Request/Response

```json
// POST /case-files/{id}/map/location-detail
// Request:
{"location_name": "Palm Beach"}

// Response:
{
  "location": "Palm Beach",
  "connected_entities": {
    "persons": [{"name": "John Doe", "relationship_count": 5}],
    "organizations": [{"name": "Acme Corp", "relationship_count": 2}],
    "events": [{"name": "Meeting 2019", "relationship_count": 1}],
    "other": []
  },
  "relationship_count": 8,
  "documents": [
    {"document_id": "uuid", "title": "doc_name.pdf", "mention_count": 3}
  ],
  "neighbors": [
    {"name": "John Doe", "type": "person", "relationship": "visited"}
  ]
}
```

### AI Analysis Request/Response

```json
// POST /case-files/{id}/map/ai-analysis
// Request:
{
  "locations": [
    {"name": "Palm Beach", "lat": 26.7, "lng": -80.0, "connection_count": 12, "persons": ["John Doe"]}
  ]
}

// Response:
{
  "analysis": {
    "clustering": "Activity is concentrated in Southeast Florida...",
    "travel_corridors": "High-frequency corridor between Palm Beach and Virgin Islands...",
    "jurisdictional": "Activity spans Florida state jurisdiction and US Virgin Islands federal territory...",
    "anomalies": "Unusual concentration of meetings at remote island location..."
  }
}
```

### Cross-Case Locations Request/Response

```json
// POST /map/cross-case-locations
// Request:
{"case_file_id": "uuid"}

// Response:
{
  "cross_case_locations": [
    {
      "location": "Palm Beach",
      "cases": [
        {"case_id": "uuid-1", "case_name": "Case Alpha"},
        {"case_id": "uuid-2", "case_name": "Case Beta"}
      ],
      "case_count": 2
    }
  ],
  "total": 1
}
```

### Existing Aurora Tables Used (no migrations needed)

- `entities` — `entity_id, case_file_id, canonical_name, entity_type, occurrence_count`
- `relationships` — `source_entity, target_entity, relationship_type, case_file_id, occurrence_count`
- `entity_document_links` — `entity_id, document_id, case_file_id, mention_count`
- `case_files` — `id, name` (for cross-case case name lookup)

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Normalization produces lowercase punctuation-free output

*For any* input string, the `_normalize()` function SHALL return a string that is entirely lowercase, contains no punctuation characters, and has no leading/trailing whitespace. The output length SHALL be less than or equal to the input length.

**Validates: Requirements 1.2**

### Property 2: Fuzzy match threshold determines resolution

*For any* location name, if the best fuzzy match score against the curated lookup table is above 0.8, `geocode()` SHALL return non-null coordinates; if the best score is below 0.8 and there is no exact match, `geocode()` SHALL return null for that name.

**Validates: Requirements 1.3, 1.4**

### Property 3: Geocoding determinism

*For any* location name, calling `geocode([name])` twice SHALL produce identical results — the same coordinates or the same null value.

**Validates: Requirements 1.6**

### Property 4: Travel line extraction from graph edges

*For any* set of graph nodes and edges, and a selected person name, the computed travel lines SHALL contain exactly the pairs of locations that are both connected to that person via edges. No travel line SHALL reference a location not connected to the selected person.

**Validates: Requirements 2.1**

### Property 5: Heat map data reflects filtered relationship counts

*For any* set of geocoded locations with relationship counts and any person filter, the heat map data points SHALL include only locations connected to the filtered person (or all locations if no filter), and each point's intensity SHALL be proportional to that location's relationship count.

**Validates: Requirements 3.1, 3.4**

### Property 6: Location detail returns grouped entities with document limit

*For any* location entity that exists in the case, `get_location_detail()` SHALL return connected entities grouped into exactly four categories (persons, organizations, events, other), the documents list SHALL contain at most 10 entries, and the neighbors list SHALL contain only 1-hop connections from the Neptune graph.

**Validates: Requirements 4.1, 4.2, 4.3, 4.5**

### Property 7: AI geographic prompt includes entity names and covers all categories

*For any* non-empty list of geocoded locations with person associations, the prompt sent to Bedrock SHALL contain every location name and every person name from the input, and the parsed response SHALL contain sections for clustering, travel corridors, jurisdictional observations, and anomalies.

**Validates: Requirements 5.2, 5.6**

### Property 8: Cross-case locations include all overlapping cases

*For any* case that has location entities shared with other cases, `cross_case_locations()` SHALL return each shared location with the complete list of case IDs where it appears, and the case count SHALL equal the length of the cases list.

**Validates: Requirements 6.1, 6.3**

### Property 9: Geocode response counts are consistent

*For any* list of location names submitted to the geocode endpoint, the response `total` SHALL equal the input list length, `resolved` SHALL equal the number of keys in `geocoded`, and `resolved + len(unresolved)` SHALL equal `total`.

**Validates: Requirements 7.4, 1.5**

## Error Handling

| Scenario | Behavior |
|---|---|
| Geocode called with empty list | Return `{"geocoded": {}, "unresolved": [], "total": 0, "resolved": 0}` |
| Location detail for non-existent location | Return 404 with `LOCATION_NOT_FOUND` error code |
| Neptune unreachable during location detail | Return partial result (Aurora data only), `neighbors: []`, log warning |
| Bedrock timeout during AI analysis | Return 504 with `AI_ANALYSIS_TIMEOUT` error, frontend shows retry button |
| Bedrock throttled | Return 429 with `AI_THROTTLED` error |
| Cross-case query with invalid case_file_id | Return 404 with `CASE_NOT_FOUND` error |
| No cross-case locations found | Return `{"cross_case_locations": [], "total": 0}` (not an error) |
| Leaflet.heat CDN fails to load | Frontend shows toast "Heat map plugin unavailable" and disables toggle |
| Fuzzy match returns multiple equal-score matches | Return the first alphabetically (deterministic) |

## V3 Enhancements

### AI Insight Cards (Requirement 8)

Each location marker on the Evidence_Map gets a persistent AI Insight Card rendered as a Leaflet DivIcon tooltip/overlay anchored next to the marker. The card is generated client-side from data already available after the geocode + patterns response — no additional API call required for the basic card.

**Card Content:**
- Location name (bold header)
- Role badge: "Hub" (red) if `connection_count >= 5`, "Node" (blue) otherwise
- Top 2 connected person names (from graph edges)
- "So what" summary line generated from entity type counts (e.g., "Key coordination point — 5 persons, 3 orgs intersect here")

**Rendering approach:**
- Cards are Leaflet `L.divIcon` custom markers offset from the circle marker so they don't overlap the click target
- Semi-transparent dark background (`rgba(15, 23, 42, 0.85)`) with light text, matching the existing UI theme
- Cards use `pointer-events: none` CSS so clicks pass through to the underlying circle marker for drill-down
- Cards are created in `loadMap()` after markers are plotted, iterating over the geocoded locations and their graph edge data

**Data flow:**
```
loadMap() → geocode response + patterns response
  → for each location: compute connection_count, find top 2 persons from edges
  → classify Hub/Node based on threshold (5)
  → generate "so what" string from entity type counts
  → create L.divIcon with HTML template → add to map layer group
```

### Entity Geo-Drill (Requirement 9)

A new navigation flow from the Network Graph drill-down to the Evidence_Map. When a user clicks "Show on Map" on an entity card in the network graph panel, the map filters to show only that entity's geographic footprint.

**New function: `entityGeoDrill(entityName, entityType)`**

1. Queries the existing `/case-files/{id}/patterns` endpoint with a filter for the specific entity
2. Filters the geocoded locations to only those connected to the entity via graph edges
3. Clears existing markers and replots only the filtered locations
4. Draws curved travel arcs (Leaflet `L.curve` or quadratic bezier polylines) between filtered locations
5. Calls a new backend method `InvestigatorAIEngine.narrate_entity_geography(entity_name, locations)` to generate a one-paragraph AI narrative
6. Displays the narrative in a floating panel above the map
7. Adds a "Back to Full Map" button that calls `loadMap()` to restore the complete view

**New API method on InvestigatorAIEngine:**

```python
def narrate_entity_geography(self, case_id: str, entity_name: str, 
                              entity_type: str, locations: list[dict]) -> str:
    """Generate a one-paragraph AI narrative about an entity's geographic pattern.
    
    Args:
        entity_name: The entity being drilled into
        entity_type: 'person', 'organization', etc.
        locations: [{"name": str, "lat": float, "lng": float, "doc_count": int}]
    
    Returns: A narrative string like "Subject traveled between NY and Virgin Islands 
             across 47 documents, with activity concentrated in..."
    """
```

**Frontend state management:**
- A `geoDrillActive` boolean flag tracks whether the map is in filtered mode
- When active, heat map / cross-case toggles are disabled (they apply to full case view)
- The "Back to Full Map" button sets `geoDrillActive = false` and calls `loadMap()`

### Static Professional Markers (Requirement 10)

All location markers are rendered as static `L.circleMarker` instances with no CSS animations, no pulsing effects, and no scale transforms.

**Marker styling:**
- Hub locations (5+ connections): `{ color: '#fc8181', fillColor: '#fc8181', radius: 8, fillOpacity: 0.9 }`
- Node locations (<5 connections): `{ color: '#4a9eff', fillColor: '#4a9eff', radius: 6, fillOpacity: 0.8 }`
- No `L.marker` with animated icons — strictly `L.circleMarker`

**Auto-fit zoom:**
- After plotting all markers, call `map.fitBounds(markerGroup.getBounds(), { padding: [20, 20] })` with minimal padding
- This replaces any hardcoded `setView()` call, ensuring the zoom level tightly fits the actual data extent
- For Entity Geo-Drill filtered views, `fitBounds` is called again on the filtered marker subset

**Click reliability:**
- Each `L.circleMarker` gets a `.on('click', () => showLocationDrillDown(locationName))` handler
- AI Insight Card overlays use `pointer-events: none` to prevent click interception
- Marker `zIndex` is set above travel lines and heat layer to ensure clickability

### Updated Correctness Properties for V3

#### Property 10: AI Insight Card role classification

*For any* location with a `connection_count`, the AI Insight Card SHALL display "Hub" if `connection_count >= 5` and "Node" otherwise. The card SHALL always contain exactly 2 or fewer person names (top connected).

**Validates: Requirements 8.1, 8.2**

#### Property 11: Entity Geo-Drill filters locations correctly

*For any* entity name and the full set of graph edges, the Entity Geo-Drill filtered location set SHALL contain exactly the locations that have at least one edge connecting them to the specified entity. No location without an edge to the entity SHALL appear.

**Validates: Requirements 9.1, 9.5**

#### Property 12: Static marker color coding matches Hub/Node threshold

*For any* set of geocoded locations with connection counts, markers with `connection_count >= 5` SHALL use fill color `#fc8181` (red) and markers with `connection_count < 5` SHALL use fill color `#4a9eff` (blue). No marker SHALL have animation or transform CSS properties.

**Validates: Requirements 10.1, 10.2**

## Testing Strategy

### Property-Based Testing

We use `hypothesis` (Python) for property-based testing. Each property test runs a minimum of 100 iterations.

| Property | Test File | Strategy |
|---|---|---|
| P1: Normalization | `test_geocoding_service.py` | Generate random Unicode strings via `hypothesis.strategies.text()`, verify output is lowercase + punctuation-free |
| P2: Fuzzy threshold | `test_geocoding_service.py` | Generate known location names with random character insertions/deletions, verify threshold behavior |
| P3: Determinism | `test_geocoding_service.py` | Generate random strings, call geocode twice, assert equality |
| P4: Travel lines | `test_geocoding_service.py` | Generate random graph structures (nodes + edges), select random person, verify travel line correctness |
| P5: Heat data | `test_geocoding_service.py` | Generate random location sets with counts and person filters, verify filtering and proportionality |
| P6: Location detail | `test_geocoding_service.py` | Generate random entity sets with types, verify grouping into 4 categories and document limit |
| P7: AI prompt | `test_geocoding_service.py` | Generate random location/person lists, verify prompt contains all names and response has 4 sections |
| P8: Cross-case | `test_geocoding_service.py` | Generate random multi-case entity sets, verify shared locations and case counts |
| P9: Geocode counts | `test_geocoding_service.py` | Generate random name lists (mix of known/unknown), verify count arithmetic |

Each property test MUST be tagged with a comment:
```python
# Feature: geospatial-evidence-map, Property {N}: {property_text}
```

### Unit Tests (Examples and Edge Cases)

| Test | Validates |
|---|---|
| Curated lookup has >= 200 entries | Req 1.1 |
| Geocode endpoint returns correct shape | Req 1.5 |
| Travel line tooltip data has required fields | Req 2.3 |
| "All Persons" filter clears travel lines (empty result) | Req 2.4 |
| Heat toggle off returns empty heat data | Req 3.3 |
| Location detail error returns 404 | Req 4.6 |
| Location detail endpoint exists | Req 4.7 |
| AI analysis request sends correct payload | Req 5.1 |
| AI analysis error returns retry-able response | Req 5.5 |
| Cross-case endpoint exists | Req 6.4 |
| Empty cross-case result returns notification-worthy response | Req 6.5 |

### Test Configuration

- Library: `hypothesis` (already available in test dependencies)
- Min iterations: 100 per property (`@settings(max_examples=100)`)
- Test file: `tests/unit/test_geocoding_service.py`
- Run: `pytest tests/unit/test_geocoding_service.py -v`

