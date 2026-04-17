# Requirements Document

## Introduction

The Investigative Discovery Engine replaces the current Patterns tab and the Patterns sub-panel in the Research Hub with a two-lens investigative discovery experience. Lens 1 ("Did You Know") uses Bedrock Claude as the primary discovery engine to generate narrative, surprise-based investigative discoveries with feedback learning. Lens 2 ("Anomaly Radar") uses statistical algorithms to detect structural pattern deviations across temporal, network, frequency, co-absence, and volume dimensions. The two lenses enforce a zero-overlap rule: Did You Know never shows raw statistics, and Anomaly Radar never generates narratives. Both lenses feed into the existing 3-level investigation drilldown and can save discoveries to case findings via the existing FindingsService.

## Glossary

- **Discovery_Engine**: The DiscoveryEngineService backend component that orchestrates "Did You Know" generation, feedback incorporation, and iterative batch generation via Bedrock Claude
- **Anomaly_Detector**: The AnomalyDetectionService backend component that computes statistical anomalies across temporal, network, frequency, co-absence, and volume dimensions using algorithmic analysis
- **Discovery_Card**: A UI card in the "Did You Know" section displaying a narrative investigative discovery with thumbs-up/thumbs-down feedback controls and a drill-in action
- **Anomaly_Card**: A compact UI card in the "Anomaly Radar" section displaying a statistical finding with a sparkline or mini-chart and an "Investigate" button
- **Feedback_Store**: The Aurora PostgreSQL table (discovery_feedback) that persists user thumbs-up/thumbs-down ratings per discovery for feedback learning
- **Discovery_History**: The Aurora PostgreSQL table (discovery_history) that tracks previously generated discoveries per case to enable exclusion in subsequent batches
- **Investigation_Drilldown**: The existing 3-level investigative findings drilldown (investigative-findings-drilldown spec) that provides Level 1 leads, Level 2 evidence threads, and Level 3 source documents
- **Investigator_View**: The main investigator.html frontend application containing the tab bar, Research Hub, and case workspace
- **Batch**: A set of 5 discovery items generated in a single invocation of the Discovery_Engine
- **Sparkline**: A compact inline chart rendered within an Anomaly_Card showing the statistical trend or deviation visually

## Requirements

### Requirement 1: Did You Know — AI-Driven Discovery Generation

**User Story:** As an investigator, I want AI-generated narrative discoveries framed as "Did you know...?" so that I can quickly identify the most surprising and non-obvious findings across my case data.

#### Acceptance Criteria

1. WHEN an investigator opens the Discovery tab for a case, THE Discovery_Engine SHALL gather all available context (documents, entities, graph connections, temporal data, visual evidence) for the case and generate a Batch of 5 Discovery_Cards using Bedrock Claude as the primary discovery engine.
2. THE Discovery_Engine SHALL frame each discovery as a narrative "Did you know...?" statement that explains the investigative significance of the finding.
3. THE Discovery_Engine SHALL generate discoveries that are surprise-based, non-obvious, and actionable rather than restating raw statistics or graph metrics.
4. THE Discovery_Card SHALL display the narrative text, and THE Discovery_Card SHALL NOT display raw statistical values, counts, or graph metrics as standalone content.
5. WHEN the Discovery_Engine generates discoveries, THE Discovery_Engine SHALL use Bedrock Claude as the primary brain for synthesis, reading all available case context to determine what is interesting and investigatively significant.

### Requirement 2: Did You Know — Iterative Batch Generation

**User Story:** As an investigator, I want to request additional discoveries beyond the initial batch so that I can explore more findings without re-seeing previous ones.

#### Acceptance Criteria

1. WHEN the investigator clicks "Show me 5 more", THE Discovery_Engine SHALL generate a new Batch of 5 Discovery_Cards excluding all discovery IDs stored in the Discovery_History for the current case.
2. THE Discovery_Engine SHALL store each generated Batch in the Discovery_History table with the case_id, batch_number, and the full set of discovery content.
3. WHEN generating subsequent batches, THE Discovery_Engine SHALL include feedback context from the Feedback_Store in the generation prompt so that Bedrock Claude aligns new discoveries with the investigator's demonstrated preferences.
4. THE Discovery_Engine SHALL inject feedback into the prompt using the pattern: "The investigator found these types of discoveries useful: [thumbs-up examples]. They did NOT find these useful: [thumbs-down examples]. Generate discoveries that align with their preferences."

### Requirement 3: Did You Know — Feedback Learning

**User Story:** As an investigator, I want to give thumbs-up or thumbs-down feedback on each discovery so that the AI learns my investigative taste and generates more relevant discoveries over time.

#### Acceptance Criteria

1. THE Discovery_Card SHALL display a thumbs-up (👍) button and a thumbs-down (👎) button for each discovery.
2. WHEN the investigator clicks thumbs-up on a Discovery_Card, THE Investigator_View SHALL store a positive rating in the Feedback_Store with the discovery_id, case_id, user_id, rating value, discovery_type, content_hash, and created_at timestamp.
3. WHEN the investigator clicks thumbs-down on a Discovery_Card, THE Investigator_View SHALL store a negative rating in the Feedback_Store with the discovery_id, case_id, user_id, rating value, discovery_type, content_hash, and created_at timestamp.
4. WHEN the investigator has provided feedback and requests a new Batch, THE Discovery_Engine SHALL retrieve all feedback records for the case from the Feedback_Store and incorporate them into the Bedrock Claude generation prompt.

### Requirement 4: Did You Know — Drill-In Navigation

**User Story:** As an investigator, I want to drill into any discovery card to investigate the finding deeper using the existing investigation funnel so that I can follow up on interesting discoveries.

#### Acceptance Criteria

1. WHEN the investigator clicks on a Discovery_Card, THE Investigator_View SHALL open the Investigation_Drilldown for the primary entity or entities referenced in the discovery.
2. THE Discovery_Card SHALL provide a visible click target or action button that navigates to the Investigation_Drilldown.

### Requirement 5: Anomaly Radar — Statistical Anomaly Detection

**User Story:** As an investigator, I want to see structural pattern deviations detected by statistical algorithms so that I can identify temporal irregularities, network holes, frequency outliers, co-absence patterns, and volume anomalies in my case data.

#### Acceptance Criteria

1. WHEN an investigator opens the Discovery tab for a case, THE Anomaly_Detector SHALL compute anomalies across five dimensions: temporal, network, frequency, co-absence, and volume.
2. WHEN a temporal anomaly is detected, THE Anomaly_Detector SHALL identify statistically significant changes in document frequency over time periods (e.g., frequency drops or spikes between date ranges).
3. WHEN a network anomaly is detected, THE Anomaly_Detector SHALL identify structural holes where an entity connects to multiple separate clusters that have no connections to each other.
4. WHEN a frequency anomaly is detected, THE Anomaly_Detector SHALL identify terms or entities whose occurrence count deviates significantly from the expected distribution across a specific dimension (e.g., year, source, document type).
5. WHEN a co-absence anomaly is detected, THE Anomaly_Detector SHALL identify sets of entities that consistently co-occur except in documents from a specific source or time period.
6. WHEN a volume anomaly is detected, THE Anomaly_Detector SHALL identify cases where the ratio of entity types deviates significantly from the expected ratio for the case type.
7. THE Anomaly_Detector SHALL use statistical algorithms as the primary brain for detection and SHALL NOT use AI narrative generation for anomaly identification.

### Requirement 6: Anomaly Radar — Compact Card Display

**User Story:** As an investigator, I want anomaly findings displayed as compact statistical cards with visual indicators so that I can quickly scan structural deviations without reading lengthy narratives.

#### Acceptance Criteria

1. THE Anomaly_Card SHALL display the statistical finding as a concise factual statement without narrative framing or AI-generated prose.
2. THE Anomaly_Card SHALL include a Sparkline or mini-chart that visually represents the statistical trend or deviation.
3. THE Anomaly_Card SHALL include an "Investigate" button that opens the relevant entity drilldown or evidence library view.
4. THE Anomaly_Card SHALL NOT contain AI-generated narrative text, subjective language, or "Did you know" framing.

### Requirement 7: Anomaly Radar — Investigate Action

**User Story:** As an investigator, I want to click "Investigate" on any anomaly card to drill into the relevant entities or evidence so that I can follow up on detected structural deviations.

#### Acceptance Criteria

1. WHEN the investigator clicks "Investigate" on an Anomaly_Card, THE Investigator_View SHALL open the entity drilldown for the primary entity referenced in the anomaly OR open the evidence library filtered to the relevant documents.
2. THE Investigator_View SHALL determine the appropriate drill-in target based on the anomaly type: entity drilldown for network and co-absence anomalies, evidence library for temporal, frequency, and volume anomalies.

### Requirement 8: Zero Overlap Rule

**User Story:** As an investigator, I want the two discovery lenses to have clearly separated responsibilities so that I receive narrative insights from AI and statistical findings from algorithms without confusion or duplication.

#### Acceptance Criteria

1. THE Discovery_Card SHALL use Bedrock Claude as the primary brain for content generation and SHALL present findings as narrative, subjective, surprise-based statements.
2. THE Anomaly_Card SHALL use statistical algorithms as the primary brain for content generation and SHALL present findings as factual statistical deviations.
3. THE Discovery_Engine SHALL NOT produce output that contains raw statistical values, deviation percentages, or algorithmic metrics as the primary content of a discovery.
4. THE Anomaly_Detector SHALL NOT produce output that contains AI-generated narrative prose, subjective assessments, or "Did you know" framing.

### Requirement 9: UI Layout — Tab Replacement

**User Story:** As an investigator, I want the Discovery Engine to replace the current Patterns tab and Patterns sub-panel so that I access the new two-lens experience from the same navigation locations.

#### Acceptance Criteria

1. THE Investigator_View SHALL replace the existing Patterns tab in the main tab bar with a Discovery tab that renders the two-lens layout.
2. THE Investigator_View SHALL replace the existing Patterns sub-panel in the Research Hub tab with the Discovery two-lens layout.
3. THE Investigator_View SHALL render the "Did You Know" section at the top of the Discovery layout displaying Discovery_Cards with feedback controls and a "Show me 5 more" button.
4. THE Investigator_View SHALL render the "Anomaly Radar" section at the bottom of the Discovery layout displaying Anomaly_Cards with Sparklines and "Investigate" buttons.

### Requirement 10: Save to Case Findings

**User Story:** As an investigator, I want to save any discovery or anomaly to my case findings so that I can preserve important findings for my investigation record.

#### Acceptance Criteria

1. WHEN the investigator chooses to save a Discovery_Card to case findings, THE Investigator_View SHALL call the existing FindingsService to persist the discovery narrative, associated entity names, and discovery metadata.
2. WHEN the investigator chooses to save an Anomaly_Card to case findings, THE Investigator_View SHALL call the existing FindingsService to persist the anomaly description, statistical data, and associated entity names.

### Requirement 11: Backend Data Storage

**User Story:** As a system operator, I want discovery feedback and history stored in Aurora PostgreSQL so that the system can learn from investigator preferences and avoid regenerating seen discoveries.

#### Acceptance Criteria

1. THE Discovery_Engine SHALL store feedback records in the Feedback_Store table with columns: discovery_id, case_id, user_id, rating, discovery_type, content_hash, and created_at.
2. THE Discovery_Engine SHALL store discovery history records in the Discovery_History table with columns: discovery_id, case_id, batch_number, and discoveries (JSONB).
3. WHEN the Discovery_Engine generates a new Batch, THE Discovery_Engine SHALL query the Discovery_History table to retrieve all previously generated discovery IDs for the case and exclude them from the new generation.

### Requirement 12: Existing Service Reuse

**User Story:** As a developer, I want the Discovery Engine to reuse existing backend services so that the implementation leverages proven infrastructure and avoids duplication.

#### Acceptance Criteria

1. THE Anomaly_Detector SHALL reuse graph query methods from PatternDiscoveryService (src/services/pattern_discovery_service.py) for retrieving entity relationships, centrality data, and co-occurrence patterns needed for anomaly detection.
2. THE Discovery_Engine SHALL follow the narrative generation approach established by LeadGeneratorService (src/services/lead_generator_service.py) for structuring Bedrock Claude prompts with gathered context and parsing structured JSON responses.
3. THE Discovery_Engine SHALL use entity neighborhood intelligence from InvestigatorAIEngine (src/services/investigator_ai_engine.py) for gathering comprehensive entity context including graph neighborhood, document mentions, and relationship data.
4. WHEN saving discoveries or anomalies to case findings, THE Investigator_View SHALL use the existing FindingsService for persistence.
5. WHEN drilling into a discovery or anomaly, THE Investigator_View SHALL use the existing Investigation_Drilldown (investigative-findings-drilldown) for the drill-deeper flow.

### Requirement 13: Error Handling

**User Story:** As an investigator, I want graceful error handling when AI generation or anomaly detection fails so that I can still use the available lens and retry failed operations.

#### Acceptance Criteria

1. IF Bedrock Claude invocation fails during discovery generation, THEN THE Discovery_Engine SHALL return a fallback set of discoveries generated from graph statistics with narrative framing, and THE Investigator_View SHALL display a warning banner indicating AI-generated discoveries are temporarily unavailable.
2. IF the Anomaly_Detector encounters a database or graph query failure, THEN THE Anomaly_Detector SHALL return partial results for the anomaly dimensions that succeeded and THE Investigator_View SHALL display the available anomalies with an indicator showing which dimensions could not be computed.
3. IF no discoveries or anomalies are found for a case, THEN THE Investigator_View SHALL display an appropriate empty state message for each section rather than showing a blank area.

### Requirement 14: Model Provider Exclusion

**User Story:** As a customer administrator, I want to permanently exclude specific model providers (e.g., Anthropic) from the model selector so that investigators cannot accidentally select models from providers that are not approved for use in our environment.

#### Acceptance Criteria

1. THE model registry configuration SHALL support an `excluded_providers` list that removes all models from specified providers from the model selector dropdown.
2. WHEN a provider is listed in `excluded_providers`, THE Investigator_View SHALL NOT display any models from that provider in the model selector dropdown.
3. WHEN a provider is excluded and the current default model belongs to that provider, THE Discovery_Engine SHALL automatically fall back to the next available model from a non-excluded provider.
4. THE `excluded_providers` configuration SHALL be stored in the model registry config file (`config/bedrock_models.json`) so that it can be set at deployment time without code changes.
