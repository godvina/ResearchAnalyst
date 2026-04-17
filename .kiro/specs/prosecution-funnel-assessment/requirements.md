# Requirements Document

## Introduction

This feature introduces a three-tier investigative assessment system modeled after professional prosecution tools (Palantir Gotham, Relativity, i2 Analyst's Notebook, DOJ USAM workflow). It addresses four core problems: duplicate findings in the Research Notebook, lack of per-entity prosecution evaluation, disconnected case strength scoring, and ephemeral graph insights. The system adds Entity Dossier singletons, Subject Assessment with DOJ prosecution funnel dispositions, case strength rollup from subject assessments, and persistent graph insight capture — all stored in localStorage as a first pass with API persistence planned for a later phase.

## Glossary

- **Dossier_Manager**: The frontend JavaScript module responsible for creating, retrieving, and updating Entity Dossier singleton records in localStorage, keyed by normalized entity name per case.
- **Subject_Assessor**: The frontend JavaScript module responsible for managing per-entity prosecution evaluation state including role assignment, disposition lifecycle, evidence strength scoring, and analyst notes.
- **Scorecard_Engine**: The existing `computeCaseStrengthScorecard()` function enhanced to incorporate subject assessment data into its 6-dimension scoring model.
- **Graph_Insight_Recorder**: The frontend JavaScript module responsible for capturing, persisting, and displaying analyst observations from knowledge graph node interactions.
- **Entity_Dossier**: A singleton record per entity per case containing the entity's profile, chronological activity log, graph insights, evidence links, and subject assessment state.
- **Subject_Assessment**: A per-entity prosecution evaluation record containing role, disposition, evidence strength score, and analyst notes following the DOJ prosecution funnel model.
- **Disposition**: The lifecycle state of a subject's prosecution evaluation: Unassessed, Investigating, Assessed, or a terminal state (Target, Subject, Cooperator, Witness, Victim, Cleared, Declined).
- **Activity_Log**: A chronological, timestamped list of notes and events appended to an Entity Dossier, sourced from manual analyst input, search findings, graph insights, and lead assessments.
- **Graph_Insight**: A saved analyst observation from a knowledge graph node interaction, including the entity name, connection count, connected entity snapshot, freeform note, and timestamp.
- **Research_Notebook**: The existing dashboard section (`research-notebook`) that displays saved investigation findings, to be enhanced to show deduplicated Entity Dossier views.
- **Tracked_Entity**: An entity pinned by the analyst via the 📌 Track button, stored in `_trackedEntities` array in localStorage per case.
- **Evidence_Strength_Score**: A computed 0-100 score per entity based on document mentions, graph connections, corroborating findings, and timeline presence.

## Requirements

### Requirement 1: Entity Dossier Singleton Storage

**User Story:** As an investigator, I want one dossier per entity so that I see a consolidated view of all intelligence about an entity instead of duplicate flat finding entries.

#### Acceptance Criteria

1. WHEN a finding is saved for an entity name that already has an Entity_Dossier in localStorage, THE Dossier_Manager SHALL append the finding to the existing Entity_Dossier's Activity_Log instead of creating a new record.
2. WHEN a finding is saved for an entity name that does not have an Entity_Dossier in localStorage, THE Dossier_Manager SHALL create a new Entity_Dossier keyed by the normalized (lowercased, trimmed) entity name.
3. THE Dossier_Manager SHALL store Entity_Dossier records in localStorage under the key `entityDossiers_{caseId}` as a JSON object keyed by normalized entity name.
4. THE Dossier_Manager SHALL include in each Entity_Dossier: entity name, entity type, role, disposition, Activity_Log (array of timestamped entries), graph insights (array), evidence links (array), evidence strength score, and last-updated timestamp.
5. WHEN the Research_Notebook section loads, THE Research_Notebook SHALL render deduplicated Entity_Dossier cards grouped by entity instead of a flat list of individual findings.
6. WHEN an Entity_Dossier card is clicked in the Research_Notebook, THE Research_Notebook SHALL expand the card to show the full chronological Activity_Log, graph insights, and evidence links for that entity.
7. IF localStorage for `entityDossiers_{caseId}` is corrupted or unparseable, THEN THE Dossier_Manager SHALL initialize an empty dossier store and log a warning to the browser console.

### Requirement 2: Subject Assessment Panel

**User Story:** As an investigator, I want to evaluate each tracked entity individually following the DOJ prosecution funnel so that I can assign roles, track dispositions, and score evidence strength per subject.

#### Acceptance Criteria

1. THE Subject_Assessor SHALL provide a Subject Assessment panel accessible from three entry points: Entity Dossier drill-down, Lead Investigation tab entity cards, and tracked entity bar badge click.
2. THE Subject_Assessor SHALL allow the analyst to assign one role per entity from the set: Target, Subject, Cooperator, Witness, Victim, Cleared, Declined.
3. THE Subject_Assessor SHALL track each entity through a disposition lifecycle: Unassessed → Investigating → Assessed → terminal disposition (Target, Subject, Cooperator, Witness, Victim, Cleared, Declined).
4. THE Subject_Assessor SHALL compute an Evidence_Strength_Score (0-100) per entity based on: document count mentioning the entity (weight 0.30), graph connection count (weight 0.25), corroborating finding count (weight 0.25), and timeline event presence (weight 0.20).
5. THE Subject_Assessor SHALL provide a freeform notes textarea whose contents append to the entity's Entity_Dossier Activity_Log with source tagged as "assessment".
6. THE Subject_Assessor SHALL store all subject assessment state in localStorage under the key `subjectAssessments_{caseId}` as a JSON object keyed by normalized entity name.
7. WHEN the analyst changes a role or disposition, THE Subject_Assessor SHALL update the Entity_Dossier and append a timestamped Activity_Log entry recording the change.
8. THE Subject_Assessor SHALL display the current role as a color-coded badge (Target=red, Subject=orange, Cooperator=blue, Witness=teal, Victim=purple, Cleared=green, Declined=gray) and the disposition as a lifecycle progress indicator.

### Requirement 3: Case Strength Rollup from Subject Assessments

**User Story:** As an investigator, I want the Case Strength Scorecard to reflect my subject assessments so that the overall case viability score accounts for who has been identified, assessed, and what their dispositions are.

#### Acceptance Criteria

1. THE Scorecard_Engine SHALL compute the "Subject Identification" dimension score using: proportion of tracked entities that have been assessed (weight 0.50) and proportion of assessed entities with Target or Subject disposition (weight 0.50).
2. THE Scorecard_Engine SHALL add a "Prosecution Readiness" sub-score computed from: count of entities with Target disposition having Evidence_Strength_Score above 60 (weight 0.40), count of entities with Cooperator disposition (weight 0.30), and absence of all primary targets being Cleared or Declined (weight 0.30).
3. WHEN all tracked entities with Target disposition have been changed to Cleared or Declined, THE Scorecard_Engine SHALL reduce the overall case strength score by a penalty factor of 0.40.
4. THE Scorecard_Engine SHALL render a "Subject Summary" table within the scorecard showing each tracked entity's name, type, assigned role, current disposition, and individual Evidence_Strength_Score.
5. THE Scorecard_Engine SHALL display the Prosecution Readiness sub-score as a separate labeled bar alongside the existing 6 dimension bars, with color coding: green (above 70), yellow (40-70), red (below 40).

### Requirement 4: Graph Insight Persistence

**User Story:** As an investigator, I want to save observations from the knowledge graph so that graph-derived intelligence is captured in the entity's dossier and visible on the graph itself.

#### Acceptance Criteria

1. WHEN an entity node is clicked in the knowledge graph and the drill-down panel opens, THE Graph_Insight_Recorder SHALL display a "💡 Save Graph Insight" button in the drill-down panel.
2. WHEN the analyst clicks "💡 Save Graph Insight", THE Graph_Insight_Recorder SHALL present a freeform text input for the analyst's observation note.
3. WHEN the analyst submits a graph insight, THE Graph_Insight_Recorder SHALL save the insight to the entity's Entity_Dossier including: entity name, connection count at capture time, list of connected entity names at capture time, analyst's freeform note, and ISO 8601 timestamp.
4. THE Graph_Insight_Recorder SHALL persist graph insights within the Entity_Dossier's `graphInsights` array in localStorage.
5. WHEN the knowledge graph renders, THE Graph_Insight_Recorder SHALL display a 💡 indicator on nodes that have at least one saved Graph_Insight in their Entity_Dossier.
6. WHEN an entity node with a 💡 indicator is clicked, THE Graph_Insight_Recorder SHALL show previously saved insights in the drill-down panel below the AI analysis section, ordered by timestamp descending.
7. THE Graph_Insight_Recorder SHALL keep the full graph visible with the clicked entity highlighted in-place rather than rendering a separate ego graph.

### Requirement 5: Entity Dossier Data Model

**User Story:** As an investigator, I want a consistent data structure for entity intelligence so that all modules (dossier, assessment, graph insights, scorecard) operate on the same underlying record.

#### Acceptance Criteria

1. THE Dossier_Manager SHALL structure each Entity_Dossier record as a JSON object containing: `entityName` (string), `entityType` (string), `role` (string, default "unassigned"), `disposition` (string, default "unassessed"), `evidenceStrength` (number 0-100, default 0), `notes` (array of `{text, timestamp, source}` objects), `graphInsights` (array of `{note, connections, connectedEntities, timestamp}` objects), `evidenceLinks` (array of `{documentId, title, relevanceScore}` objects), and `lastUpdated` (ISO 8601 string).
2. THE Dossier_Manager SHALL normalize entity name keys by lowercasing and trimming whitespace before storage and lookup.
3. THE Dossier_Manager SHALL serialize the Entity_Dossier to JSON for localStorage and deserialize on read, preserving all nested arrays and objects.
4. FOR ALL valid Entity_Dossier objects, serializing to JSON then deserializing SHALL produce an equivalent object (round-trip property).
5. WHEN an Entity_Dossier field is updated by any module (Subject_Assessor, Graph_Insight_Recorder, Research_Notebook), THE Dossier_Manager SHALL update the `lastUpdated` timestamp to the current ISO 8601 time.

### Requirement 6: Research Notebook Dossier View

**User Story:** As an investigator, I want the Research Notebook to show entity dossiers instead of duplicate findings so that I have a clean, organized view of my investigation intelligence per entity.

#### Acceptance Criteria

1. WHEN the Research_Notebook section loads, THE Research_Notebook SHALL display Entity_Dossier cards sorted by `lastUpdated` descending, each showing: entity name, type badge, role badge, disposition indicator, evidence strength bar, Activity_Log entry count, and graph insight count.
2. WHEN an Entity_Dossier card is expanded, THE Research_Notebook SHALL show the full Activity_Log in reverse chronological order with each entry displaying its text, timestamp, and source tag (search, assessment, graph, manual).
3. THE Research_Notebook SHALL continue to display the existing freeform "Add Investigation Note" form, and WHEN a note is saved with entity tags, THE Dossier_Manager SHALL append the note to each tagged entity's Activity_Log.
4. THE Research_Notebook SHALL show a summary header with: total dossier count, count by disposition category, and count of entities with Evidence_Strength_Score above 60.
5. WHEN the Research_Notebook has both Entity_Dossier records in localStorage and findings from the API, THE Research_Notebook SHALL merge API findings into the appropriate Entity_Dossier Activity_Logs by matching entity names, without creating duplicate Activity_Log entries.
