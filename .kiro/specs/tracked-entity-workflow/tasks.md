# Implementation Plan: Tracked Entity Workflow

## Overview

Add a persistent entity-tracking system to `src/frontend/investigator.html`. Investigators pin entities from any discovery point (briefing cards, search results, leads, dossier, entity links) and see them in a floating bar across all 7 tabs. Tracked entities drive filtering/highlighting in Timeline, Map, and Evidence Library tabs, and provide contextual summaries in the Playbook sidebar. All state is localStorage per case. No backend changes. All code is inline CSS, HTML, and JavaScript in the single HTML file.

## Tasks

- [x] 1. Add CSS styles for the tracked entity bar and track buttons
  - [x] 1.1 Add tracked entity CSS to the existing `<style>` block in investigator.html
    - Add `#trackedEntityBar` styles (background: #1a2332, border-bottom: 1px solid #2d3748, padding: 6px 16px, flex row, min-height: 36px, overflow-x: auto, white-space: nowrap)
    - Add `.tracked-entity-badge` styles (inline-flex, gap: 4px, padding: 3px 10px, border-radius: 14px, font-size: 0.72em, cursor: pointer, border: 1px solid, transition: all 0.2s)
    - Add badge color variants: `.tracked-entity-badge[data-type="person"]` (#63b3ed border/text), `[data-type="organization"]` (#9f7aea), `[data-type="location"]` (#48bb78), `[data-type="other"]` (#f6e05e)
    - Add `.tracked-entity-badge.active` style (brighter border, background tint)
    - Add `.tracked-entity-badge .badge-remove` (background: none, border: none, color: #718096, cursor: pointer, font-size: 0.85em, hover: color #e53e3e)
    - Add `.track-entity-btn` styles (background: none, border: 1px solid #4a5568, color: #718096, padding: 3px 8px, border-radius: 4px, font-size: 0.72em, cursor: pointer)
    - Add `.track-entity-btn.tracked` styles (border-color: #63b3ed, color: #63b3ed, background: rgba(99,179,237,0.1))
    - Add `.tracked-entity-placeholder` (color: #4a5568, font-size: 0.72em, font-style: italic)
    - Add `.tracked-filter-toggle` styles (display: flex, gap: 4px, margin-bottom: 8px) and `.tracked-filter-btn` / `.tracked-filter-btn.active`
    - Add `.tracked-highlight` style (border-left: 3px solid, padding-left: 8px)
    - Add `#entityContextMenu` styles (position: fixed, z-index: 200, background: #1a2332, border: 1px solid #4a5568, border-radius: 6px, box-shadow, padding: 4px 0)
    - _Requirements: 1.4, 1.5, 2.5, 5.4, 6.4, 7.4_

- [x] 2. Add HTML for the tracked entity bar
  - [x] 2.1 Insert `#trackedEntityBar` div between the `.tabs` div and `<div id="tab-dashboard">` in investigator.html
    - Add `<div id="trackedEntityBar">` with: count span `#trackedEntityCount`, badges container `#trackedEntityBadges`, placeholder span, Clear All button `#trackedEntityClearAll`
    - Add `<div id="entityContextMenu" style="display:none;">` before `</body>` for the right-click context menu
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 3.5, 9.1_

- [x] 3. Implement core tracked entity state management
  - [x] 3.1 Add state variables and core functions in the second `<script>` block
    - Add `var _trackedEntities = [];` and filter state vars (`_trackedEntityTimelineFilter`, `_trackedEntityMapFilter`, `_trackedEntityEvidenceFilter` — all default `'all'`)
    - Implement `_loadTrackedEntities()` — reads `localStorage.getItem('trackedEntities_' + selectedCaseId)`, parses JSON in try/catch, falls back to `[]` on error, populates `_trackedEntities`
    - Implement `_persistTrackedEntities()` — `JSON.stringify(_trackedEntities)` → `localStorage.setItem(...)`, try/catch for quota errors → `showToast('⚠ Could not save tracked entities — storage full')`
    - Implement `trackEntity(name, type)` — check `isEntityTracked(name)`, if not tracked push `{name, type: type || 'other', trackedAt: new Date().toISOString()}`, persist, re-render bar, update track buttons
    - Implement `untrackEntity(name)` — filter out by case-insensitive name match, persist, re-render bar, update track buttons
    - Implement `isEntityTracked(name)` — returns boolean, case-insensitive `.some()` check
    - Implement `clearAllTrackedEntities()` — `confirm()` prompt, if yes clear array, persist, re-render bar, update track buttons
    - Implement `toggleTrackEntity(btn)` — reads `data-track-entity` and `data-track-type` from button, calls `trackEntity` or `untrackEntity` based on current state
    - _Requirements: 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.4, 4.5, 4.6_

  - [ ]* 3.2 Write property test for trackEntity/untrackEntity (Property 3 & 4)
    - **Property 3: trackEntity adds entity to list**
    - **Property 4: untrackEntity removes entity from list**
    - Use fast-check to generate entity names and types, verify length changes and isEntityTracked results
    - **Validates: Requirements 2.6, 3.1, 3.2**

  - [ ]* 3.3 Write property test for persistence round-trip (Property 5)
    - **Property 5: Persistence round-trip**
    - Use fast-check to generate sequences of track/untrack operations, verify localStorage matches in-memory array
    - **Validates: Requirements 3.3, 4.1, 4.2, 4.6**

  - [ ]* 3.4 Write property test for case isolation (Property 6)
    - **Property 6: Case isolation**
    - Use fast-check to generate two case IDs with independent entity sets, verify switching preserves each case's data
    - **Validates: Requirements 4.3**

  - [ ]* 3.5 Write property test for JSON structure (Property 7)
    - **Property 7: Tracked entity JSON structure**
    - Use fast-check to generate entities, verify each has non-empty name, valid type, valid ISO 8601 trackedAt
    - **Validates: Requirements 4.4**

- [x] 4. Implement tracked entity bar rendering
  - [x] 4.1 Add `renderTrackedEntityBar()` and `updateTrackButtons()` functions
    - `renderTrackedEntityBar()` — if `_trackedEntities.length === 0`, show placeholder message "No tracked entities. Use 📌 to pin entities for cross-tab investigation." and hide Clear All button; otherwise render badges with entity name, type icon (person=👤, organization=🏢, location=📍, other=🔖), remove ✕ button, and show count + Clear All button
    - `updateTrackButtons()` — query all `[data-track-entity]` buttons, for each check `isEntityTracked()`, toggle `.tracked` class and update text to "📌 Tracked" or "📌 Track"
    - _Requirements: 1.2, 1.3, 1.6, 2.5, 3.4_

  - [ ]* 4.2 Write property test for bar rendering invariant (Property 1)
    - **Property 1: Bar rendering invariant**
    - Use fast-check to generate arrays of 0-20 tracked entities, verify count display, badge count, and placeholder behavior
    - **Validates: Requirements 1.2, 1.3, 1.6**

  - [ ]* 4.3 Write property test for track button state (Property 2)
    - **Property 2: Track button state reflects tracked status**
    - Use fast-check to generate entity names and tracked/untracked states, verify button text and class
    - **Validates: Requirements 2.5, 3.4, 9.2**

- [ ] 5. Checkpoint — Core state and bar rendering
  - Ensure tracked entity bar renders correctly with 0 and N entities, track/untrack works, localStorage persists, case switch loads correct entities.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Add track buttons to discovery points
  - [x] 6.1 Add track buttons to AI Briefing finding cards, search results, lead cards, and Entity Dossier
    - Extend AI Briefing finding card rendering (in `loadDashboardAIBriefing` or its render helper) to include a `<button class="track-entity-btn" data-track-entity="..." data-track-type="..." onclick="toggleTrackEntity(this)">📌 Track</button>` next to the existing "🔎 Investigate" button
    - Extend `renderIntelligenceBrief()` to include a track button next to the "💾 Save to Notebook" button on each entity/finding result
    - Extend lead card rendering in `renderLeadQueue()` to include a track button in the lead card header area
    - Extend `openEntityDossier()` to include a track button in the dossier header next to the entity name, reflecting current tracked state
    - Call `updateTrackButtons()` after each render to sync button states
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 9.2_

- [x] 7. Add entity link context menu for tracking
  - [x] 7.1 Implement right-click context menu on `.entity-link` elements
    - Add `contextmenu` event listener on `document.body` that checks if target (or closest) is `.entity-link`
    - If yes, prevent default, position `#entityContextMenu` at mouse coordinates, populate with "📌 Track Entity" or "📌 Untrack Entity" based on current state
    - Add click-away listener to hide the context menu
    - Extract entity name from the link text content and type from `data-entity-type` attribute (or default to 'other')
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 8. Add badge click → Entity Dossier and active state
  - [x] 8.1 Wire badge click to open Entity Dossier and manage active highlight
    - In `renderTrackedEntityBar()`, make badge name clickable → calls `openEntityDossier(name, type)`
    - Add `.active` class to clicked badge, remove from others
    - Hook into dossier close to remove `.active` class from all badges
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 9. Wire tracked entities into case selection flow
  - [x] 9.1 Hook `_loadTrackedEntities()` and `renderTrackedEntityBar()` into `selectCase()`
    - Append `_loadTrackedEntities(); renderTrackedEntityBar();` call at the end of `selectCase()` (extend, don't replace)
    - Reset filter state vars to `'all'` on case switch
    - On initial page load, if a case is already selected, load its tracked entities
    - _Requirements: 4.2, 4.3_

- [ ] 10. Checkpoint — Track buttons and case integration
  - Ensure track buttons appear in all 4 discovery points, toggle state works, context menu works on entity links, badge click opens dossier, case switch loads correct tracked entities.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Timeline tab entity filtering
  - [x] 11.1 Add `applyTrackedEntityTimelineFilter()` function and hook into `loadTimeline()`
    - After `loadTimeline()` renders, if `_trackedEntities.length > 0`, inject a filter toggle ("Show All" / "Tracked Only") at the top of the timeline content
    - For each timeline event, concatenate title + description + entities into lowercase string, check if any tracked entity name is a case-insensitive substring
    - Matching events get a colored left border (entity type color)
    - When "Tracked Only" is active, hide non-matching events
    - When no tracked entities, skip filtering entirely
    - Hook call at end of `loadTimeline()` or via the `switchTab('timeline')` lazy-load path
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 12. Implement Map tab entity filtering
  - [x] 12.1 Add `applyTrackedEntityMapFilter()` function and hook into `loadMap()`
    - After `loadMap()` renders markers, if `_trackedEntities.length > 0`, inject a filter toggle at the top of the map content
    - For each map marker, check if associated entity names match any tracked entity (case-insensitive substring)
    - Matching markers get a pulsing animation or distinct color
    - When "Tracked Only" is active, hide non-matching markers
    - When no tracked entities, skip filtering entirely
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 13. Implement Evidence Library tab entity filtering
  - [x] 13.1 Add `applyTrackedEntityEvidenceFilter()` function and hook into `loadEvidence()`
    - After `loadEvidence()` renders, if `_trackedEntities.length > 0`, inject a filter toggle at the top of the evidence content
    - For each evidence item, concatenate filename + labels + matched_entities into lowercase string, check for tracked entity name matches
    - Matching items get a colored left border or background tint
    - When "Tracked Only" is active, hide non-matching items
    - When no tracked entities, skip filtering entirely
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 13.2 Write property test for entity matching function (Property 8)
    - **Property 8: Entity matching function correctness**
    - Use fast-check to generate tracked entity names and text items, verify matching returns true iff at least one entity name is a case-insensitive substring
    - **Validates: Requirements 5.1, 5.3, 6.1, 6.3, 7.1, 7.3**

- [ ] 14. Checkpoint — Tab filtering
  - Ensure Timeline, Map, and Evidence Library tabs show filter toggles when tracked entities exist, highlighting works, "Tracked Only" filter hides non-matching items, no filtering when no tracked entities.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement Playbook tracked entity context panel
  - [x] 15.1 Add `renderPlaybookEntityContext(stepIndex)` function and hook into playbook step expansion
    - When a playbook step is expanded and `_trackedEntities.length > 0`, append a context section below the step actions
    - For timeline-targeting steps: count matching timeline events per tracked entity using the same matching logic
    - For map-targeting steps: count matching map markers per tracked entity
    - For evidence-targeting steps: count matching evidence items per tracked entity
    - For lead-targeting steps: show which tracked entities have matching leads and their status
    - When no tracked entities, show: "Pin entities with 📌 to see investigation context here."
    - When tab data not yet loaded, show: "Load [tab name] to see entity context"
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 15.2 Write property test for playbook context counts (Property 9)
    - **Property 9: Playbook context counts match actual data**
    - Use fast-check to generate tracked entities and tab data arrays, verify reported counts match actual matching item counts
    - **Validates: Requirements 8.2, 8.3, 8.4, 8.5**

- [ ] 16. Deploy to S3
  - [ ] 16.1 Upload updated investigator.html to S3 bucket
    - Run: `aws s3 cp src/frontend/investigator.html s3://research-analyst-data-lake-974220725866/frontend/investigator.html --content-type "text/html"`
    - Verify the tracked entity bar renders and track buttons appear
    - _Requirements: all_

- [ ] 17. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All code goes into `src/frontend/investigator.html`: CSS in `<style>`, HTML between `.tabs` and tab content divs, JS in second `<script>` block
- Use `var` for top-level variables (existing codebase convention); template literals inside functions are OK
- Use `esc()` helper for all entity names before HTML insertion (XSS prevention)
- Property tests validate universal correctness properties from the design document using fast-check
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
