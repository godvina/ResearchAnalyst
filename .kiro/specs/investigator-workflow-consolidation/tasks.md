# Implementation Plan: Investigator Workflow Consolidation

## Overview

Restructure `src/frontend/investigator.html` from 16 tabs to 7 focused tabs following the investigative workflow pattern. All backend services are deployed — the only backend change is a minor AIResearchAgent wiring fix. Implementation is incremental: restructure tab bar first, then build each tab's content, then clean up removed content, then deploy.

## Tasks

- [x] 1. Restructure Tab Bar from 16 to 7 tabs
  - [x] 1.1 Replace the existing 16-tab bar HTML in `src/frontend/investigator.html` with 7 tabs: 📋 Case Dashboard (`dashboard`), 🎯 Lead Investigation (`leadinvestigation`), 🔍 Evidence Library (`evidencelibrary`), 📅 Timeline (`timeline`), 🗺️ Map (`map`), ⚙️ Pipeline (`pipeline`), 📊 Portfolio (`portfolio`)
    - Add `<span class="tab-indicator"></span>` inside each tab button for workflow indicators
    - Set Case Dashboard as the default active tab on load
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 1.2 Update the `switchTab()` function to use the new 7-tab `allTabs` array and add lazy-load triggers for each tab
    - Update tab content div toggling to match new tab IDs
    - Add lazy-load calls: `loadDashboard()`, `loadLeadQueue()`, `loadEvidence()`, `loadTimeline()`, `loadMap()`, `loadPipelineStatus()`, `loadPortfolio()`
    - _Requirements: 1.5, 16.2_

  - [x] 1.3 Create empty `<div id="tab-dashboard" class="tab-content">`, `<div id="tab-leadinvestigation" class="tab-content">`, and `<div id="tab-evidencelibrary" class="tab-content">` placeholder divs
    - These will be populated in subsequent tasks
    - Rename existing `tab-pipeline` div to hold the merged pipeline content
    - _Requirements: 1.1_

- [x] 2. Build Case Dashboard tab content
  - [x] 2.1 Build the `tab-dashboard` layout with left sidebar (case list) and right main content area
    - Migrate the existing case sidebar HTML from `tab-cases` into the dashboard left panel
    - Preserve the case selection click handler, updating it to set `window.selectedCaseId` and `window.selectedCaseData` shared state
    - On case select: clear `window._sectionCache`, reset all tab indicator dots, trigger AI Briefing fetch
    - _Requirements: 2.1, 16.1, 16.4_

  - [x] 2.2 Implement the AI Briefing Section in the dashboard main content area
    - Add loading skeleton with animated placeholders shown during fetch
    - Fetch from `GET /case-files/{id}/investigator-analysis` on case select
    - Render executive summary narrative, case statistics (doc count, entity count, relationship count, active leads), and finding cards grid
    - Each finding card gets a "🔎 Investigate" button that calls `POST /case-files/{id}/investigative-search`
    - Show Intelligence Brief results in a slide-out panel using existing `.drill-overlay` + `.drill-panel` pattern
    - Add error fallback with "Retry" button if API fails
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 2.3 Migrate the search bar and Research Notebook into the dashboard
    - Move existing search bar HTML with Internal/External scope toggle
    - Move existing Research Notebook panel (findings list with title, summary, tags, date, confidence badge)
    - Preserve "Save Finding" button on Intelligence Brief results calling `POST /case-files/{id}/findings`
    - Ensure External scope passes `search_scope: "internal_external"` to the API
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.4 Implement collapsible intelligence sections in the dashboard
    - Add 4 collapsible sections: Evidence Triage, AI Hypotheses, Subpoena Recommendations, Top Patterns
    - Implement `toggleSection(sectionId, fetchFn)` with lazy-fetch on first expand and `window._sectionCache` caching
    - Wire fetch functions: `/case-files/{id}/evidence-triage`, `/case-files/{id}/ai-hypotheses`, `/case-files/{id}/subpoena-recommendations`, `/case-files/{id}/patterns` (top 5)
    - Add per-section error fallback with "Retry" button
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 2.5 Write property tests for Dashboard (Properties 1, 2, 3)
    - **Property 1: Case selection triggers shared state update and dashboard auto-fetch**
    - **Property 2: AI Briefing rendering completeness**
    - **Property 3: Collapsible section lazy-fetch and caching**
    - **Validates: Requirements 2.1, 2.2, 2.4, 4.5, 16.1, 16.2, 16.4, 19.2**

- [ ] 3. Checkpoint — Verify Dashboard tab
  - Ensure the Case Dashboard tab loads, case selection works, AI Briefing renders, collapsible sections expand/collapse, and search + Research Notebook function correctly. Ask the user if questions arise.

- [x] 4. Build Lead Investigation tab
  - [x] 4.1 Implement the lead queue UI in `tab-leadinvestigation`
    - Fetch leads from `GET /case-files/{id}/investigative-leads` on tab activation
    - Render Lead Cards with: entity name, color-coded score badge (green >70, yellow 40-70, red <40), AI justification one-liner, status badge (New=blue, Investigating=amber, Assessed=green/red, Closed=gray)
    - Default sort by score descending; add sort toggles for status and name
    - Show empty state message when no leads exist with prompt to run AI Briefing or import leads
    - Load lead statuses from `localStorage['leadStatuses_' + caseId]` on case select
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.1, 9.3, 9.4_

  - [x] 4.2 Implement the "Investigate Lead" action
    - On Lead Card click: update status to "Investigating", call `POST /case-files/{id}/investigative-search` with entity name and `search_scope: "internal_external"`
    - On success: expand Intelligence Brief panel below the card (executive summary, evidence, graph, AI analysis, gaps, next steps), update status to "Assessed" with confidence badge
    - On failure: show error with "Retry" button, revert status to "New"
    - Add "💾 Save to Notebook" button on Intelligence Brief results
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 3.3_

  - [x] 4.3 Implement lead assessment with viability rating
    - Add "Assess Lead" button on each Lead Card calling `POST /case-files/{id}/lead-assessment` with lead subjects
    - Display Case Viability Rating badge (viable=green, promising=yellow, insufficient=red) and consolidated summary
    - Display cross-subject connections found between subjects
    - Add "Investigate All" button for batch assessment of all "New" leads, processing sequentially and updating each card as results arrive
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 4.4 Implement lead import modal
    - Add "Import Lead" button opening a modal with two modes: JSON paste and simple form
    - JSON mode: accept `{ name, type, context, aliases }` with name required
    - Form mode: entity name input (required), type dropdown (person/organization), context textarea, aliases comma-separated
    - On valid import: add lead to queue with status "New", score 0, persist to `localStorage['importedLeads_' + caseId]`
    - On invalid import: show validation error, keep modal open
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 4.5 Implement lead status workflow and persistence
    - Add "Close Lead" button on assessed leads → update status to "Closed", move to collapsed "Closed Leads" section at bottom
    - Persist all status changes to `localStorage['leadStatuses_' + caseId]`
    - On case change: load statuses from localStorage for new case
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 4.6 Write property tests for Lead Investigation (Properties 4, 5, 6, 7, 8, 9)
    - **Property 4: Lead card rendering completeness**
    - **Property 5: Lead queue default sort order**
    - **Property 6: Lead investigation lifecycle**
    - **Property 7: Lead status round-trip persistence**
    - **Property 8: Lead import validation and persistence**
    - **Property 9: Lead assessment result rendering**
    - **Validates: Requirements 5.2, 5.3, 6.1, 6.2, 6.3, 7.2, 7.3, 8.2, 8.4, 8.5, 9.1, 9.3, 9.4**

- [ ] 5. Checkpoint — Verify Lead Investigation tab
  - Ensure lead queue renders, investigate action works, assessment displays viability, import modal validates, and statuses persist in localStorage. Ask the user if questions arise.

- [x] 6. Build Entity Dossier slide-out panel
  - [x] 6.1 Create the Entity Dossier overlay HTML and CSS
    - Add `<div id="entityDossierOverlay" class="drill-overlay">` and `<div id="entityDossierPanel" class="drill-panel">` to the page
    - Style as right-side slide-out panel (consistent with existing drill panel pattern)
    - Add close button and Escape key handler
    - _Requirements: 10.1, 10.4_

  - [x] 6.2 Implement the delegated click handler for entity links
    - Add `document.body` delegated click handler for elements with class `entity-link` and `data-entity` attribute
    - On click: open Entity Dossier panel, fetch entity data from multiple endpoints in parallel
    - Fetch: `/case-files/{id}/entity-photos`, `/case-files/{id}/entity-neighborhood?entity_name=X&hops=2`, `/case-files/{id}/findings` (filtered by entity)
    - _Requirements: 10.1_

  - [x] 6.3 Render Entity Dossier sections
    - Entity photo (if available), type + aliases
    - Document mentions list
    - Graph neighborhood vis.js mini-graph (2-hop data)
    - Timeline events involving the entity
    - Prior findings from Research Notebook matching entity name
    - "🔎 Investigate" button → runs investigative search inline within dossier
    - Show "No graph connections found" if entity-neighborhood returns empty
    - _Requirements: 10.2, 10.3, 10.5_

  - [ ]* 6.4 Write property tests for Entity Dossier (Properties 10, 11)
    - **Property 10: Entity Dossier opens on entity name click**
    - **Property 11: Entity Dossier rendering completeness**
    - **Validates: Requirements 10.1, 10.2**

- [x] 7. Deduplicate Evidence Library tab
  - [x] 7.1 Move all evidence functionality into `tab-evidencelibrary`
    - Migrate the full evidence browser from the standalone Evidence tab: document listing, classification toggle, entity badges, document preview, Rekognition label filtering, media type filtering, evidence detail modal
    - Remove the evidence sub-tab from the old Case Investigations tab content
    - Remove the standalone `tab-evidence` div
    - Ensure `loadEvidence()` function targets the new `tab-evidencelibrary` container
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 8. Merge Pipeline tabs into one
  - [x] 8.1 Restructure `tab-pipeline` with sub-navigation buttons
    - Add sub-nav bar with 3 buttons: Pipeline Status (default), Pipeline Config, Pipeline Monitor
    - Create `<div id="pipe-pipeStatus">`, `<div id="pipe-pipeConfig">`, `<div id="pipe-pipeMonitor">` sub-sections
    - Implement `switchPipelineSection(section)` to toggle visibility and active button state
    - Move existing Pipeline Status content into `pipe-pipeStatus`
    - Move existing Pipeline Config content from `tab-pipeconfig` into `pipe-pipeConfig`
    - Move existing Pipeline Monitor content from `tab-pipemonitor` into `pipe-pipeMonitor`
    - Remove standalone `tab-pipeconfig` and `tab-pipemonitor` divs
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [x] 9. Enhance Portfolio tab with New Case button
  - [x] 9.1 Add "New Case" button to the Portfolio tab
    - Add a "➕ New Case" button to the Portfolio tab header area
    - On click: open the wizard form as a modal dialog (reuse existing wizard HTML/JS from `tab-wizard`)
    - Remove the standalone `tab-wizard` div after migrating the form to a modal
    - _Requirements: 15.1, 15.2, 15.3, 18.2_

- [x] 10. Fix external search scope backend wiring
  - [x] 10.1 Verify and fix AIResearchAgent invocation in `src/services/investigative_search_service.py`
    - Ensure that when `search_scope == "internal_external"`, the `AIResearchAgent` is properly invoked to generate external research
    - Ensure external research results are passed to `_generate_cross_reference_report()`
    - Ensure cross-reference report entries have `category` field: `confirmed_internally`, `external_only`, or `needs_research`
    - Verify graceful degradation if AIResearchAgent fails within 25s budget
    - _Requirements: 17.1, 17.2, 17.3, 17.5_

  - [x] 10.2 Implement cross-reference report rendering in the frontend
    - When Intelligence Brief response contains `cross_reference_report`, render a "Cross-Reference Report" section
    - Display each finding with category badge and source attribution
    - _Requirements: 17.4_

  - [ ]* 10.3 Write property test for external search scope (Property 12)
    - **Property 12: External search scope produces cross-reference report**
    - **Validates: Requirements 3.4, 17.1, 17.2, 17.3, 17.4**

- [x] 11. Implement tab workflow indicator dots
  - [x] 11.1 Add CSS for tab indicator dots and implement indicator logic
    - Add `.tab-indicator` CSS: 6px green (#238636) dot, positioned top-right of tab button, hidden by default
    - Add `.tab-indicator.loaded` class to show the dot
    - After each successful tab data load, add `loaded` class to that tab's indicator
    - On case change: remove `loaded` class from all indicators, clear `window._tabDataLoaded`
    - _Requirements: 19.1, 19.2, 19.3_

  - [ ]* 11.2 Write property test for tab indicators (Property 14)
    - **Property 14: Tab data-loaded indicator dots**
    - **Validates: Requirements 19.1, 19.2**

- [ ] 12. Clean up removed tab content
  - [ ] 12.1 Remove all HTML content divs for removed tabs
    - Delete `tab-crosscase`, `tab-workbench`, `tab-leads`, `tab-triage`, `tab-hypotheses`, `tab-subpoenas`, `tab-aibriefing` divs from the HTML
    - Delete `tab-wizard` div (wizard form already migrated to modal in task 9.1)
    - Delete `tab-evidence` div (evidence already migrated in task 7.1)
    - Delete `tab-pipeconfig` and `tab-pipemonitor` divs (already migrated in task 8.1)
    - _Requirements: 1.3, 1.4, 18.1, 18.2, 18.3, 18.4_

  - [ ] 12.2 Audit and migrate any JavaScript functions from removed tabs that are still needed
    - Scan removed tab content for function definitions and event handlers
    - Preserve any functions referenced by the consolidated tabs (keep function signatures and behavior)
    - Remove dead code that is no longer referenced by any tab
    - _Requirements: 18.5_

  - [x] 12.3 Add "no case selected" prompts to all tabs
    - In each tab's load function, check if `selectedCaseId` is set
    - If not, display: "Select a case from the Case Dashboard to get started"
    - _Requirements: 16.3_

- [ ] 13. Checkpoint — Full integration verification
  - Ensure all 7 tabs render correctly, tab switching works, case selection propagates to all tabs, lead workflow functions end-to-end, Entity Dossier opens from all tabs, Pipeline sub-sections toggle, and no JavaScript errors in console. Ask the user if questions arise.

- [ ] 14. Deploy and verify
  - [ ] 14.1 Deploy updated frontend and Lambda code
    - Zip contents from inside `src/` directory (not the `src/` folder itself)
    - Upload frontend `investigator.html` to S3 bucket `research-analyst-data-lake-974220725866`
    - If backend changes were made (task 10.1), update Lambda `ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq` with new zip
    - _Requirements: All_

  - [ ]* 14.2 Write unit tests for tab structure and removed elements
    - Verify tab bar contains exactly 7 tabs in correct order
    - Verify removed tab divs are absent from DOM
    - Verify Pipeline tab has 3 sub-sections
    - Verify Portfolio tab has "New Case" button
    - _Requirements: 1.1, 1.3, 12.1, 15.3_

- [ ] 15. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The frontend is a single 7704-line HTML file with inline JavaScript — no build system or framework
- All backend services are already deployed; only `investigative_search_service.py` may need a minor wiring fix
- API Gateway has a 29-second timeout; frontend fetch calls should handle timeouts gracefully
- Python backend code must be Python 3.10 compatible (`Optional[type]` not `type | None`)
- Deploy: zip from inside `src/` directory, upload to S3 for frontend, update Lambda for backend

## Future Enhancements (build after this spec + Intelligence Trawler)

### Priority Order
1. **Intelligence Trawler** (Phase 2 — PRIORITY, build immediately after this consolidation)
   - Persistent collection / standing queries / automated alerts on new intelligence
   - EventBridge scheduled Lambda, SNS/SES notifications, monitor management UI
   - Reuses 100% of InvestigativeSearchService + FindingsService

2. **Investigation Board / Analyst Canvas** (dedicated Research Workspace)
   - Full-screen visual canvas where investigators pin entities, documents, findings
   - Drag-and-drop spatial arrangement, draw connections between items
   - Build case narrative visually — like Palantir's Object Explorer or i2 Analyst's Notebook
   - Would use a canvas library (Fabric.js or custom drag-and-drop)
   - Separate from the Research Notebook (which is a list) — this is a spatial workspace
   - Could become an 8th tab or replace the Research Notebook panel in the Dashboard

3. **Court-Ready Export & Reporting** (spec exists, needs frontend)
4. **Investigation Playbooks / Workflow Automation** (AI-guided investigation templates)
5. **Collaboration & Annotations** (multi-user shared workspaces, comment threads)
6. **Full Audit Trail & Provenance** (chain of custody, immutable event log)
7. **Data Lineage & Processing Provenance** (visual trace from finding to source)
8. **Role-Based Dashboards & Views** (analyst/supervisor/prosecutor role switching)

### Known Issues to Address
- Internal search quality needs improvement (results not always relevant)
- External search (Internal+External toggle) needs AIResearchAgent wiring fix (Task 10)
- AI analysis in graph insight panel shows "requires search index" — needs Bedrock direct call fallback

### Technical Debt: Code Duplication Audit (DO NOT FIX NOW — note for future cleanup)

The `investigator.html` file is 8500+ lines of inline JS with no module system. Known duplication areas to consolidate in a future refactor:

1. **vis.js graph rendering** — Graph initialization code appears in 3+ places:
   - Entity Graph tab (main graph with layers/fullscreen)
   - AI Briefing finding detail (`loadEntityNeighborhood`)
   - Entity Dossier panel (`openEntityDossier`)
   - Lead Investigation investigate results
   → Should extract a shared `renderMiniGraph(container, nodes, edges, options)` helper

2. **Intelligence Brief rendering** — Similar HTML generation for search results:
   - `renderIntelligenceBrief()` in search results (Case Dashboard)
   - Lead Investigation expand panel (`_renderLeadBrief`)
   - Entity Dossier investigate results (`investigateFromDossier`)
   → Should extract a shared `renderBriefHTML(data)` function

3. **API call + error handling pattern** — Repeated try/catch with loading spinner → result → error fallback:
   - Every tab load function has its own version
   → Could use a shared `loadWithSpinner(containerId, fetchFn, renderFn)` wrapper

4. **Entity photo lookup** — `_findPhotoForNode()` pattern duplicated across graph renderers
   → Should be a single shared utility

5. **Case ID handling** — `mainCase` hardcoded in multiple places vs `selectedCaseId`
   → Should be a single `getGraphCaseId()` / `getSearchCaseId()` pair

6. **Toast/notification** — `showBriefingToast()` and `showToast()` are separate functions doing the same thing
   → Consolidate into one

**Recommendation**: When the file gets a proper refactor (or moves to a framework), extract these into shared utility functions. Don't fix now — risk of breaking working features outweighs the benefit. The backend Python code is clean with proper service separation and DI.

### Frontend Code Cleanup (PRIORITY — do after testing is complete)

The investigator.html file needs a cleanup pass to:
- Remove dead HTML divs from old tabs that are no longer visible (tab-crosscase, tab-workbench, tab-wizard, tab-aibriefing, tab-leads, tab-triage, tab-hypotheses, tab-subpoenas)
- Remove dead JS functions that only served removed tabs
- Consolidate duplicate rendering functions (see Technical Debt section above)
- Remove old switchTab override hooks that are no longer needed
- Scan for and eliminate duplicate function definitions
- Consider splitting the monolithic 8500+ line file into separate JS modules loaded via script tags (e.g. leads.js, evidence.js, timeline.js, dossier.js)
- This is a safe refactor to do AFTER the workflow is tested and stable — not during active feature development

### Testing Feedback — Issues Found

1. **Pipeline tab not working** — The merged Pipeline tab may not be showing content properly. The sub-nav buttons (Status/Config/Monitor) were added but the old tab-pipeline content may not be visible due to display:none from switchTab. Need to verify the pipeline content div is shown when Pipeline tab is active. Also: Pipeline is an admin/ops tab, not investigator-facing. Consider whether it belongs in the investigator UI at all, or should be a separate admin page.

2. **Portfolio tab sections empty** — Portfolio loads the header and filter controls but the case sections (Cases Requiring Attention, All Cases, Portfolio Analytics) appear collapsed/empty. The `loadPortfolio()` function calls `/portfolio/` API — need to verify this API returns data and that the case cards render inside the sections. The "New Case" button may also not be visible if it was added to the wrong location.

3. **Investigation Playbook / Process Flow not built** — User expected a guided step-by-step investigative workflow (Gotham-style playbook). The current implementation uses tab order as the implicit workflow, but there's no explicit guided flow with progress tracking. This is the "Investigation Playbooks / Workflow Automation" item from the Gotham gap analysis — noted as future enhancement #4 in the priority list. Would be a strong demo feature: a sidebar or overlay showing "Step 1 of 6: Review AI Briefing ✓ → Step 2: Investigate Top Leads → Step 3: Review Evidence → ..."

### Pipeline Tab Decision — REMOVE from investigator UI

The Pipeline tab should be removed from the 7-tab investigator bar (making it 6 tabs). Pipeline/ingestion is admin/ops functionality that belongs in the upper-level nav bar where Pipeline Config, Batch Loader, Admin already exist. The investigator doesn't need pipeline controls while investigating.

Proposed upper-nav pipeline consolidation (separate spec):
- Merge Pipeline Config, Batch Loader, Pipeline Monitor into one visual pipeline flow
- Show pipeline as clickable step cards: Upload → Parse → Extract Entities → Embed → Graph Load → Index
- Click a step card to configure that step
- Show real-time status per step with progress indicators
- This is a data engineer/admin feature, not investigator-facing
