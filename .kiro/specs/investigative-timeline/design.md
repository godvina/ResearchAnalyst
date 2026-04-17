# Design Document: Investigative Timeline

## Overview

The Investigative Timeline feature replaces the existing basic vis.js timeline in the Investigator UI with a full-featured chronological reconstruction tool. The current implementation simply plots date entities from the Neptune graph as flat markers on a vis.js Timeline widget — no swim lanes, no clustering, no gap analysis, no document linking.

This design introduces:
- A dedicated `TimelineService` (src/services/timeline_service.py) that reconstructs events from documents, entity metadata, and Neptune graph relationships
- A `TimelineHandler` (src/lambdas/api/timeline_handler.py) exposing REST endpoints routed through the existing `dispatch_handler` in case_files.py
- A rebuilt Timeline tab in investigator.html with entity swim lanes, activity clustering, document-linked event markers, temporal gap analysis, multi-modal event type markers, and AI analysis

The backend follows the same patterns as `PatternDiscoveryService` and `patterns.py`: Neptune HTTP API queries, Bedrock AI synthesis, Aurora metadata lookups, and OpenSearch snippet retrieval.

## Architecture

```mermaid
graph TD
    UI[investigator.html Timeline Tab] -->|POST /case-files/{id}/timeline| GW[API Gateway /{proxy+}]
    UI -->|POST /case-files/{id}/timeline/ai-analysis| GW
    GW --> DH[case_files.py dispatch_handler]
    DH --> TH[timeline_handler.py]
    TH --> TS[TimelineService]
    TS --> Neptune[Neptune Graph DB]
    TS --> Aurora[Aurora PostgreSQL]
    TS --> OS[OpenSearch]
    TS --> Bedrock[Bedrock Claude]
    Neptune -->|Date entities + relationships| TS
    Aurora -->|Document metadata, entity table| TS
    OS -->|Source snippets around date mentions| TS
    Bedrock -->|AI temporal analysis| TS
```

### Routing Integration

New routes are added to `case_files.py dispatch_handler` BEFORE the existing catch-all patterns, following the same pattern as `/top-patterns`:

```python
# --- Timeline routes ---
if "/timeline" in path and "/case-files/" in path:
    from lambdas.api.timeline_handler import dispatch_handler as tl_dispatch
    return tl_dispatch(event, context)
```

This must be placed before the `/patterns` catch-all and before the case file CRUD catch-all.

## Components and Interfaces

### 1. TimelineHandler (src/lambdas/api/timeline_handler.py)

Lambda handler module following the `patterns.py` dispatch pattern with `@with_access_control`.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/case-files/{id}/timeline` | Reconstruct and return timeline events with clustering and gap analysis |
| POST | `/case-files/{id}/timeline/ai-analysis` | Generate AI temporal pattern analysis |

**POST /case-files/{id}/timeline — Request Body:**
```json
{
  "clustering_window_hours": 48,
  "gap_threshold_days": 30
}
```

**POST /case-files/{id}/timeline — Response:**
```json
{
  "events": [
    {
      "event_id": "evt-uuid",
      "timestamp": "2019-03-15T00:00:00Z",
      "event_type": "meeting",
      "entities": [
        {"name": "John Doe", "type": "person"},
        {"name": "New York", "type": "location"}
      ],
      "source_documents": [
        {
          "document_id": "doc-uuid",
          "filename": "meeting_notes.pdf",
          "snippet": "On March 15, John Doe met with..."
        }
      ]
    }
  ],
  "clusters": [
    {
      "cluster_id": "cl-uuid",
      "event_count": 4,
      "start_timestamp": "2019-03-14T00:00:00Z",
      "end_timestamp": "2019-03-16T00:00:00Z",
      "shared_entities": ["John Doe"],
      "event_ids": ["evt-1", "evt-2", "evt-3", "evt-4"]
    }
  ],
  "gaps": [
    {
      "entity_name": "John Doe",
      "gap_start": "2019-04-01T00:00:00Z",
      "gap_end": "2019-06-15T00:00:00Z",
      "gap_days": 75,
      "event_before_id": "evt-5",
      "event_after_id": "evt-6"
    }
  ],
  "summary": {
    "total_events": 42,
    "total_entities": 12,
    "total_clusters": 5,
    "total_gaps": 3
  }
}
```

**POST /case-files/{id}/timeline/ai-analysis — Request Body:**
```json
{
  "events": [...],
  "gaps": [...]
}
```

**POST /case-files/{id}/timeline/ai-analysis — Response:**
```json
{
  "analysis": {
    "chronological_patterns": "...",
    "escalation_trends": "...",
    "clustering_significance": "...",
    "gap_interpretation": "...",
    "cross_entity_coordination": "...",
    "recommended_followups": ["...", "..."]
  }
}
```

### 2. TimelineService (src/services/timeline_service.py)

Core service class following the `PatternDiscoveryService` pattern: Neptune HTTP API queries (not gremlinpython WebSocket), Aurora ConnectionManager, OpenSearch snippet retrieval, Bedrock AI synthesis.

```python
class TimelineService:
    def __init__(self, aurora_conn: ConnectionManager, bedrock_client: Any):
        self._aurora = aurora_conn
        self._bedrock = bedrock_client

    def reconstruct_timeline(self, case_id: str, clustering_window_hours: int = 48,
                             gap_threshold_days: int = 30) -> dict:
        """Main entry point: extract events, cluster, detect gaps."""

    def _extract_events(self, case_id: str) -> list[dict]:
        """Query Neptune for date entities and their graph relationships,
        query Aurora entities table for co-occurrences, build TimelineEvents."""

    def _infer_event_type(self, connected_entity_types: list[str]) -> str:
        """Infer Event_Type from connected entity types."""

    def _get_source_snippets(self, case_id: str, date_str: str,
                              document_ids: list[str]) -> list[dict]:
        """Query OpenSearch for text surrounding date mentions."""

    def _cluster_events(self, events: list[dict],
                        window_hours: int) -> list[dict]:
        """Group events within temporal proximity sharing common entities."""

    def _detect_gaps(self, events: list[dict], entity_names: list[str],
                     threshold_days: int) -> list[dict]:
        """Find temporal gaps per entity exceeding threshold."""

    def generate_ai_analysis(self, case_id: str, events: list[dict],
                             gaps: list[dict]) -> dict:
        """Send timeline data to Bedrock Claude for temporal pattern analysis."""
```

### 3. Event Type Inference Rules

The service infers `Event_Type` from connected entity types in the graph:

| Connected Entity Types | Inferred Event_Type |
|----------------------|---------------------|
| person + location | travel |
| person + financial_amount | financial_transaction |
| person + person | meeting |
| person + phone_number OR email | communication |
| organization + legal term in snippet | legal_proceeding |
| document creation date (metadata) | document_creation |
| fallback | other |

### 4. Frontend Timeline Tab (investigator.html)

Replaces the existing `loadTimeline()` / `showTimelineDetail()` / `renderTimelineDensity()` / `filterTimeline()` / `aiTimelineAnalysis()` functions and the `#tab-timeline` HTML block.

**View Modes:**
- Flat timeline: all events on one track (default)
- Swim lane view: events grouped by entity in horizontal lanes
- Cluster view: events grouped into Activity_Clusters

**UI Components:**
- View mode toggle (flat / swim lane / cluster)
- Entity picker (multi-select for swim lanes, defaults to top 5 by event count)
- Event type filter (multi-select dropdown)
- Zoom controls (+/- buttons, mouse wheel)
- Density bar (event frequency distribution)
- Summary badge (event count, entity count, cluster count, gap count)
- Event detail panel (on click: source documents with snippets)
- Gap markers (hatched overlay on swim lanes)
- AI Analysis button and results panel
- Event type legend panel

**Keyboard Navigation:**
- Left/Right arrows: pan
- +/-: zoom
- Escape: close detail panels

## Data Models

### TimelineEvent

```python
@dataclass
class TimelineEvent:
    event_id: str           # UUID
    timestamp: str          # ISO 8601
    event_type: str         # communication|meeting|financial_transaction|travel|legal_proceeding|document_creation|other
    entities: list[dict]    # [{"name": str, "type": str}]
    source_documents: list[dict]  # [{"document_id": str, "filename": str, "snippet": str}]
```

### ActivityCluster

```python
@dataclass
class ActivityCluster:
    cluster_id: str         # UUID
    event_count: int
    start_timestamp: str    # ISO 8601
    end_timestamp: str      # ISO 8601
    shared_entities: list[str]
    event_ids: list[str]
```

### GapInterval

```python
@dataclass
class GapInterval:
    entity_name: str
    gap_start: str          # ISO 8601
    gap_end: str            # ISO 8601
    gap_days: int
    event_before_id: str
    event_after_id: str
```

### Neptune Query Pattern

Date entities are stored with label `Entity_{case_id}` and `entity_type='date'`. The service queries via Neptune HTTP API (same as `_gremlin_query` in pattern_discovery_service.py):

```gremlin
g.V().hasLabel('Entity_{case_id}').has('entity_type','date')
  .project('name','neighbors','neighbor_types')
  .by('canonical_name')
  .by(both('RELATED_TO').values('canonical_name').fold())
  .by(both('RELATED_TO').values('entity_type').fold())
```

### Aurora Entity Table Query

For document co-occurrence context, the service queries the entities table:

```sql
SELECT e.canonical_name, e.entity_type, e.source_document_refs,
       d.document_id, d.source_filename
FROM entities e
JOIN documents d ON d.case_file_id = e.case_file_id
WHERE e.case_file_id = %s AND e.entity_type = 'date'
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Event reconstruction produces well-structured events

*For any* case with date entities connected to other entities in the graph, reconstructing the timeline SHALL produce TimelineEvents where each event contains a non-empty event_id, a valid ISO 8601 timestamp, a non-empty event_type from the allowed set, a non-empty entities list with name and type fields, and source_documents where each snippet is at most 200 characters.

**Validates: Requirements 1.1, 1.2, 4.1**

### Property 2: Event type inference follows entity type rules

*For any* combination of connected entity types, the inferred event_type SHALL match the defined inference rules: person + location → travel, person + financial_amount → financial_transaction, person + person → meeting, person + phone_number/email → communication, and all other combinations → other or document_creation as appropriate. The inference function is deterministic: the same input always produces the same output.

**Validates: Requirements 1.3, 6.5**

### Property 3: Date normalization produces valid ISO 8601

*For any* date string that can be parsed into a valid date, the normalized output SHALL be a valid ISO 8601 formatted string. Parsing the normalized string back into a date and re-normalizing SHALL produce the same string (round-trip).

**Validates: Requirements 1.4**

### Property 4: Events are sorted in ascending chronological order

*For any* set of timeline events returned by `reconstruct_timeline`, the events list SHALL be sorted such that for all consecutive pairs (events[i], events[i+1]), events[i].timestamp <= events[i+1].timestamp.

**Validates: Requirements 1.7, 9.4**

### Property 5: Clustering groups temporally proximate events sharing entities

*For any* set of timeline events and a clustering_window_hours value > 0, every Activity_Cluster returned SHALL satisfy: (a) all events in the cluster have timestamps within clustering_window_hours of at least one other event in the cluster, (b) all events in the cluster share at least one common entity, (c) the cluster contains a valid cluster_id, event_count matching the actual number of events, start_timestamp <= end_timestamp, and a non-empty shared_entities list.

**Validates: Requirements 3.1, 3.2, 3.5**

### Property 6: Gap detection identifies intervals exceeding threshold

*For any* entity with two or more timeline events and a gap_threshold_days value, every Gap_Interval returned SHALL satisfy: (a) the gap duration in days equals the difference between gap_end and gap_start, (b) the gap duration >= gap_threshold_days, (c) the gap contains a valid entity_name, gap_start, gap_end, gap_days, event_before_id, and event_after_id.

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 7: Gap boundary invariant

*For any* Gap_Interval returned by the service, the gap_start date SHALL be equal to the timestamp of the event referenced by event_before_id, AND the gap_end date SHALL be equal to the timestamp of the event referenced by event_after_id. The gap_start SHALL be strictly before gap_end.

**Validates: Requirements 5.7**

## Error Handling

### Handler Level (timeline_handler.py)

| Scenario | Status Code | Error Code | Behavior |
|----------|-------------|------------|----------|
| Missing case_file_id | 400 | VALIDATION_ERROR | Return descriptive error message |
| Invalid case_file_id format | 400 | VALIDATION_ERROR | Return descriptive error message |
| Case file not found | 404 | NOT_FOUND | Return "Case file not found: {id}" |
| Neptune query failure | 200 | N/A | Return empty events array with warning in response |
| OpenSearch snippet failure | 200 | N/A | Return events without snippets, include "source unavailable" indicator |
| Bedrock AI analysis failure | 500 | AI_ANALYSIS_ERROR | Return error message with failure reason |
| Invalid clustering_window_hours | 400 | VALIDATION_ERROR | Must be non-negative integer |
| Invalid gap_threshold_days | 400 | VALIDATION_ERROR | Must be positive integer |
| CORS preflight (OPTIONS) | 200 | N/A | Return CORS headers |

### Service Level (timeline_service.py)

- Unparseable date entities are silently excluded from the timeline with a logger.warning call (Req 1.5)
- Missing/deleted source documents produce a reference with `snippet: null` and `status: "source_unavailable"` (Req 4.5)
- Neptune timeout: return partial results from Aurora-only data with a warning flag
- Empty case (no date entities): return empty events/clusters/gaps arrays with zero-count summary

## Testing Strategy

### Unit Tests

Unit tests verify specific examples, edge cases, and error conditions using `pytest` with mocked dependencies.

**TimelineService unit tests** (tests/unit/test_timeline_service.py):
- Event type inference for each specific entity type combination (person+location→travel, etc.)
- Date parsing for various formats (ISO 8601, MM/DD/YYYY, YYYY-MM-DD, etc.)
- Unparseable date exclusion (Req 1.5 edge case)
- Clustering with window=0 disables clustering (Req 3.6 edge case)
- Missing document handling returns "source_unavailable" (Req 4.5 edge case)
- Empty case returns empty arrays
- AI analysis response structure contains all required sections (Req 7.2)

**TimelineHandler unit tests** (tests/unit/test_timeline_handler.py):
- Invalid case_file_id returns 400
- OPTIONS returns CORS headers
- Valid request returns 200 with events and gaps arrays (Req 9.3)

### Integration Tests

Integration tests verify the full routing chain per the deployment-integration-testing steering rule.

**dispatch_handler integration tests** (tests/unit/test_timeline_handler.py):
- Invoke `dispatch_handler` from case_files.py with realistic API Gateway proxy event for `POST /case-files/{uuid}/timeline` — verify response is not 404 and not 500 (Req 9.1)
- Invoke `dispatch_handler` with realistic event for `POST /case-files/{uuid}/timeline/ai-analysis` — verify response is not 404 and not 500 (Req 9.2)
- Verify timeline response contains `events` array and `gaps` array (Req 9.3)
- Verify events are sorted ascending by timestamp (Req 9.4)
- Verify invalid case_file_id returns 400 (Req 9.5)

### Property-Based Tests

Property-based tests use the `hypothesis` library with minimum 100 iterations per property. Each test references its design document property.

**Property test file**: tests/unit/test_timeline_properties.py

Each property test will:
1. Generate random inputs using Hypothesis strategies (random date strings, entity type combinations, event lists)
2. Execute the function under test
3. Assert the property holds for all generated inputs
4. Be tagged with: `# Feature: investigative-timeline, Property {N}: {title}`

| Property | Test Description | Min Iterations |
|----------|-----------------|----------------|
| Property 1 | Generate random date entities with connections, verify event structure | 100 |
| Property 2 | Generate random entity type combinations, verify inference rules | 100 |
| Property 3 | Generate parseable date strings, verify ISO 8601 round-trip | 100 |
| Property 4 | Generate random events, verify ascending sort | 100 |
| Property 5 | Generate random events with timestamps and entities, verify clustering invariants | 100 |
| Property 6 | Generate random event sequences per entity, verify gap detection | 100 |
| Property 7 | Generate random event sequences, verify gap boundary invariant | 100 |
