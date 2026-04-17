# Requirements Document

## Introduction

The Tracked Entity Workflow feature adds a persistent entity tracking system to the Investigator UI. Currently, investigators can save findings to a Research Notebook but have no way to pin specific entities (people, organizations, locations) for cross-tab investigation. This feature introduces a "tracked entities" concept: a floating bar visible across all tabs showing pinned entities, with automatic filtering and highlighting in Timeline, Map, and Evidence Library tabs. Tracked entities persist per case in localStorage and integrate with the existing Playbook sidebar to show contextual findings per step.

## Glossary

- **Tracked_Entity_Bar**: A persistent, floating UI bar displayed below the tab bar showing all currently tracked entities for the active case. Visible across all 7 tabs.
- **Tracked_Entity**: An entity (person, organization, location, or other named entity) that the investigator has pinned for cross-tab investigation. Stored as an object with name, type, and timestamp.
- **Track_Button**: A "📌 Track Entity" button rendered on AI Briefing finding cards, lead investigation results, search results, and Entity Dossier panels.
- **Entity_Filter**: The mechanism by which Timeline, Map, and Evidence Library tabs auto-filter or highlight content related to tracked entities when those tabs are loaded.
- **Playbook_Context_Panel**: A section within each expanded playbook step that shows what was found for tracked entities in the current view.
- **Tracked_Entity_Store**: The localStorage-based persistence layer that stores tracked entities per case using the key pattern `trackedEntities_{caseId}`.
- **Investigator_UI**: The single-page frontend application at `src/frontend/investigator.html` with 7 tabs and inline JavaScript.

## Requirements

### Requirement 1: Tracked Entity Bar Display

**User Story:** As an investigator, I want to see a persistent bar showing my tracked entities across all tabs, so that I always know which entities I am actively investigating.

#### Acceptance Criteria

1. THE Tracked_Entity_Bar SHALL render as a fixed bar below the tab bar and above tab content, visible across all 7 tabs.
2. WHEN no entities are tracked, THE Tracked_Entity_Bar SHALL display a placeholder message: "No tracked entities. Use 📌 to pin entities for cross-tab investigation."
3. WHEN one or more entities are tracked, THE Tracked_Entity_Bar SHALL display each Tracked_Entity as a badge showing the entity name, entity type icon, and a remove button.
4. THE Tracked_Entity_Bar SHALL use the existing dark theme styling (background: #1a2332, border: #2d3748, text: #e2e8f0, entity badges with accent colors per type: person=#63b3ed, organization=#9f7aea, location=#48bb78, other=#f6e05e).
5. WHEN the tracked entity list exceeds the visible width, THE Tracked_Entity_Bar SHALL allow horizontal scrolling to reveal additional entity badges.
6. THE Tracked_Entity_Bar SHALL display a count badge showing the total number of tracked entities.

### Requirement 2: Track Entity Button Placement

**User Story:** As an investigator, I want "📌 Track Entity" buttons on finding cards, search results, lead results, and Entity Dossier panels, so that I can pin entities for investigation from any discovery point.

#### Acceptance Criteria

1. WHEN the Investigator_UI renders an AI Briefing finding card in the Dashboard, THE Investigator_UI SHALL include a "📌 Track" button next to the existing "🔎 Investigate" button on each finding card.
2. WHEN the Investigator_UI renders search results via renderIntelligenceBrief(), THE Investigator_UI SHALL include a "📌 Track" button next to the existing "💾 Save to Notebook" button.
3. WHEN the Investigator_UI renders lead investigation results in the Lead Investigation tab, THE Investigator_UI SHALL include a "📌 Track" button on each lead card.
4. WHEN the Investigator_UI opens an Entity Dossier panel, THE Investigator_UI SHALL include a "📌 Track Entity" button in the dossier header next to the entity name.
5. WHEN an entity is already tracked, THE Track_Button SHALL display as "📌 Tracked" with a visually distinct style (filled/highlighted state) and clicking the button SHALL untrack the entity.
6. WHEN the investigator clicks a Track_Button for an untracked entity, THE Investigator_UI SHALL add the entity to the tracked list and update the Tracked_Entity_Bar immediately.

### Requirement 3: Untrack and Remove Entities

**User Story:** As an investigator, I want to remove entities from my tracked list, so that I can focus my investigation on the most relevant subjects.

#### Acceptance Criteria

1. WHEN the investigator clicks the remove button (✕) on a Tracked_Entity badge in the Tracked_Entity_Bar, THE Investigator_UI SHALL remove that entity from the tracked list.
2. WHEN an entity is removed from the tracked list, THE Tracked_Entity_Bar SHALL update immediately to reflect the removal.
3. WHEN an entity is removed from the tracked list, THE Tracked_Entity_Store SHALL persist the updated list to localStorage.
4. WHEN an entity is removed, THE Investigator_UI SHALL revert any Track_Buttons for that entity back to the untracked "📌 Track" state.
5. THE Tracked_Entity_Bar SHALL include a "Clear All" button that removes all tracked entities after a confirmation prompt.

### Requirement 4: Tracked Entity Persistence

**User Story:** As an investigator, I want my tracked entities to persist per case, so that I can resume my investigation across browser sessions.

#### Acceptance Criteria

1. THE Tracked_Entity_Store SHALL persist tracked entities to localStorage using the key `trackedEntities_{caseId}` where `{caseId}` is the value of `selectedCaseId`.
2. WHEN the investigator selects a case, THE Tracked_Entity_Store SHALL load tracked entities from localStorage for that case and populate the Tracked_Entity_Bar.
3. WHEN the investigator switches to a different case, THE Tracked_Entity_Bar SHALL update to show only the tracked entities for the newly selected case.
4. THE Tracked_Entity_Store SHALL store each tracked entity as a JSON object with fields: `name` (string, required), `type` (string: person/organization/location/other), and `trackedAt` (ISO 8601 timestamp).
5. IF localStorage write fails due to quota or other error, THEN THE Investigator_UI SHALL display a warning toast and retain the in-memory tracked entity list.
6. WHEN the investigator adds or removes a tracked entity, THE Tracked_Entity_Store SHALL persist the change immediately.

### Requirement 5: Timeline Tab Entity Filtering

**User Story:** As an investigator, I want the Timeline tab to highlight events related to my tracked entities, so that I can see temporal patterns for my investigation subjects.

#### Acceptance Criteria

1. WHEN the Timeline tab loads and tracked entities exist, THE Investigator_UI SHALL highlight timeline events that mention any tracked entity name in their description, title, or associated entities.
2. WHEN tracked entities exist, THE Timeline tab SHALL display a filter toggle allowing the investigator to switch between "Show All" and "Tracked Only" views.
3. WHEN "Tracked Only" filter is active, THE Timeline tab SHALL display only events related to tracked entities.
4. THE Timeline tab SHALL visually distinguish highlighted events using a colored left border matching the tracked entity type color.
5. WHEN no tracked entities exist, THE Timeline tab SHALL load normally without any filtering or highlighting.

### Requirement 6: Map Tab Entity Filtering

**User Story:** As an investigator, I want the Map tab to highlight locations related to my tracked entities, so that I can see geographic patterns for my investigation subjects.

#### Acceptance Criteria

1. WHEN the Map tab loads and tracked entities exist, THE Investigator_UI SHALL highlight map markers that are associated with any tracked entity.
2. WHEN tracked entities exist, THE Map tab SHALL display a filter toggle allowing the investigator to switch between "Show All" and "Tracked Only" views.
3. WHEN "Tracked Only" filter is active, THE Map tab SHALL display only markers related to tracked entities.
4. THE Map tab SHALL visually distinguish highlighted markers using a pulsing animation or distinct marker color.
5. WHEN no tracked entities exist, THE Map tab SHALL load normally without any filtering or highlighting.

### Requirement 7: Evidence Library Tab Entity Filtering

**User Story:** As an investigator, I want the Evidence Library to highlight documents related to my tracked entities, so that I can quickly find relevant evidence.

#### Acceptance Criteria

1. WHEN the Evidence Library tab loads and tracked entities exist, THE Investigator_UI SHALL highlight evidence items that mention any tracked entity name in their title, content, or entity tags.
2. WHEN tracked entities exist, THE Evidence Library tab SHALL display a filter toggle allowing the investigator to switch between "Show All" and "Tracked Only" views.
3. WHEN "Tracked Only" filter is active, THE Evidence Library tab SHALL display only evidence items related to tracked entities.
4. THE Evidence Library tab SHALL visually distinguish highlighted items using a colored left border or background tint.
5. WHEN no tracked entities exist, THE Evidence Library tab SHALL load normally without any filtering or highlighting.

### Requirement 8: Playbook Tracked Entity Context

**User Story:** As an investigator, I want each playbook step to show what was found for my tracked entities in the relevant view, so that I have investigation context at each step.

#### Acceptance Criteria

1. WHEN a playbook step is expanded and tracked entities exist, THE Playbook_Context_Panel SHALL display a summary of tracked entity relevance for that step's target tab.
2. WHEN the playbook step targets the Timeline tab, THE Playbook_Context_Panel SHALL show the count of timeline events matching each tracked entity.
3. WHEN the playbook step targets the Map tab, THE Playbook_Context_Panel SHALL show the count of map markers matching each tracked entity.
4. WHEN the playbook step targets the Evidence Library tab, THE Playbook_Context_Panel SHALL show the count of evidence items matching each tracked entity.
5. WHEN the playbook step targets the Lead Investigation tab, THE Playbook_Context_Panel SHALL show which tracked entities have matching leads and their investigation status.
6. WHEN no tracked entities exist, THE Playbook_Context_Panel SHALL display: "Pin entities with 📌 to see investigation context here."

### Requirement 9: Entity Tracking from Entity Links

**User Story:** As an investigator, I want to track entities directly from entity name links throughout the UI, so that I can quickly pin entities I encounter during investigation.

#### Acceptance Criteria

1. WHEN the investigator right-clicks or long-presses an entity link (elements with class `entity-link`), THE Investigator_UI SHALL show a context option to track that entity.
2. WHEN the Entity Dossier panel is open, THE Track_Button in the dossier header SHALL reflect the current tracked/untracked state of that entity.
3. WHEN the investigator tracks an entity from the Entity Dossier, THE Tracked_Entity_Bar SHALL update immediately without closing the dossier.

### Requirement 10: Tracked Entity Bar Interaction

**User Story:** As an investigator, I want to click on a tracked entity badge to quickly access its dossier, so that I can review entity details without searching.

#### Acceptance Criteria

1. WHEN the investigator clicks on a Tracked_Entity badge name in the Tracked_Entity_Bar, THE Investigator_UI SHALL open the Entity Dossier panel for that entity.
2. THE Tracked_Entity_Bar SHALL visually indicate which tracked entity is currently being viewed in the Entity Dossier (active state highlight).
3. WHEN the Entity Dossier is closed, THE Tracked_Entity_Bar SHALL remove the active state highlight from all entity badges.
