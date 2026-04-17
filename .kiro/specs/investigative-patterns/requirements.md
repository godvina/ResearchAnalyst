# Requirements Document

## Introduction

The "Top 5 Investigative Patterns" feature is the key demo differentiator for the investigative intelligence platform. It combines multi-modal intelligence — text entities from document extraction, visual labels from Rekognition, face matches from watchlist comparison, and document co-occurrence from Neptune graph traversal — into a prioritized list of 5 investigative questions. Each question is ranked by probability of leading to actionable evidence. The UI provides a progressive disclosure interaction: click a pattern to see a summary, click again to see detailed evidence with source documents and images. This feature extends the existing `pattern_discovery_service.py`, `patterns.py` API handler, and `investigator.html` frontend.

## Glossary

- **Pattern_Engine**: The backend service that queries Neptune graph data (text entities, visual entities, face crops, co-occurrence edges) and Aurora document data, then uses Bedrock Claude to synthesize multi-modal evidence into ranked investigative questions. Extends `pattern_discovery_service.py`.
- **Patterns_API**: The Lambda API handler that serves Top 5 pattern requests and detail drill-downs. Extends `src/lambdas/api/patterns.py`.
- **Investigator_UI**: The single-page HTML frontend (`src/frontend/investigator.html`) that renders the Top 5 patterns panel with progressive disclosure interaction.
- **Neptune_Graph**: The Amazon Neptune graph database containing Entity, VisualEntity, FaceCrop, and Document nodes with RELATED_TO, DETECTED_IN, CO_OCCURS_WITH, FACE_DETECTED_IN, and HAS_FACE_MATCH edges.
- **Multi_Modal_Evidence**: The combination of text-extracted entities (persons, organizations, locations, dates), Rekognition visual labels (34 entity types), face match results (8 matched entity faces), and document co-occurrence relationships.
- **Pattern_Question**: A single investigative question posed as a natural-language question, ranked by priority, with a summary and detailed evidence breakdown.
- **Evidence_Bundle**: The collection of source documents, images, face crops, entity connections, and co-occurrence data that supports a specific Pattern_Question.

## Requirements

### Requirement 1: Multi-Modal Pattern Discovery

**User Story:** As an investigator, I want the system to combine text entities, visual labels, face matches, and document co-occurrence into ranked investigative questions, so that I can focus on the most promising leads across all evidence types.

#### Acceptance Criteria

1. WHEN an investigator requests Top 5 patterns for a case, THE Pattern_Engine SHALL query Neptune_Graph for text entities (RELATED_TO edges), visual entities (DETECTED_IN edges), face matches (HAS_FACE_MATCH edges), and document co-occurrence (CO_OCCURS_WITH edges) for the specified case.
2. THE Pattern_Engine SHALL combine text entity graph centrality, visual entity co-occurrence frequency, face match connections, and document semantic similarity into a unified scoring model.
3. THE Pattern_Engine SHALL rank discovered patterns by a composite score combining evidence strength (number of supporting sources), cross-modal corroboration (pattern supported by 2+ evidence types), and investigative novelty (unexpected connections).
4. THE Pattern_Engine SHALL return exactly 5 Pattern_Questions, each numbered 1-5 by priority.
5. IF fewer than 5 distinct patterns are discoverable, THEN THE Pattern_Engine SHALL return the available patterns with an explanation that fewer patterns were found.

### Requirement 2: AI-Synthesized Investigative Questions

**User Story:** As an investigator, I want each pattern presented as a natural-language investigative question, so that I can immediately understand what to investigate next.

#### Acceptance Criteria

1. WHEN the Pattern_Engine has ranked the top patterns, THE Pattern_Engine SHALL call Bedrock Claude to synthesize each pattern into a natural-language investigative question.
2. THE Pattern_Engine SHALL provide Bedrock Claude with the multi-modal evidence context: entity names, entity types, visual labels, face match identities, co-occurring documents, and relationship types.
3. WHEN Bedrock Claude returns the synthesized questions, THE Pattern_Engine SHALL include a confidence percentage (0-100) and a list of evidence modalities (text, visual, face, document) that support each question.
4. IF Bedrock Claude is unavailable, THEN THE Pattern_Engine SHALL generate a fallback question using a template: "Investigate the connection between [Entity A] and [Entity B] found in [N] documents with [modalities] evidence."

### Requirement 3: Pattern Summary (First Click)

**User Story:** As an investigator, I want to click a pattern question and see a concise summary of the supporting evidence, so that I can quickly assess whether to investigate further.

#### Acceptance Criteria

1. WHEN an investigator clicks a Pattern_Question in the Investigator_UI, THE Investigator_UI SHALL expand an inline summary panel below the question.
2. THE summary panel SHALL display: the AI-generated explanation (2-3 sentences), the number of supporting documents, the number of supporting images, the evidence modalities involved, and the confidence score.
3. THE Investigator_UI SHALL render the summary within 200ms of the click using data already fetched in the initial Top 5 response (no additional API call for summary).
4. WHEN the investigator clicks the same Pattern_Question again while the summary is visible, THE Investigator_UI SHALL expand to show the detailed Evidence_Bundle view (Requirement 4).

### Requirement 4: Detailed Evidence Bundle (Second Click)

**User Story:** As an investigator, I want to drill into a pattern and see the actual source documents, images, face crops, and entity connections, so that I can verify the evidence and build my case.

#### Acceptance Criteria

1. WHEN an investigator clicks an expanded Pattern_Question summary, THE Investigator_UI SHALL call the Patterns_API to fetch the detailed Evidence_Bundle.
2. THE Patterns_API SHALL return the Evidence_Bundle containing: source document excerpts with document IDs, presigned S3 URLs for supporting images, presigned S3 URLs for face crop thumbnails with matched entity names, entity connection paths from Neptune_Graph, and co-occurring visual labels.
3. THE Investigator_UI SHALL display source documents as clickable cards showing filename, excerpt (first 200 characters), and a download link.
4. THE Investigator_UI SHALL display supporting images as a thumbnail gallery with visual labels overlaid.
5. THE Investigator_UI SHALL display face crops with the matched entity name below each thumbnail.
6. IF the Evidence_Bundle API call takes longer than 10 seconds, THEN THE Investigator_UI SHALL display a loading indicator with the message "Gathering evidence..."

### Requirement 5: Progressive Disclosure Interaction

**User Story:** As an investigator, I want the Top 5 patterns panel to use progressive disclosure (collapsed → summary → detail), so that I can scan quickly and drill in only where needed.

#### Acceptance Criteria

1. THE Investigator_UI SHALL display the Top 5 patterns in a numbered list, with each Pattern_Question initially in collapsed state showing only the question text, confidence badge, and evidence modality icons.
2. WHEN an investigator clicks a collapsed Pattern_Question, THE Investigator_UI SHALL transition the question to summary state with a slide-down animation.
3. WHEN an investigator clicks a summary-state Pattern_Question, THE Investigator_UI SHALL transition to detail state, fetching the Evidence_Bundle if not already cached.
4. WHEN an investigator clicks a detail-state Pattern_Question, THE Investigator_UI SHALL collapse the question back to the initial collapsed state.
5. THE Investigator_UI SHALL allow only one Pattern_Question to be in detail state at a time; expanding a new question to detail state SHALL collapse any previously expanded detail.

### Requirement 6: Cross-Modal Corroboration Indicators

**User Story:** As an investigator, I want to see which evidence types corroborate each pattern, so that I can prioritize patterns with the strongest multi-modal support.

#### Acceptance Criteria

1. THE Investigator_UI SHALL display evidence modality icons next to each Pattern_Question: a document icon for text entity evidence, a camera icon for visual label evidence, a face icon for face match evidence, and a link icon for co-occurrence evidence.
2. WHEN a pattern is supported by 3 or more evidence modalities, THE Investigator_UI SHALL display a "Strong Corroboration" badge in a distinct color.
3. WHEN a pattern is supported by only 1 evidence modality, THE Investigator_UI SHALL display a "Single Source" indicator to signal lower confidence.

### Requirement 7: API Endpoint for Top 5 Patterns

**User Story:** As a frontend developer, I want a dedicated API endpoint for Top 5 investigative patterns, so that the Investigator_UI can fetch patterns without conflicting with existing pattern discovery endpoints.

#### Acceptance Criteria

1. WHEN a GET request is made to `/case-files/{id}/top-patterns`, THE Patterns_API SHALL return the Top 5 Pattern_Questions with summaries.
2. WHEN a GET request is made to `/case-files/{id}/top-patterns/{pattern_index}/evidence`, THE Patterns_API SHALL return the detailed Evidence_Bundle for the specified pattern.
3. THE Patterns_API SHALL cache the Top 5 results in Aurora for 15 minutes to avoid redundant Neptune and Bedrock calls.
4. IF the cache is stale or missing, THEN THE Patterns_API SHALL regenerate the Top 5 patterns and update the cache.
5. THE Patterns_API SHALL complete the Top 5 generation within 25 seconds to stay within API Gateway's 29-second timeout (per lessons-learned Issue 1).

### Requirement 8: Integration with Existing Investigator Page

**User Story:** As an investigator, I want the Top 5 patterns panel to appear on the existing investigator page alongside the entity graph, image gallery, and chat, so that I have a unified investigation workspace.

#### Acceptance Criteria

1. THE Investigator_UI SHALL render the Top 5 patterns panel as a new section in the existing investigator.html page, positioned above the entity graph section.
2. WHEN a case is selected in the Investigator_UI, THE Investigator_UI SHALL automatically fetch and display the Top 5 patterns for that case.
3. WHEN an entity name appears in a Pattern_Question, THE Investigator_UI SHALL render the entity name as a clickable link that scrolls to and highlights the entity in the existing entity graph.
4. WHEN a source document appears in an Evidence_Bundle, THE Investigator_UI SHALL render the document as a clickable link that opens the existing document download flow.
