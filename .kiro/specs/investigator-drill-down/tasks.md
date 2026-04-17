# Implementation Plan: Investigator Drill-Down

## Overview

Implement a 4-level hierarchical drill-down panel in `src/frontend/investigator.html` that enables prosecutors to progressively explore case data — from investigative threads, through entity networks, to individual document evidence — with AI-generated narrative summaries at each level. Entirely client-side (HTML/CSS/JS), leveraging existing API endpoints.

## Tasks

- [x] 1. Panel Infrastructure and Navigation
  - [x] 1.1 Add drill-down panel CSS and DOM structure to `src/frontend/investigator.html`
    - Add `.drill-overlay`, `.drill-panel`, `.drill-header`, `.drill-body` CSS classes
    - Add fixed-position overlay DOM elements (`drillOverlay`, `drillHeader`, `drillBody`)
    - Slide-in/slide-out animation via CSS transitions on `.active` class
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.2 Implement `DrillDown` object with lifecycle methods
    - `open(caseId)` — slide panel in, fetch graph data, classify into threads, render Level 1
    - `close()` — slide panel out, clear navigation stack (idempotent when already closed)
    - `pushLevel(level, title, id, data)` — append to navigation stack, render
    - `goBack(idx)` — truncate stack to index, re-render
    - `render()` — dispatch to correct level renderer based on top of stack
    - `renderHeader()` — render breadcrumb trail from navigation stack
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 1.3 Write property test for navigation stack integrity
    - **Property 1: Stack Integrity** — after `pushLevel(level, ...)`, stack length equals level
    - **Property 7: Panel State** — `isOpen === true` iff panel has `.active` class; `isOpen === false` implies empty stack
    - **Property 9: Level Bounds** — `pushLevel` only accepts levels 1–4; `goBack(i)` only accepts valid indices
    - **Property 10: Idempotent Close** — calling `close()` when closed is a no-op

  - [ ]* 1.4 Write property test for breadcrumb consistency
    - **Property 2: Breadcrumb Consistency** — breadcrumb trail always reflects navigation stack entries

- [x] 2. Thread Classification (Level 1)
  - [x] 2.1 Implement `ThreadClassifier.classify(nodes, edges)` in `src/frontend/investigator.html`
    - Define `THREAD_DEFS` with 6 thread categories and entity type mappings
    - Define `TYPE_TO_THREAD` mapping: financial_amount/account_number → financial, phone_number/email → communication, address/location/vehicle → property, person → persons, organization → organizations, date/event → timeline
    - Default unmapped types to `organizations` thread
    - Flag cross-thread entities when edges connect different threads
    - Compute `entityCount` per thread
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 2.2 Implement `renderL1(threads)` — Level 1 thread cards view
    - Display investigative overview summary with total entity/edge counts
    - Render thread cards with icon, label, entity count, top 3 entities preview
    - Show empty state message when no entities found
    - _Requirements: 3.6_

  - [ ]* 2.3 Write property test for thread partition completeness
    - **Property 3: Thread Completeness** — every input node appears in exactly one thread; sum of entityCounts equals input node count
    - **Property 4: Entity Uniqueness** — no entity name appears more than once within a single thread

- [x] 3. Thread Detail (Level 2)
  - [x] 3.1 Implement `openThread(threadId)` and `renderL2(data)` in `src/frontend/investigator.html`
    - Sort entities by degree descending
    - Display entity cards with icon, name, type, connection count, cross-thread badge
    - Generate AI thread briefing via `AINarrator` with entity count, connection count, top 5 entities, cross-thread alerts, thread-specific prosecutor guidance
    - Render mini knowledge graph scoped to thread entities using vis.js
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 3.2 Write property test for entity sort stability
    - **Property 5: Sort Stability** — entities in Level 2 are always sorted by degree descending

- [x] 4. Entity Profile (Level 3)
  - [x] 4.1 Implement `openEntity(name, type)` and `renderL3(data)` in `src/frontend/investigator.html`
    - Parallel fetch: search API for documents, patterns API for neighbors, cross-case search for hits
    - Display entity significance narrative from `AINarrator.entityProfile()`
    - Render SVG neighborhood graph with entity photos integration
    - Display document list sorted by relevance score with excerpts
    - Display neighbor entities as clickable cards
    - Show cross-case hits with case name and match count
    - Generate investigative questions and AI insights
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 4.2 Implement `loadCrossCaseHits(entityName, currentCaseId)`
    - Search each case (excluding current) for entity name via keyword search
    - Return array of `{caseId, caseName, matchCount}` for cases with matches
    - Silently skip failed cases
    - _Requirements: 5.5_

  - [ ]* 4.3 Write property test for cross-case exclusion
    - **Property 8: Cross-Case Exclusion** — cross-case hits never include the current case

- [x] 5. Document Evidence (Level 4)
  - [x] 5.1 Implement `openDoc(idx)` and `renderL4(data)` in `src/frontend/investigator.html`
    - Display evidentiary assessment narrative from `AINarrator.evidenceAssessment()`
    - Render full document text with entity name highlighting
    - Show document metadata (filename, relevance score)
    - Add "View Original" button for document download
    - Add "Add Annotation" button with annotation form
    - Add "AI Auto-Tag" button for automated entity tagging
    - Support text selection for inline annotations
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 6. AI Narrator
  - [x] 6.1 Implement `AINarrator` object with template-based narrative generators
    - `investigativeOverview(threads)` — case-level summary with thread counts
    - `threadBriefing(threadId, entities, edges)` — thread assessment with prosecutor guidance
    - `entityProfile(entity, docs, neighbors, crossCaseHits)` — entity significance narrative
    - `evidenceAssessment(doc, entity, relatedDocs)` — evidentiary value assessment
    - Template-based with entity/count interpolation (future Bedrock RAG hook)
    - _Requirements: 4.3, 5.3, 6.2_

- [x] 7. Integration Points
  - [x] 7.1 Wire "Investigate" button on case header to `DrillDown.open(caseId)`
    - _Requirements: 1.1_

  - [x] 7.2 Wire graph node clicks to `DrillDown.openEntity(name, type)`
    - Single-click on graph node opens entity profile in drill-down panel
    - _Requirements: 5.1_

  - [x] 7.3 Wire multi-select analysis to drill-down panel
    - "Analyze Selection" button opens drill-down with selected entities
    - _Requirements: 5.1_

- [ ] 8. Final checkpoint — Verify all drill-down levels work end-to-end
  - Ensure panel opens/closes cleanly, all 4 levels render, breadcrumb navigation works

## Notes

- All tasks are frontend-only changes to `src/frontend/investigator.html`
- No backend changes required — uses existing patterns, search, and cross-case APIs
- Tasks marked with `*` are optional property-based tests
- The feature was implemented directly; this tasks.md is a retroactive documentation of the work done
