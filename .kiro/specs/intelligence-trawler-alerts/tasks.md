# Implementation Plan: Intelligence Trawler & Alerts

## Overview

Implement the Intelligence Trawler as a multi-phase background analysis engine that proactively detects new intelligence leads across Neptune graph, OpenSearch documents, pattern scores, cross-case overlaps, and external OSINT sources. The system generates prioritized alerts displayed in a new Alert Panel within the investigator UI. All code extends existing services and UI without replacing anything.

## Tasks

- [x] 1. Database migration and alert store service
  - [x] 1.1 Create Aurora migration `src/db/migrations/011_intelligence_trawler.sql`
    - Create `trawler_alerts` table with all fields: alert_id, case_id, scan_id, alert_type, severity, title, summary, entity_names (JSONB), evidence_refs (JSONB), source_type, is_read, is_dismissed, created_at, updated_at
    - Create `trawl_scans` table with fields: scan_id, case_id, started_at, completed_at, alerts_generated, scan_status, scan_type, phase_timings, error_message, pattern_baseline
    - Create `trawl_configs` table with fields: case_id, enabled_alert_types, min_severity, external_trawl_enabled, created_at, updated_at
    - Add all indexes from design (case_id, unread, type, severity, source, created, GIN entity_names, dedup)
    - _Requirements: 3.1, 3.3, 9.1, 7.2, 7.3_

  - [x] 1.2 Implement `src/services/trawler_alert_store.py` — TrawlerAlertStore class
    - `list_alerts(case_id, alert_type, severity, source_type, is_read, is_dismissed, limit)` with multi-filter SQL query
    - `get_alert(alert_id)` returning full alert dict
    - `update_alert(alert_id, is_read, is_dismissed)` for PATCH operations
    - `get_unread_count(case_id)` for badge count (is_read=False, is_dismissed=False)
    - `list_scan_history(case_id, limit)` returning recent scans sorted by started_at DESC
    - `find_duplicate(case_id, alert_type, entity_names, days)` for dedup check within 7-day window
    - `merge_into_existing(alert_id, new_evidence_refs, new_summary)` resetting is_read and updating created_at
    - Use `Optional[type]` syntax for Python 3.10 compatibility
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 9.1, 9.2, 11.1, 11.2, 11.3_

  - [ ]* 1.3 Write property test for alert query filtering (Property 9)
    - **Property 9: Alert query filtering correctness**
    - Generate arbitrary sets of alerts with varied alert_type, severity, source_type, is_read, is_dismissed
    - For any combination of filter parameters, verify the result contains exactly matching alerts
    - Use Hypothesis strategies for alert fields
    - **Validates: Requirements 3.3**

- [x] 2. Checkpoint — Ensure migration and alert store tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. TrawlerEngine core service
  - [x] 3.1 Implement `src/services/trawler_engine.py` — TrawlerEngine class constructor and scan orchestration
    - Constructor accepting aurora_cm, pattern_service, cross_case_service, optional research_agent, optional search_service, neptune_endpoint, neptune_port
    - `run_scan(case_id, targeted_doc_ids)` orchestrating all phases sequentially with time budgeting
    - Create trawl_scans record at start (status=running), update on completion/failure/partial
    - Load last scan timestamp and pattern baseline from Aurora
    - Load trawl_config and respect enabled_alert_types and min_severity
    - Handle partial failures: if a phase fails, log error, set scan_status="partial", continue to next phase
    - Store scan timestamp and pattern baseline after completion
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 9.1, 9.4, 7.5_

  - [x] 3.2 Implement Phase 1: `_phase_graph_scan` — Neptune graph scan
    - Query Neptune for new entity connections added since last scan timestamp
    - Detect new_connection alerts (2+ previously unconnected entities with ≥3 shared evidence docs)
    - Detect network_expansion alerts (≥3 new connections to a single entity)
    - Detect temporal_anomaly alerts (cluster of events in 48-hour window with ≥3 tracked entities)
    - Build evidence_refs with ref_type="graph_edge" and source_label=edge ID
    - _Requirements: 1.1, 2.1, 2.5, 2.6_

  - [x] 3.3 Implement Phase 2: `_phase_document_scan` — OpenSearch document scan
    - Query OpenSearch for newly ingested documents matching tracked entities or case keywords
    - Support targeted scan with specific doc_ids for ingestion trigger
    - Detect entity_spike alerts (single entity in ≥5 new docs)
    - Detect new_evidence_match alerts for documents matching tracked entities
    - Build evidence_refs with ref_type="document" and source_label=filename
    - _Requirements: 1.2, 2.3, 10.1, 10.2, 10.3_

  - [x] 3.4 Implement Phase 3: `_phase_pattern_comparison` — pattern score comparison
    - Invoke PatternDiscoveryService.discover_top_patterns to get current scores
    - Compare against previous baseline stored in trawl_scans
    - Detect pattern_change alerts when score increases >25%
    - _Requirements: 1.3, 2.2_

  - [x] 3.5 Implement Phase 4: `_phase_cross_case_scan` — cross-case overlap detection
    - Invoke CrossCaseService.scan_for_overlaps(case_id)
    - Generate cross_case_overlap alerts with severity high for new overlaps
    - Build evidence_refs from matched entity data
    - _Requirements: 1.4, 2.4_

  - [x] 3.6 Implement Phase 5: `_phase_external_trawl` — OSINT via AIResearchAgent
    - Only run when external_trawl_enabled=True in trawl_config
    - Invoke AIResearchAgent.research_all_subjects for top 5 tracked entities
    - Invoke InvestigativeSearchService._generate_cross_reference_report to compare external vs internal
    - Generate external_lead alerts: "external_only" findings as alerts, "confirmed_internally" as severity medium
    - Set source_type="osint" on generated alerts
    - Build evidence_refs with ref_type="external_url" and source_label=actual URL/domain
    - Limit to 5 entities and 60 seconds total for external phase
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.6, 13.7_

  - [x] 3.7 Implement alert generation, severity assignment, and deduplication
    - `_generate_alerts(case_id, candidates, config)` applying severity rules: ≥10 refs=critical, 5-9=high, 3-4=medium, 1-2=low
    - Filter by config enabled_alert_types and min_severity threshold
    - `_deduplicate_alerts(case_id, alerts)` checking for existing non-dismissed alerts with same type, case_id, overlapping entity_names within 7 days
    - Merge into existing alert if duplicate found (update evidence_refs, summary, reset is_read, update created_at)
    - `_persist_alerts(case_id, scan_id, alerts)` with individual error handling per alert (Req 3.4)
    - Set source_type="internal" for phases 1-4, "osint" for phase 5
    - Log deduplicated alerts at debug level
    - _Requirements: 2.7, 3.2, 3.4, 7.5, 11.1, 11.2, 11.3, 11.4_

  - [x] 3.8 Implement trawl config CRUD
    - `get_trawl_config(case_id)` loading from Aurora trawl_configs, falling back to defaults
    - `save_trawl_config(case_id, config)` upserting to Aurora
    - Default config: all alert types enabled, min_severity="low", external_trawl_enabled=False
    - _Requirements: 7.2, 7.3, 7.5, 13.5_

- [ ] 4. TrawlerEngine property-based tests
  - [ ]* 4.1 Write property test for severity assignment (Property 1)
    - **Property 1: Severity assignment follows evidence count thresholds**
    - For any non-negative integer evidence count, verify correct severity mapping
    - **Validates: Requirements 2.7**

  - [ ]* 4.2 Write property test for threshold-based alert generation (Property 2)
    - **Property 2: Threshold-based alert generation**
    - For any candidate with count and alert type with threshold, verify alert generated iff count ≥ threshold
    - **Validates: Requirements 2.1, 2.3, 2.5**

  - [ ]* 4.3 Write property test for pattern score change detection (Property 3)
    - **Property 3: Pattern score change detection**
    - For any pair of baseline/current score dicts, verify pattern_change alert iff current > baseline × 1.25
    - **Validates: Requirements 1.3, 2.2**

  - [ ]* 4.4 Write property test for temporal anomaly detection (Property 4)
    - **Property 4: Temporal anomaly detection**
    - For any set of timestamped events, verify temporal_anomaly alert iff 48-hour window with ≥3 distinct entities
    - **Validates: Requirements 2.6**

  - [ ]* 4.5 Write property test for config-based alert filtering (Property 5)
    - **Property 5: Config-based alert filtering**
    - For any config and candidate alerts, verify filtered output matches enabled types AND meets severity threshold
    - **Validates: Requirements 7.5**

  - [ ]* 4.6 Write property test for alert deduplication (Property 6)
    - **Property 6: Alert deduplication**
    - For any new candidate and existing alerts, verify duplicate detection iff same case_id, alert_type, overlapping entity, within 7 days
    - **Validates: Requirements 11.1, 11.2**

  - [ ]* 4.7 Write property test for evidence reference structure (Property 7)
    - **Property 7: Evidence reference structure completeness**
    - For any generated evidence ref, verify all required fields present, ref_type valid, excerpt ≤500 chars
    - For external_lead alerts, verify ref_type="external_url" and source_label non-empty
    - **Validates: Requirements 3.5, 13.7**

  - [ ]* 4.8 Write property test for external finding categorization (Property 8)
    - **Property 8: External finding categorization produces correct alerts**
    - For any cross-reference entry, verify correct alert generation based on category
    - **Validates: Requirements 13.3, 13.4**

- [x] 5. Checkpoint — Ensure TrawlerEngine and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. API handler and router integration
  - [x] 6.1 Implement `src/lambdas/api/trawl.py` — dispatch_handler and route handlers
    - `dispatch_handler(event, context)` routing based on path and method
    - `run_trawl_handler` — POST `/case-files/{id}/trawl`: instantiate TrawlerEngine, run scan, return summary
    - `list_alerts_handler` — GET `/case-files/{id}/alerts`: query params for alert_type, severity, source_type, is_read, limit
    - `update_alert_handler` — PATCH `/case-files/{id}/alerts/{alert_id}`: update is_read/is_dismissed
    - `investigate_alert_handler` — POST `/case-files/{id}/alerts/{alert_id}/investigate`: mark read, return entity_names + evidence_refs
    - `scan_history_handler` — GET `/case-files/{id}/trawl/history`: return recent scans
    - `trawl_config_handler` — PUT `/case-files/{id}/trawl-config`: get/save config
    - Return 404 for missing case_id or alert_id
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.2, 7.4_

  - [x] 6.2 Add router integration in `src/lambdas/api/case_files.py`
    - Add routing block for `/trawl` and `/alerts` paths before the catch-all section
    - Route to `trawl.py` dispatch_handler when path contains `/trawl` or `/alerts` under `/case-files/`
    - Add `alert_id` path parameter extraction in `_normalize_resource` for `/alerts/{alert_id}` paths
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 12.2_

  - [x] 6.3 Add API routes in `scripts/add_api_routes.py`
    - Add trawl route: `/case-files/{id}/trawl` (POST)
    - Add alerts route: `/case-files/{id}/alerts` (GET)
    - Add alert by ID route: `/case-files/{id}/alerts/{alert_id}` (PATCH)
    - Add investigate route: `/case-files/{id}/alerts/{alert_id}/investigate` (POST)
    - Add trawl history route: `/case-files/{id}/trawl/history` (GET)
    - Add trawl config route: `/case-files/{id}/trawl-config` (PUT)
    - Add OPTIONS for all new routes
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 9.2, 7.4_

  - [ ]* 6.4 Write unit tests for API handler `tests/unit/test_trawl_handler.py`
    - Test POST /trawl invokes TrawlerEngine and returns scan summary
    - Test GET /alerts returns filtered alert list
    - Test PATCH /alerts/{id} updates is_read/is_dismissed
    - Test POST /alerts/{id}/investigate marks read and returns drill-down data
    - Test GET /trawl/history returns sorted scan records
    - Test PUT /trawl-config persists and returns config
    - Test 404 for missing case_id and alert_id
    - Test Save to Notebook creates finding with finding_type="trawler_alert"
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.2, 7.4, 8.6_

- [x] 7. Checkpoint — Ensure API handler tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Frontend Alert Panel and Badge
  - [x] 8.1 Implement Alert Panel HTML/CSS/JS in `src/frontend/investigator.html`
    - Append self-contained HTML, CSS, and JS to end of investigator.html
    - AlertPanelManager JS class: renders collapsible alert section at top of Case Dashboard
    - Alert cards showing: severity icon (🔴🟠🟡🔵), source badge (🏠 Internal / 🌐 External), type badge, title, truncated summary, entity count, timestamp
    - Expanded card view: full summary, clickable entity_names, clickable evidence_refs with ref_type icons (📄🕸️🌐) and source_label
    - Filter buttons for severity levels, source filter toggle (All/Internal/External), show/hide dismissed toggle
    - "Dismiss" button: PATCH API to mark dismissed, fade card visually
    - "Investigate" button: mark read, navigate to appropriate tab based on alert_type
    - "Save to Notebook" button: save alert as finding via FindingsService with finding_type="trawler_alert"
    - "⚙️ Trawl Settings" button opening config modal with alert type toggles and severity threshold selector
    - "📊 Scan History" link showing collapsible scan history section
    - "Run Trawl" button triggering POST /trawl
    - External Sources toggle in config modal (disabled by default)
    - Persist config to localStorage key `trawlConfig_{caseId}` and PUT API
    - Dark theme styling: background #1a2332, borders #2d3748, severity colors for accent
    - Use `.trawler-alert-*` CSS class prefix for scoping
    - z-index below Entity Dossier panel (< 200)
    - Do not modify any existing HTML elements, CSS classes, or JS functions
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.3, 12.1, 12.2, 12.3, 13.5, 13.8_

  - [x] 8.2 Implement Alert Badge on Case Dashboard tab
    - AlertBadgeManager JS class: polls GET /alerts?is_read=false&is_dismissed=false for unread count
    - Display red badge (#e53e3e background, white text) at top-right of Case Dashboard tab label
    - Update count on alert read/dismiss/new scan without full page reload
    - Hide badge when count is zero
    - Append badge element to existing tab without altering onclick handler or styling
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 12.4_

  - [x] 8.3 Implement alert-to-investigation navigation workflows
    - new_connection → Dashboard tab, open Entity Dossier for primary entity
    - cross_case_overlap → Dashboard tab, trigger cross-case search for overlapping entity
    - entity_spike → Evidence Library tab with entity name pre-filled in search
    - temporal_anomaly → Timeline tab with relevant date range highlighted
    - network_expansion → Dashboard tab, open Entity Dossier for expanding entity
    - external_lead → Dashboard tab, trigger internal+external investigative search pre-populated with finding context
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 13.8_

- [x] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- All Python code must use `Optional[type]` syntax (Python 3.10 compatible)
- All frontend code is appended to existing investigator.html — never modify existing elements
