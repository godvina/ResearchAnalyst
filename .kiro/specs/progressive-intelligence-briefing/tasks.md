# Implementation Plan: Progressive Intelligence Briefing

## Overview

Replace the flat alert list in AlertPanelManager with a 3-layer progressive disclosure system. Layer 1 is a compact headline bar (viability score, delta, alert count). Layer 2 is an expandable AI intelligence brief with indicator comparison bars. Layer 3 groups alerts by entity cluster with three enhancements: investigative entity titles, per-entity 4-section intelligence briefs, and inline network graphs. Add one new backend endpoint (`GET /trawl/briefing`) and extend the existing frontend AlertPanelManager.

## Tasks

- [x] 1. Backend — Briefing API endpoint
  - [x] 1.1 Add `trawl_briefing_handler` to `src/lambdas/api/trawl.py`
    - Add route `GET /case-files/{id}/trawl/briefing` in `dispatch_handler` BEFORE existing `/trawl/impact` route
    - Handler loads alerts via `_build_alert_store().list_alerts(case_id, is_dismissed=False)`
    - Handler loads impact data by reusing logic from `trawl_impact_handler` (get 2 most recent scans, compute before/after snapshots)
    - Compute top 5 entities by frequency from alert `entity_names` arrays
    - Build `indicator_deltas` dict with before/after for all 5 indicators
    - Attempt Bedrock Claude Haiku invocation with 3-second read timeout (`botocore.config.Config(read_timeout=3, connect_timeout=2, retries={'max_attempts': 0})`)
    - Prompt: alert count, top entities, indicator deltas, viability before→after; ask for 3-4 sentence briefing
    - On Bedrock success: return `source: "ai"` with AI-generated `brief_text`
    - On Bedrock timeout/error/unavailable: return `source: "fallback"` with deterministic fallback brief
    - Fallback template: `"{alert_count} new findings detected. Top entities: {top_3}. Viability moved from {before} to {after} ({direction}). {strongest_indicator} is the strongest signal at {score}/100."`
    - Response JSON: `brief_text`, `top_entities`, `indicator_deltas`, `generated_at` (ISO), `source` ("ai"|"fallback")
    - Return 404 if case has no scan history
    - Use `Optional[type]` syntax for Python 3.10 compatibility
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2, 8.3, 8.4, 9.2_

  - [x] 1.2 Write unit tests for briefing handler in `tests/unit/test_briefing_service.py`
    - Test: briefing route dispatches correctly via `dispatch_handler`
    - Test: successful Bedrock call returns `source: "ai"` with brief text
    - Test: Bedrock timeout returns `source: "fallback"` with deterministic brief
    - Test: Bedrock error returns `source: "fallback"`
    - Test: response contains all required fields (brief_text, top_entities, indicator_deltas, generated_at, source)
    - Test: 404 returned for non-existent case
    - Test: top_entities sorted by frequency descending, max 5
    - Test: indicator_deltas contains all 5 indicator keys with before/after
    - Mock `_build_alert_store` and Bedrock client
    - _Requirements: 4.3, 4.4, 8.1, 8.2, 8.3_

- [ ] 2. Backend — Property-based tests
  - [ ]* 2.1 Write property test: Verdict classification and color assignment (Property 1)
    - **Property 1: Verdict classification and color assignment are consistent with score thresholds**
    - Generate random integers 0-100
    - Verify verdict is PURSUE (67-100), INVESTIGATE FURTHER (34-66), CLOSE (0-33)
    - Verify color is #48bb78 (PURSUE), #ecc94b (INVESTIGATE FURTHER), #fc8181 (CLOSE)
    - Use Hypothesis `integers(min_value=0, max_value=100)`
    - Minimum 100 iterations
    - **Validates: Requirements 1.1, 1.7**

  - [ ]* 2.2 Write property test: Delta display formatting (Property 2)
    - **Property 2: Delta display formatting follows sign rules**
    - Generate random non-zero integers (-1000 to 1000, excluding 0)
    - Verify positive → "↑" + "STRONGER", negative → "↓" + "WEAKER"
    - Generate zero, verify no delta display produced
    - Minimum 100 iterations
    - **Validates: Requirements 1.2, 1.3**

  - [ ]* 2.3 Write property test: Fallback brief template (Property 3)
    - **Property 3: Fallback brief contains all required data elements**
    - Generate random: alert_count (0-500), entity_names (lists of 0-10 strings), before/after scores (0-100), indicator scores (0-100 each)
    - Verify fallback brief string contains: alert count, up to 3 entity names, both scores, direction word, strongest indicator name and score
    - Minimum 100 iterations
    - **Validates: Requirements 4.5, 9.2**

  - [ ]* 2.4 Write property test: Entity grouping (Property 4)
    - **Property 4: Entity grouping produces correctly keyed and sorted groups**
    - Generate random alert arrays (0-50 alerts) with varied entity_names (0-5 names each, some empty)
    - Verify: every alert in exactly one group, group key matches first entity_name (or "Ungrouped"), groups sorted by count descending
    - Minimum 100 iterations
    - **Validates: Requirements 5.2, 5.3, 5.5**

  - [ ]* 2.5 Write property test: Filter application in grouped view (Property 5)
    - **Property 5: Filters applied to grouped view produce correct subsets**
    - Generate random alert arrays with varied severity/source_type/is_dismissed
    - Generate random filter combinations (severity threshold, source filter)
    - Verify filtered grouped view contains exactly matching alerts
    - Minimum 100 iterations
    - **Validates: Requirements 10.1**

- [x] 3. Checkpoint — Backend tests pass
  - Run `pytest tests/unit/test_briefing_service.py -v` and verify all tests pass

- [x] 4. Frontend — Layer 1 Headline Bar
  - [x] 4.1 Refactor `AlertPanelManager.render()` to support 3-layer progressive disclosure
    - Add new state properties: `_currentLayer` (1|2|3), `_impactData` (cached), `_briefData` (cached), `_briefLoading` (bool), `_expandedGroups` ({})
    - Replace current `_loadCaseStrength` with `_loadImpactData` that caches the full impact response
    - Modify `render()` to call `_renderHeadlineBar()` (always visible) + layer-specific content based on `_currentLayer`
    - Preserve existing `panelOpen` behavior — headline bar replaces the old header
    - Keep `_renderCard` method unchanged for reuse in Layer 3
    - Keep all existing filter state and methods
    - _Requirements: 1.8, 6.1, 10.3, 10.4_

  - [x] 4.2 Implement `_renderHeadlineBar()` method
    - Display viability score as "{score}/100" with verdict text
    - Color code score: green (#48bb78) for PURSUE (67-100), amber (#ecc94b) for INVESTIGATE FURTHER (34-66), red (#fc8181) for CLOSE (0-33)
    - Display delta: "↑{pts} pts — Case STRONGER" (green) or "↓{pts} pts — Case WEAKER" (red) for non-zero deltas
    - Omit delta display for zero delta or no previous scan
    - Display "{count} new findings" from non-dismissed alert count
    - Display last scan timestamp
    - Include "▶ Run Trawl" button in headline actions area (moved from old header)
    - Include expand/collapse indicator: ▶ when L1, ▼ when L2/L3
    - Wire `onclick` to `toggleHeadline()`
    - Dark theme: background #1a2332, border #2d3748
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.3, 7.1_

- [ ] 5. Frontend — Layer 2 Intelligence Brief
  - [x] 5.1 Implement `_loadBriefing(caseId)` method
    - Async fetch `GET /case-files/{caseId}/trawl/briefing`
    - Set `_briefLoading = true` during fetch, render loading spinner
    - On success: cache response in `_briefData`, re-render
    - On failure: generate client-side fallback from cached `_impactData` and alert count
    - _Requirements: 3.2, 3.3_

  - [x] 5.2 Implement `_renderIntelligenceBrief()` method
    - Display brief text from `_briefData.brief_text`
    - Display source label: "(AI-generated)" for source="ai", "(auto-summary)" for source="fallback"
    - Render 5 indicator comparison bars using `_renderIndicatorBar(key, before, after)` from `_briefData.indicator_deltas`
    - Each bar: label, horizontal bar with muted "before" segment and colored "after" segment
    - Bar colors: green for >60, amber for 30-60, red for <30
    - Display "View All Findings →" button wired to `showGroupedView()`
    - _Requirements: 3.1, 3.4, 3.5, 3.6, 9.4_

  - [x] 5.3 Implement `toggleHeadline()` method
    - If `_currentLayer === 1`: set to 2, call `_loadBriefing()` if not cached
    - If `_currentLayer === 2`: set to 1
    - If `_currentLayer === 3`: set to 2 (back to brief)
    - Call `render()` after state change
    - _Requirements: 2.1, 2.2, 6.4_

- [x] 6. Frontend — Layer 3 Grouped Detail View
  - [x] 6.1 Implement `_groupAlertsByEntity()` method
    - Group filtered alerts by first element of `entity_names` array
    - Alerts with empty `entity_names` go to "Ungrouped" cluster
    - Return array of `{ entity, alerts, count }` sorted by count descending
    - _Requirements: 5.2, 5.3, 5.5, 5.8_

  - [x] 6.2 Implement `_renderGroupedDetailView()` method
    - Display "← Back to Brief" button wired to `backToBrief()`
    - Render existing filter buttons (severity, source, dismissed) — filters apply to grouped alerts
    - For each entity group: collapsible section header with entity name + count (e.g., "Visoski Network (12 overlaps)")
    - On header click: toggle `_expandedGroups[entity]`, re-render
    - When expanded: render individual alert cards using existing `_renderCard(alert)` method
    - _Requirements: 5.1, 5.4, 5.6, 5.7, 6.3, 10.1, 10.2_

  - [x] 6.3 Implement `showGroupedView()` and `backToBrief()` navigation methods
    - `showGroupedView()`: set `_currentLayer = 3`, render
    - `backToBrief()`: set `_currentLayer = 2`, render
    - _Requirements: 5.1, 6.3_

- [x] 7. Frontend — Refresh and state management
  - [x] 7.1 Update `runTrawl()` to refresh all layers after scan completes
    - After scan POST succeeds: reload alerts, reload impact data, clear cached `_briefData`
    - If `_currentLayer === 2`: re-fetch briefing
    - Preserve current layer state across refresh
    - _Requirements: 7.2, 7.3, 6.2_

  - [x] 7.2 Ensure existing features preserved within new layer system
    - Severity and source filter buttons work in Layer 3 grouped view
    - Dismiss, investigate, save-to-notebook actions work on cards within groups
    - Scan history toggle and case evolution timeline still accessible
    - AlertBadgeManager badge count polling unchanged
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 8. Checkpoint — Full integration test
  - Deploy frontend to S3: `aws s3 cp src/frontend/investigator.html s3://research-analyst-data-lake-974220725866/frontend/investigator.html --content-type "text/html" --cache-control "no-cache"`
  - Deploy Lambda: `Compress-Archive -Path src\* -DestinationPath lambda-update.zip -Force` then `aws lambda update-function-code --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --zip-file fileb://lambda-update.zip`
  - Verify Layer 1 headline shows viability score, delta, alert count
  - Verify Layer 2 expands with AI brief or fallback
  - Verify Layer 3 shows grouped alerts with collapsible entity clusters
  - Verify Run Trawl button works from all layers
  - Verify existing filters, dismiss, investigate actions work in grouped view

- [x] 9. Layer 3 Enhancement — Investigative Entity Titles
  - [x] 9.1 Implement `_buildInvestigativeTitle(group)` method in AlertPanelManager
    - Count `alert_type` frequency across all alerts in the group
    - Select dominant (most frequent) alert type
    - Return `{ descriptor, metric, color }` based on dominant type:
      - `cross_case_overlap` → "Cross-Case Key Entity", "{count} overlap(s)", `#63b3ed` (blue)
      - `network_expansion` → "Network Hub", "{count} connection(s)", `#48bb78` (green)
      - `entity_spike` → "Evidence Spike", "{count} new doc(s)", `#f6ad55` (orange)
      - Default → "Intelligence Finding", "{count} alert(s)", `#9f7aea` (purple)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 9.2 Update `_renderGroupedDetailView()` to use investigative titles
    - Call `_buildInvestigativeTitle(group)` for each entity group header
    - Render header as "{Entity Name} — {Descriptor} ({Metric})" with descriptor in the computed color
    - Replace the previous generic "{entity} ({count} overlaps)" format
    - _Requirements: 11.1, 11.4_

- [x] 10. Layer 3 Enhancement — 4-Section Intelligence Brief Per Entity
  - [x] 10.1 Implement `_renderEntityIntelBrief(group)` method in AlertPanelManager
    - Render 4-section brief with color-coded left borders:
      - BLUF (green `#48bb78`): entity name, finding count, case names from alert titles, evidence doc count
      - Key Finding (blue `#63b3ed`): cross-case significance description
      - Critical Gap (red `#fc8181`): missing evidence types (financial, communication records)
      - Next Action (amber `#ecc94b`): "🔍 Search for {entity}" button + "🕸️ Show Network" button
    - Extract case names from alert titles via regex matching
    - Count evidence documents from `evidence_refs` arrays across group alerts
    - All content generated deterministically from alert data — no Bedrock call
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x] 10.2 Implement individual findings toggle with `_expandedGroupCards` state
    - Add `_expandedGroupCards: {}` state object to AlertPanelManager
    - Render "📎 View N individual findings" / "📎 Hide individual findings" toggle button
    - `toggleGroupCards(entity)` method toggles `_expandedGroupCards[entity]` and re-renders
    - When toggled open, render individual alert cards via existing `_renderCard(alert)` method
    - _Requirements: 12.8, 12.9, 12.10_

  - [x] 10.3 Wire entity brief into `_renderGroupedDetailView()`
    - When an entity group is expanded (`_expandedGroups[entity]`), call `_renderEntityIntelBrief(group)` instead of directly rendering cards
    - Entity brief renders above the individual card toggle
    - _Requirements: 12.1_

- [x] 11. Layer 3 Enhancement — Inline Network Graph
  - [x] 11.1 Implement `showEntityNetwork(entity)` method in AlertPanelManager
    - Locate graph container div by ID (`entityNetGraph_{safeId}`)
    - Toggle off if graph already displayed (clear container innerHTML)
    - Show loading spinner with "Loading network graph..." text
    - Fetch `GET /case-files/{graphCaseId}/entity-neighborhood?entity_name={entity}&hops=1`
    - On success with nodes: call `_renderForceGraph(container, entity, nodes, edges)` (limit 20 nodes)
    - On success with 0 nodes: show "No graph data available for this entity" message
    - On error: show error message with failure reason
    - _Requirements: 13.1, 13.2, 13.12, 13.13, 13.14, 13.16_

  - [x] 11.2 Implement `_renderForceGraph(container, centerEntity, nodes, edges)` method
    - Build node list with deduplication by name; center entity pinned at (W/2, H/2)
    - Deterministic seeded layout: seed = sum of entity name character codes, LCG random
    - 100-iteration force simulation:
      - Repulsion: force = 800 / distance² between all node pairs
      - Attraction: force = (distance - 60) × 0.05 along edges
      - Center gravity: velocity += (center - position) × 0.01
      - Damping: 0.85 per iteration
      - Center entity pinned with zero velocity
      - Nodes clamped to [30, W-30] × [30, H-30]
    - Render inline SVG (600×300 viewBox, 300px height, `#0d1117` background)
    - Edges: gray lines (`#2d3748`, opacity 0.6)
    - Center node: radius 12, white border (width 2)
    - Neighbor nodes: radius 8, subtle border
    - Node colors by type: person=#48bb78, organization=#63b3ed, location=#f6ad55, date=#9f7aea, phone_number=#f687b3, email=#90cdf4, default=#718096
    - Labels: truncated to 15 chars with ellipsis, font-size 8px, color `#a0aec0`
    - Legend below SVG: Person, Organization, Location, Date, Other with color dots
    - Close button (✕) in top-right corner clears container
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10, 13.11, 13.15_

  - [x] 11.3 Add graph container div to `_renderEntityIntelBrief()`
    - Insert `<div id="entityNetGraph_{safeId}">` after the Next Action section
    - Container is initially empty; populated by `showEntityNetwork()` on button click
    - _Requirements: 13.1_

- [x] 12. Deployment — CloudFormation Prerequisites
  - [x] 12.1 Document Aurora PostgreSQL requirements
    - Migrations 011 (trawler tables), 012 (command center cache), 013 (ai_insight + indicator_snapshot columns)
    - Tables: `trawler_alerts`, `trawl_scans`, `trawl_configs`, `command_center_cache`, `top_pattern_cache`, `chat_conversations`
  - [x] 12.2 Document Neptune graph database requirements
    - Entity data with `Entity_{case_id}` vertex labels and `RELATED_TO` edges
    - Vertex properties: `name`, `type`
    - Same VPC as Lambda
  - [x] 12.3 Document Lambda function configuration
    - VPC access to Aurora and Neptune
    - Environment variables: NEPTUNE_ENDPOINT, NEPTUNE_PORT, AURORA_SECRET_ARN, AURORA_DB_NAME, BEDROCK_LLM_MODEL_ID, S3_BUCKET_NAME, OPENSEARCH_ENDPOINT, GRAPH_CASE_ID
    - IAM permissions: bedrock:InvokeModel, secretsmanager:GetSecretValue, neptune-db:*, s3:GetObject/PutObject
  - [x] 12.4 Document API Gateway and S3 frontend hosting
    - REST API with `{proxy+}` catch-all route to Lambda
    - S3 bucket with `investigator.html` at `frontend/investigator.html`
    - Bedrock Claude Haiku model access (optional — deterministic fallback available)

## Notes

- Tasks marked with `*` are optional property-based tests
- All Python code must use `Optional[type]` syntax (Python 3.10 compatible)
- All frontend code extends existing `AlertPanelManager` — never replace existing methods
- The `_renderCard` method is reused unchanged for individual alert cards in Layer 3
- Briefing endpoint reuses impact computation logic already in `trawl_impact_handler`
- Client-side entity grouping avoids adding a new backend endpoint
- Enhancement 1-3 are purely frontend changes in `investigator.html` (except the Neptune API call in Enhancement 3 which uses the existing `entity-neighborhood` endpoint)
- All three enhancements work without Bedrock — they are fully deterministic
- The inline network graph (Enhancement 3) requires Neptune connectivity but gracefully handles errors/empty responses
