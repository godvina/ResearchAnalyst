# Implementation Plan: AI Briefing Experience

## Overview

Extends the existing investigator analysis backend and frontend to fix the API Gateway 29-second timeout and add 3-level progressive disclosure UI. Backend changes modify `investigator_analysis.py` (new handlers), `investigator_ai_engine.py` (async trigger + entity neighborhood), and `case_files.py` (two new route matches). Frontend changes ADD new functions to `investigator.html` (polling, finding cards, detail panel, vis-network graph, supporting docs, confirm/dismiss). All Python, all Lambda code updates — no CDK deploy, no new migrations, no new files except tests.

## Tasks

- [x] 1. Backend: Async analysis trigger and polling
  - [x] 1.1 Add `trigger_async_analysis()` and `get_analysis_status()` methods to `InvestigatorAIEngine`
    - In `src/services/investigator_ai_engine.py`, ADD a `trigger_async_analysis(case_id)` method that:
      1. Calls `get_cached_analysis(case_id)` — if fresh cache hit, return it immediately
      2. Writes `{status: "processing"}` to `investigator_analysis_cache` via `_cache_analysis()`
      3. Calls `boto3.client('lambda').invoke(FunctionName=os.environ['AWS_LAMBDA_FUNCTION_NAME'], InvocationType='Event', Payload=json.dumps({"action": "async_analysis", "case_id": case_id}))`
      4. Returns `CaseAnalysisResult(case_id=case_id, status="processing")`
    - ADD a `get_analysis_status(case_id)` method that reads ONLY from `investigator_analysis_cache` and returns the row as-is (status + analysis_result if completed, or status + error_message if error), returns None if no row
    - ADD a `run_async_analysis(case_id)` method that wraps `analyze_case()` in a try/except, writing `status='error'` + error_message to cache on failure
    - DO NOT modify the existing `analyze_case()` method — the new `trigger_async_analysis` replaces it as the POST entry point
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Modify handlers in `investigator_analysis.py` for async flow
    - In `src/lambdas/api/investigator_analysis.py`:
    - MODIFY `trigger_analysis()`: replace `engine.analyze_case(case_id)` with `engine.trigger_async_analysis(case_id)` — returns 202 for processing, 200 for cache hit
    - MODIFY `get_analysis()`: replace `engine.get_cached_analysis(case_id)` with `engine.get_analysis_status(case_id)` — pure read-only from cache, returns status/result/error
    - ADD `async_analysis_handler(event, context)`: extracts `case_id` from `event["case_id"]`, calls `engine.run_async_analysis(case_id)`, returns success/error dict (no HTTP response needed — this is an async Lambda invoke, not API Gateway)
    - ADD `entity_neighborhood_handler(event, context)`: extracts `case_id` from pathParameters, `entity_name` and `hops` from queryStringParameters, validates hops 1–3 (default 2), calls `engine.get_entity_neighborhood(case_id, entity_name, hops)`, returns 200 with nodes/edges
    - ADD the entity-neighborhood route to the `dispatch_handler` routes dict: `("GET", "/case-files/{id}/entity-neighborhood"): entity_neighborhood_handler`
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3_

  - [x] 1.3 Extend `case_files.py` dispatcher with two new route matches
    - In `src/lambdas/api/case_files.py`, in `dispatch_handler()`:
    - MODIFY the existing investigator AI-first route match to include `/entity-neighborhood`:
      ```python
      if any(seg in path for seg in ("/investigator-analysis", "/investigative-leads", "/evidence-triage",
                                      "/ai-hypotheses", "/subpoena-recommendations", "/session-briefing",
                                      "/entity-neighborhood")):
      ```
    - ADD async action routing near the existing `process_batch`/`extract_zip` block:
      ```python
      if event.get("action") == "async_analysis":
          from lambdas.api.investigator_analysis import async_analysis_handler
          return async_analysis_handler(event, context)
      ```
    - _Requirements: 1.2, 6.1_

  - [ ]* 1.4 Write unit tests for async trigger and polling handlers
    - Create `tests/unit/test_ai_briefing_async.py`
    - `test_trigger_analysis_returns_202_when_no_cache`: mock Aurora (no cache row), mock Lambda client — verify 202 response with `{"status": "processing"}`
    - `test_trigger_analysis_returns_200_when_cache_fresh`: mock Aurora with completed cache — verify 200 with cached data, no Lambda invoke
    - `test_get_analysis_returns_404_when_no_cache`: mock Aurora (no row) — verify 404
    - `test_get_analysis_returns_processing_status`: mock Aurora with `status=processing` — verify 200 with processing status
    - `test_get_analysis_returns_error_status`: mock Aurora with `status=error` — verify 200 with error_message
    - `test_async_handler_writes_completed_on_success`: mock analyze_case success — verify cache updated to completed
    - `test_async_handler_writes_error_on_failure`: mock analyze_case raises — verify cache updated to error with message
    - `test_entity_neighborhood_validates_hops`: hops=0 → 400, hops=4 → 400, hops=2 → 200
    - `test_dispatcher_routes_entity_neighborhood`: verify case_files.py routes `/entity-neighborhood` path to investigator_analysis
    - `test_dispatcher_routes_async_analysis_action`: verify case_files.py routes `action=async_analysis` to async handler
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 6.1, 7.1, 7.3_


  - [ ]* 1.5 Write property tests for async trigger and cache behavior
    - **Property 1: Async trigger returns 202 with correct shape**
    - Generate random UUIDs as case_ids, mock Aurora (no cache), mock Lambda client
    - Verify `trigger_async_analysis` always returns status="processing" and case_id matches input
    - **Validates: Requirements 1.1**

    - **Property 2: Async trigger initiates Lambda self-invoke**
    - Generate random UUIDs as case_ids, mock Aurora (no cache), capture Lambda.invoke calls
    - Verify InvocationType='Event' and payload contains `{"action": "async_analysis", "case_id": "<id>"}`
    - **Validates: Requirements 1.2**

    - **Property 3: Cache hit returns 200 without triggering new work**
    - Generate random CaseAnalysisResult objects, seed into mock cache with matching evidence counts
    - Verify `get_analysis_status` returns the seeded data and no Lambda/Bedrock/Neptune calls made
    - **Validates: Requirements 1.3, 7.1**

    - **Property 4: Async failure writes error status to cache**
    - Generate random case_ids, mock analyze_case to raise random exceptions
    - Verify cache row has status='error' and non-empty error_message
    - **Validates: Requirements 1.4**

- [x] 2. Backend: Entity neighborhood endpoint
  - [x] 2.1 Add `get_entity_neighborhood()` method to `InvestigatorAIEngine`
    - In `src/services/investigator_ai_engine.py`, ADD a `get_entity_neighborhood(case_id, entity_name, hops=2)` method that:
      1. Constructs a Gremlin query via Neptune HTTP API: starting from vertex with `canonical_name=entity_name` and label `Entity_{case_id}`, traverse `bothE().otherV()` for N hops, collecting nodes and edges
      2. Returns `{"entity_name": entity_name, "case_id": case_id, "hops": hops, "nodes": [...], "edges": [...]}` where each node has `name`, `type`, `degree` and each edge has `source`, `target`, `relationship`
      3. If entity not found, returns empty nodes/edges arrays (not an error)
      4. Uses the same `ssl.create_default_context()` + `urllib.request` pattern as existing `_generate_leads()`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 2.2 Write property test for entity neighborhood response shape
    - **Property 5: Entity neighborhood response correctness**
    - Generate random graph structures (nodes with types, edges with relationships), mock Neptune HTTP responses
    - Verify every node has `name` (str), `type` (str), `degree` (int ≥ 0); every edge has `source` (str), `target` (str), `relationship` (str)
    - **Validates: Requirements 6.1, 6.2**

- [x] 3. Checkpoint — Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Frontend: Polling and progress indicator
  - [x] 4.1 Add polling logic to `loadAIBriefing()` in `investigator.html`
    - MODIFY `loadAIBriefing()` to:
      1. POST to trigger analysis — if 202, call `pollAnalysisStatus(caseId, el)`
      2. If 200 (cache hit), render immediately via `renderBriefing()`
    - ADD `pollAnalysisStatus(caseId, el)` function:
      1. Show progress spinner with "Analysis in progress..." message and elapsed time counter
      2. GET `/case-files/{id}/investigator-analysis` every 3 seconds
      3. On `status: "completed"` → stop polling, call `renderBriefing(data)`
      4. On `status: "error"` → stop polling, show error message + "Retry Analysis" button
      5. On `status: "processing"` → continue polling, update elapsed time
      6. On network error → stop polling, show "Connection lost" + retry button
    - _Requirements: 1.5, 1.6, 7.1, 7.2_

- [x] 5. Frontend: Level 1 — Executive summary and finding cards
  - [x] 5.1 Rewrite `renderBriefing()` for Level 1 executive summary in `investigator.html`
    - REPLACE the body of `renderBriefing()` to render:
      1. Case statistics bar: document count, entity count, relationship count, active leads count
      2. Analyst narrative section (the `briefing.narrative` text)
      3. Finding cards grid via `renderFindingCards(data.leads)`
    - Style with professional legal software look: serif section headers, muted color palette, clear visual hierarchy
    - _Requirements: 2.1, 2.4_

  - [x] 5.2 Add `renderFindingCards(leads)` function to `investigator.html`
    - ADD function that renders each lead as a clickable card showing:
      1. Entity name and type
      2. Lead priority score as color-coded badge (green >70, yellow 40–70, red <40)
      3. One-line AI justification summary (truncated to ~100 chars)
      4. Current decision state badge (AI_Proposed / Human_Confirmed / Human_Overridden)
      5. Confirm/Dismiss toggle buttons (visible only when state is AI_Proposed)
    - Each card has `onclick` → `expandFindingDetail(lead)`
    - _Requirements: 2.2, 2.3, 5.1_

- [x] 6. Frontend: Level 2 — Finding detail panel with knowledge graph
  - [x] 6.1 Add `expandFindingDetail(lead)` function to `investigator.html`
    - ADD function that expands a detail panel below the clicked finding card showing:
      1. Full AI justification text
      2. Confidence breakdown: 4 labeled progress bars for evidence_strength, connection_density, novelty, prosecution_readiness
      3. A container div for the mini knowledge graph (populated by `loadEntityNeighborhood`)
      4. A "View Supporting Documents" button → calls `loadSupportingDocuments()`
    - Collapse any previously expanded detail panel
    - Call `loadEntityNeighborhood(caseId, lead.entity_name)` to populate the graph
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 6.2 Add `loadEntityNeighborhood(caseId, entityName)` function to `investigator.html`
    - ADD function that:
      1. Fetches `GET /case-files/{caseId}/entity-neighborhood?entity_name={entityName}&hops=2`
      2. If nodes array is non-empty, renders a vis-network graph in the detail panel's graph container
      3. Nodes colored by type (person=blue, organization=green, location=orange, event=purple), sized by degree
      4. Edges labeled with relationship type
      5. If nodes array is empty, shows "No graph connections found for this entity"
    - vis-network is already loaded via CDN in investigator.html — just use `new vis.Network(container, data, options)`
    - _Requirements: 3.2, 3.5, 6.1, 6.2_

- [x] 7. Frontend: Level 3 — Supporting documents view
  - [x] 7.1 Add `loadSupportingDocuments(caseId, entityName)` function to `investigator.html`
    - ADD function that:
      1. Calls `POST /case-files/{caseId}/search` with `{"query": entityName, "limit": 10}`
      2. Renders results as document cards: title, type badge, relevance score, excerpt with `<mark>` highlighting
      3. Each document card clickable → opens existing drill-down panel
      4. If zero results, shows "No supporting documents found for this finding. The entity may have been extracted from graph relationships rather than document text."
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 8. Frontend: Confirm/Dismiss toggle
  - [x] 8.1 Add `confirmFinding()` and `dismissFinding()` functions to `investigator.html`
    - ADD `confirmFinding(decisionId, cardEl)`:
      1. PUT `/decisions/{decisionId}/confirm` with `{"attorney_id": "investigator"}`
      2. On success, update card badge to "Human_Confirmed", hide action buttons
      3. On 409, refresh card state, show toast "Decision already updated"
    - ADD `dismissFinding(decisionId, cardEl)`:
      1. PUT `/decisions/{decisionId}/override` with `{"attorney_id": "investigator", "override_rationale": "Dismissed by investigator from briefing"}`
      2. On success, update card badge to "Human_Overridden", hide action buttons
      3. On 409, refresh card state, show toast "Decision already updated"
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 9. Checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Property test: Lead priority score
  - [ ]* 10.1 Write property test for lead priority score bounds and determinism
    - **Property 6: Lead priority score is bounded and deterministic**
    - Generate random floats for doc_count (≥0), total_docs (≥1), degree_centrality (0–1), previously_flagged_ratio (0–1), prosecution_readiness (0–1)
    - Verify `compute_lead_priority_score` always returns int in [0, 100] and is idempotent (same inputs → same output)
    - **Validates: Requirements 2.2**

- [ ] 11. Final checkpoint — All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All backend changes EXTEND existing files — do NOT rewrite working code (per lessons-learned.md critical rule)
- `investigator.html` is large — frontend tasks describe what to ADD, not what to replace (except `renderBriefing()` body)
- No CDK deploy needed — all changes are Lambda code updates (zip + update-function-code)
- No new migrations — `investigator_analysis_cache` already has TEXT status and JSONB analysis_result columns
- vis-network is already loaded in investigator.html via CDN
- The `case_files.py` dispatcher needs only two small additions: `/entity-neighborhood` in the path match list, and `async_analysis` action routing
