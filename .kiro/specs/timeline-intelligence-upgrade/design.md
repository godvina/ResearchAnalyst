# Design Document: Timeline Intelligence Upgrade

## Overview

This upgrade transforms the existing investigative timeline from a raw date-entity plot into a production-grade investigative analysis tool. The current implementation (delivered by the `investigative-timeline` spec) has critical usability problems observed in production with the Epstein Combined case (33 events, 75 entities, 19 gaps):

1. **Noise dates** from historical references (e.g., "Immigration Act of 1882") stretch the timeline to 135+ years
2. **Clustering returns 0 clusters** despite 33 events — the entity overlap check is too strict
3. **Event labels** show truncated graph IDs instead of readable names
4. **Default flat view** is less useful than swim lanes for investigative work
5. **AI analysis** treats noise gaps as real investigative findings (flagging "81-year gaps")
6. **Dead space** between timeline canvas and AI panel wastes screen real estate

This design modifies the existing files — no new service classes or handlers are created:

- **Backend**: `src/services/timeline_service.py` — add noise filtering, relevant date range computation, investigative phase detection, narrative header generation, display_label computation, clustering fix
- **Handler**: `src/lambdas/api/timeline_handler.py` — pass new parameters (noise_cutoff_year), return new response fields
- **Frontend**: `src/frontend/investigator.html` — noise toggle, quick zoom presets, phase bands, narrative header, compact layout, default swim lane view, improved event labels

## Architecture

The architecture remains unchanged — same service, handler, and frontend files. The upgrade adds new logic within the existing call chain:

```mermaid
graph TD
    UI[investigator.html Timeline Tab] -->|POST /case-files/{id}/timeline| GW[API Gateway]
    GW --> DH[case_files.py dispatch_handler]
    DH --> TH[timeline_handler.py]
    TH --> TS[TimelineService]
    TS --> Aurora[Aurora PostgreSQL]
    TS --> Bedrock[Bedrock Claude]

    subgraph "New Logic in TimelineService"
        NF[_filter_noise_dates] --> RDR[_compute_relevant_range]
        RDR --> PH[_detect_phases]
        PH --> NH[_generate_narrative_header]
        DL[_compute_display_label]
        CF[Fixed _cluster_events]
    end

    TS --> NF
    TS --> DL
    TS --> CF
```

### Modified Call Flow in `reconstruct_timeline`

The existing `reconstruct_timeline` method is extended with these steps inserted into the pipeline:

1. `_extract_events` (existing) — now also computes `display_label` per event
2. **NEW**: `_filter_noise_dates` — density-based cutoff detection, splits events into relevant + noise
3. Sort events ascending (existing)
4. **NEW**: `_compute_relevant_range` — 80% density window algorithm
5. `_cluster_events` (existing, **FIXED**) — now clusters on relevant events only, relaxed entity overlap
6. `_detect_gaps` (existing) — now runs on relevant events only
7. **NEW**: `_detect_phases` — rule-based investigative phase labeling
8. **NEW**: `_generate_narrative_header` — lightweight Bedrock call

### New Request/Response Fields

**Request body additions** (POST /case-files/{id}/timeline):
```json
{
  "clustering_window_hours": 48,
  "gap_threshold_days": 30,
  "skip_snippets": true,
  "noise_cutoff_year": null
}
```

**Response additions** (merged into existing response):
```json
{
  "events": [...],
  "clusters": [...],
  "gaps": [...],
  "summary": {...},
  "filtered_noise_events": [...],
  "noise_filter_summary": {
    "auto_cutoff_year": 1995,
    "events_filtered": 5,
    "relevant_range_start": "1999-01-01T00:00:00Z",
    "relevant_range_end": "2019-12-31T00:00:00Z"
  },
  "relevant_range": {
    "start": "1999-01-01T00:00:00Z",
    "end": "2019-12-31T00:00:00Z"
  },
  "phases": [
    {
      "phase_id": "ph-uuid",
      "label": "Active Criminal Period",
      "start": "2001-03-15T00:00:00Z",
      "end": "2008-06-30T00:00:00Z",
      "description": "Peak period of financial transactions and meetings involving 8 key persons",
      "event_count": 18
    }
  ],
  "narrative_header": "Criminal activity spanning 1999–2019 involving 12 key persons across 4 locations with 8 financial transactions and 15 communications"
}
```

## Components and Interfaces

### 1. TimelineService — New Methods (src/services/timeline_service.py)

#### `_filter_noise_dates(events, noise_cutoff_year=None) -> tuple[list, list]`

Separates events into relevant and noise based on density analysis.

**Algorithm — Density-Based Cutoff Detection:**
1. Extract all event years from timestamps
2. If `noise_cutoff_year` is provided by the investigator, use it directly as the cutoff
3. Otherwise, build a year histogram (count of events per year)
4. Find the **Density_Cluster**: the largest contiguous block of years where each year has at least 1 event and no gap between consecutive active years exceeds 5 years
5. Set the auto cutoff to `Density_Cluster.start_year - 20`
6. If all events fall within a 20-year window, apply no filtering (cutoff = earliest event year)
7. Return `(relevant_events, noise_events)` where noise events have timestamps before the cutoff

```python
def _filter_noise_dates(self, events: list[dict], noise_cutoff_year: int | None = None) -> tuple[list[dict], list[dict]]:
    """Split events into relevant and noise based on density analysis."""
```

#### `_compute_relevant_range(events) -> dict | None`

Computes the smallest time window containing ≥80% of events.

**Algorithm — 80% Density Window:**
1. Sort event timestamps ascending
2. Compute target count = ceil(len(events) * 0.8)
3. Slide a window of size `target_count` across the sorted timestamps
4. For each window position, compute `window_span = timestamps[i + target_count - 1] - timestamps[i]`
5. Return the window with the smallest span as `{"start": iso, "end": iso}`
6. If fewer than 3 events, return None (no meaningful range)

```python
def _compute_relevant_range(self, events: list[dict]) -> dict | None:
    """Find the smallest time window containing >= 80% of events."""
```

#### `_detect_phases(events) -> list[dict]`

Rule-based investigative phase detection from event types and temporal distribution.

**Algorithm:**
1. If fewer than 5 events, return empty list
2. Sort events by timestamp, divide the timeline into temporal thirds
3. Analyze event type distribution per third:
   - First third with mostly `document_creation` / `other` → "Early Activity"
   - Middle third with `financial_transaction` / `meeting` / `travel` → "Peak Activity" or "Active Criminal Period"
   - Last third with `legal_proceeding` → "Legal Proceedings"
4. Detect transitions: if event types shift from non-legal to legal, mark "Investigation Phase" at the transition point
5. Each phase gets: `phase_id`, `label`, `start`, `end`, `description`, `event_count`

This is rule-based (no Bedrock call) to keep it fast and deterministic. The phase labels come from a fixed vocabulary: "Pre-Criminal Activity", "Early Activity", "Escalation", "Peak Activity", "Active Criminal Period", "Investigation Phase", "Legal Proceedings", "Post-Resolution".

```python
def _detect_phases(self, events: list[dict]) -> list[dict]:
    """Detect investigative phases from event type distribution."""
```

#### `_generate_narrative_header(events, relevant_range, phases) -> str`

Lightweight Bedrock call to produce a one-sentence investigative summary.

**Prompt design:**
- Input: event count, time span, entity counts by type, top event types, phase labels
- Output: single sentence in investigative language
- Max tokens: 150 (keeps it fast)
- Fallback on failure: compute a template-based string from the data (e.g., "33 events from Jan 1999 to Dec 2019 involving 12 entities")

```python
def _generate_narrative_header(self, events: list[dict], relevant_range: dict | None, phases: list[dict]) -> str:
    """Generate a one-sentence AI narrative header for the timeline."""
```

#### `_compute_display_label(event) -> str`

Computes a human-readable label for each event marker.

**Rules:**
1. Get top 2 entity names from `event["entities"]`
2. If an entity name exceeds 25 characters, truncate to 22 chars + "..."
3. Format: `"{entity1}, {entity2} — {formatted_date}"` or `"{entity1} — {formatted_date}"` if only one entity
4. If no entities, use `"{event_type_label} — {formatted_date}"`
5. Date format: "Mar 15, 2019" (abbreviated month, day, 4-digit year)

```python
@staticmethod
def _compute_display_label(event: dict) -> str:
    """Build a human-readable label for a timeline event marker."""
```

### 2. Clustering Fix (in existing `_cluster_events`)

**Root cause of 0 clusters:** The current algorithm requires `cluster_entity_names & other_entity_names` — i.e., the new event must share at least one entity name with the growing cluster. In the Epstein case, many events have entities extracted from different documents with no overlapping entity names, even though they're temporally close.

**Fix — Relaxed Entity Overlap:**
1. Keep the existing temporal proximity check (within `window_hours`)
2. Change the entity overlap requirement: instead of requiring shared entity *names*, also consider **document co-occurrence** — if two events share a source document ID, they are related
3. If neither entity overlap nor document overlap exists, still cluster events that are within `window_hours / 2` of each other (tight temporal clustering without entity requirement)
4. After clustering on relevant events only (post noise filtering), log cluster count at INFO level
5. If 0 clusters for 10+ events, log WARNING with diagnostics

```python
def _cluster_events(self, events: list[dict], window_hours: int) -> list[dict]:
    """Group events within temporal proximity — relaxed overlap rules."""
```

### 3. TimelineHandler Changes (src/lambdas/api/timeline_handler.py)

Minimal changes:
- Parse `noise_cutoff_year` from request body (optional integer, validated)
- Pass it to `reconstruct_timeline`
- Response already returns whatever dict `reconstruct_timeline` returns

### 4. Frontend Changes (src/frontend/investigator.html)

#### Default Swim Lane View
- Change `tlCurrentView = 'flat'` to `tlCurrentView = 'swimlane'`
- Update the view toggle buttons so "Swim Lanes" has the `active` class by default

#### Narrative Header Banner
- Add a `<div id="tlNarrativeHeader">` above the density bar
- Style: accent color (#48bb78), 14px font, padding 10px
- On load: show "Generating investigative summary..." placeholder
- On response: populate with `data.narrative_header`
- On failure: compute fallback from event data

#### Noise Date Toggle
- Add a toggle switch in the controls row: "Show noise dates"
- When enabled, merge `filtered_noise_events` into the display with muted styling (opacity 0.4, dashed border)
- When disabled (default), show only relevant events
- Store `tlNoiseEvents` and `tlNoiseFilterSummary` from response

#### Quick Zoom Presets
- Add 4 buttons next to zoom controls: "1Y", "5Y", "Dense", "All"
- "Dense" uses `relevant_range` from response
- "1Y" / "5Y" compute from the latest event timestamp
- "All" fits to full range including noise
- Active preset highlighted with #48bb78
- Manual zoom/pan deselects active preset

#### Phase Bands
- Render phases as horizontal colored bands behind event markers
- Each phase category gets a distinct semi-transparent background color
- Hover tooltip shows phase description and event count

#### Compact Layout
- Remove fixed `min-height: 420px` from `.tl-canvas`, use `min-height: 200px; max-height: 500px`
- AI panel renders directly below canvas with 8px gap, no extra spacers
- Collapsed AI panel shows single-line "AI Analysis ▸" bar (40px height)

#### Improved Event Labels
- Use `display_label` from response if available
- Fallback to existing label logic
- Set `.tl-event-label` to `max-width: 200px; font-size: 11px; white-space: normal;` (allow wrapping)

#### Auto-Fit to Relevant Range
- On timeline load, if `relevant_range` is present, compute zoom/pan to fit that range with 5% padding
- When "Show noise dates" is toggled on, maintain current viewport (don't re-fit)

## Data Models

### New/Extended Response Fields

#### NoiseFilterSummary
```python
{
    "auto_cutoff_year": int,          # The year used as noise cutoff
    "events_filtered": int,           # Count of events classified as noise
    "relevant_range_start": str,      # ISO 8601
    "relevant_range_end": str         # ISO 8601
}
```

#### RelevantRange
```python
{
    "start": str,   # ISO 8601 — start of 80% density window
    "end": str      # ISO 8601 — end of 80% density window
}
```

#### InvestigativePhase
```python
{
    "phase_id": str,        # UUID
    "label": str,           # One of the fixed phase vocabulary
    "start": str,           # ISO 8601
    "end": str,             # ISO 8601
    "description": str,     # One-sentence description
    "event_count": int      # Events within this phase
}
```

#### Extended TimelineEvent (new field)
```python
{
    "event_id": str,
    "timestamp": str,
    "event_type": str,
    "entities": list[dict],
    "source_documents": list[dict],
    "display_label": str    # NEW — human-readable label
}
```

### Existing Data Models (Unchanged)

- `TimelineEvent`, `ActivityCluster`, `GapInterval` — same structure as original design
- Neptune query pattern — unchanged (Aurora-only extraction)
- Aurora entity table query — unchanged



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Noise filtering partition invariant

*For any* list of timeline events, after calling `_filter_noise_dates`, the union of the returned relevant events and noise events SHALL equal the original event list (no events lost or duplicated), AND `noise_filter_summary.events_filtered` SHALL equal the length of the noise events list, AND every noise event SHALL have a timestamp year earlier than the auto-detected cutoff year.

**Validates: Requirements 1.1, 1.2, 1.4, 1.5**

### Property 2: Manual cutoff override

*For any* list of timeline events and any valid `noise_cutoff_year`, calling `_filter_noise_dates` with that cutoff SHALL classify every event with a timestamp year before `noise_cutoff_year` as noise, and every event with a timestamp year >= `noise_cutoff_year` as relevant.

**Validates: Requirements 1.3**

### Property 3: Relevant date range contains at least 80% of events

*For any* list of 3 or more non-noise timeline events, the `relevant_range` returned by `_compute_relevant_range` SHALL contain at least 80% of the events (i.e., events whose timestamps fall within `[relevant_range.start, relevant_range.end]`), AND no strictly smaller window SHALL also contain 80% of the events.

**Validates: Requirements 2.2, 2.3**

### Property 4: Phase detection structure and vocabulary

*For any* list of 5 or more timeline events, `_detect_phases` SHALL return a non-empty list of phases where each phase has a non-empty `phase_id`, a `label` from the fixed vocabulary {"Pre-Criminal Activity", "Early Activity", "Escalation", "Peak Activity", "Active Criminal Period", "Investigation Phase", "Legal Proceedings", "Post-Resolution"}, a `start` <= `end` as valid ISO 8601 timestamps, a non-empty `description`, and an `event_count` >= 1. For any list of fewer than 5 events, `_detect_phases` SHALL return an empty list.

**Validates: Requirements 3.1, 3.2, 3.3, 3.6**

### Property 5: Display label composition

*For any* timeline event with at least one entity, `_compute_display_label` SHALL produce a string containing at least one entity name (or its truncation) and a formatted date. *For any* timeline event with no entities, the label SHALL contain the event type label and a formatted date. *For any* entity name exceeding 25 characters, the name in the label SHALL be truncated to at most 25 characters.

**Validates: Requirements 5.1, 5.2, 5.4, 5.5**

### Property 6: Clustering produces clusters for temporally close events

*For any* list of timeline events where at least 2 events have timestamps within `clustering_window_hours` of each other, `_cluster_events` SHALL return at least one cluster. Each cluster SHALL contain at least 2 events, and all events in a cluster SHALL have timestamps within `clustering_window_hours` of at least one other event in the same cluster.

**Validates: Requirements 9.1**

### Property 7: Document co-occurrence enables clustering

*For any* two timeline events that share a source document ID and have timestamps within `clustering_window_hours` of each other, `_cluster_events` SHALL place them in the same cluster, even if they share no entity names.

**Validates: Requirements 9.3**

### Property 8: Noise events excluded from downstream processing

*For any* timeline reconstruction result, no event in the `clusters` array's `event_ids` SHALL reference an event from `filtered_noise_events`, AND no gap in the `gaps` array SHALL reference an event from `filtered_noise_events`.

**Validates: Requirements 9.2, 10.1, 10.4**

### Property 9: Fallback narrative contains event data

*For any* list of timeline events, the fallback narrative header (computed without AI) SHALL contain the total event count as a substring and SHALL contain at least one entity count or time span reference.

**Validates: Requirements 4.5**

## Error Handling

### Handler Level (timeline_handler.py) — Additions

| Scenario | Status Code | Error Code | Behavior |
|----------|-------------|------------|----------|
| Invalid noise_cutoff_year (not integer) | 400 | VALIDATION_ERROR | Return "noise_cutoff_year must be an integer" |
| noise_cutoff_year in the future | 400 | VALIDATION_ERROR | Return "noise_cutoff_year cannot be in the future" |
| Narrative header Bedrock failure | 200 | N/A | Return fallback narrative computed from event data |
| Phase detection failure | 200 | N/A | Return empty phases array, log warning |

### Service Level (timeline_service.py) — Additions

- `_filter_noise_dates`: If all events are noise (unlikely), return all as relevant with no filtering applied
- `_compute_relevant_range`: If fewer than 3 events, return None (no meaningful range)
- `_detect_phases`: If event type variety is insufficient (all same type), return empty phases
- `_generate_narrative_header`: Bedrock timeout/error → return template-based fallback string, never raise
- `_compute_display_label`: If entity names are all empty strings, fall back to event type + date

All existing error handling from the original design remains unchanged.

## Testing Strategy

### Unit Tests

Unit tests verify specific examples, edge cases, and error conditions using `pytest` with mocked dependencies. These extend the existing test files.

**TimelineService unit tests** (tests/unit/test_timeline_service.py — extend existing):
- Noise filtering with known event sets: verify correct partition for a case with 1882, 1953, 1999-2019 dates
- Manual cutoff override: verify noise_cutoff_year=2000 filters events before 2000
- Relevant range computation: verify 80% window for a known 10-event set
- Phase detection: verify phases for a known event set with legal_proceeding events in the last third
- Phase detection with < 5 events returns empty list
- Display label: verify label format for events with 0, 1, 2 entities
- Display label: verify truncation for entity names > 25 characters
- Clustering fix: verify clusters produced for events within 48 hours sharing a document
- Clustering: verify 0-cluster warning logged for 10+ events with no clusters
- Narrative header fallback: verify template string contains event count
- No-filtering edge case: all events within 20-year window → no noise events

**TimelineHandler unit tests** (tests/unit/test_timeline_handler.py — extend existing):
- Invalid noise_cutoff_year returns 400
- Valid noise_cutoff_year passes through to service
- Response contains new fields: filtered_noise_events, noise_filter_summary, relevant_range, phases, narrative_header

### Property-Based Tests

Property-based tests use the `hypothesis` library with minimum 100 iterations per property. Each test references its design document property.

**Property test file**: tests/unit/test_timeline_upgrade_properties.py

Each property test will:
1. Generate random inputs using Hypothesis strategies (random timestamps, entity lists, event sets)
2. Execute the function under test
3. Assert the property holds for all generated inputs
4. Be tagged with a comment referencing the design property

| Property | Test Description | Min Iterations |
|----------|-----------------|----------------|
| Property 1 | Generate random event lists with timestamps spanning decades, verify partition invariant | 100 |
| Property 2 | Generate random event lists and cutoff years, verify manual cutoff classification | 100 |
| Property 3 | Generate random timestamp lists (3+), verify 80% window optimality | 100 |
| Property 4 | Generate random event lists (5+) with varied event types, verify phase structure | 100 |
| Property 5 | Generate random events with entity names of varying lengths, verify label composition | 100 |
| Property 6 | Generate random events with at least 2 within window_hours, verify cluster production | 100 |
| Property 7 | Generate random event pairs sharing a document ID within window, verify co-clustering | 100 |
| Property 8 | Generate random event lists, run full reconstruct_timeline, verify noise exclusion from clusters/gaps | 100 |
| Property 9 | Generate random event lists, verify fallback narrative contains event count | 100 |

Each test tagged: `# Feature: timeline-intelligence-upgrade, Property {N}: {title}`

### Testing Configuration

- Library: `hypothesis` (already in project dependencies)
- Min iterations: 100 per property (via `@settings(max_examples=100)`)
- Unit tests and property tests are complementary:
  - Unit tests catch concrete bugs with known inputs and edge cases
  - Property tests verify general correctness across randomized inputs
- Each correctness property is implemented by a single property-based test
