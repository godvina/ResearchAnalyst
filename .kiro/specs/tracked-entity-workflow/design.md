# Design Document: Tracked Entity Workflow

## Overview

The Tracked Entity Workflow adds a persistent entity-pinning system to the Investigator UI (`src/frontend/investigator.html`). Investigators can pin entities (people, organizations, locations) from any discovery point and see them in a persistent bar across all tabs. Tracked entities drive automatic filtering/highlighting in Timeline, Map, and Evidence Library tabs, and provide contextual summaries in the Playbook sidebar.

This is a frontend-only feature. All state is stored in localStorage per case. No backend API changes are needed. All code changes extend the existing inline JavaScript and HTML in `investigator.html`.

### Key Design Decisions

1. **Fixed HTML bar, not dynamically generated per case**: The Tracked Entity Bar is a static `<div>` in the HTML, placed between the `.tabs` div and the first `tab-content` div. Its contents are re-rendered by JS when tracked entities change or a case is selected.
2. **In-memory array + localStorage sync**: A `var _trackedEntities = []` array holds the current case's tracked entities. Every mutation syncs to `localStorage` immediately. On case switch, the array is reloaded from localStorage.
3. **Case-insensitive substring matching**: Entity filtering in Timeline, Map, and Evidence tabs uses `text.toLowerCase().indexOf(entityName.toLowerCase()) !== -1` — consistent with the existing Entity Dossier findings filter pattern.
4. **Extend, never replace**: All changes add new functions and HTML. Existing `loadTimeline()`, `loadMap()`, `loadEvidence()`, `openEntityDossier()`, and `renderPlaybookPanel()` are extended with post-render hooks, not rewritten.

## Architecture

```mermaid
graph TD
    subgraph "Tracked Entity System"
        TEBar["Tracked Entity Bar (HTML div)"]
        TEStore["localStorage: trackedEntities_{caseId}"]
        TEMemory["var _trackedEntities (in-memory array)"]
    end

    subgraph "Entry Points (Track Buttons)"
        BriefingCard["AI Briefing Finding Cards"]
        SearchResult["Search Results"]
        LeadCard["Lead Investigation Cards"]
        DossierPanel["Entity Dossier Panel"]
        EntityLink["entity-link Right-Click"]
    end

    subgraph "Consumers (Filtering)"
        Timeline["loadTimeline() → applyTrackedEntityFilter()"]
        MapTab["loadMap() → applyTrackedEntityMapFilter()"]
        Evidence["loadEvidence() → applyTrackedEntityEvidenceFilter()"]
        Playbook["renderPlaybookPanel() → renderPlaybookEntityContext()"]
    end

    BriefingCard -->|trackEntity()| TEMemory
    SearchResult -->|trackEntity()| TEMemory
    LeadCard -->|trackEntity()| TEMemory
    DossierPanel -->|trackEntity()| TEMemory
    EntityLink -->|trackEntity()| TEMemory

    TEMemory -->|_persistTrackedEntities()| TEStore
    TEMemory -->|renderTrackedEntityBar()| TEBar

    TEMemory --> Timeline
    TEMemory --> MapTab
    TEMemory --> Evidence
    TEMemory --> Playbook

    selectCase -->|_loadTrackedEntities()| TEStore
    TEStore -->|parse JSON| TEMemory
```

### Data Flow

1. **Track**: User clicks 📌 → `trackEntity(name, type)` → pushes to `_trackedEntities` → `_persistTrackedEntities()` → `renderTrackedEntityBar()` → updates any visible Track Buttons to "Tracked" state
2. **Untrack**: User clicks ✕ on badge or clicks "Tracked" button → `untrackEntity(name)` → filters `_trackedEntities` → persist → re-render bar → revert Track Buttons
3. **Case Switch**: `selectCase(caseId)` calls `_loadTrackedEntities()` → reads `localStorage.getItem('trackedEntities_' + caseId)` → populates `_trackedEntities` → `renderTrackedEntityBar()`
4. **Tab Filter**: `switchTab('timeline')` → `loadTimeline()` runs → after render, `applyTrackedEntityFilter()` injects filter toggle and highlights matching events

## Components and Interfaces

### 1. Tracked Entity Bar (HTML)

A fixed `<div id="trackedEntityBar">` inserted in the HTML between the `.tabs` div and `<div id="tab-dashboard">`. Styled with the dark theme.

```html
<!-- Tracked Entity Bar — inserted after .tabs div -->
<div id="trackedEntityBar" style="background:#1a2332;border-bottom:1px solid #2d3748;padding:6px 16px;display:flex;align-items:center;gap:8px;min-height:36px;overflow-x:auto;white-space:nowrap;">
    <span id="trackedEntityCount" style="font-size:0.7em;font-weight:700;color:#718096;flex-shrink:0;">📌 0</span>
    <div id="trackedEntityBadges" style="display:flex;gap:6px;align-items:center;overflow-x:auto;flex:1;"></div>
    <button id="trackedEntityClearAll" onclick="clearAllTrackedEntities()" style="display:none;flex-shrink:0;background:none;border:1px solid #4a5568;color:#718096;padding:2px 8px;border-radius:4px;font-size:0.65em;cursor:pointer;">Clear All</button>
</div>
```

### 2. Core State Functions (JavaScript)

```
var _trackedEntities = [];

function _loadTrackedEntities()        // Read from localStorage for selectedCaseId
function _persistTrackedEntities()     // Write to localStorage, with try/catch for quota errors
function trackEntity(name, type)       // Add entity, deduplicate by name (case-insensitive), persist, re-render
function untrackEntity(name)           // Remove by name (case-insensitive), persist, re-render
function isEntityTracked(name)         // Returns boolean, case-insensitive match
function clearAllTrackedEntities()     // Confirm prompt, then clear array, persist, re-render
function renderTrackedEntityBar()      // Rebuild badge HTML in #trackedEntityBadges
function updateTrackButtons()          // Scan DOM for [data-track-entity] buttons, toggle tracked/untracked style
```

### 3. Track Button Rendering

Track buttons are added to existing render functions. Each button has a `data-track-entity` attribute with the entity name and `data-track-type` with the entity type:

```html
<button class="track-entity-btn" data-track-entity="John Doe" data-track-type="person"
        onclick="toggleTrackEntity(this)" style="...">📌 Track</button>
```

When tracked, the button text changes to "📌 Tracked" with a highlighted border color.

Placement locations:
- **AI Briefing finding cards**: Next to existing "🔎 Investigate" button
- **Search results** (`renderIntelligenceBrief()`): Next to "💾 Save to Notebook"
- **Lead cards** (`renderLeadQueue()`): In the lead card header
- **Entity Dossier** (`openEntityDossier()`): In the dossier header next to entity name

### 4. Tab Filter Functions

Each tab gets a post-load filter function that:
1. Checks if `_trackedEntities.length > 0`
2. If yes, injects a filter toggle ("Show All" / "Tracked Only") at the top of the tab content
3. Highlights matching items with a colored left border
4. When "Tracked Only" is active, hides non-matching items

```
function applyTrackedEntityTimelineFilter()   // Hooks after loadTimeline() renders
function applyTrackedEntityMapFilter()        // Hooks after loadMap() renders markers
function applyTrackedEntityEvidenceFilter()   // Hooks after loadEvidence() renders grid
```

**Matching logic**: For each item (event/marker/evidence), concatenate its text fields (title, description, entities, etc.) into a single lowercase string, then check if any tracked entity name appears as a substring.

### 5. Playbook Context Panel

When a playbook step is expanded, `renderPlaybookEntityContext(stepIndex)` appends a context section showing:
- For timeline-targeting steps: count of matching timeline events per tracked entity
- For map-targeting steps: count of matching map markers per tracked entity
- For evidence-targeting steps: count of matching evidence items per tracked entity
- For lead-targeting steps: which tracked entities have matching leads and their status

This uses the already-loaded data arrays (`tlEvents`, `mapMarkers`, `evidenceImages`, lead queue data).

### 6. Entity Link Context Menu

A `contextmenu` event listener on `document.body` checks if the target is an `.entity-link` element. If so, it shows a small custom context menu with "📌 Track Entity" / "📌 Untrack Entity" option. The menu is a positioned `<div>` that auto-hides on click-away.

### 7. Badge Click → Dossier

Clicking a tracked entity badge name calls `openEntityDossier(name, type)` — reusing the existing dossier panel. The clicked badge gets an `active` CSS class (brighter border). When the dossier closes, the active class is removed.

## Data Models

### Tracked Entity Object (localStorage)

```json
{
    "name": "Jeffrey Epstein",
    "type": "person",
    "trackedAt": "2025-01-15T10:30:00.000Z"
}
```

### localStorage Key Pattern

```
trackedEntities_{caseId}
```

Value: JSON array of tracked entity objects.

Example:
```json
[
    {"name": "Jeffrey Epstein", "type": "person", "trackedAt": "2025-01-15T10:30:00Z"},
    {"name": "Palm Beach", "type": "location", "trackedAt": "2025-01-15T10:31:00Z"},
    {"name": "JP Morgan Chase", "type": "organization", "trackedAt": "2025-01-15T10:32:00Z"}
]
```

### Entity Type Color Map

Reuses existing `TYPE_COLORS` where possible, with specific badge colors:

| Type | Badge Color | Border |
|------|------------|--------|
| person | #63b3ed | rgba(99,179,237,0.3) |
| organization | #9f7aea | rgba(159,122,234,0.3) |
| location | #48bb78 | rgba(72,187,120,0.3) |
| other | #f6e05e | rgba(246,224,94,0.3) |

### Filter State Variables

```javascript
var _trackedEntities = [];                    // Current case's tracked entities
var _trackedEntityTimelineFilter = 'all';     // 'all' or 'tracked'
var _trackedEntityMapFilter = 'all';          // 'all' or 'tracked'
var _trackedEntityEvidenceFilter = 'all';     // 'all' or 'tracked'
```

These reset to `'all'` on case switch.


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Bar rendering invariant

*For any* array of tracked entities (0 to N), calling `renderTrackedEntityBar()` should produce HTML where: (a) the count display equals the array length, (b) each entity in the array has exactly one badge containing its name and a remove button, and (c) when the array is empty, the placeholder message is shown instead of badges.

**Validates: Requirements 1.2, 1.3, 1.6**

### Property 2: Track button state reflects tracked status

*For any* entity name, the result of `isEntityTracked(name)` should determine the button state: if true, all `[data-track-entity]` buttons matching that name (case-insensitive) should display "📌 Tracked" style; if false, they should display "📌 Track" style.

**Validates: Requirements 2.5, 3.4, 9.2**

### Property 3: trackEntity adds entity to list

*For any* valid entity name and type that is not already tracked, calling `trackEntity(name, type)` should increase `_trackedEntities.length` by exactly 1, and `isEntityTracked(name)` should return true afterward.

**Validates: Requirements 2.6, 3.1**

### Property 4: untrackEntity removes entity from list

*For any* entity name that is currently tracked, calling `untrackEntity(name)` should decrease `_trackedEntities.length` by exactly 1, and `isEntityTracked(name)` should return false afterward.

**Validates: Requirements 3.1, 3.2**

### Property 5: Persistence round-trip

*For any* case ID and any sequence of `trackEntity` / `untrackEntity` operations, reading back from `localStorage.getItem('trackedEntities_' + caseId)` and parsing the JSON should produce an array equivalent to the current `_trackedEntities` in-memory array.

**Validates: Requirements 3.3, 4.1, 4.2, 4.6**

### Property 6: Case isolation

*For any* two distinct case IDs with independently tracked entity sets, switching from case A to case B via `_loadTrackedEntities()` should load only case B's entities, and switching back to case A should restore case A's entities unchanged.

**Validates: Requirements 4.3**

### Property 7: Tracked entity JSON structure

*For any* tracked entity in the `_trackedEntities` array, the object should have a `name` (non-empty string), a `type` (one of 'person', 'organization', 'location', 'other'), and a `trackedAt` (valid ISO 8601 timestamp string).

**Validates: Requirements 4.4**

### Property 8: Entity matching function correctness

*For any* set of tracked entity names and any text item (timeline event description, map marker name, evidence item title/content), the matching function should return true if and only if at least one tracked entity name appears as a case-insensitive substring of the item's concatenated text fields. When the "Tracked Only" filter is active, only matching items should be included in the filtered result set.

**Validates: Requirements 5.1, 5.3, 6.1, 6.3, 7.1, 7.3**

### Property 9: Playbook context counts match actual data

*For any* playbook step targeting a specific tab and any set of tracked entities, the count reported in the Playbook Context Panel for each tracked entity should equal the number of items in that tab's data array that match the entity name using the same matching function from Property 8.

**Validates: Requirements 8.2, 8.3, 8.4, 8.5**

## Error Handling

| Scenario | Handling |
|----------|----------|
| localStorage quota exceeded on persist | Catch error in `_persistTrackedEntities()`, show warning toast via `showToast('⚠ Could not save tracked entities — storage full')`, retain in-memory array |
| Corrupted JSON in localStorage | `_loadTrackedEntities()` wraps `JSON.parse` in try/catch, falls back to empty array `[]` |
| Entity name contains special characters | `esc()` function (already exists) sanitizes all entity names before HTML insertion |
| Duplicate track attempt (same entity name, case-insensitive) | `trackEntity()` checks `isEntityTracked()` first, silently no-ops if already tracked |
| Case switch with no localStorage entry | `_loadTrackedEntities()` returns empty array, bar shows placeholder |
| Tab data not yet loaded when playbook context requested | Context panel shows "Load [tab name] to see entity context" message |
| Entity Dossier fails to open from badge click | Reuses existing `openEntityDossier()` error handling (retry button) |

## Testing Strategy

### Unit Tests

Unit tests verify specific examples and edge cases:

- Empty tracked list renders placeholder message
- Track button appears in AI Briefing card render output
- Track button appears in search result render output
- Track button appears in lead card render output
- Track button appears in Entity Dossier header
- Clear All button triggers confirmation and clears list
- Right-click on entity-link shows context menu
- Badge click opens Entity Dossier
- Filter toggle appears when tracked entities exist
- Filter toggle does not appear when no tracked entities
- localStorage quota error shows toast and retains in-memory data
- Corrupted localStorage JSON falls back to empty array

### Property-Based Tests

Property-based tests verify universal properties across randomized inputs. Use **fast-check** as the PBT library (JavaScript, runs in browser or Node).

Each property test should run a minimum of 100 iterations.

Each test must be tagged with a comment referencing the design property:
- **Feature: tracked-entity-workflow, Property 1: Bar rendering invariant**
- **Feature: tracked-entity-workflow, Property 2: Track button state reflects tracked status**
- **Feature: tracked-entity-workflow, Property 3: trackEntity adds entity to list**
- **Feature: tracked-entity-workflow, Property 4: untrackEntity removes entity from list**
- **Feature: tracked-entity-workflow, Property 5: Persistence round-trip**
- **Feature: tracked-entity-workflow, Property 6: Case isolation**
- **Feature: tracked-entity-workflow, Property 7: Tracked entity JSON structure**
- **Feature: tracked-entity-workflow, Property 8: Entity matching function correctness**
- **Feature: tracked-entity-workflow, Property 9: Playbook context counts match actual data**

**Generators needed:**
- Entity name generator: random non-empty strings including unicode, spaces, special characters
- Entity type generator: one of `['person', 'organization', 'location', 'other']`
- Tracked entity list generator: arrays of 0-20 entity objects with unique names
- Case ID generator: UUID-format strings
- Text item generator: random strings that may or may not contain entity names as substrings
- Timeline event generator: objects with `description`, `title`, `entities` fields
- Evidence item generator: objects with `filename`, `labels`, `matched_entities` fields

**Note:** Since this is an inline-JS frontend feature with no module system, property tests would need to either:
1. Extract the core logic functions (`trackEntity`, `untrackEntity`, `isEntityTracked`, entity matching) into testable pure functions, or
2. Use a DOM testing approach (jsdom + fast-check) to test the integrated behavior

The recommended approach is (1): extract the core state management and matching logic into pure functions that can be tested independently of the DOM.
