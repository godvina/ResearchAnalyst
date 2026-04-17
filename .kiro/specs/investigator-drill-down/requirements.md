# Requirements Document

## Introduction

The Investigator Drill-Down feature adds a 4-level hierarchical exploration panel to the DOJ Antitrust Division Investigative Case Analysis platform (`investigator.html`). The panel slides in from the right as a fixed-position overlay, enabling prosecutors and investigators to progressively drill into case data — from high-level investigative threads, through entity networks, down to individual document evidence — with AI-generated narrative summaries at each level.

The feature is entirely client-side (pure HTML/CSS/JS, no build step). It leverages the existing API surface: the patterns endpoint for Neptune graph data, the search endpoint for OpenSearch document retrieval, and the cross-case analyze endpoint for cross-case flags. AI summaries are generated client-side by synthesizing entity and document data into prosecutor-style briefings, with a future hook for Bedrock RAG integration.

## Glossary

- **Platform**: The DOJ Antitrust Division Investigative Case Analysis platform — the complete system including all backend services, AI components, and the `investigator.html` frontend
- **Drill_Panel**: The fixed-position right-side overlay panel that hosts the 4-level hierarchical drill-down interface
- **Navigation_Stack**: An ordered array of NavigationEntry objects representing the user's current drill-down path, used to render the breadcrumb trail and support back-navigation
- **NavigationEntry**: A single entry in the Navigation_Stack containing level (1–4), title, icon, identifier, and cached level data
- **Thread_Classifier**: The component that takes raw Neptune graph data (nodes and edges) and groups entities into 6 investigative thread categories based on entity type mappings
- **Investigative_Thread**: A grouping of entities by category (Financial Network, Communication Chain, Property and Assets, Key Persons of Interest, Organizations and Entities, Timeline and Events) produced by the Thread_Classifier
- **AI_Narrator**: The component that generates prosecutor-style briefing text at each drill-down level by synthesizing entity and document data using client-side templates
- **Level_Renderer**: One of four renderer functions that produce the HTML content for each drill-down level (Threads, Thread Detail, Entity Profile, Document Evidence)
- **Entity_Profile**: A complete profile for a single entity at Level 3, including documents, neighbors, cross-case hits, timeline, and AI narrative
- **Cross_Case_Hit**: A record indicating that an entity appears in a case other than the currently selected case, including the other case's ID, name, and match count
- **Case_File**: A logical investigation container representing a single case, identified by a UUID
- **Knowledge_Graph**: The Neptune graph database containing entities and relationships extracted from case documents

## Requirements

### Requirement 1: Drill-Down Panel Lifecycle

**User Story:** As a prosecutor, I want to open and close a drill-down panel from the case view, so that I can explore case data in depth without leaving the main investigation interface.

#### Acceptance Criteria

1. WHEN a user clicks the "Investigate" button on a selected case, THE Drill_Panel SHALL slide in from the right side of the screen as a fixed-position overlay and load Level 1 content for that Case_File
2. WHEN the Drill_Panel is open, THE Drill_Panel SHALL display a close button that, when clicked, slides the panel out and clears the Navigation_Stack
3. WHEN the Drill_Panel is closed, THE Drill_Panel SHALL have an empty Navigation_Stack and the panel DOM element SHALL NOT have the "active" CSS class
4. WHEN the Drill_Panel is already closed and close is called, THE Drill_Panel SHALL perform no action and SHALL NOT throw an error
5. WHEN the Drill_Panel opens, THE Platform SHALL fetch graph data from the patterns API with graph mode enabled and classify the returned nodes into Investigative_Threads using the Thread_Classifier

### Requirement 2: Breadcrumb Navigation

**User Story:** As an investigator, I want a breadcrumb trail showing my drill-down path, so that I can see where I am in the hierarchy and quickly navigate back to any previous level.

#### Acceptance Criteria

1. THE Drill_Panel SHALL display a breadcrumb trail that reflects every entry in the Navigation_Stack, showing each entry's title and icon
2. WHEN a user clicks a breadcrumb segment at index i, THE Drill_Panel SHALL truncate the Navigation_Stack to index i+1 and re-render the view at that level
3. WHEN a user navigates to a new level, THE Drill_Panel SHALL append a new NavigationEntry to the Navigation_Stack and update the breadcrumb trail
4. THE Navigation_Stack SHALL contain at most 4 entries, corresponding to the 4 drill-down levels
5. WHEN navigateBack is called with an index less than 0 or greater than or equal to the Navigation_Stack length, THE Drill_Panel SHALL perform no action

### Requirement 3: Thread Classification (Level 1)

**User Story:** As a prosecutor, I want case entities automatically grouped into investigative threads (Financial, Communication, Property, Persons, Organizations, Timeline), so that I can see the major lines of inquiry at a glance.

#### Acceptance Criteria

1. WHEN the Thread_Classifier receives nodes and edges from the Knowledge_Graph, THE Thread_Classifier SHALL assign every node to exactly one Investigative_Thread based on the node's entity type
2. THE Thread_Classifier SHALL map entity types to threads as follows: financial_amount and account_number to Financial Network, phone_number and email to Communication Chain, address, location, and vehicle to Property and Assets, person to Key Persons of Interest, organization to Organizations and Entities, date and event to Timeline and Events
3. WHEN a node has an entity type not listed in the thread type mappings, THE Thread_Classifier SHALL assign that node to the Organizations and Entities thread as a default
4. WHEN an edge connects two entities in different Investigative_Threads, THE Thread_Classifier SHALL flag both entities with a crossThread indicator
5. THE Thread_Classifier SHALL compute entityCount for each thread equal to the number of entities in that thread's entities array
6. WHEN the patterns API returns zero nodes, THE Drill_Panel SHALL display an informational message indicating no entities were found and suggesting the user run the ingestion pipeline

### Requirement 4: Thread Detail View (Level 2)

**User Story:** As a prosecutor, I want to drill into a specific investigative thread to see its entities ranked by connectivity and an AI-generated briefing, so that I can prioritize which entities to investigate further.

#### Acceptance Criteria

1. WHEN a user clicks an Investigative_Thread card at Level 1, THE Drill_Panel SHALL navigate to Level 2 and display the thread's entities sorted by degree in descending order
2. THE Level_Renderer for Level 2 SHALL display each entity as a card showing the entity's icon, name, type, connection count, and a cross-thread badge when the entity has the crossThread flag
3. THE AI_Narrator SHALL generate a thread briefing that includes the thread label, entity count, connection count, top 5 entities by degree, cross-thread alerts when applicable, and thread-specific prosecutor guidance
4. THE Level_Renderer for Level 2 SHALL render a mini knowledge graph scoped to the thread's entities and edges using vis.js
5. WHEN a user clicks an entity card at Level 2, THE Drill_Panel SHALL navigate to Level 3 for that entity
