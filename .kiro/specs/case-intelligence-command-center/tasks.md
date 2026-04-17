# Implementation Plan: Case Intelligence Command Center

## Overview

Additive frontend overhaul to `src/frontend/investigator.html`: insert 3 new sections (Case Health Bar, Did You Know, Anomaly Radar) between AI Briefing and Matter Assessment, make Matter Assessment collapsible, enhance Key Subjects and Recommended Actions with click handlers, add Legacy labels, and wire graph highlighting. One backend change updates anomaly description templates in `src/services/anomaly_detection_service.py` to use investigator-friendly language. All property tests use fast-check in `tests/frontend/test_command_center_dashboard.test.js`.

## Tasks

- [x] 1. Add CSS styles and pure helper functions
  - [x] 1.1 Add CSS rules for Health Bar, Did You Know, and Anomaly Radar to the existing `<style>` block in `src/frontend/investigator.html`
    - Add `.health-gauge-item`, `.health-tooltip`, `.dyk-card`, `.dyk-feedback-btn-sm`, `.anomaly-radar-card` classes
    - Follow existing dark theme palette: #1a2332 backgrounds, #2d3748 borders, #e2e8f0 text
    - _Requirements: 20.1, 20.2, 20.3_

  - [x] 1.2 Add pure helper functions to the existing `<script>` block in `src/frontend/investigator.html`
    - Implement `_healthGaugeColor(score)`: ≥60 → #48bb78, ≥30 → #f6ad55, <30 → #fc8181
    - Implement `_dykConfidenceColor(confidence)`: >0.7 → #48bb78, ≥0.4 → #f6ad55, <0.4 → #fc8181
    - Implement `_severityColor(severity)`: high → #fc8181, medium → #f6ad55, low → #48bb78, default → #718096
    - Implement `_anomalyTypeIcon(type)`: temporal → ⏰, network → 🕸️, frequency → 📊, co_absence → 👻, volume → 📈, default → 📡
    - Implement `_renderMiniSparkline(dataPoints, color)`: returns 80×24 SVG string with polyline, adapted from existing `renderSparkline`
    - _Requirements: 2.2, 2.3, 2.4, 6.3, 9.1, 9.3, 9.5_


  - [ ]* 1.3 Write property test: gauge color classification covers all scores (Property 1)
    - **Property 1: Mini gauge color classification covers all scores**
    - For any integer score in [0, 100], `_healthGaugeColor(score)` returns exactly one of #48bb78, #f6ad55, or #fc8181 with exhaustive non-overlapping ranges
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 1.4 Write property test: confidence dot color classification covers all values (Property 4)
    - **Property 4: Confidence dot color classification covers all values**
    - For any float confidence in [0.0, 1.0], `_dykConfidenceColor(confidence)` returns exactly one of #48bb78, #f6ad55, or #fc8181 with exhaustive non-overlapping ranges
    - **Validates: Requirements 6.3**

  - [ ]* 1.5 Write property test: severity color consistency (Property 7)
    - **Property 7: Severity color is consistent across badge and sparkline**
    - For any severity in {high, medium, low}, `_severityColor(severity)` returns the correct color: high → #fc8181, medium → #f6ad55, low → #48bb78
    - **Validates: Requirements 9.3, 9.5**

  - [ ]* 1.6 Write property test: sparkline renders valid SVG (Property 8)
    - **Property 8: Sparkline renders valid SVG from trend data**
    - For any array of 2+ numeric data points, `_renderMiniSparkline(dataPoints, color)` returns SVG with width="80", height="24", a polyline with correct coordinate count, and specified stroke color
    - **Validates: Requirements 9.4**

  - [ ]* 1.7 Write property test: arc fill proportional to score (Property 2)
    - **Property 2: Arc fill is proportional to score**
    - For any score in [0, 100] and gauge size in [40, 48], the SVG stroke-dasharray fill from `_ccArcSvg(size, score, color, 3)` equals `arcLength * (score / 100)` where `arcLength = 2 * π * r * 0.75`
    - **Validates: Requirements 2.5**

- [x] 2. Checkpoint — Ensure CSS and helper functions are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Insert new HTML sections in `selectCase()` and implement load functions
  - [x] 3.1 Insert Health Bar, Did You Know, and Anomaly Radar HTML containers into the `selectCase()` function in `src/frontend/investigator.html`
    - Add 3 section-card `<div>` containers with placeholder content between AI Briefing and Matter Assessment
    - Health Bar: `#healthBarContent`, border-left #63b3ed, heading "🏥 Case Health Bar"
    - Did You Know: `#dykContent`, border-left #f6e05e, heading "💡 Did You Know" with "See all discoveries →" link
    - Anomaly Radar: `#anomalyRadarContent`, border-left #fc8181, heading "📡 Anomaly Radar" with "See all anomalies →" link
    - Section order: AI Briefing → Health Bar → Did You Know → Anomaly Radar → Matter Assessment
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 5.4, 5.5, 8.1, 8.2, 8.3, 8.4, 18.1_

  - [x] 3.2 Implement `loadCommandCenterHealth(caseId)` in `src/frontend/investigator.html`
    - Fetch `GET /case-files/{caseId}/command-center` via existing `api()` helper
    - Compute `overallViability = Math.round(mean of 5 scores)`, clamped 0-100
    - Render 5 mini gauges using `_ccArcSvg(44, score, color, 3)` into `#healthBarContent`
    - Each gauge wrapped in `.health-gauge-item` with tooltip showing name + score + insight
    - Show loading spinner while fetching; on error render 5 zeroed gauges with #4a5568 color and "Data unavailable" tooltip
    - _Requirements: 2.1, 2.5, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4_

  - [ ]* 3.3 Write property test: overall viability is clamped arithmetic mean (Property 3)
    - **Property 3: Overall viability is the clamped arithmetic mean**
    - For any 5 integer scores in [0, 100], overallViability equals `Math.min(100, Math.max(0, Math.round((s1+s2+s3+s4+s5)/5)))` and is always an integer in [0, 100]
    - **Validates: Requirements 4.2**

  - [x] 3.4 Implement `loadDidYouKnow(caseId)` in `src/frontend/investigator.html`
    - Fetch `GET /case-files/{caseId}/discoveries` via existing `api()` helper
    - Render up to 3 `.dyk-card` cards in horizontal flex row into `#dykContent`
    - Each card: narrative text, entity badge, confidence dot via `_dykConfidenceColor`, thumbs up/down buttons
    - If >3 discoveries, enable overflow-x:auto for horizontal scroll
    - Empty state: "No discoveries yet — the AI is still analyzing your case data."
    - Error state: error message + Retry button calling `loadDidYouKnow(selectedCaseId)`
    - _Requirements: 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 3.5 Write property test: discovery card contains narrative and entity (Property 5)
    - **Property 5: Discovery card contains narrative and entity**
    - For any discovery with non-empty narrative and entity strings, the rendered card HTML contains the narrative as visible content and the entity within a badge element
    - **Validates: Requirements 6.1, 6.2**

  - [x] 3.6 Implement `submitDykFeedback(discoveryId, rating)` in `src/frontend/investigator.html`
    - POST to `/case-files/{caseId}/discoveries/{discoveryId}/feedback` with rating
    - Immediately disable both buttons, highlight selected button with `.selected-up` or `.selected-down` class
    - On error: re-enable buttons, show toast
    - _Requirements: 6.5, 6.6_

  - [x] 3.7 Implement `loadAnomalyRadar(caseId)` in `src/frontend/investigator.html`
    - Fetch `GET /case-files/{caseId}/anomalies` via existing `api()` helper
    - Render top 2-3 `.anomaly-radar-card` cards in horizontal flex row into `#anomalyRadarContent`
    - Each card: type icon via `_anomalyTypeIcon`, description, severity badge via `_severityColor`, sparkline via `_renderMiniSparkline`
    - Empty state: "No anomalies detected — case data appears structurally consistent."
    - Error state: error message + Retry button calling `loadAnomalyRadar(selectedCaseId)`
    - _Requirements: 8.2, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4_

  - [ ]* 3.8 Write property test: anomaly card contains type icon and description (Property 6)
    - **Property 6: Anomaly card contains type icon and description**
    - For any anomaly with valid type in {temporal, network, frequency, co_absence, volume} and non-empty description, the rendered card HTML contains the correct icon and description text
    - **Validates: Requirements 9.1, 9.2**

  - [x] 3.9 Wire auto-load calls in `selectCase()` after `main.innerHTML = h`
    - Add independent calls: `loadCommandCenterHealth(caseId)`, `loadDidYouKnow(caseId)`, `loadAnomalyRadar(caseId)`
    - Each call is independent with its own try/catch — failure in one does not affect others
    - _Requirements: 4.1, 7.1, 10.1, 19.4_

  - [ ]* 3.10 Write property test: section independence on API failure (Property 9)
    - **Property 9: Section independence on API failure**
    - For any combination of success/failure across the 3 API calls, each section renders its own state independently; failure in one does not prevent the other two from loading
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4**

  - [x] 3.11 Implement `navigateToDiscovery()` in `src/frontend/investigator.html`
    - Switch to Research Hub tab via `switchTab('research')`, then to Discovery sub-panel via `switchResearchPanel('rh-patterns')`
    - Called by "See all discoveries →" and "See all anomalies →" links
    - _Requirements: 5.4, 8.3_

- [x] 4. Checkpoint — Ensure new sections load and render correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Graph highlighting and card click handlers
  - [x] 5.1 Implement `highlightGraphEntities(entityNames)` in `src/frontend/investigator.html`
    - Find matching nodes in `cachedGraphData` by `canonical_name`
    - Dim non-matching nodes (opacity 0.15) and edges (opacity 0.08)
    - Apply glow animation (`map-story-active` CSS class) to matching nodes
    - Fit vis-network view to matching nodes with padding
    - Scroll Knowledge Graph section into view with smooth scroll
    - If no matching nodes found, show toast: "Entity not found in graph"
    - Reuse same pattern as existing Top 5 Patterns click-to-highlight behavior
    - _Requirements: 14.1, 14.3, 15.1, 15.4_

  - [x] 5.2 Implement `highlightDykInGraph(entityName)` in `src/frontend/investigator.html`
    - Called on Did You Know card click
    - Highlight primary entity + 1-hop neighbors using `highlightGraphEntities`
    - Scroll Knowledge Graph into view
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

  - [x] 5.3 Implement `highlightAnomalyInGraph(anomalyEntities, anomalyType, metadata)` in `src/frontend/investigator.html`
    - Called on Anomaly Radar card click
    - For network anomalies: highlight bridge entity + cluster members with distinct cluster colors using `metadata.clusters`
    - For other types: highlight all entities in the anomaly
    - Scroll Knowledge Graph into view
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [x] 5.4 Add onclick handlers to Did You Know cards and Anomaly Radar cards
    - DYK card click → `highlightDykInGraph(entityName)`
    - Anomaly card click → `highlightAnomalyInGraph(entities, type, metadata)`
    - Clear previous highlighting when a different card is clicked
    - _Requirements: 14.1, 14.4, 15.1_

  - [ ]* 5.5 Write property test: graph highlighting targets correct entities (Property 11)
    - **Property 11: Graph highlighting targets correct entities**
    - For any DYK card click with non-empty entity name, `highlightDykInGraph` highlights nodes matching the entity + 1-hop neighbors. For any anomaly card click with non-empty entities array, `highlightAnomalyInGraph` highlights exactly the matching nodes.
    - **Validates: Requirements 14.1, 14.3, 15.1, 15.3**

- [x] 6. Matter Assessment collapsible wrapper and existing section enhancements
  - [x] 6.1 Wrap Matter Assessment in collapsible toggle in `selectCase()` in `src/frontend/investigator.html`
    - Add `data-section="matter-assessment"` to section card
    - Add clickable header with toggle arrow (`#dashAssessment-arrow`)
    - Wrap content in `#dashAssessment-body` div, `display:none` by default
    - Extend `toggleSection` dispatch to handle `loadDashboardAssessment` which calls existing `loadCaseAssessment(selectedCaseId, window.selectedCaseData)`
    - Move existing action buttons (Report, Case Strength, Hypothesis) inside the collapsible header
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 6.2 Enhance Key Subjects with clickable drill-down in `src/frontend/investigator.html`
    - Add `onmouseover` color change to #63b3ed and `onmouseout` back to #e2e8f0
    - Add `text-decoration:underline` on hover
    - Existing `onclick` calling `DrillDown.openEntity` is already present — verify and enhance hover states
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 6.3 Enhance Recommended Actions with click handlers in `src/frontend/investigator.html`
    - Actions referencing entities → `onclick` calls `DrillDown.openEntity(entityName, 'person')`
    - Actions with "search"/"investigate" → `onclick` populates search input and calls `runSearch()`
    - Actions with "hypothesis"/"test" → `onclick` opens Hypothesis Tester with pre-populated text
    - Add `cursor:pointer`, hover color change, left-border highlight on hover
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 6.4 Add "(Legacy)" labels to AI Hypotheses and Top 5 Patterns headers in `selectCase()` in `src/frontend/investigator.html`
    - Append `<span style="color:#718096;font-size:0.75em;font-weight:400;">(Legacy)</span>` to both section headers
    - Sections retain all existing functionality
    - _Requirements: 17.1, 17.2, 17.3_

- [x] 7. Checkpoint — Ensure graph highlighting, collapsible, and enhancements work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Backend — Investigator-friendly anomaly descriptions
  - [x] 8.1 Update anomaly description templates in `src/services/anomaly_detection_service.py`
    - Network detector: change "bridges N disconnected clusters" → "connects N separate groups who have no other links — potential intermediary or cutout"
    - Frequency detector: change "occurs N times, exceeding threshold" → "is mentioned N times — far more than typical — possible central figure or key subject"
    - Co-absence detector: change "co-occur in N sources but are absent from" → "appear together in N sources but are missing from — possible deliberate omission or gap in evidence"
    - Temporal detector: change "Document frequency increased/decreased" → "Unusual spike/drop in activity — may indicate a triggering event"
    - Volume detector: update to investigator-friendly language about entity type distribution
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 8.2 Write property test: anomaly descriptions use investigative language (Property 10)
    - **Property 10: Anomaly descriptions use investigative language**
    - For any anomaly generated by AnomalyDetectionService, the description SHALL NOT contain graph theory jargon ("bridges disconnected clusters", "exceeding threshold", "co-occur"). Descriptions SHALL use investigative language ("connects separate groups", "far more than typical", "possible deliberate omission").
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**

- [x] 9. Final checkpoint — Ensure all tests pass and sections render in correct order
  - Verify section ordering: AI Briefing → Health Bar → Did You Know → Anomaly Radar → Matter Assessment (collapsed) → Intelligence Search → Research Notebook → Evidence Triage → AI Hypotheses (Legacy) → Subpoena Recommendations → Top 5 Patterns (Legacy) → Knowledge Graph
  - Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 18.1, 18.2_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use fast-check (JavaScript PBT library) in `tests/frontend/test_command_center_dashboard.test.js`
- All frontend changes are additive to `src/frontend/investigator.html` — extend existing code, never replace
- Backend change is limited to description template strings in `src/services/anomaly_detection_service.py`
- Reuse existing patterns: `_ccArcSvg` for gauges, `renderSparkline` for sparklines, `toggleSection` for collapsible, Top 5 Patterns click-to-highlight for graph highlighting
