# Implementation Plan: Investigative Playbooks

## Overview

Add a collapsible sidebar playbook panel to `src/frontend/investigator.html` with three hardcoded playbook templates, localStorage persistence, step navigation/completion/notes, and keyboard shortcut. All code is inline CSS, HTML, and JavaScript in the single HTML file. No backend changes.

## Tasks

- [x] 1. Add CSS styles for the playbook panel
  - [x] 1.1 Add playbook panel CSS to the existing `<style>` block in investigator.html
    - Add `.playbook-panel` (fixed position, right: 0, width: 320px, z-index: 150, full height below header/tab bar, dark theme #1a2332 background, #2d3748 borders)
    - Add `.playbook-panel.collapsed` (width: 0, overflow: hidden)
    - Add `.playbook-toggle-btn` (fixed position, right edge, vertical center, z-index: 150)
    - Add `.playbook-step`, `.playbook-step.active` (blue left border #4299e1), `.playbook-step-expanded`
    - Add `.playbook-progress-bar` (green #48bb78 fill), `.playbook-selector`, `.playbook-note`, `.playbook-warning`
    - Add transition for panel expand/collapse (margin-right on `.ops-main` when panel is open)
    - _Requirements: 1.1, 1.2, 1.4, 1.6, 3.3, 7.1, 7.2, 12.1, 12.2_

- [x] 2. Add HTML for playbook panel and toggle button
  - [x] 2.1 Add playbook panel div and toggle button before `</body>` in investigator.html
    - Add `#playbookPanel` div with: header (title + collapse button), `#playbookWarning` element, `#playbookSelector` dropdown, `#playbookProgress` bar area, `#playbookSteps` scrollable container
    - Add `#playbookToggleBtn` fixed button showing "📋 Playbook N/M"
    - Add "Select a case" prompt element for no-case-selected state
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.7, 2.1, 3.1, 7.1, 7.4_

- [x] 3. Implement playbook templates as hardcoded JavaScript objects
  - [x] 3.1 Add `PLAYBOOK_TEMPLATES` object in the second `<script>` block (before closing `</script>` near line 7041+)
    - Define `general` template: 10 steps (Review AI Briefing → Dashboard, Triage Top Leads → leadinvestigation, Investigate Priority Subjects → leadinvestigation, Review Evidence → evidencelibrary, Map Connections → dashboard, Analyze Timeline → timeline, Check Geospatial Data → map, Document Findings → dashboard, Assess Case Strength → leadinvestigation, Generate Report → null)
    - Define `financial_fraud` template: 10 steps (Review AI Briefing → dashboard, Identify Financial Entities → leadinvestigation, Trace Money Flow → dashboard, Cross-Reference Public Records → dashboard, Map Corporate Structure → dashboard, Review Transaction Timeline → timeline, Identify Regulatory Violations → dashboard, Document Evidence Chain → dashboard, Assess Prosecution Readiness → leadinvestigation, Prepare Case Summary → null)
    - Define `human_trafficking` template: 10 steps (Review AI Briefing → dashboard, Identify Victims and Perpetrators → leadinvestigation, Map Travel Patterns → map, Analyze Communication Networks → dashboard, Review Document Evidence → evidencelibrary, Cross-Reference External Sources → dashboard, Build Timeline of Events → timeline, Identify Witnesses and Corroboration → leadinvestigation, Document Chain of Evidence → dashboard, Case Assessment and Referral → null)
    - Each step has: title, description, targetTab (string or null)
    - _Requirements: 2.2, 9.1–9.11, 10.1–10.10, 11.1–11.10_

- [x] 4. Implement playbook state management (localStorage read/write)
  - [x] 4.1 Add state management functions in the second `<script>` block
    - Implement `loadPlaybookState(caseId)` — reads from `localStorage['playbookState_' + caseId]`, parses JSON, validates template exists and step count matches, returns state or null
    - Implement `savePlaybookState(caseId)` — serializes current state to JSON, writes to localStorage, catches quota/write errors and calls `showPlaybookWarning()`
    - Implement `resetPlaybookState(templateId)` — creates fresh state: all statuses 'pending', all notes null, activeStepIndex 0, panelCollapsed from current state
    - Implement `calculateProgress(stepStatuses)` — returns percentage: `Math.round((complete + skipped) / total * 100)`
    - Implement `showPlaybookWarning(msg)` — shows warning in `#playbookWarning`, auto-hides after 4 seconds
    - Handle edge cases: malformed JSON → default to general, unknown template → default to general, wrong step count → reset
    - _Requirements: 2.3, 2.4, 2.5, 5.3, 5.4, 8.1, 8.2, 8.3, 8.4, 8.5, 14.2, 14.3_

  - [ ]* 4.2 Write property test for progress calculation (Property 1)
    - **Property 1: Progress calculation correctness**
    - Use fast-check to generate arrays of step statuses ('pending', 'in_progress', 'complete', 'skipped')
    - Assert `calculateProgress(statuses)` equals `Math.round((complete + skipped) / total * 100)`
    - Assert toggle text shows N = complete count, M = total count
    - **Validates: Requirements 1.4, 5.3, 7.2, 7.3, 7.4**

  - [ ]* 4.3 Write property test for template switch reset (Property 2)
    - **Property 2: Template switch resets all state**
    - Use fast-check to generate random template IDs from ['general', 'financial_fraud', 'human_trafficking']
    - Assert `resetPlaybookState(templateId)` produces all 'pending' statuses, all null notes, activeStepIndex 0, progress 0%
    - **Validates: Requirements 2.3, 2.4, 14.2, 14.3**

  - [ ]* 4.4 Write property test for state persistence round-trip (Property 3)
    - **Property 3: Playbook state persistence round-trip**
    - Use fast-check to generate valid playbook states (templateId, stepStatuses array, stepNotes array, activeStepIndex, panelCollapsed)
    - Assert save then load produces equivalent state object
    - **Validates: Requirements 2.5, 8.1, 8.2, 8.3, 15.2**

- [x] 5. Implement panel rendering (selector, progress bar, step list)
  - [x] 5.1 Add `renderPlaybookPanel()` function in the second `<script>` block
    - Populate `#playbookSelector` dropdown with template names, set selected to current templateId
    - Render `#playbookProgress` bar: filled width = progress%, text shows "N%"
    - Render `#playbookSteps` list: each step shows number, title, status icon (○ pending, ● in_progress, ✓ complete, — skipped)
    - Highlight active step with blue left border
    - Show "Select a case" prompt when no case is selected
    - Show "✅ Playbook complete!" when all steps are complete/skipped
    - Use `esc()` helper for all user-generated text (notes)
    - _Requirements: 1.7, 2.1, 3.1, 3.2, 3.3, 5.5, 7.1, 7.2, 7.3_

  - [ ]* 5.2 Write property test for step rendering (Property 4)
    - **Property 4: Step rendering includes number, title, and correct status icon**
    - Use fast-check to generate template + step index + status combinations
    - Assert rendered HTML contains step number (1-based), title text, and correct icon for status
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 5.3 Write property test for accordion behavior (Property 5)
    - **Property 5: Accordion — only one step expanded at a time**
    - Use fast-check to generate pairs of distinct step indices
    - Assert expanding step B collapses step A; at most one step detail visible
    - **Validates: Requirements 3.5**

- [x] 6. Implement step actions (navigate, complete, skip, notes)
  - [x] 6.1 Add step action functions in the second `<script>` block
    - Implement `playbookNavigate(stepIndex)` — calls `switchTab(step.targetTab)`, sets step as active, changes pending → in_progress, persists state
    - Implement `playbookComplete(stepIndex)` — sets status to 'complete', advances active step to next pending/in_progress, updates progress, persists state
    - Implement `playbookSkip(stepIndex)` — sets status to 'skipped', advances active step to next pending/in_progress, persists state
    - Implement `playbookToggleStep(stepIndex)` — expands clicked step detail (accordion: collapses any other expanded step)
    - Implement `playbookAddNote(stepIndex)` — shows text input below step actions
    - Implement `playbookSaveNote(stepIndex)` — saves note text + ISO timestamp to state, persists to localStorage, re-renders step
    - Disable Navigate button when step.targetTab is null; show tooltip "No tab action for this step"
    - Ignore empty note text on save
    - Allow editing existing notes by clicking on displayed note text
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4_

  - [ ]* 6.2 Write property test for navigate action (Property 6)
    - **Property 6: Navigate action calls switchTab and updates status**
    - Use fast-check to generate step index + initial status combinations for steps with non-null targetTab
    - Assert switchTab called with correct tab, step becomes active, pending → in_progress, other statuses unchanged
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [ ]* 6.3 Write property test for complete/skip advance (Property 7)
    - **Property 7: Complete and Skip advance active step to next actionable step**
    - Use fast-check to generate step index + array of statuses
    - Assert complete sets status to 'complete', skip sets to 'skipped', active advances to next pending/in_progress or stays if none
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 6.4 Write property test for note persistence (Property 8)
    - **Property 8: Note persistence round-trip**
    - Use fast-check to generate step index + non-empty note text
    - Assert saving note stores text + timestamp, reload preserves both
    - **Validates: Requirements 6.2, 6.3**

- [x] 7. Implement panel toggle and keyboard shortcut
  - [x] 7.1 Add toggle and keyboard handler in the second `<script>` block
    - Implement `togglePlaybookPanel()` — toggles `.collapsed` class on `#playbookPanel`, toggles `#playbookToggleBtn` visibility, adjusts `margin-right` on `.ops-main`, updates panelCollapsed in state, persists to localStorage
    - Add `keydown` listener: Ctrl+Shift+P (Cmd+Shift+P on Mac) calls `togglePlaybookPanel()`, `e.preventDefault()`
    - Ensure Escape key is NOT captured (reserved for Entity Dossier close)
    - _Requirements: 1.3, 1.5, 13.1, 13.2, 15.1, 15.2_

- [x] 8. Wire playbook into case selection flow
  - [x] 8.1 Add `loadPlaybookForCase(caseId)` call at end of existing case selection flow
    - Implement `loadPlaybookForCase(caseId)` — loads state from localStorage, falls back to general template if none, calls `renderPlaybookPanel()`, updates toggle button text
    - Hook into existing `selectCase()` function by appending the call (do NOT modify existing function body — add a wrapper or event-based hook)
    - Wire `#playbookSelector` change event to reset state and re-render
    - On initial page load: if a case is already selected, load its playbook state; if panel was expanded, restore expanded state; otherwise start collapsed
    - _Requirements: 2.5, 8.3, 8.4, 12.3, 12.4, 15.1, 15.2_

- [ ] 9. Checkpoint — Verify all functionality
  - Ensure all playbook panel features work: template selection, step navigation, completion, skip, notes, progress bar, toggle, keyboard shortcut, localStorage persistence
  - Ensure Entity Dossier panel still renders above playbook panel
  - Ensure all 6 tabs still function correctly with playbook panel open
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Deploy to S3
  - [x] 10.1 Upload updated investigator.html to S3 bucket
    - Upload `src/frontend/investigator.html` to S3 bucket `research-analyst-data-lake-974220725866`
    - Verify the file is accessible and the playbook panel renders correctly
    - _Requirements: 12.3, 12.4_

- [ ] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All code goes into `src/frontend/investigator.html`: CSS in `<style>`, HTML before `</body>`, JS in second `<script>` block before closing `</script>`
- Property tests validate universal correctness properties from the design document using fast-check
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation

### Testing Feedback — Navigation Issues

1. **"Document Findings" step lands on Knowledge Graph** — The step navigates to `dashboard` tab which is correct (that's where the Research Notebook lives), but the Dashboard shows the graph at the top and the user has to scroll down to find the search bar and notebook. Fix: add scroll-to-section behavior in `playbookNavigate()` — after calling `switchTab()`, scroll to the relevant DOM element (e.g., `document.getElementById('searchResults').scrollIntoView()`). This applies to all steps that target `dashboard` — each should scroll to the relevant section:
   - "Review AI Briefing" → scroll to AI briefing section (top of dashboard, no scroll needed)
   - "Map Connections" → scroll to graph section
   - "Document Findings" → scroll to search bar / Research Notebook section
   - "Assess Case Strength" → scroll to search results / confidence section

2. **Multiple steps target same tab** — Steps 1, 5, 8 all go to `dashboard`. The description text differentiates them but the visual experience is the same. Scroll-to-section would fix this. Alternatively, once Dashboard enhancements (Task 2 from consolidation spec) are built with distinct sections, each step can target a specific section anchor.

### Additional Testing Feedback

3. **"Assess Case Strength" goes to Lead Investigation** — This mapping is correct (leadinvestigation tab shows lead viability ratings after assessment), but the user expected something more like a case strength summary view. The leads need to be investigated first to show confidence levels. Consider: after Dashboard enhancements (Task 2), add a "Case Strength Summary" section to the Dashboard that aggregates confidence levels from all assessed leads — then "Assess Case Strength" could navigate there instead.
