# Implementation Plan: Prosecution Funnel Assessment

## Overview

Implement a prosecution-oriented intelligence layer beneath the existing 8-step investigator playbook. Four modules (DossierManager, SubjectAssessor, GraphInsightRecorder, enhanced existing functions) are added as inline JavaScript in `src/frontend/investigator.html`. All data persists in localStorage. Build order follows dependency graph: DossierManager first, then SubjectAssessor + GraphInsightRecorder, then existing function enhancements, then scorecard rollup, then tests.

## Tasks

- [x] 1. Implement DossierManager module (localStorage CRUD)
  - [x] 1.1 Add DossierManager object with normalizeName, _storageKey, _loadStore, _saveStore
    - Implement `normalizeName(name)` returning `(name || '').trim().toLowerCase()`
    - Implement `_storageKey()` returning `'entityDossiers_' + selectedCaseId`
    - Implement `_loadStore()` with JSON.parse, corruption guard returning `{}` on failure, `console.warn` on parse error
    - Implement `_saveStore(store)` with JSON.stringify, catch `QuotaExceededError` and show toast
    - Place the DossierManager object after the existing tracked entity state variables in `investigator.html`
    - _Requirements: 1.3, 1.7, 5.2, 5.3_

  - [x] 1.2 Add getDossier, upsertDossier, appendActivity, appendGraphInsight, getAllDossiers, hasGraphInsights
    - `getDossier(entityName)` — normalize + lookup, return null if not found
    - `upsertDossier(entityName, updates)` — merge fields into existing or create from default template, update `lastUpdated`, reject empty keys
    - `appendActivity(entityName, entry)` — create dossier if needed, push `{text, source, timestamp}` to `notes` array, update `lastUpdated`
    - `appendGraphInsight(entityName, insight)` — push `{note, connections, connectedEntities, timestamp}` to `graphInsights` array
    - `getAllDossiers()` — return array of dossier objects sorted by `lastUpdated` descending
    - `hasGraphInsights(entityName)` — return boolean
    - Default template: `{entityName, entityType:'unknown', role:'unassigned', disposition:'unassessed', evidenceStrength:0, notes:[], graphInsights:[], evidenceLinks:[], lastUpdated: new Date().toISOString()}`
    - Early return no-op when `selectedCaseId` is null or entity name is empty
    - _Requirements: 1.1, 1.2, 1.4, 5.1, 5.5_

  - [ ]* 1.3 Write property tests for DossierManager (Properties 1–6)
    - **Property 1: Dossier append preserves singleton** — appending to existing entity increases notes length by 1, dossier count unchanged
    - **Validates: Requirement 1.1**
    - **Property 2: Dossier creation on new entity** — upsertDossier/appendActivity on new name increases dossier count by 1, keyed by normalized name
    - **Validates: Requirement 1.2**
    - **Property 3: Dossier structure completeness** — new dossier contains all required fields with correct types
    - **Validates: Requirements 1.4, 5.1**
    - **Property 4: Name normalization idempotence** — `normalizeName(normalizeName(x)) === normalizeName(x)`, whitespace/case variants produce same key
    - **Validates: Requirement 5.2**
    - **Property 5: Dossier serialization round-trip** — `JSON.parse(JSON.stringify(dossier))` deeply equals original
    - **Validates: Requirements 5.3, 5.4**
    - **Property 6: lastUpdated monotonicity** — any update operation produces `lastUpdated >= previous lastUpdated`
    - **Validates: Requirement 5.5**
    - Use fast-check in `tests/frontend/test_prosecution_funnel.js` with mock localStorage and mock `selectedCaseId`

- [x] 2. Implement SubjectAssessor module (per-entity prosecution evaluation)
  - [x] 2.1 Add SubjectAssessor object with ROLES, ROLE_COLORS, DISPOSITIONS, _storageKey, getAssessment, getAllAssessments
    - Define `ROLES` array: `['unassigned','target','subject','cooperator','witness','victim','cleared','declined']`
    - Define `ROLE_COLORS` mapping per design (target=red, subject=orange, cooperator=blue, witness=teal, victim=purple, cleared=green, declined=gray)
    - Define `DISPOSITIONS`: `['unassessed','investigating','assessed']`
    - `_storageKey()` returning `'subjectAssessments_' + selectedCaseId`
    - `getAssessment(entityName)` — load from localStorage, return `{role, disposition, evidenceStrength, notes}` or null
    - `getAllAssessments()` — return full object from localStorage
    - _Requirements: 2.2, 2.3, 2.6, 2.8_

  - [x] 2.2 Add setRole, setDisposition, computeEvidenceStrength, saveAssessmentNotes
    - `setRole(entityName, role)` — validate against ROLES, save to assessment store, call `DossierManager.upsertDossier()` with role, append activity log entry with source "assessment"
    - `setDisposition(entityName, disposition)` — validate lifecycle (unassessed→investigating→assessed), reject invalid transitions with console.warn, save + log
    - `computeEvidenceStrength(entityName)` — formula: `min(100, round(docScore*0.30 + graphScore*0.25 + findingScore*0.25 + timelineScore*0.20))`, each component normalized 0-100, return 0 when data unavailable
    - `saveAssessmentNotes(entityName, text)` — append to dossier activity log with source "assessment"
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.7_

  - [x] 2.3 Add openSubjectAssessment UI panel renderer
    - `openSubjectAssessment(entityName)` — render modal/panel with: entity name header, role dropdown with color-coded badges, disposition lifecycle indicator, evidence strength bar (0-100), freeform notes textarea with save button
    - Role dropdown shows all 7 roles with color indicators from ROLE_COLORS
    - Disposition shows as a 3-step progress indicator (unassessed → investigating → assessed)
    - Evidence strength renders as a horizontal bar with numeric label
    - Notes textarea appends to dossier on save
    - Panel accessible from Entity Dossier drill-down, Lead Investigation cards, tracked entity bar
    - _Requirements: 2.1, 2.8_

  - [ ]* 2.4 Write property tests for SubjectAssessor (Properties 7–10)
    - **Property 7: Role assignment persistence** — setRole then getAssessment returns matching role
    - **Validates: Requirement 2.2**
    - **Property 8: Disposition lifecycle validity** — only valid transitions accepted (unassessed→investigating→assessed)
    - **Validates: Requirement 2.3**
    - **Property 9: Evidence strength score bounds and weights** — output always in [0,100], matches weighted formula
    - **Validates: Requirement 2.4**
    - **Property 10: Role/disposition change audit logging** — each change adds exactly one activity log entry with source "assessment"
    - **Validates: Requirement 2.7**
    - Use fast-check in `tests/frontend/test_prosecution_funnel.js`

- [x] 3. Implement GraphInsightRecorder module
  - [x] 3.1 Add GraphInsightRecorder object with renderInsightButton, saveInsight, renderSavedInsights, hasInsights
    - `renderInsightButton(entityName)` — return HTML string with "💡 Save Graph Insight" button and collapsible freeform text input + submit button
    - `saveInsight(entityName, note)` — capture connection count and connected entity names from `cachedGraphData` (default 0 and [] if null), delegate to `DossierManager.appendGraphInsight()`
    - `renderSavedInsights(entityName)` — return HTML string showing saved insights in reverse chronological order with note, connection count, connected entities, timestamp
    - `hasInsights(entityName)` — delegate to `DossierManager.hasGraphInsights()`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6_

  - [ ]* 3.2 Write property tests for GraphInsightRecorder (Properties 15–17)
    - **Property 15: Graph insight persistence with all fields** — saved insight contains note, connections (number), connectedEntities (array), timestamp (ISO 8601)
    - **Validates: Requirements 4.3, 4.4**
    - **Property 16: Graph insight indicator correctness** — hasInsights returns true iff entity has ≥1 graph insight
    - **Validates: Requirement 4.5**
    - **Property 17: Saved insights reverse chronological order** — multiple insights rendered most-recent-first
    - **Validates: Requirement 4.6**
    - Use fast-check in `tests/frontend/test_prosecution_funnel.js`

- [ ] 4. Checkpoint — Verify core modules
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Enhance existing functions — saveFreeformFinding and assessLead
  - [x] 5.1 Extend saveFreeformFinding to append to entity dossiers
    - After the existing API save logic, iterate over tagged entities and call `DossierManager.appendActivity(entityName, {text, source:'manual', timestamp})` for each
    - Do not modify the existing API call or finding save behavior
    - _Requirements: 1.1, 6.3_

  - [x] 5.2 Extend assessLead to open SubjectAssessment and save to dossier
    - After the existing API assessment completes successfully, call `DossierManager.appendActivity(entityName, {text: assessment summary, source:'assessment', timestamp})`
    - Call `SubjectAssessor.openSubjectAssessment(entityName)` to open the assessment panel
    - Do not modify the existing API call or lead status update behavior
    - _Requirements: 2.1, 2.7_

  - [ ]* 5.3 Write property test for multi-entity note distribution (Property 19)
    - **Property 19: Multi-entity note distribution** — saving a note with N entity tags appends exactly one entry per tagged entity's activity log with source "manual"
    - **Validates: Requirements 6.3, 2.5**
    - Use fast-check in `tests/frontend/test_prosecution_funnel.js`

- [x] 6. Enhance existing functions — loadResearchNotebook dossier view
  - [x] 6.1 Extend loadResearchNotebook to render Entity Dossier cards
    - Call `DossierManager.getAllDossiers()` to get sorted dossier array
    - Render summary header: total dossier count, count by disposition category, count with evidenceStrength > 60
    - Render each dossier as a collapsible card showing: entity name, type badge, role badge (color-coded), disposition indicator, evidence strength bar, activity log count, graph insight count
    - On card expand: show full Activity_Log in reverse chronological order with text, timestamp, source tag
    - Merge API findings into dossier activity logs by matching entity names, deduplicate by text+timestamp
    - Preserve existing freeform "Add Investigation Note" form
    - _Requirements: 1.5, 1.6, 6.1, 6.2, 6.4, 6.5_

  - [ ]* 6.2 Write property tests for Research Notebook rendering (Properties 18, 20, 21)
    - **Property 18: Dossier cards sorted by lastUpdated** — cards ordered by lastUpdated descending
    - **Validates: Requirement 6.1**
    - **Property 20: Summary header counts accuracy** — total count, disposition counts sum to total, evidenceStrength>60 count matches actual
    - **Validates: Requirement 6.4**
    - **Property 21: API finding merge deduplication** — no duplicate entries (same text + timestamp) after merge
    - **Validates: Requirement 6.5**
    - Use fast-check in `tests/frontend/test_prosecution_funnel.js`

- [x] 7. Enhance existing functions — graph integration
  - [x] 7.1 Extend DrillDown.openEntity to inject graph insight UI
    - After existing drill-down panel HTML is built, append `GraphInsightRecorder.renderInsightButton(entityName)` HTML
    - Append `GraphInsightRecorder.renderSavedInsights(entityName)` below the AI analysis section
    - Keep full graph visible with clicked entity highlighted (do not render separate ego graph)
    - _Requirements: 4.1, 4.2, 4.6, 4.7_

  - [x] 7.2 Extend _nodeWithPhoto and loadGraph for 💡 indicators
    - In `_nodeWithPhoto()`: append " 💡" to node label when `GraphInsightRecorder.hasInsights(name)` returns true
    - In `loadGraph()`: after graph renders, iterate nodes and update labels to show 💡 for entities with saved insights
    - _Requirements: 4.5_

- [ ] 8. Checkpoint — Verify enhanced functions
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Enhance computeCaseStrengthScorecard with prosecution rollup
  - [x] 9.1 Add Subject Identification score enhancement and Prosecution Readiness sub-score
    - Replace existing Subject Identification dimension computation with: `round(proportionAssessed * 0.50 + proportionTargetOrSubject * 0.50) * 100` using `SubjectAssessor.getAllAssessments()` and `_trackedEntities`
    - Add Prosecution Readiness sub-score: `round(targetStrength * 0.40 + cooperatorBonus * 0.30 + notAllClearedBonus * 0.30)` per design formula
    - Apply 0.60 penalty multiplier to overall score when all Target-disposition entities are Cleared or Declined
    - Render Subject Summary table: each tracked entity's name, type, role, disposition, evidence strength
    - Render Prosecution Readiness bar alongside existing 6 dimension bars with color coding: green (>70), yellow (40-70), red (<40)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 9.2 Write property tests for scorecard rollup (Properties 11–14)
    - **Property 11: Subject Identification score computation** — matches formula `round(proportionAssessed * 0.50 + proportionTargetOrSubject * 0.50) * 100`
    - **Validates: Requirement 3.1**
    - **Property 12: Prosecution Readiness score computation** — matches formula `round(targetStrength * 0.40 + cooperatorBonus * 0.30 + notAllClearedBonus * 0.30)`
    - **Validates: Requirement 3.2**
    - **Property 13: All-targets-cleared penalty** — overall score multiplied by 0.60 when all targets cleared/declined, no penalty otherwise
    - **Validates: Requirement 3.3**
    - **Property 14: Scorecard rendering completeness** — rendered HTML contains each entity's name, type, role, disposition, evidence strength; Prosecution Readiness bar uses correct color thresholds
    - **Validates: Requirements 3.4, 3.5**
    - Use fast-check in `tests/frontend/test_prosecution_funnel.js`

- [ ] 10. Final checkpoint — Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All code goes in `src/frontend/investigator.html` as inline JavaScript
- All tests go in `tests/frontend/test_prosecution_funnel.js` using fast-check
- Each task extends existing code — no replacements of existing functions
- localStorage keys: `entityDossiers_{caseId}` and `subjectAssessments_{caseId}`
- The 8 playbook steps remain unchanged — no new steps added
- Property tests validate universal correctness properties from the design document
