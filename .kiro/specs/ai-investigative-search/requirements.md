# Requirements Document

## Introduction

AI Investigative Search transforms the existing raw-document-chunk search into an intelligence-grade investigative search engine. Instead of returning a list of matching text snippets, the system synthesizes an AI-generated intelligence brief that combines OpenSearch semantic results, Neptune graph entity relationships, Aurora metadata, and Bedrock AI analysis into a single structured assessment. The feature supports natural language investigative queries ("what was the relationship between Branson and Epstein"), entity-based client list extraction, optional external research cross-referencing, and inbound lead deep-dive from external systems. Every search produces a structured Investigative Assessment with evidence citations, graph connections, gap analysis, and a confidence rating.

## Glossary

- **Investigative_Search_Engine**: The backend orchestration service that receives an investigative query, fans out to multiple data sources (OpenSearch, Neptune, Aurora, Bedrock), and synthesizes results into a structured Investigative Assessment.
- **Intelligence_Brief**: The AI-synthesized output of an investigative search, containing evidence excerpts, entity relationships, significance analysis, evidence gaps, and recommended next steps.
- **Investigative_Assessment**: The structured JSON output produced for every search, containing sections for internal evidence, graph connections, AI analysis, gaps, next steps, and confidence level.
- **Search_Scope**: A user-selected mode controlling which data sources are queried: "internal" (OpenSearch + Neptune + Aurora only) or "internal+external" (adds Bedrock-generated external research).
- **Entity_Extraction_Pass**: An AI step that identifies person, organization, location, and event entities mentioned in search results and maps them to Neptune graph nodes.
- **Lead_JSON**: A structured JSON payload received from an external system containing subject names, identifiers, OSINT directives, and evidence hints for deep-dive assessment.
- **Confidence_Level**: A three-tier rating assigned to each Investigative Assessment: "strong_case", "needs_more_evidence", or "insufficient".
- **Evidence_Citation**: A reference linking an assertion in the Intelligence Brief back to a specific document chunk, including document ID, filename, page number, and relevance score.
- **Graph_Connection**: A relationship edge retrieved from Neptune between two entities, including relationship type, properties, and the documents that established the connection.
- **Cross_Reference_Report**: A section of the Investigative Assessment that compares internal evidence against external research findings, categorizing each finding as "confirmed_internally", "external_only", or "needs_research".

## Requirements

### Requirement 1: AI-Synthesized Search Response

**User Story:** As an investigator, I want my search queries to return an AI-synthesized intelligence brief instead of raw document chunks, so that I can immediately understand the investigative significance of the results.

#### Acceptance Criteria

1. WHEN an investigator submits a natural language query via the search endpoint, THE Investigative_Search_Engine SHALL query OpenSearch for semantically relevant document chunks, query Neptune for entity relationships matching extracted entities, and query Aurora for document metadata.
2. WHEN all data source results are collected, THE Investigative_Search_Engine SHALL pass the combined context to Bedrock Claude to generate an Intelligence_Brief that synthesizes findings across all sources.
3. THE Intelligence_Brief SHALL contain the following sections: executive summary, evidence excerpts with Evidence_Citations, entity relationships from the graph, AI significance analysis, and source attribution for every claim.
4. WHEN the query matches zero documents in OpenSearch, THE Investigative_Search_Engine SHALL still query Neptune for entity matches and return an Intelligence_Brief noting the absence of document evidence while presenting any graph-based findings.
5. THE Investigative_Search_Engine SHALL return the raw search results alongside the Intelligence_Brief so the investigator can verify AI assertions against source material.
6. WHEN Bedrock synthesis fails or times out, THE Investigative_Search_Engine SHALL return the raw search results and graph connections without the AI synthesis, along with an error indicator explaining the synthesis failure.

### Requirement 2: Natural Language Investigative Queries

**User Story:** As an investigator, I want to ask relationship-based questions like "what was the relationship between Branson and Epstein" and get a structured answer, so that I can quickly understand connections between entities.

#### Acceptance Criteria

1. WHEN a query contains two or more entity names, THE Investigative_Search_Engine SHALL extract those entities, query Neptune for direct and indirect paths between them (up to 3 hops), and include the relationship paths in the Bedrock synthesis context.
2. WHEN a query asks about a single entity (e.g., "Richard Branson"), THE Investigative_Search_Engine SHALL retrieve the entity's full Neptune neighborhood (up to 2 hops), all document mentions, and produce a comprehensive entity profile in the Intelligence_Brief.
3. THE Entity_Extraction_Pass SHALL use Bedrock Claude to identify entity names in the query before graph lookup, handling aliases, partial names, and misspellings by fuzzy-matching against known Neptune entity labels.
4. WHEN no matching entities are found in Neptune, THE Investigative_Search_Engine SHALL fall back to document-only search and note in the Intelligence_Brief that no graph entities matched the query.

### Requirement 3: Entity List Extraction and Cross-Referencing

**User Story:** As an investigator, I want to ask questions like "produce a possible client list of Epstein based on data in the files" and receive a structured entity list with evidence citations, so that I can identify persons of interest systematically.

#### Acceptance Criteria

1. WHEN a query requests an entity list (e.g., "list all people connected to X"), THE Investigative_Search_Engine SHALL search documents for person entity mentions co-occurring with the target entity, query Neptune for all person nodes connected to the target entity, and merge both result sets.
2. THE Investigative_Search_Engine SHALL present the merged entity list as a structured table containing: entity name, relationship type, number of document mentions, document citations, and graph connection path.
3. WHEN duplicate entities appear across document extraction and graph results, THE Investigative_Search_Engine SHALL merge them into a single entry, combining evidence from both sources.
4. THE Investigative_Search_Engine SHALL rank entities in the list by a relevance score computed from the number of document mentions, graph connection strength (hop distance), and co-occurrence frequency.

### Requirement 4: Search Scope Selection

**User Story:** As an investigator, I want to choose between "internal files only" and "internal + external sources" search modes, so that I can control whether external research is included in my assessment.

#### Acceptance Criteria

1. THE Investigative_Search_Engine SHALL accept a Search_Scope parameter with values "internal" or "internal_external" on every search request, defaulting to "internal".
2. WHEN Search_Scope is "internal", THE Investigative_Search_Engine SHALL query only OpenSearch, Neptune, and Aurora, and produce the Intelligence_Brief from internal evidence alone.
3. WHEN Search_Scope is "internal_external", THE Investigative_Search_Engine SHALL first produce the internal Intelligence_Brief, then invoke the AI_Research_Agent to generate external research for each key entity identified, and append a Cross_Reference_Report to the assessment.
4. THE Cross_Reference_Report SHALL categorize each finding as "confirmed_internally" (evidence exists in internal files), "external_only" (found only in external research), or "needs_research" (mentioned but unverified).
5. WHEN the AI_Research_Agent fails to produce external research for a subject, THE Investigative_Search_Engine SHALL include the internal-only assessment and note the external research failure for that subject.

### Requirement 5: Lead Intake Deep-Dive Assessment

**User Story:** As an investigator, I want to submit a lead in JSON format from an external system and receive a comprehensive deep-dive assessment across all data sources, so that I can quickly determine whether we have a viable case.

#### Acceptance Criteria

1. WHEN a Lead_JSON payload is submitted to the lead assessment endpoint, THE Investigative_Search_Engine SHALL validate the payload structure, extract all subjects, and run an investigative search for each subject against internal and external sources.
2. THE Investigative_Search_Engine SHALL produce a consolidated Investigative_Assessment that covers all subjects in the lead, cross-referencing connections between subjects found in internal evidence.
3. WHEN the Lead_JSON contains OSINT directives, THE Investigative_Search_Engine SHALL pass those directives to the AI_Research_Agent for targeted external research on each subject.
4. WHEN the Lead_JSON contains evidence hints with URLs, THE Investigative_Search_Engine SHALL reference those hints in the Bedrock synthesis prompt so the AI can incorporate them into the assessment narrative.
5. IF the Lead_JSON payload fails validation, THEN THE Investigative_Search_Engine SHALL return a structured error response listing each validation failure with the field path and expected format.

### Requirement 6: Structured Investigative Assessment Output

**User Story:** As an investigator, I want every search to produce a structured assessment with evidence, graph connections, analysis, gaps, next steps, and confidence level, so that I have a consistent format for evaluating investigative findings.

#### Acceptance Criteria

1. THE Investigative_Assessment SHALL contain the following sections: "internal_evidence" (document excerpts with Evidence_Citations), "graph_connections" (entity relationships as Graph_Connections), "ai_analysis" (Bedrock-generated significance narrative), "evidence_gaps" (list of missing evidence areas with suggested actions), "recommended_next_steps" (prioritized list of investigative actions), and "confidence_level" (one of "strong_case", "needs_more_evidence", or "insufficient").
2. WHEN the Investigative_Assessment is generated, THE Investigative_Search_Engine SHALL assign a Confidence_Level based on: "strong_case" when corroborating evidence exists across multiple documents and graph connections confirm relationships; "needs_more_evidence" when partial evidence exists but key connections are unverified; "insufficient" when fewer than two document sources mention the query subject.
3. THE "internal_evidence" section SHALL include for each cited document: the document ID, source filename, page number or chunk index, the relevant text excerpt, and the semantic similarity score.
4. THE "evidence_gaps" section SHALL identify specific missing evidence areas and include actionable suggestions (e.g., "Request financial records for entity X for the period 2015-2018").
5. THE "recommended_next_steps" section SHALL list investigative actions ranked by priority, each with a brief rationale derived from the evidence analysis.

### Requirement 7: Search UI Intelligence Brief Display

**User Story:** As an investigator, I want the search section of the investigator UI to display the Intelligence Brief in a readable, structured format alongside the raw results, so that I can review both the AI synthesis and the source material.

#### Acceptance Criteria

1. WHEN search results are returned with an Intelligence_Brief, THE investigator UI SHALL display the Intelligence_Brief in a collapsible panel above the raw search results.
2. THE investigator UI SHALL render each section of the Investigative_Assessment (evidence, graph connections, analysis, gaps, next steps, confidence) as a distinct visual block with appropriate icons and formatting.
3. THE investigator UI SHALL display the Confidence_Level as a color-coded badge: green for "strong_case", amber for "needs_more_evidence", red for "insufficient".
4. THE investigator UI SHALL provide a Search_Scope toggle allowing the investigator to switch between "Internal Only" and "Internal + External" modes before executing a search.
5. WHEN an Evidence_Citation is displayed, THE investigator UI SHALL make the citation clickable, navigating the investigator to the source document or highlighting the relevant excerpt.
6. WHEN the Intelligence_Brief is absent due to synthesis failure, THE investigator UI SHALL display a warning banner explaining the failure and show the raw results below.

### Requirement 8: Investigative Search API Endpoint

**User Story:** As a developer, I want a dedicated API endpoint for investigative search that is backward-compatible with the existing search endpoint, so that the new intelligence features can be adopted incrementally.

#### Acceptance Criteria

1. THE Investigative_Search_Engine SHALL expose a new endpoint POST /case-files/{id}/investigative-search that accepts a JSON body with fields: "query" (string, required), "search_scope" (string, optional, default "internal"), "top_k" (integer, optional, default 10), and "output_format" (string, optional, "full" or "brief", default "full").
2. WHEN "output_format" is "full", THE endpoint SHALL return the complete Investigative_Assessment with all sections.
3. WHEN "output_format" is "brief", THE endpoint SHALL return only the executive summary, confidence level, and top 3 evidence citations for faster response.
4. THE existing POST /case-files/{id}/search endpoint SHALL continue to function unchanged, returning raw search results without AI synthesis.
5. IF the case file ID does not exist, THEN THE endpoint SHALL return a 404 error with a descriptive message.
6. IF the query parameter is missing or empty, THEN THE endpoint SHALL return a 400 validation error.

### Requirement 9: Lead Assessment API Endpoint

**User Story:** As a developer integrating external systems, I want a dedicated endpoint for submitting leads for deep-dive assessment, so that external case management systems can trigger investigative analysis programmatically.

#### Acceptance Criteria

1. THE Investigative_Search_Engine SHALL expose a new endpoint POST /case-files/{id}/lead-assessment that accepts a Lead_JSON payload containing: "lead_id" (string, required), "subjects" (array of subject objects, required), "osint_directives" (array of strings, optional), and "evidence_hints" (array of hint objects, optional).
2. WHEN a valid Lead_JSON is submitted, THE endpoint SHALL return the consolidated Investigative_Assessment covering all subjects, with cross-references between subjects where internal evidence connects them.
3. THE endpoint SHALL include a "case_viability" field in the response with values "viable" (strong evidence across multiple subjects), "promising" (partial evidence warrants further investigation), or "insufficient" (not enough evidence to proceed).
4. IF the Lead_JSON contains more than 20 subjects, THEN THE endpoint SHALL return a 400 error indicating the maximum subject limit.
5. WHEN processing takes longer than 30 seconds, THE endpoint SHALL return a 202 Accepted response with a job ID, and the investigator SHALL poll a GET /case-files/{id}/lead-assessment/{job_id} endpoint for the completed result.


### Requirement 10: Research Findings Persistence & Notebook

**User Story:** As an investigator, I want to save search results, AI assessments, and my own notes to a persistent research notebook linked to the case, so that I can build an evidence trail over time, reference previous findings in future searches, and share research with colleagues.

#### Acceptance Criteria

1. WHEN an Investigative_Assessment is displayed, THE UI SHALL provide a "Save Finding" button that persists the assessment to Aurora with the investigator's user ID, timestamp, and optional tags.
2. THE system SHALL store saved findings in an `investigation_findings` table in Aurora with columns: finding_id (UUID PK), case_id (FK), user_id, query, finding_type (search_result|entity_list|lead_assessment|manual_note), title, summary (AI-generated or user-provided), full_assessment (JSONB), source_citations (JSONB array), entity_names (JSONB array for graph linking), tags (JSONB array), investigator_notes (text), confidence_level, created_at, updated_at.
3. WHEN an investigator saves a finding, THE system SHALL also store the full InvestigativeAssessment JSON in S3 at `cases/{case_id}/findings/{finding_id}.json` for archival and large payload support.
4. THE UI SHALL provide a "Research Notebook" panel accessible from the search section that lists all saved findings for the current case, sortable by date, confidence, and tags.
5. WHEN viewing the Research Notebook, THE investigator SHALL be able to add/edit notes on any saved finding, add tags, and mark findings as "key evidence" or "needs follow-up".
6. THE system SHALL make saved findings searchable — when running a new investigative search, previously saved findings for the same entities SHALL be included in the Bedrock synthesis context to build on prior research.
7. THE system SHALL provide API endpoints: POST /case-files/{id}/findings (save), GET /case-files/{id}/findings (list), PUT /case-files/{id}/findings/{finding_id} (update notes/tags), DELETE /case-files/{id}/findings/{finding_id} (remove).
