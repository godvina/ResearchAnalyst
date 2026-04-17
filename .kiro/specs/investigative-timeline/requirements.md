# Requirements Document

## Introduction

The Investigative Timeline replaces the existing basic vis.js timeline in the Investigator UI (the "Timeline" tab in investigator.html) with a full-featured chronological reconstruction tool. The current implementation simply plots date entities extracted from the graph as flat markers on a vis.js Timeline widget, with no swim lanes, no clustering, no gap analysis, and no document linking. This feature builds a dedicated backend Timeline_Service that reconstructs events from ingested documents, entity metadata, and Neptune graph relationships, then renders them in the frontend with entity swim lanes, activity clustering, document-linked event markers, temporal gap analysis, and multi-modal event type markers. All changes extend the existing investigator.html Timeline tab and add new backend endpoints routed through case_files.py dispatch_handler.

## Glossary

- **Timeline_Service**: A Python backend service module (src/services/timeline_service.py) that reconstructs chronological events from case documents, entities, and graph relationships, and performs clustering and gap analysis
- **Timeline_Handler**: A Lambda API handler (src/lambdas/api/timeline_handler.py) that exposes REST endpoints for timeline data, dispatched from case_files.py
- **Timeline_Event**: A structured data object representing a single reconstructable event on the timeline, containing a timestamp, event type, associated entities, source document references, and text snippets
- **Swim_Lane**: A horizontal visual lane in the timeline UI assigned to a specific entity (person, organization, or location) that displays only the Timeline_Events associated with that entity, enabling parallel activity comparison
- **Activity_Cluster**: A group of two or more Timeline_Events that occur within a configurable temporal proximity window (default 48 hours) and share at least one common entity, displayed as a single expandable cluster marker on the timeline
- **Gap_Interval**: A period of time between consecutive Timeline_Events for a given entity that exceeds a configurable threshold (default 30 days), flagged as a potential gap in evidence or period of investigative interest
- **Event_Type**: A classification of a Timeline_Event into one of the supported categories: communication, meeting, financial_transaction, travel, legal_proceeding, document_creation, or other
- **Source_Snippet**: A short text excerpt (up to 200 characters) from the source document that provides context for a Timeline_Event, stored alongside the document reference

## Requirements

### Requirement 1: Timeline Event Reconstruction

**User Story:** As an investigator, I want the system to automatically reconstruct a chronological timeline of events from ingested case documents and entity metadata, so that I can see what happened and when without manually reading every document.

#### Acceptance Criteria

1. WHEN an investigator requests the timeline for a case, THE Timeline_Service SHALL extract Timeline_Events by querying date entities and their graph relationships from Neptune, and by retrieving document metadata and entity co-occurrences from the entities table
2. THE Timeline_Service SHALL construct each Timeline_Event with: a parsed timestamp, an inferred Event_Type, a list of associated entity names with types, a list of source document IDs, and a Source_Snippet from each linked document
3. WHEN a date entity is connected to person and location entities via graph edges, THE Timeline_Service SHALL infer the Event_Type based on connected entity types (e.g., person + location = travel, person + financial_amount = financial_transaction, person + person = meeting)
4. THE Timeline_Service SHALL normalize all date strings into ISO 8601 format for consistent sorting and display
5. IF a date entity cannot be parsed into a valid date, THEN THE Timeline_Service SHALL exclude that entity from the timeline and log a warning
6. THE Timeline_Service SHALL expose a REST endpoint (POST /case-files/{id}/timeline) that returns the reconstructed timeline as a sorted JSON array of Timeline_Events
7. FOR ALL Timeline_Events returned by the endpoint, the events SHALL be sorted in ascending chronological order by timestamp

### Requirement 2: Entity Swim Lanes

**User Story:** As an investigator, I want to see horizontal swim lanes for each key entity showing their activity over time, so that I can compare parallel activities of different persons, organizations, and locations.

#### Acceptance Criteria

1. WHEN the timeline loads, THE Timeline UI SHALL render a swim lane view with one horizontal lane per entity, where each lane displays only the Timeline_Events associated with that entity
2. THE Timeline UI SHALL support swim lanes for entity types: person, organization, and location
3. THE Timeline UI SHALL allow the investigator to select which entities appear as swim lanes via a multi-select entity picker, defaulting to the top 5 entities by event count
4. WHEN an entity is added or removed from the swim lane selection, THE Timeline UI SHALL re-render the swim lane view without a full page reload
5. THE Timeline UI SHALL color-code each swim lane using the existing entity type color scheme (person: #fc8181, organization: #f6ad55, location: #90cdf4)
6. THE Timeline UI SHALL display a shared time axis across all swim lanes so that vertical alignment indicates temporal co-occurrence
7. WHEN a Timeline_Event involves multiple entities that each have a swim lane, THE Timeline UI SHALL display that event in each relevant swim lane with a visual connector line between them

### Requirement 3: Activity Clustering

**User Story:** As an investigator, I want related events that happen close together in time to be grouped into clusters, so that I can identify bursts of coordinated activity without being overwhelmed by individual event markers.

#### Acceptance Criteria

1. THE Timeline_Service SHALL group Timeline_Events into Activity_Clusters when two or more events occur within a configurable temporal proximity window and share at least one common entity
2. THE Timeline_Service SHALL accept a clustering_window_hours parameter (default: 48) that defines the maximum time gap between events in the same cluster
3. THE Timeline UI SHALL render each Activity_Cluster as a single expandable marker showing the cluster event count and date range
4. WHEN an investigator clicks an Activity_Cluster marker, THE Timeline UI SHALL expand the cluster to reveal the individual Timeline_Events within it
5. THE Timeline_Service SHALL return cluster metadata including: cluster ID, event count, start timestamp, end timestamp, and the list of shared entities
6. WHEN the clustering window is set to 0, THE Timeline_Service SHALL disable clustering and return all events individually

### Requirement 4: Document-Linked Events

**User Story:** As an investigator, I want each timeline event to link back to its source documents with relevant text snippets, so that I can quickly verify the evidence behind any event on the timeline.

#### Acceptance Criteria

1. THE Timeline_Service SHALL include for each Timeline_Event a list of source document references containing: document_id, document filename, and a Source_Snippet of up to 200 characters showing the relevant passage
2. WHEN an investigator clicks a Timeline_Event marker, THE Timeline UI SHALL display a detail panel showing all linked source documents with their snippets
3. WHEN an investigator clicks a document reference in the detail panel, THE Timeline UI SHALL navigate to the document search view with that document highlighted
4. THE Timeline_Service SHALL retrieve Source_Snippets by querying OpenSearch for the document text surrounding the date entity mention
5. IF a source document has been deleted or is inaccessible, THEN THE Timeline_Service SHALL include the document reference with a "source unavailable" indicator and omit the snippet

### Requirement 5: Temporal Gap Analysis

**User Story:** As an investigator, I want the system to identify and highlight temporal gaps in entity activity, so that I can spot periods where evidence may be missing or where subjects went quiet.

#### Acceptance Criteria

1. THE Timeline_Service SHALL analyze the timeline for each entity and identify Gap_Intervals where the time between consecutive Timeline_Events exceeds a configurable threshold
2. THE Timeline_Service SHALL accept a gap_threshold_days parameter (default: 30) that defines the minimum gap duration to flag
3. THE Timeline_Service SHALL return Gap_Intervals containing: entity name, gap start date, gap end date, gap duration in days, and the events immediately before and after the gap
4. THE Timeline UI SHALL render Gap_Intervals as highlighted regions on the relevant entity swim lane with a distinct visual style (hatched or semi-transparent overlay)
5. WHEN an investigator clicks a Gap_Interval marker, THE Timeline UI SHALL display a detail panel showing the gap duration, the bounding events, and an AI-generated hypothesis about the gap significance
6. THE Timeline_Service SHALL expose gap analysis via the timeline endpoint response, included as a separate gaps array alongside the events array
7. FOR ALL Gap_Intervals returned, the gap start date SHALL be after the preceding event date AND the gap end date SHALL be before the following event date

### Requirement 6: Multi-Modal Event Type Markers

**User Story:** As an investigator, I want different visual markers for different event types on the timeline, so that I can quickly distinguish communications from meetings, financial transactions, travel, and legal proceedings at a glance.

#### Acceptance Criteria

1. THE Timeline UI SHALL render distinct visual markers for each Event_Type: communication (📞 phone icon, purple), meeting (🤝 handshake icon, green), financial_transaction (💰 money icon, yellow), travel (✈️ plane icon, blue), legal_proceeding (⚖️ scales icon, red), document_creation (📄 document icon, gray), and other (📎 clip icon, muted)
2. THE Timeline UI SHALL display a legend panel listing all Event_Type markers with their icons and colors
3. THE Timeline UI SHALL support filtering by Event_Type via a multi-select dropdown, allowing the investigator to show or hide specific event types
4. WHEN an Event_Type filter is applied, THE Timeline UI SHALL hide events of excluded types from both the main timeline and all swim lanes
5. THE Timeline_Service SHALL classify each Timeline_Event into an Event_Type based on the connected entity types and relationship types in the graph

### Requirement 7: AI Timeline Analysis

**User Story:** As an investigator, I want AI-generated analysis of the timeline that identifies patterns, escalation trends, and investigative leads, so that I can get expert-level temporal analysis without manual review.

#### Acceptance Criteria

1. WHEN the investigator clicks the AI Analysis button, THE Timeline_Service SHALL send the reconstructed timeline events and gap analysis to the Bedrock Claude model for temporal pattern analysis
2. THE Timeline_Service SHALL generate analysis covering: chronological patterns and escalation trends, temporal clustering significance, gap analysis interpretation, cross-entity coordination patterns, and recommended investigative follow-ups
3. THE Timeline UI SHALL display the AI analysis in a formatted panel below the timeline with distinct sections for each analysis category
4. WHEN AI analysis is in progress, THE Timeline UI SHALL display a loading indicator with the text "Analyzing temporal patterns..."
5. IF the AI analysis request fails, THEN THE Timeline UI SHALL display an error message with the failure reason and a retry button
6. THE Timeline_Service SHALL expose AI analysis via a REST endpoint (POST /case-files/{id}/timeline/ai-analysis) that accepts the timeline data and returns structured analysis

### Requirement 8: Timeline View Controls and UX

**User Story:** As an investigator, I want professional timeline controls for zooming, panning, and switching between views, so that the timeline feels like a top-tier investigative tool.

#### Acceptance Criteria

1. THE Timeline UI SHALL provide a view mode toggle between: flat timeline (all events on one track), swim lane view (events grouped by entity), and cluster view (events grouped into Activity_Clusters)
2. THE Timeline UI SHALL provide zoom controls that allow zooming from a single-day view to a multi-year overview
3. WHEN the timeline loads, THE Timeline UI SHALL auto-fit the time range to encompass all Timeline_Events with appropriate padding
4. THE Timeline UI SHALL display a density bar above the main timeline showing event frequency distribution across the time range
5. THE Timeline UI SHALL display a summary badge showing total event count, entity count, cluster count, and gap count
6. THE Timeline UI SHALL maintain the dark theme consistent with the existing Investigator UI color scheme (#0f1923 background, #48bb78 accent, #e2e8f0 text)
7. THE Timeline UI SHALL support keyboard navigation: left/right arrows for panning, +/- for zooming, and Escape to close detail panels

### Requirement 9: Integration Testing

**User Story:** As a developer, I want integration tests that verify the timeline API endpoints work through the full routing chain, so that deployments do not break the timeline feature.

#### Acceptance Criteria

1. THE integration test suite SHALL include a test that invokes dispatch_handler with a realistic API Gateway proxy event for POST /case-files/{id}/timeline and verifies the response status code is not 404 and not 500
2. THE integration test suite SHALL include a test that invokes dispatch_handler with a realistic API Gateway proxy event for POST /case-files/{id}/timeline/ai-analysis and verifies the response status code is not 404 and not 500
3. THE integration test suite SHALL verify that the timeline endpoint returns a JSON response containing an events array and a gaps array
4. THE integration test suite SHALL verify that timeline events are sorted in ascending chronological order
5. IF the timeline endpoint is called with an invalid case_file_id, THEN THE Timeline_Handler SHALL return a 400 status code with a descriptive error message
