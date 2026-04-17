# Requirements Document

## Introduction

The Case Intelligence Command Center is an additive dashboard overhaul for the Overview tab in `src/frontend/investigator.html`. Nothing is removed — three new high-value sections are inserted between the existing AI Intelligence Briefing and the Matter Assessment, and several existing sections receive non-destructive enhancements. The goal is to surface AI-driven insights immediately so the investigator sees what matters in under 5 seconds without clicking or expanding anything.

The three new sections are: (1) a Case Health Bar — a compact single-row strip of 5 mini radial gauges showing Evidence Coverage, Network Density, Temporal Coherence, Prosecution Readiness, and Overall Viability; (2) Did You Know Cards — 3 horizontal cards showing the top AI-generated discoveries from the Discovery Engine API; and (3) Anomaly Radar — 2-3 compact cards showing the top anomalies with inline SVG sparklines from the Anomaly Detection API.

Existing section changes are limited to: making the Matter Assessment collapsible (collapsed by default), making Key Subjects clickable for drill-down, making Recommended Actions clickable to trigger workflows, and adding "(Legacy)" labels to AI Hypotheses and Top 5 Patterns. The Knowledge Graph remains always visible and unchanged.

The backend APIs already exist: `/case-files/{id}/command-center` returns the five indicator scores, `/case-files/{id}/discoveries` returns AI discoveries, and `/case-files/{id}/anomalies` returns statistical anomalies. All frontend changes go in `src/frontend/investigator.html`.

## Glossary

- **Dashboard**: The Overview tab content rendered by the `selectCase()` function in `src/frontend/investigator.html`
- **Health_Bar**: A compact single-row horizontal strip containing five Mini_Gauges, positioned after the AI Briefing and before the Matter Assessment
- **Mini_Gauge**: A small SVG radial arc gauge (40-48px diameter) displaying a 0-100 numeric score with color coding: green for scores 60 and above, amber for scores 30-59, red for scores below 30
- **Command_Center_API**: The existing `/case-files/{id}/command-center` backend endpoint that returns the five indicator scores: signal_strength, corroboration_depth, network_density, temporal_coherence, prosecution_readiness
- **Overall_Viability**: A composite score computed as the average of the five indicator scores returned by the Command_Center_API
- **Discovery_API**: The existing `/case-files/{id}/discoveries` backend endpoint that returns AI-generated narrative discoveries with entity tags and confidence scores
- **Discovery_Card**: A horizontal card displaying one AI discovery: narrative text, primary entity tag, confidence dot (green/amber/red), and thumbs-up/thumbs-down feedback buttons
- **Anomaly_API**: The existing `/case-files/{id}/anomalies` backend endpoint that returns statistical anomalies with type, description, severity, and trend data
- **Anomaly_Card**: A compact card displaying one anomaly: type icon, description text, severity badge, and an inline SVG sparkline
- **Sparkline**: A compact inline SVG line chart (approximately 80x24px) rendered within an Anomaly_Card showing the statistical trend or deviation
- **Matter_Assessment**: The existing "📊 Matter Assessment — Investigator Command View" section containing the Case Strength score, stat boxes, Evidence Coverage grid, Key Subjects, and Recommended Actions
- **Investigator_View**: The main `investigator.html` single-page application containing all dashboard rendering logic
- **Research_Hub**: The existing Research Hub tab containing Chat, Compare, Discovery, and External Research sub-panels
- **DrillDown**: The existing entity drill-down system accessed via `DrillDown.open()` for investigating specific entities

## Requirements

### Requirement 1: Case Health Bar — Layout and Positioning

**User Story:** As an investigator, I want a compact health bar with 5 mini gauges always visible at the top of my dashboard, so that I can assess case health in one glance without scrolling or clicking.

#### Acceptance Criteria

1. WHEN the Dashboard renders for a selected case, THE Investigator_View SHALL insert the Health_Bar section after the AI Intelligence Briefing section and before the Matter_Assessment section.
2. THE Health_Bar SHALL render as a single horizontal row containing exactly five Mini_Gauges: Evidence Coverage, Network Density, Temporal Coherence, Prosecution Readiness, and Overall Viability.
3. THE Health_Bar SHALL remain always visible and SHALL NOT be collapsible.
4. THE Health_Bar SHALL use a section card container with a left border accent color of #63b3ed and a background consistent with the existing dark theme (#1a2332 card background).

### Requirement 2: Case Health Bar — Mini Gauge Rendering

**User Story:** As an investigator, I want each health gauge to show a color-coded arc with a numeric score, so that I can instantly distinguish strong dimensions from weak ones.

#### Acceptance Criteria

1. THE Mini_Gauge SHALL render as an inline SVG radial arc between 40 and 48 pixels in diameter with the numeric score (0-100) centered inside the arc.
2. WHEN a Mini_Gauge score is 60 or above, THE Mini_Gauge SHALL render the arc stroke and score text in green (#48bb78).
3. WHEN a Mini_Gauge score is between 30 and 59 inclusive, THE Mini_Gauge SHALL render the arc stroke and score text in amber (#f6ad55).
4. WHEN a Mini_Gauge score is below 30, THE Mini_Gauge SHALL render the arc stroke and score text in red (#fc8181).
5. THE Mini_Gauge arc SHALL fill proportionally to the score value using SVG stroke-dasharray, where a score of 100 fills the complete arc and a score of 0 shows only the background track.

### Requirement 3: Case Health Bar — Tooltip Insights

**User Story:** As an investigator, I want to hover on any gauge to see a brief insight, so that I can understand what each score means without navigating away.

#### Acceptance Criteria

1. WHEN the investigator hovers over a Mini_Gauge, THE Investigator_View SHALL display a tooltip containing the indicator name, the numeric score, and a one-line insight text returned by the Command_Center_API.
2. THE tooltip SHALL appear within 200 milliseconds of hover and disappear when the cursor leaves the Mini_Gauge area.
3. THE tooltip SHALL render with a dark background (#0d1520), light text (#e2e8f0), and a subtle border (#2d3748) consistent with the existing UI theme.

### Requirement 4: Case Health Bar — Data Loading

**User Story:** As an investigator, I want the health bar to load automatically when I select a case, so that I see scores without any manual action.

#### Acceptance Criteria

1. WHEN the investigator selects a case, THE Investigator_View SHALL call the Command_Center_API endpoint (`/case-files/{id}/command-center`) to retrieve the five indicator scores.
2. THE Investigator_View SHALL compute the Overall_Viability score as the arithmetic mean of the five indicator scores, clamped to the integer range 0-100.
3. WHILE the Command_Center_API request is in progress, THE Health_Bar SHALL display a loading spinner in place of the gauges.
4. IF the Command_Center_API returns an error or is unavailable, THEN THE Health_Bar SHALL display all five Mini_Gauges with a score of 0 and a muted color (#4a5568) with a "Data unavailable" tooltip.

### Requirement 5: Did You Know Cards — Layout and Positioning

**User Story:** As an investigator, I want to see the top 3 AI discoveries as horizontal cards immediately below the health bar, so that I can spot surprising findings without navigating to the Research Hub.

#### Acceptance Criteria

1. WHEN the Dashboard renders for a selected case, THE Investigator_View SHALL insert the Did You Know section after the Health_Bar and before the Anomaly Radar section.
2. THE Did You Know section SHALL display up to 3 Discovery_Cards in a horizontal row.
3. WHEN the Discovery_API returns more than 3 discoveries, THE Did You Know section SHALL enable horizontal scrolling to reveal additional cards.
4. THE Did You Know section SHALL display a "See all discoveries →" link that navigates the investigator to the Research Hub Discovery tab.
5. THE Did You Know section SHALL use a section heading of "💡 Did You Know" with a left border accent color of #f6e05e.

### Requirement 6: Did You Know Cards — Card Content

**User Story:** As an investigator, I want each discovery card to show the narrative, entity tag, confidence level, and feedback buttons, so that I can evaluate and rate discoveries inline.

#### Acceptance Criteria

1. THE Discovery_Card SHALL display the narrative text returned by the Discovery_API as the primary content.
2. THE Discovery_Card SHALL display the primary entity name as a tag badge below the narrative text.
3. THE Discovery_Card SHALL display a confidence indicator dot: green (#48bb78) for confidence above 0.7, amber (#f6ad55) for confidence between 0.4 and 0.7 inclusive, red (#fc8181) for confidence below 0.4.
4. THE Discovery_Card SHALL display a thumbs-up (👍) button and a thumbs-down (👎) button for feedback.
5. WHEN the investigator clicks the thumbs-up button, THE Investigator_View SHALL send a positive feedback rating to the Discovery_API feedback endpoint for the discovery.
6. WHEN the investigator clicks the thumbs-down button, THE Investigator_View SHALL send a negative feedback rating to the Discovery_API feedback endpoint for the discovery.

### Requirement 7: Did You Know Cards — Data Loading

**User Story:** As an investigator, I want the discovery cards to load automatically when I select a case, so that I see AI insights without manual action.

#### Acceptance Criteria

1. WHEN the investigator selects a case, THE Investigator_View SHALL call the Discovery_API endpoint (`/case-files/{id}/discoveries`) to retrieve the top discoveries.
2. WHILE the Discovery_API request is in progress, THE Did You Know section SHALL display a loading spinner.
3. IF the Discovery_API returns an empty result set, THEN THE Did You Know section SHALL display an empty state message: "No discoveries yet — the AI is still analyzing your case data."
4. IF the Discovery_API returns an error, THEN THE Did You Know section SHALL display an error message with a "Retry" button that re-invokes the Discovery_API call.

### Requirement 8: Anomaly Radar — Layout and Positioning

**User Story:** As an investigator, I want to see the top anomalies as compact cards with sparklines below the discovery cards, so that I can spot structural deviations at a glance.

#### Acceptance Criteria

1. WHEN the Dashboard renders for a selected case, THE Investigator_View SHALL insert the Anomaly Radar section after the Did You Know section and before the Matter_Assessment section.
2. THE Anomaly Radar section SHALL display 2 to 3 Anomaly_Cards in a horizontal row.
3. THE Anomaly Radar section SHALL display a "See all anomalies →" link that navigates the investigator to the Research Hub Discovery tab.
4. THE Anomaly Radar section SHALL use a section heading of "📡 Anomaly Radar" with a left border accent color of #fc8181.

### Requirement 9: Anomaly Radar — Card Content

**User Story:** As an investigator, I want each anomaly card to show the type, description, severity, and a sparkline, so that I can quickly assess the nature and magnitude of each anomaly.

#### Acceptance Criteria

1. THE Anomaly_Card SHALL display an anomaly type icon corresponding to the anomaly type (temporal, network, frequency, co-absence, or volume).
2. THE Anomaly_Card SHALL display the anomaly description text as the primary content.
3. THE Anomaly_Card SHALL display a severity badge color-coded by severity level: red for "high", amber for "medium", green for "low".
4. THE Anomaly_Card SHALL render an inline SVG Sparkline (approximately 80 pixels wide by 24 pixels tall) showing the trend data returned by the Anomaly_API.
5. THE Sparkline SHALL render as a polyline SVG element with a stroke color matching the severity badge color.

### Requirement 10: Anomaly Radar — Data Loading

**User Story:** As an investigator, I want the anomaly cards to load automatically when I select a case, so that I see structural deviations without manual action.

#### Acceptance Criteria

1. WHEN the investigator selects a case, THE Investigator_View SHALL call the Anomaly_API endpoint (`/case-files/{id}/anomalies`) to retrieve the top anomalies.
2. WHILE the Anomaly_API request is in progress, THE Anomaly Radar section SHALL display a loading spinner.
3. IF the Anomaly_API returns an empty result set, THEN THE Anomaly Radar section SHALL display an empty state message: "No anomalies detected — case data appears structurally consistent."
4. IF the Anomaly_API returns an error, THEN THE Anomaly Radar section SHALL display an error message with a "Retry" button that re-invokes the Anomaly_API call.

### Requirement 11: Matter Assessment — Collapsible Enhancement

**User Story:** As an investigator, I want the Matter Assessment section collapsed by default since the Health Bar now provides the at-a-glance view, so that the dashboard is less cluttered while still allowing me to expand the full assessment when needed.

#### Acceptance Criteria

1. WHEN the Dashboard renders, THE Investigator_View SHALL render the Matter_Assessment section as a collapsible section with a toggle arrow, collapsed by default.
2. WHEN the investigator clicks the Matter_Assessment header or toggle arrow, THE Investigator_View SHALL expand the section to show the full Case Strength score, stat boxes, Evidence Coverage grid, Key Subjects, and Recommended Actions.
3. WHEN the Matter_Assessment is collapsed, THE Investigator_View SHALL display only the section header with the toggle arrow indicator.
4. THE Matter_Assessment SHALL retain all existing content and functionality — the collapsible behavior is additive and does not remove or alter any existing elements.

### Requirement 12: Key Subjects — Clickable Enhancement

**User Story:** As an investigator, I want each person in the Key Subjects list to be clickable for drill-down, so that I can investigate any subject directly from the dashboard.

#### Acceptance Criteria

1. WHEN the Matter_Assessment renders Key Subjects, THE Investigator_View SHALL render each subject name as a clickable element with a hover cursor and underline indicator.
2. WHEN the investigator clicks a Key Subject name, THE Investigator_View SHALL open the DrillDown for that entity using the existing `DrillDown.open()` function with the entity name and case ID.
3. THE clickable Key Subject element SHALL display a visual hover state (color change to #63b3ed) to indicate interactivity.

### Requirement 13: Recommended Actions — Clickable Enhancement

**User Story:** As an investigator, I want each recommended action to be clickable to trigger the relevant workflow, so that I can act on recommendations directly from the dashboard.

#### Acceptance Criteria

1. WHEN the Matter_Assessment renders Recommended Actions, THE Investigator_View SHALL render each action as a clickable element with a hover cursor.
2. WHEN the investigator clicks a Recommended Action that references a search query, THE Investigator_View SHALL populate the Intelligence Search input with the query text and trigger a search.
3. WHEN the investigator clicks a Recommended Action that references an entity, THE Investigator_View SHALL open the DrillDown for that entity.
4. WHEN the investigator clicks a Recommended Action that references a hypothesis, THE Investigator_View SHALL open the Hypothesis Tester panel with the hypothesis text pre-populated.
5. THE clickable Recommended Action element SHALL display a visual hover state to indicate interactivity.

### Requirement 14: Did You Know Cards — Graph Highlighting

**User Story:** As an investigator, I want to click a Did You Know card and see the relevant entities highlighted in the Knowledge Graph, so that I can visually understand the discovery's context within the relationship network.

#### Acceptance Criteria

1. WHEN the investigator clicks a Discovery_Card, THE Investigator_View SHALL highlight the discovery's primary entity and its direct connections in the Knowledge Graph using the same glow animation and focused zoom used by the existing Top 5 Patterns click behavior.
2. THE Investigator_View SHALL scroll the Knowledge Graph section into view if it is not currently visible.
3. THE Investigator_View SHALL dim non-relevant nodes and edges to visually isolate the discovery's entity neighborhood.
4. WHEN the investigator clicks a different Discovery_Card, THE Investigator_View SHALL clear the previous highlighting and apply highlighting for the newly selected discovery.

### Requirement 15: Anomaly Radar — Graph Highlighting

**User Story:** As an investigator, I want to click an Anomaly Radar card and see the anomaly's entities highlighted in the Knowledge Graph, so that I can visually assess the structural anomaly in context.

#### Acceptance Criteria

1. WHEN the investigator clicks an Anomaly_Card, THE Investigator_View SHALL highlight all entities listed in the anomaly's entity array and their direct connections in the Knowledge Graph using the same glow animation and focused zoom used by the existing Top 5 Patterns click behavior.
2. FOR network anomalies that identify bridge entities, THE Investigator_View SHALL additionally highlight the disconnected clusters on either side of the bridge entity using distinct cluster colors.
3. THE Investigator_View SHALL scroll the Knowledge Graph section into view if it is not currently visible.
4. THE Investigator_View SHALL dim non-relevant nodes and edges to visually isolate the anomaly's entity neighborhood.

### Requirement 16: Anomaly Descriptions — Investigator-Friendly Language

**User Story:** As an investigator, I want anomaly descriptions written in investigative language rather than graph theory jargon, so that I can immediately understand the significance of each anomaly.

#### Acceptance Criteria

1. THE AnomalyDetectionService network detector SHALL generate descriptions using investigative language. INSTEAD OF "Entity 'X' bridges N disconnected clusters with no inter-cluster connections", THE description SHALL read "X connects N separate groups who have no other links — potential intermediary or cutout".
2. THE AnomalyDetectionService frequency detector SHALL generate descriptions using investigative language. INSTEAD OF "Entity 'X' occurs N times, exceeding threshold", THE description SHALL read "X is mentioned N times — far more than typical — possible central figure or key subject".
3. THE AnomalyDetectionService co-absence detector SHALL generate descriptions using investigative language. INSTEAD OF "Entities 'X' and 'Y' co-occur in N sources but are absent from Z", THE description SHALL read "X and Y appear together in N sources but are missing from Z — possible deliberate omission or gap in evidence".
4. THE AnomalyDetectionService temporal detector SHALL generate descriptions using investigative language. INSTEAD OF "Document frequency increased N% between periods", THE description SHALL read "Unusual spike in activity between [period1] and [period2] — N% increase may indicate a triggering event".
5. THE AnomalyDetectionService volume detector SHALL generate descriptions using investigative language appropriate for entity type distribution anomalies.

### Requirement 17: Legacy Section Labels

**User Story:** As an investigator, I want the AI Hypotheses and Top 5 Patterns sections labeled as legacy, so that I understand these are older features being superseded by the new intelligence sections.

#### Acceptance Criteria

1. WHEN the Dashboard renders the AI Hypotheses section header, THE Investigator_View SHALL append a "(Legacy)" label styled in muted text (#718096, font-size 0.75em) after the section title.
2. WHEN the Dashboard renders the Top 5 Investigative Patterns section header, THE Investigator_View SHALL append a "(Legacy)" label styled in muted text (#718096, font-size 0.75em) after the section title.
3. THE "(Legacy)" labels SHALL be additive — the sections retain all existing functionality and content.

### Requirement 18: Dashboard Section Ordering

**User Story:** As an investigator, I want the dashboard sections in a specific order that puts AI-driven insights first, so that the most actionable intelligence is visible without scrolling.

#### Acceptance Criteria

1. THE Dashboard SHALL render sections in the following order from top to bottom: AI Intelligence Briefing, Health_Bar, Did You Know, Anomaly Radar, Matter_Assessment (collapsible, collapsed), Intelligence Search, Research Notebook (collapsed), Evidence Triage (collapsed), AI Hypotheses (collapsed, legacy label), Subpoena Recommendations (collapsed), Top 5 Investigative Patterns (collapsed, legacy label), Knowledge Graph (always visible).
2. THE Dashboard SHALL preserve the existing rendering of all sections not modified by this specification — only positioning and collapsibility change.

### Requirement 19: Graceful Degradation

**User Story:** As an investigator, I want the new sections to handle API failures gracefully, so that a backend issue does not break my entire dashboard.

#### Acceptance Criteria

1. IF the Command_Center_API is unavailable, THEN THE Health_Bar SHALL render with zeroed gauges and a "Data unavailable" indicator, and THE remaining Dashboard sections SHALL continue to render and function.
2. IF the Discovery_API is unavailable, THEN THE Did You Know section SHALL display its error state, and THE remaining Dashboard sections SHALL continue to render and function.
3. IF the Anomaly_API is unavailable, THEN THE Anomaly Radar section SHALL display its error state, and THE remaining Dashboard sections SHALL continue to render and function.
4. THE three new sections SHALL operate independently — a failure in one section SHALL NOT prevent the other two sections from loading and displaying data.

### Requirement 20: Dark Theme Consistency

**User Story:** As an investigator, I want the new sections to match the existing dark theme, so that the dashboard looks cohesive and professional.

#### Acceptance Criteria

1. THE Health_Bar, Did You Know section, and Anomaly Radar section SHALL use the existing dark theme color palette: #0f1923 page background, #1a2332 card backgrounds, #2d3748 borders, #e2e8f0 primary text, #718096 secondary text, #48bb78 accent green.
2. THE new sections SHALL use the existing `section-card` CSS class for card containers and follow the existing inline style patterns used throughout the Dashboard.
3. THE new sections SHALL render all visual elements (gauges, sparklines, confidence dots) using inline SVG within the existing inline JavaScript pattern — no external CSS files or JavaScript libraries.
