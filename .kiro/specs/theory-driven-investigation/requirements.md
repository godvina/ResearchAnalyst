# Requirements Document

## Introduction

The Theory-Driven Investigation Engine replaces the broken AI Hypotheses section with a top-down investigative methodology: start with theories, find evidence, score, refine. Instead of bottom-up pattern matching that never produced actionable results, this feature uses an Analysis of Competing Hypotheses (ACH) framework where the investigator and AI collaborate to generate, evaluate, and resolve theories against case evidence.

The engine has six phases: (1) a `TheoryEngineService` backend that scans all case evidence via Aurora, Neptune, and Bedrock to auto-generate 10-20 ranked theories; (2) an ACH scoring framework that evaluates each theory across 5 dimensions — Evidence Consistency, Evidence Diversity, Predictive Power, Contradiction Strength, and Evidence Gaps; (3) a Theory Dashboard tab showing theory cards in a grid with radar charts and scores; (4) a Theory Deep Dive view with supporting/contradicting evidence panels, entity maps, timelines, and investigator verdict controls; (5) REST API endpoints for theory CRUD, generation, and scoring; (6) integration with existing features including Did You Know, Anomaly Radar, Knowledge Graph, Research Hub, and Case Health Bar.

The feature works for any case type — crime, intelligence, research, compliance, or Ancient Aliens investigations. Theories are cached in Aurora (new `theories` table), re-scored on demand or when new evidence arrives, and support both AI-generated and manually-added entries. The existing AI Hypotheses section remains as legacy; this feature supersedes it.

## Glossary

- **Theory**: A structured investigative hypothesis with a title, description, type classification, confidence score, supporting entities, and evidence linkages, stored in the Aurora `theories` table
- **Theory_Type**: A classification category for a Theory: one of `financial`, `temporal`, `relational`, `behavioral`, or `structural`
- **TheoryEngineService**: The new Python backend service (`src/services/theory_engine_service.py`) responsible for generating, scoring, storing, and retrieving theories
- **ACH_Framework**: Analysis of Competing Hypotheses — a structured scoring methodology that evaluates each Theory across five dimensions to produce an Overall_Score
- **Evidence_Consistency**: ACH dimension (0-100) measuring how much case evidence directly supports the Theory
- **Evidence_Diversity**: ACH dimension (0-100) measuring whether supporting evidence comes from multiple independent sources
- **Predictive_Power**: ACH dimension (0-100) measuring whether the Theory explains observations that other theories cannot
- **Contradiction_Strength**: ACH dimension (0-100) measuring the strength of contradicting evidence, scored inversely — a high score means weak contradictions, which is favorable
- **Evidence_Gaps**: ACH dimension (0-100) measuring evidence completeness, scored inversely — a high score means few gaps, which is favorable
- **Overall_Score**: A weighted average of the five ACH dimensions, clamped to integer range 0-100
- **Radar_Chart**: A small inline SVG pentagon chart rendered on each Theory_Card showing the five ACH dimension scores
- **Theory_Card**: A UI card in the Theory Dashboard displaying a Theory's title, summary, Radar_Chart, Overall_Score, evidence count, and entity badges
- **Theory_Dashboard**: The grid view of all Theory_Cards for a case, with sort and filter controls
- **Theory_Deep_Dive**: The detailed view shown when clicking a Theory_Card, containing evidence panels, entity map, timeline, and action buttons
- **Verdict**: An investigator's final assessment of a Theory: one of `confirmed`, `refuted`, or `inconclusive`
- **Investigator_View**: The main `investigator.html` single-page application containing all dashboard rendering logic
- **Bedrock_LLM**: Amazon Bedrock Claude Haiku (or configured model from FedRAMP registry) used for theory generation and evidence evaluation
- **Aurora_DB**: The Aurora PostgreSQL database storing case data, documents, entities, findings, and the new theories table
- **Neptune_Graph**: The Neptune knowledge graph storing entity relationships, used for relational context during theory generation
- **Theory_API**: The set of REST API endpoints under `/case-files/{id}/theories` for theory CRUD, generation, and scoring
- **Research_Hub**: The existing Research Hub tab containing Chat, Compare, Discovery, and External Research sub-panels
- **Knowledge_Graph**: The existing vis.js network visualization in the dashboard showing entity relationships
- **Health_Bar**: The existing Case Health Bar showing 5 radial gauges for case health indicators
- **DrillDown**: The existing entity drill-down system accessed via `DrillDown.open()` for investigating specific entities

## Requirements

### Requirement 1: Theory Generation — Evidence Scanning

**User Story:** As an investigator, I want the AI to scan all case evidence and generate theories automatically, so that I have a structured starting point for top-down investigation.

#### Acceptance Criteria

1. WHEN the investigator triggers theory generation for a case, THE TheoryEngineService SHALL query Aurora_DB for all documents, entities, findings, and pattern reports associated with the case.
2. WHEN Neptune_Graph is available, THE TheoryEngineService SHALL query Neptune_Graph for entity relationships, cluster structures, and bridge entities associated with the case.
3. IF Neptune_Graph is unavailable, THEN THE TheoryEngineService SHALL proceed with Aurora_DB data only and log a warning indicating Neptune data was excluded from theory generation.
4. THE TheoryEngineService SHALL pass the gathered evidence context to Bedrock_LLM with a structured prompt requesting theory generation.
5. THE TheoryEngineService SHALL complete theory generation within 30 seconds, including evidence scanning and Bedrock_LLM invocation.

### Requirement 2: Theory Generation — Theory Structure

**User Story:** As an investigator, I want each generated theory to have a clear title, description, type, and initial scoring, so that I can quickly assess and prioritize theories.

#### Acceptance Criteria

1. THE TheoryEngineService SHALL generate between 10 and 20 theories per generation request.
2. WHEN generating a Theory, THE TheoryEngineService SHALL produce: a concise title (under 120 characters), a one-paragraph description explaining the theory, a Theory_Type classification, an initial Overall_Score, a list of supporting entity names, and an evidence count.
3. THE TheoryEngineService SHALL assign each Theory exactly one Theory_Type from the set: `financial`, `temporal`, `relational`, `behavioral`, `structural`.
4. THE TheoryEngineService SHALL assign an initial Overall_Score between 0 and 100 based on the Bedrock_LLM's assessment of evidence strength.
5. THE TheoryEngineService SHALL extract entity names referenced in the Theory from the case's existing entity set in Aurora_DB.

### Requirement 3: Theory Storage — Aurora Schema

**User Story:** As an investigator, I want theories persisted in the database, so that they survive across sessions and can be tracked over time.

#### Acceptance Criteria

1. THE Aurora_DB SHALL contain a `theories` table with columns: `theory_id` (UUID primary key), `case_file_id` (UUID foreign key to case_files), `title` (VARCHAR 255), `description` (TEXT), `theory_type` (VARCHAR 20), `overall_score` (INTEGER 0-100), `evidence_consistency` (INTEGER 0-100), `evidence_diversity` (INTEGER 0-100), `predictive_power` (INTEGER 0-100), `contradiction_strength` (INTEGER 0-100), `evidence_gaps` (INTEGER 0-100), `supporting_entities` (JSONB), `evidence_count` (INTEGER), `verdict` (VARCHAR 20, nullable), `created_by` (VARCHAR 50), `created_at` (TIMESTAMP WITH TIME ZONE), `scored_at` (TIMESTAMP WITH TIME ZONE, nullable).
2. THE `theories` table SHALL have a foreign key constraint on `case_file_id` referencing `case_files(case_id)` with ON DELETE CASCADE.
3. THE `theories` table SHALL have a CHECK constraint on `verdict` allowing only `confirmed`, `refuted`, `inconclusive`, or NULL.
4. THE `theories` table SHALL have a CHECK constraint on `theory_type` allowing only `financial`, `temporal`, `relational`, `behavioral`, or `structural`.
5. THE Aurora_DB SHALL include indexes on `case_file_id` and `overall_score` for the `theories` table.

### Requirement 4: Theory Manual Entry

**User Story:** As an investigator, I want to manually add my own theories, so that I can test investigative hunches alongside AI-generated theories.

#### Acceptance Criteria

1. WHEN the investigator submits a manual theory with a title and description, THE TheoryEngineService SHALL create a new Theory record with `created_by` set to `investigator`.
2. WHEN a manual theory is created without a Theory_Type, THE TheoryEngineService SHALL use Bedrock_LLM to classify the theory into the appropriate Theory_Type based on the description.
3. WHEN a manual theory is created, THE TheoryEngineService SHALL set the initial Overall_Score to 50 and all five ACH dimension scores to 50 pending scoring.
4. THE TheoryEngineService SHALL extract entity names from the manual theory description by matching against the case's existing entity set in Aurora_DB.

### Requirement 5: ACH Scoring — Five Dimensions

**User Story:** As an investigator, I want each theory scored across 5 structured dimensions, so that I can understand exactly where a theory is strong or weak.

#### Acceptance Criteria

1. WHEN scoring a Theory, THE TheoryEngineService SHALL evaluate Evidence_Consistency by prompting Bedrock_LLM to assess how many pieces of case evidence directly support the Theory, producing a score from 0 to 100.
2. WHEN scoring a Theory, THE TheoryEngineService SHALL evaluate Evidence_Diversity by prompting Bedrock_LLM to assess whether supporting evidence comes from multiple independent document sources, producing a score from 0 to 100.
3. WHEN scoring a Theory, THE TheoryEngineService SHALL evaluate Predictive_Power by prompting Bedrock_LLM to assess whether the Theory explains observations that competing theories cannot, producing a score from 0 to 100.
4. WHEN scoring a Theory, THE TheoryEngineService SHALL evaluate Contradiction_Strength by prompting Bedrock_LLM to assess the strength of contradicting evidence, producing a score from 0 to 100 where a high score indicates weak contradictions.
5. WHEN scoring a Theory, THE TheoryEngineService SHALL evaluate Evidence_Gaps by prompting Bedrock_LLM to assess evidence completeness, producing a score from 0 to 100 where a high score indicates few gaps.
6. THE TheoryEngineService SHALL compute the Overall_Score as the weighted average of the five dimension scores, clamped to integer range 0-100.

### Requirement 6: ACH Scoring — Evidence Evaluation

**User Story:** As an investigator, I want the scoring to evaluate actual case evidence against each theory, so that scores reflect real data rather than abstract assessments.

#### Acceptance Criteria

1. WHEN scoring a Theory, THE TheoryEngineService SHALL retrieve all documents and findings for the case from Aurora_DB.
2. WHEN scoring a Theory, THE TheoryEngineService SHALL pass relevant evidence passages to Bedrock_LLM along with the Theory description for evaluation.
3. THE TheoryEngineService SHALL classify each evaluated evidence passage as `supporting`, `contradicting`, or `neutral` relative to the Theory.
4. THE TheoryEngineService SHALL store the updated five dimension scores and Overall_Score in the `theories` table and update the `scored_at` timestamp.
5. THE TheoryEngineService SHALL update the `evidence_count` field with the total number of evidence passages classified as `supporting` or `contradicting`.

### Requirement 7: Theory Re-Scoring on New Evidence

**User Story:** As an investigator, I want theories re-scored when new evidence is ingested, so that scores stay current as the case evolves.

#### Acceptance Criteria

1. WHEN new documents are ingested into a case, THE TheoryEngineService SHALL mark all theories for that case as stale by setting `scored_at` to NULL.
2. WHEN the investigator views a stale Theory (where `scored_at` is NULL), THE Theory_Dashboard SHALL display a "Scores may be outdated" indicator on the Theory_Card.
3. WHEN the investigator requests re-scoring for a Theory, THE TheoryEngineService SHALL re-evaluate the Theory against all current case evidence and update all five dimension scores and the Overall_Score.
4. THE Theory_API SHALL provide an endpoint to re-score a specific Theory on demand.

### Requirement 8: Theory Dashboard — Grid Layout

**User Story:** As an investigator, I want to see all theories in a visual grid with key metrics on each card, so that I can scan and compare theories at a glance.

#### Acceptance Criteria

1. WHEN the investigator navigates to the Theory_Dashboard, THE Investigator_View SHALL render Theory_Cards in a responsive grid layout with 2 columns on standard screens and 3 columns on wide screens.
2. THE Theory_Card SHALL display: the Theory title, a one-line summary (first sentence of description), a Radar_Chart showing the five ACH dimension scores, the Overall_Score as a prominent number, the evidence count, and entity name badges (up to 5 entities, with a "+N more" indicator for additional entities).
3. THE Theory_Card SHALL display a color-coded border based on Overall_Score: green (#48bb78) for scores 70 and above, amber (#f6ad55) for scores 40-69, red (#fc8181) for scores below 40.
4. WHEN a Theory has a Verdict set, THE Theory_Card SHALL display a verdict badge: green "✓ Confirmed" for `confirmed`, red "✗ Refuted" for `refuted`, gray "? Inconclusive" for `inconclusive`.

### Requirement 9: Theory Dashboard — Sort and Filter

**User Story:** As an investigator, I want to sort and filter theories by score, type, and other criteria, so that I can focus on the most relevant theories.

#### Acceptance Criteria

1. THE Theory_Dashboard SHALL provide sort controls with options: "Highest Score" (default), "Most Evidence", "Newest", and "Most Contradicted" (lowest Contradiction_Strength score).
2. THE Theory_Dashboard SHALL provide filter controls for Theory_Type with options: "All Types" (default), "Financial", "Temporal", "Relational", "Behavioral", "Structural".
3. THE Theory_Dashboard SHALL provide a score range filter with a minimum score slider (0-100, default 0).
4. WHEN the investigator changes sort or filter controls, THE Theory_Dashboard SHALL re-render the Theory_Card grid within 200 milliseconds using client-side filtering.

### Requirement 10: Theory Dashboard — Action Buttons

**User Story:** As an investigator, I want buttons to generate theories and add manual theories directly from the dashboard, so that I can drive the investigation from one place.

#### Acceptance Criteria

1. THE Theory_Dashboard SHALL display a "🤖 Generate Theories" button that triggers AI theory generation via the Theory_API.
2. WHEN the investigator clicks "Generate Theories", THE Investigator_View SHALL call `POST /case-files/{id}/theories/generate` and display a loading state with a progress message.
3. WHEN theory generation completes, THE Theory_Dashboard SHALL refresh the Theory_Card grid with the newly generated theories.
4. THE Theory_Dashboard SHALL display an "➕ Add Theory" button that opens a modal form with fields for title, description, and optional Theory_Type.
5. WHEN the investigator submits the Add Theory form, THE Investigator_View SHALL call `POST /case-files/{id}/theories` and add the new Theory_Card to the grid.

### Requirement 11: Theory Dashboard — Empty State

**User Story:** As an investigator, I want a clear empty state when no theories exist, so that I know how to get started with theory-driven investigation.

#### Acceptance Criteria

1. WHEN a case has zero theories, THE Theory_Dashboard SHALL display an empty state with the message "No theories yet — click Generate Theories to let the AI analyze your case, or Add Theory to test your own hypothesis."
2. THE empty state SHALL display both the "Generate Theories" and "Add Theory" buttons prominently.
3. THE empty state SHALL use a centered layout with a muted icon and text consistent with the dark theme.

### Requirement 12: Theory Deep Dive — Supporting Evidence Panel

**User Story:** As an investigator, I want to see all evidence that supports a theory with relevance scores, so that I can evaluate the strength of the supporting case.

#### Acceptance Criteria

1. WHEN the investigator clicks a Theory_Card, THE Investigator_View SHALL open the Theory_Deep_Dive view for that Theory.
2. THE Theory_Deep_Dive SHALL display the full Theory description at the top.
3. THE Theory_Deep_Dive SHALL display a "Supporting Evidence" panel listing all evidence passages classified as `supporting`, sorted by relevance score descending.
4. WHEN displaying a supporting evidence passage, THE Theory_Deep_Dive SHALL show: the passage text, the source document filename, a relevance score (0-100), and entity names mentioned in the passage.
5. WHEN the investigator clicks a source document filename, THE Investigator_View SHALL open the document in the existing document viewer.

### Requirement 13: Theory Deep Dive — Contradicting Evidence Panel

**User Story:** As an investigator, I want to see all evidence that contradicts a theory, so that I can assess weaknesses and potential disproving factors.

#### Acceptance Criteria

1. THE Theory_Deep_Dive SHALL display a "Contradicting Evidence" panel listing all evidence passages classified as `contradicting`, sorted by relevance score descending.
2. WHEN displaying a contradicting evidence passage, THE Theory_Deep_Dive SHALL show: the passage text, the source document filename, a relevance score (0-100), and a brief explanation of why the evidence contradicts the Theory.
3. THE Contradicting Evidence panel SHALL use a red-tinted left border (#fc8181) to visually distinguish it from the Supporting Evidence panel.

### Requirement 14: Theory Deep Dive — Evidence Gaps Panel

**User Story:** As an investigator, I want the AI to tell me what evidence is missing to prove or disprove a theory, so that I know where to focus my investigation next.

#### Acceptance Criteria

1. THE Theory_Deep_Dive SHALL display an "Evidence Gaps" panel listing AI-generated descriptions of missing evidence that would strengthen or weaken the Theory.
2. WHEN generating evidence gaps, THE TheoryEngineService SHALL prompt Bedrock_LLM to identify specific types of documents, witness statements, financial records, or other evidence that would be needed to confirm or refute the Theory.
3. THE Evidence Gaps panel SHALL display each gap as a card with a description and a suggested search query.
4. WHEN the investigator clicks a suggested search query in the Evidence Gaps panel, THE Investigator_View SHALL populate the Intelligence Search input with the query and trigger a search.

### Requirement 15: Theory Deep Dive — Entity Map

**User Story:** As an investigator, I want to see which entities are involved in a theory highlighted in the knowledge graph, so that I can understand the relational context.

#### Acceptance Criteria

1. THE Theory_Deep_Dive SHALL display an "Entity Map" section showing the entities listed in the Theory's `supporting_entities` field.
2. WHEN the Theory_Deep_Dive renders, THE Investigator_View SHALL highlight the Theory's supporting entities in the Knowledge_Graph using the same glow animation and focused zoom used by the existing Top 5 Patterns click behavior.
3. WHEN the investigator clicks an entity name in the Entity Map, THE Investigator_View SHALL open the DrillDown for that entity.
4. IF Neptune_Graph is unavailable, THEN THE Entity Map SHALL display entity names as a flat list without graph highlighting and display a note: "Graph visualization unavailable — Neptune connection not active."

### Requirement 16: Theory Deep Dive — Timeline

**User Story:** As an investigator, I want to see when evidence for a theory appeared chronologically, so that I can understand the temporal progression of the theory's evidence base.

#### Acceptance Criteria

1. THE Theory_Deep_Dive SHALL display a "Timeline" section showing supporting and contradicting evidence plotted chronologically by document indexed date.
2. THE Timeline SHALL render as a horizontal SVG timeline with evidence markers color-coded: green markers for supporting evidence, red markers for contradicting evidence.
3. WHEN the investigator hovers over a timeline marker, THE Investigator_View SHALL display a tooltip with the document filename, evidence classification, and indexed date.
4. WHEN the investigator clicks a timeline marker, THE Investigator_View SHALL scroll to the corresponding evidence passage in the Supporting or Contradicting Evidence panel.

### Requirement 17: Theory Deep Dive — Action Buttons

**User Story:** As an investigator, I want action buttons on the theory deep dive to drive further investigation, so that I can act on my analysis without leaving the context.

#### Acceptance Criteria

1. THE Theory_Deep_Dive SHALL display an "Investigate Further" button that generates targeted search queries based on the Theory's evidence gaps and opens the Intelligence Search with the first query populated.
2. THE Theory_Deep_Dive SHALL display a "Research This Theory" button that opens the Research_Hub Chat panel with the Theory title and description pre-populated as context.
3. THE Theory_Deep_Dive SHALL display a "Save Assessment" button that saves the current Theory evaluation (description, scores, evidence summary) as a new entry in the Research Notebook.
4. THE Theory_Deep_Dive SHALL display verdict buttons: "✓ Confirmed", "✗ Refuted", and "? Inconclusive" that set the Theory's Verdict via the Theory_API.
5. WHEN the investigator clicks a verdict button, THE Investigator_View SHALL call `PUT /case-files/{id}/theories/{theory_id}/verdict` and update the Theory_Card badge in the Theory_Dashboard.

### Requirement 18: Theory API — Generate Endpoint

**User Story:** As a frontend client, I want an API endpoint to trigger AI theory generation, so that the dashboard can request theory generation on demand.

#### Acceptance Criteria

1. THE Theory_API SHALL expose `POST /case-files/{id}/theories/generate` that triggers TheoryEngineService theory generation for the specified case.
2. WHEN the generate endpoint is called, THE Theory_API SHALL return a JSON response containing the list of generated theories with their IDs, titles, types, and initial scores.
3. IF the case has no documents or entities, THEN THE Theory_API SHALL return a 200 response with an empty theories list and a message: "Insufficient evidence to generate theories — ingest documents first."
4. IF Bedrock_LLM invocation fails, THEN THE Theory_API SHALL return a 500 response with an error message describing the failure.

### Requirement 19: Theory API — List and Detail Endpoints

**User Story:** As a frontend client, I want API endpoints to list all theories and get theory details, so that the dashboard can render the theory grid and deep dive views.

#### Acceptance Criteria

1. THE Theory_API SHALL expose `GET /case-files/{id}/theories` that returns all theories for the specified case, sorted by Overall_Score descending.
2. THE list endpoint SHALL return each Theory with: theory_id, title, description, theory_type, overall_score, evidence_consistency, evidence_diversity, predictive_power, contradiction_strength, evidence_gaps, supporting_entities, evidence_count, verdict, created_by, created_at, scored_at.
3. THE Theory_API SHALL expose `GET /case-files/{id}/theories/{theory_id}` that returns a single Theory with full detail including evidence passages classified as supporting, contradicting, and neutral.
4. THE detail endpoint SHALL include an `evidence_gaps` array containing AI-generated descriptions of missing evidence.
5. IF the specified theory_id does not exist, THEN THE Theory_API SHALL return a 404 response.

### Requirement 20: Theory API — Manual Create Endpoint

**User Story:** As a frontend client, I want an API endpoint to create a manual theory, so that investigators can add their own hypotheses.

#### Acceptance Criteria

1. THE Theory_API SHALL expose `POST /case-files/{id}/theories` that creates a new Theory with the provided title and description.
2. THE create endpoint SHALL accept optional fields: theory_type and supporting_entities.
3. WHEN theory_type is not provided, THE TheoryEngineService SHALL auto-classify the Theory_Type using Bedrock_LLM.
4. THE create endpoint SHALL return the created Theory with its generated theory_id and initial scores.
5. IF the title or description is missing from the request body, THEN THE Theory_API SHALL return a 400 response with a validation error message.

### Requirement 21: Theory API — Verdict and Score Endpoints

**User Story:** As a frontend client, I want API endpoints to set verdicts and trigger re-scoring, so that the dashboard can update theory status and refresh scores.

#### Acceptance Criteria

1. THE Theory_API SHALL expose `PUT /case-files/{id}/theories/{theory_id}/verdict` that sets the Theory's Verdict to `confirmed`, `refuted`, or `inconclusive`.
2. IF the verdict value is not one of `confirmed`, `refuted`, or `inconclusive`, THEN THE Theory_API SHALL return a 400 response with a validation error.
3. THE Theory_API SHALL expose `POST /case-files/{id}/theories/{theory_id}/score` that triggers re-scoring of the specified Theory against current case evidence.
4. WHEN the score endpoint is called, THE TheoryEngineService SHALL re-evaluate all five ACH dimensions and return the updated scores.
5. IF the specified theory_id does not exist for either endpoint, THEN THE Theory_API SHALL return a 404 response.

### Requirement 22: Integration — Did You Know Links to Theories

**User Story:** As an investigator, I want Did You Know discovery cards to show which theories they relate to, so that I can connect discoveries to my investigative framework.

#### Acceptance Criteria

1. WHEN rendering a Discovery_Card in the Did You Know section, THE Investigator_View SHALL check if any Theory's supporting_entities overlap with the discovery's entities.
2. WHEN a discovery has overlapping entities with one or more theories, THE Discovery_Card SHALL display a small "📐 N theories" badge linking to the related theories.
3. WHEN the investigator clicks the theories badge on a Discovery_Card, THE Investigator_View SHALL navigate to the Theory_Dashboard filtered to show only the related theories.

### Requirement 23: Integration — Anomaly Radar Links to Theories

**User Story:** As an investigator, I want anomaly cards to show which theories they support or contradict, so that I can understand how anomalies fit into my investigative theories.

#### Acceptance Criteria

1. WHEN rendering an Anomaly_Card in the Anomaly Radar section, THE Investigator_View SHALL check if any Theory's supporting_entities overlap with the anomaly's entities.
2. WHEN an anomaly has overlapping entities with one or more theories, THE Anomaly_Card SHALL display a small "📐 N theories" badge linking to the related theories.
3. WHEN the investigator clicks the theories badge on an Anomaly_Card, THE Investigator_View SHALL navigate to the Theory_Dashboard filtered to show only the related theories.

### Requirement 24: Integration — Knowledge Graph Highlighting

**User Story:** As an investigator, I want theory entities highlighted in the Knowledge Graph when viewing a theory, so that I can see the relational context visually.

#### Acceptance Criteria

1. WHEN the investigator opens a Theory_Deep_Dive, THE Investigator_View SHALL highlight all entities in the Theory's supporting_entities list in the Knowledge_Graph using the existing glow animation pattern.
2. THE Investigator_View SHALL scroll the Knowledge_Graph section into view when highlighting theory entities.
3. WHEN the investigator closes the Theory_Deep_Dive, THE Investigator_View SHALL clear the entity highlighting in the Knowledge_Graph.

### Requirement 25: Integration — Research Hub Chat

**User Story:** As an investigator, I want to discuss theories in the Research Hub Chat, so that I can use conversational AI to explore theory implications.

#### Acceptance Criteria

1. WHEN the investigator clicks "Research This Theory" in the Theory_Deep_Dive, THE Investigator_View SHALL switch to the Research_Hub Chat tab.
2. THE Investigator_View SHALL pre-populate the Chat input with context: "Analyze this theory: [Theory title]. [Theory description]. Current evidence score: [Overall_Score]/100."
3. THE Research_Hub Chat SHALL process the pre-populated context as a new conversation message.

### Requirement 26: Integration — Case Health Bar Theory Maturity Gauge

**User Story:** As an investigator, I want a Theory Maturity gauge in the Case Health Bar, so that I can see at a glance how well-developed my investigative theories are.

#### Acceptance Criteria

1. THE Health_Bar SHALL display a sixth Mini_Gauge labeled "Theory Maturity" after the existing five gauges.
2. THE Theory Maturity score SHALL be computed as: (number of theories with verdict set / total number of theories) × 100, clamped to integer range 0-100.
3. WHEN a case has zero theories, THE Theory Maturity gauge SHALL display a score of 0 with a tooltip: "No theories generated yet."
4. THE Theory Maturity gauge SHALL use the same color coding as existing gauges: green for 60 and above, amber for 30-59, red for below 30.

### Requirement 27: Theory Dashboard — Section Placement

**User Story:** As an investigator, I want the Theory Dashboard accessible as a prominent section in the Overview tab, replacing the legacy AI Hypotheses position, so that theory-driven investigation is front and center.

#### Acceptance Criteria

1. THE Investigator_View SHALL render the Theory_Dashboard section in the Overview tab after the Anomaly Radar section and before the Matter Assessment section.
2. THE Theory_Dashboard section SHALL use a section heading of "📐 Theory-Driven Investigation" with a left border accent color of #9f7aea.
3. THE Theory_Dashboard section SHALL be always visible (not collapsible) to emphasize its role as the primary investigative methodology.
4. THE existing AI Hypotheses section SHALL remain in its current position with the "(Legacy)" label — the Theory_Dashboard does not remove it.

### Requirement 28: Radar Chart Rendering

**User Story:** As an investigator, I want a small radar chart on each theory card showing the 5 ACH dimensions, so that I can visually compare theory profiles at a glance.

#### Acceptance Criteria

1. THE Radar_Chart SHALL render as an inline SVG pentagon chart approximately 80x80 pixels.
2. THE Radar_Chart SHALL plot the five ACH dimensions (Evidence_Consistency, Evidence_Diversity, Predictive_Power, Contradiction_Strength, Evidence_Gaps) as vertices of the pentagon.
3. THE Radar_Chart SHALL draw a filled polygon connecting the five dimension scores, with fill opacity of 0.3 and stroke opacity of 1.0.
4. THE Radar_Chart SHALL use the same color as the Theory_Card border (green, amber, or red based on Overall_Score).
5. THE Radar_Chart SHALL draw a background pentagon outline at the 100-score boundary in muted color (#2d3748) as a reference frame.

### Requirement 29: Graceful Degradation

**User Story:** As an investigator, I want the theory engine to work even when Neptune is unavailable, so that GovCloud deployments without Neptune can still use theory-driven investigation.

#### Acceptance Criteria

1. IF Neptune_Graph is unavailable during theory generation, THEN THE TheoryEngineService SHALL generate theories using only Aurora_DB data (documents, entities, findings, patterns) and Bedrock_LLM.
2. IF Neptune_Graph is unavailable during theory scoring, THEN THE TheoryEngineService SHALL score theories using only Aurora_DB evidence without relational context.
3. IF Neptune_Graph is unavailable, THEN THE Theory_Deep_Dive Entity Map SHALL display entity names as a flat list with a note indicating graph visualization is unavailable.
4. IF Bedrock_LLM invocation fails during scoring, THEN THE TheoryEngineService SHALL retain the existing scores and return an error message indicating scoring failed.
5. IF the Theory_API encounters an unexpected error, THEN THE Theory_API SHALL return a 500 response with a descriptive error message and THE Theory_Dashboard SHALL display an error state with a "Retry" button.

### Requirement 30: Dark Theme Consistency

**User Story:** As an investigator, I want the theory sections to match the existing dark theme, so that the dashboard looks cohesive.

#### Acceptance Criteria

1. THE Theory_Dashboard, Theory_Card, Theory_Deep_Dive, and Radar_Chart SHALL use the existing dark theme color palette: #0f1923 page background, #1a2332 card backgrounds, #2d3748 borders, #e2e8f0 primary text, #718096 secondary text.
2. THE Theory sections SHALL use the existing `section-card` CSS class for card containers and follow the existing inline style patterns used throughout the Investigator_View.
3. THE Theory sections SHALL render all visual elements (Radar_Charts, timeline, entity badges) using inline SVG within the existing inline JavaScript pattern — no external CSS files or JavaScript libraries.
