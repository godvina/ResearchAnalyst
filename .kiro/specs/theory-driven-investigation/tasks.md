# Implementation Plan: Theory-Driven Investigation Engine

## Overview

Implement a top-down ACH-based theory investigation engine. Backend: Aurora migration for `theories` table, `TheoryEngineService` delegating to existing `HypothesisTestingService`, API handler with 6 endpoints, stale-marking hook. Frontend: Theory Dashboard card grid with radar charts, Theory Deep Dive overlay with evidence panels/timeline/entity map, integration badges on DYK/Anomaly cards, Health Bar theory maturity gauge.

## Tasks

- [x] 1. Aurora database migration for theories table
  - [x] 1.1 Create `src/db/migrations/016_theory_engine.sql`
    - Create `theories` table with columns: `theory_id` (UUID PK DEFAULT gen_random_uuid()), `case_file_id` (UUID FK to case_files ON DELETE CASCADE), `title` (VARCHAR 255 NOT NULL), `description` (TEXT NOT NULL), `theory_type` (VARCHAR 20 NOT NULL CHECK IN financial/temporal/relational/behavioral/structural), `overall_score` (INTEGER NOT NULL DEFAULT 50 CHECK 0-100), `evidence_consistency` (INTEGER NOT NULL DEFAULT 50 CHECK 0-100), `evidence_diversity` (INTEGER NOT NULL DEFAULT 50 CHECK 0-100), `predictive_power` (INTEGER NOT NULL DEFAULT 50 CHECK 0-100), `contradiction_strength` (INTEGER NOT NULL DEFAULT 50 CHECK 0-100), `evidence_gaps` (INTEGER NOT NULL DEFAULT 50 CHECK 0-100), `supporting_entities` (JSONB NOT NULL DEFAULT '[]'), `evidence_count` (INTEGER NOT NULL DEFAULT 0), `verdict` (VARCHAR 20 CHECK NULL or confirmed/refuted/inconclusive), `created_by` (VARCHAR 50 NOT NULL DEFAULT 'ai'), `created_at` (TIMESTAMPTZ DEFAULT NOW()), `scored_at` (TIMESTAMPTZ nullable)
    - Create index `idx_theories_case` on `case_file_id`
    - Create index `idx_theories_score` on `overall_score`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 2. Implement TheoryEngineService
  - [x] 2.1 Create `src/services/theory_engine_service.py` with core class and internal helpers
    - Define `TheoryEngineService` class with `ACH_WEIGHTS`, `VALID_THEORY_TYPES`, `VALID_VERDICTS` constants
    - Implement `__init__` accepting aurora_cm, bedrock_client, hypothesis_svc (HypothesisTestingService), neptune_endpoint, neptune_port
    - Implement `_gather_case_context(case_id)` querying Aurora for documents, entities, findings, pattern_reports
    - Implement `_query_neptune(case_id)` for entity relationships/clusters/bridges, returning empty dict on failure
    - Implement `_extract_entities(case_id, text)` matching entity names against case entity set in Aurora
    - Implement `_classify_theory_type(description)` using Bedrock to classify into Theory_Type
    - Implement `_score_dimension(theory, evidence, dimension)` prompting Bedrock for a single ACH dimension score 0-100
    - Implement `_compute_overall_score(dimensions)` as weighted average clamped to int 0-100
    - Implement `_generate_evidence_gaps(theory, evidence)` prompting Bedrock for missing evidence with search queries
    - Follow Bedrock invocation pattern from `report_generation_service.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 14.2, 29.1, 29.2_

  - [x] 2.2 Implement `generate_theories(case_id)` method
    - Gather case context from Aurora and optionally Neptune
    - Build structured prompt for Bedrock requesting 10-20 ranked theories
    - Parse response into Theory dicts with title, description, type, initial score
    - Extract entity names via `_extract_entities()`
    - Store each theory in Aurora `theories` table
    - Return list of generated theories
    - Delegate to `HypothesisTestingService._decompose()` for claim decomposition
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.3 Implement `create_manual_theory(case_id, title, description, theory_type, supporting_entities)` method
    - Set `created_by = "investigator"`, initial `overall_score = 50`, all five ACH dimensions to 50
    - Auto-classify theory_type via Bedrock if not provided
    - Extract entities from description matching case entity set
    - Store in Aurora and return created theory
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 2.4 Implement `score_theory(case_id, theory_id)` method
    - Retrieve theory from Aurora
    - Retrieve all case evidence (documents, findings) from Aurora
    - Delegate to `HypothesisTestingService._classify_evidence()` for each evidence passage
    - Delegate to `HypothesisTestingService._search_evidence()` for evidence retrieval
    - Prompt Bedrock for each of the 5 ACH dimension scores
    - Compute `overall_score` as weighted average via `_compute_overall_score()`
    - Update `theories` table with new scores, `scored_at` timestamp, and `evidence_count`
    - Return updated theory with evidence classifications
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 2.5 Implement `get_theories()`, `get_theory_detail()`, `set_verdict()`, `mark_theories_stale()`, `compute_theory_maturity()` methods
    - `get_theories(case_id)`: list all theories sorted by overall_score desc
    - `get_theory_detail(case_id, theory_id)`: full detail with classified evidence passages and evidence gaps
    - `set_verdict(case_id, theory_id, verdict)`: validate verdict in VALID_VERDICTS, update Aurora
    - `mark_theories_stale(case_id)`: set scored_at = NULL for all case theories
    - `compute_theory_maturity(case_id)`: (theories with verdict / total) * 100, 0 if empty
    - _Requirements: 7.1, 7.3, 7.4, 14.3, 14.4, 19.1, 19.3, 21.1, 26.2, 26.3_


  - [ ]* 2.6 Write property test: Theory Structural Invariants (Property 1)
    - **Property 1: Theory Structural Invariants**
    - Generate random theory dicts with `st.text()`, `st.integers(0, 100)`, `st.sampled_from(VALID_TYPES)`. Verify title < 120 chars, non-empty description, valid theory_type, overall_score 0-100, supporting_entities is list, evidence_count >= 0.
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 2.7 Write property test: Entity Extraction Subset (Property 2)
    - **Property 2: Entity Extraction Subset**
    - Generate random text containing random entity names from a generated entity set. Verify `_extract_entities()` result is a subset of the case entity set.
    - **Validates: Requirements 2.5, 4.4**

  - [ ]* 2.8 Write property test: Manual Theory Defaults (Property 3)
    - **Property 3: Manual Theory Defaults**
    - Generate random titles and descriptions via `st.text(min_size=1)`. Verify `create_manual_theory()` produces `created_by == "investigator"`, `overall_score == 50`, all five ACH dimensions == 50.
    - **Validates: Requirements 4.1, 4.3**

  - [ ]* 2.9 Write property test: Overall Score Weighted Average (Property 4)
    - **Property 4: Overall Score Weighted Average**
    - Generate 5 random integers 0-100. Verify `_compute_overall_score()` returns `round(ec*0.25 + ed*0.20 + pp*0.20 + cs*0.20 + eg*0.15)` clamped to 0-100.
    - **Validates: Requirements 5.6**

  - [ ]* 2.10 Write property test: Evidence Count Equals Supporting Plus Contradicting (Property 5)
    - **Property 5: Evidence Count Equals Supporting Plus Contradicting**
    - Generate random lists of evidence with classifications in {supporting, contradicting, neutral}. Verify evidence_count == count(supporting) + count(contradicting).
    - **Validates: Requirements 6.5**

  - [ ]* 2.11 Write unit tests for TheoryEngineService
    - Test generate_theories with mocked Bedrock returning valid JSON
    - Test create_manual_theory with and without theory_type
    - Test score_theory with mocked HypothesisTestingService delegation
    - Test _compute_overall_score with known dimension values
    - Test mark_theories_stale sets scored_at to NULL
    - Test set_verdict with valid and invalid verdict values
    - Test Neptune unavailable degradation (proceeds with Aurora only)
    - Test Bedrock failure during generation returns 500
    - Test Bedrock failure during scoring retains existing scores
    - Test empty case (no documents/entities) returns empty theories list
    - _Requirements: 1.3, 2.1, 4.1, 4.2, 5.6, 6.5, 7.1, 7.3, 29.1, 29.2, 29.4_

- [x] 3. Checkpoint — Verify TheoryEngineService
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add API handler and route wiring
  - [x] 4.1 Create `src/lambdas/api/theory_handler.py` with dispatch and endpoint handlers
    - Implement `dispatch_handler(event, context)` routing 6 endpoints based on method + resource
    - Implement `_build_theory_engine_service()` constructing TheoryEngineService with ConnectionManager, bedrock_client, HypothesisTestingService, neptune env vars
    - Implement `generate_theories_handler`: extract case_id, call generate_theories, return 200 with theories list or empty list with message if no evidence
    - Implement `list_theories_handler`: extract case_id, call get_theories, return 200 with theories list
    - Implement `get_theory_handler`: extract case_id and theory_id, call get_theory_detail, return 200 or 404
    - Implement `create_theory_handler`: extract case_id, parse body for title/description/theory_type/supporting_entities, validate required fields, call create_manual_theory, return 200 or 400
    - Implement `set_verdict_handler`: extract case_id and theory_id, parse body for verdict, validate verdict value, call set_verdict, return 200 or 400/404
    - Implement `score_theory_handler`: extract case_id and theory_id, call score_theory, return 200 or 404/500
    - Include CORS headers on all responses and OPTIONS handler
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 19.1, 19.2, 19.3, 19.4, 19.5, 20.1, 20.2, 20.3, 20.4, 20.5, 21.1, 21.2, 21.3, 21.4, 21.5_

  - [x] 4.2 Add route matching in `src/lambdas/api/case_files.py`
    - Add `"/theories"` to the existing investigator-analysis routing block so theory requests dispatch to `theory_handler.dispatch_handler`
    - _Requirements: 18.1, 19.1, 20.1, 21.1_

  - [x] 4.3 Add stale-marking hook in `src/lambdas/api/investigator_analysis.py`
    - In the evidence ingestion handler, after new documents are ingested, call `TheoryEngineService.mark_theories_stale(case_id)` to set scored_at = NULL on all case theories
    - _Requirements: 7.1_

  - [ ]* 4.4 Write unit tests for theory API handler
    - Test dispatch_handler routes to correct handler for each of 6 endpoints
    - Test generate_theories_handler with mocked service
    - Test create_theory_handler with missing title/description returns 400
    - Test set_verdict_handler with invalid verdict returns 400
    - Test get_theory_handler with non-existent theory_id returns 404
    - Test OPTIONS returns 200 with CORS headers
    - _Requirements: 18.1, 18.3, 18.4, 19.5, 20.5, 21.2, 21.5_

- [x] 5. Checkpoint — Verify backend API end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Frontend — CSS styles and helper functions
  - [x] 6.1 Add CSS styles and utility functions to `src/frontend/investigator.html`
    - Add CSS styles for Theory_Card (dark theme: #1a2332 background, #2d3748 border, color-coded left border based on score)
    - Add CSS styles for Theory_Dashboard grid (2-column default, 3-column wide screen)
    - Add CSS styles for Theory_Deep_Dive overlay (full-width modal, evidence panels, entity badges)
    - Add CSS styles for verdict badges (green confirmed, red refuted, gray inconclusive)
    - Add CSS styles for stale indicator, empty state, loading state
    - Implement `renderRadarChart(dimensions, color)` — inline SVG pentagon 80x80px with background pentagon (#2d3748) and data polygon
    - Implement `getScoreColor(score)` — returns #48bb78 (≥70), #f6ad55 (40-69), #fc8181 (<40)
    - Implement `sortTheories(theories, sortBy)` — client-side sort by score/evidence/date/contradiction
    - Implement `filterTheories(theories, filters)` — client-side filter by type and min score
    - Implement `computeTheoryMaturity(theories)` — (with verdict / total) * 100, 0 if empty
    - Implement `getTheoriesForEntities(entities)` — find theories with overlapping supporting_entities
    - _Requirements: 8.3, 9.1, 9.2, 9.3, 9.4, 28.1, 28.2, 28.3, 28.4, 28.5, 30.1, 30.2, 30.3_


  - [ ]* 6.2 Write property test: Score-to-Color Mapping (Property 6)
    - **Property 6: Score-to-Color Mapping**
    - Generate random integers 0-100. Verify `getScoreColor(score)` returns #48bb78 for ≥70, #f6ad55 for 40-69, #fc8181 for <40. Every valid score maps to exactly one color.
    - **Validates: Requirements 8.3**

  - [ ]* 6.3 Write property test: Score Filter Correctness (Property 7)
    - **Property 7: Score Filter Correctness**
    - Generate random theory lists with random scores and a random threshold 0-100. Verify filtered list contains all and only theories with overall_score >= threshold.
    - **Validates: Requirements 9.3**

  - [ ]* 6.4 Write property test: Theory Maturity Computation (Property 9)
    - **Property 9: Theory Maturity Computation**
    - Generate random theory lists with random verdict states (None or valid verdict). Verify `computeTheoryMaturity()` returns floor((with verdict / total) * 100) clamped 0-100, and 0 for empty list.
    - **Validates: Requirements 26.2, 26.3**

  - [ ]* 6.5 Write property test: Radar Chart Points Within SVG Bounds (Property 10)
    - **Property 10: Radar Chart Points Within SVG Bounds**
    - Generate 5 random integers 0-100 for dimension scores. Verify all polygon points have x in [0, 80], y in [0, 80], and distance from center (40,40) proportional to score/100 * 35.
    - **Validates: Requirements 28.2**

- [x] 7. Frontend — Theory Dashboard section in selectCase()
  - [x] 7.1 Add Theory Dashboard section to `src/frontend/investigator.html` in the `selectCase()` flow
    - Add "📐 Theory-Driven Investigation" section after Anomaly Radar, before Matter Assessment
    - Use left border accent #9f7aea, always visible (not collapsible)
    - Render "🤖 Generate Theories" button and "➕ Add Theory" button in section header
    - Implement `renderTheoryDashboard(theories)` rendering card grid with sort/filter controls
    - Implement `renderTheoryCard(theory)` rendering: title, one-line summary, radar chart, overall_score, evidence count, entity badges (up to 5 + "+N more"), color-coded border, verdict badge, stale indicator
    - Implement `generateTheories(caseId)` calling POST /theories/generate with loading state
    - Implement `addManualTheory(caseId, data)` opening modal form, calling POST /theories
    - Implement empty state: centered message with both action buttons when zero theories
    - Load theories via GET /theories on case selection and render dashboard
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4, 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 27.1, 27.2, 27.3, 27.4_

- [x] 8. Frontend — Theory Deep Dive overlay
  - [x] 8.1 Implement Theory Deep Dive overlay in `src/frontend/investigator.html`
    - Implement `openTheoryDeepDive(theoryId)` fetching GET /theories/{tid} and rendering full overlay
    - Render full theory description at top
    - Implement `renderSupportingEvidence(evidence)` — evidence panel sorted by relevance desc, showing passage text, source filename (clickable to doc viewer), relevance score, entity names
    - Implement `renderContradictingEvidence(evidence)` — red-bordered (#fc8181) evidence panel with contradiction explanations
    - Implement `renderEvidenceGaps(gaps)` — gap cards with description and clickable search query (populates Intelligence Search)
    - Implement `renderTheoryEntityMap(entities)` — entity badges with DrillDown.open() links; flat list with note if Neptune unavailable
    - Implement `renderTheoryTimeline(evidence)` — horizontal SVG timeline with green (supporting) and red (contradicting) markers, hover tooltips, click-to-scroll
    - Implement verdict buttons: "✓ Confirmed", "✗ Refuted", "? Inconclusive" calling PUT /theories/{tid}/verdict
    - Implement "Investigate Further" button → populate Intelligence Search with first evidence gap query
    - Implement "Research This Theory" button → switch to Research Hub Chat with theory context pre-populated
    - Implement "Save Assessment" button → save to Research Notebook as findings entry
    - Implement `rescoreTheory(caseId, tid)` calling POST /theories/{tid}/score and refreshing overlay
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.2, 13.3, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 16.1, 16.2, 16.3, 16.4, 17.1, 17.2, 17.3, 17.4, 17.5, 25.1, 25.2, 25.3, 29.3, 29.5_

  - [ ]* 8.2 Write property test: Timeline Chronological Ordering (Property 8)
    - **Property 8: Timeline Chronological Ordering**
    - Generate random lists of evidence items with random `indexed_date` fields. Verify rendered timeline markers appear in ascending chronological order.
    - **Validates: Requirements 16.1**

- [x] 9. Frontend — Integration badges and Health Bar gauge
  - [x] 9.1 Add theory badges to Did You Know and Anomaly Radar cards in `src/frontend/investigator.html`
    - In Discovery_Card rendering, check entity overlap with theories via `getTheoriesForEntities()`, render "📐 N theories" badge
    - In Anomaly_Card rendering, same entity overlap check, render "📐 N theories" badge
    - On badge click, scroll to Theory Dashboard filtered to related theories
    - _Requirements: 22.1, 22.2, 22.3, 23.1, 23.2, 23.3_

  - [x] 9.2 Add Knowledge Graph entity highlighting integration
    - When Theory Deep Dive opens, call `highlightTheoryEntities(entities)` using existing glow animation pattern from Top 5 Patterns
    - Scroll Knowledge Graph section into view
    - Clear highlighting when Theory Deep Dive closes
    - _Requirements: 24.1, 24.2, 24.3_

  - [x] 9.3 Add Theory Maturity gauge to Case Health Bar
    - Add 6th Mini_Gauge labeled "Theory Maturity" after existing 5 gauges
    - Compute score via `computeTheoryMaturity(theories)`
    - Display 0 with tooltip "No theories generated yet" when zero theories
    - Use existing gauge color coding: green ≥60, amber 30-59, red <30
    - _Requirements: 26.1, 26.2, 26.3, 26.4_

- [x] 10. Checkpoint — Verify frontend rendering and integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Final checkpoint — Full feature verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (10 properties)
- Unit tests validate specific examples and edge cases
- Backend is Python, frontend is inline JavaScript in investigator.html — no build step
- TheoryEngineService delegates to existing HypothesisTestingService for evidence evaluation
- Deploy commands are not included as tasks (manual deployment per existing workflow)
