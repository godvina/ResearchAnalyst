# Requirements Document

## Introduction

The OSINT Research Agent extends the Investigative Intelligence platform beyond internal document analysis into external intelligence gathering. When the system detects an investigative pattern or the user encounters an investigative question recommending "further research," a "Research This" button appears. Clicking it triggers a backend agent that formulates search queries, retrieves and extracts web content, synthesizes findings via Amazon Bedrock Claude, and returns a compact research card with an AI summary, credibility assessment, and sourced links. The feature includes contradiction detection against internal evidence, timeline cross-referencing, entity enrichment from public records, source reliability scoring, and the ability to pin research findings as case evidence. This positions the platform as a full-spectrum investigative tool — a key differentiator over eDiscovery-only tools like Relativity for DOJ and government customers.

## Glossary

- **OSINT_Agent**: The backend Python service that orchestrates external research — query formulation, web search, content extraction, and AI synthesis via Bedrock Claude.
- **Research_Card**: The compact UI component displaying OSINT results: AI summary paragraph, credibility assessment, source type tags, and 3-5 source links with titles and one-line descriptions.
- **Research_Button**: The "Research This" UI button that appears in entity drill-down panels, pattern detail cards, and AI briefing investigative questions when further external research is recommended.
- **Source_Classifier**: The component that tags each retrieved source by type (news, academic, government, social_media, legal_filing, corporate_record, blog) and assigns a reliability weight.
- **Credibility_Assessor**: The component that computes an overall credibility rating for the synthesized research based on source reliability weights and corroboration across sources.
- **Contradiction_Detector**: The component that compares OSINT findings against internal case evidence and flags discrepancies ("internal evidence says X, but public sources say Y").
- **Timeline_Correlator**: The component that cross-references entity appearances in external news/public records against the internal document timeline.
- **Entity_Enricher**: The component that auto-pulls public records, news mentions, and corporate filings when a user clicks on a person or organization entity.
- **Research_Cache**: The Aurora PostgreSQL table that stores OSINT results keyed by a normalized query hash, preventing redundant web searches for repeated queries.
- **Investigator_App**: The single-page HTML frontend application (investigator.html) that investigators use for case analysis.
- **Findings_Service**: The existing backend service that persists investigation findings to Aurora and S3 for the research notebook.

## Requirements

### Requirement 1: Research Button Activation

**User Story:** As an investigator, I want a "Research This" button to appear contextually so that I can trigger external research from patterns, entities, and investigative questions without leaving my workflow.

#### Acceptance Criteria

1. WHEN an investigative question includes a "further research" recommendation, THE Investigator_App SHALL display a Research_Button adjacent to that question.
2. WHEN a pattern detail card is rendered in the Top 5 Investigative Patterns view, THE Investigator_App SHALL display a Research_Button on the pattern card.
3. WHEN an entity drill-down panel is opened, THE Investigator_App SHALL display a Research_Button in the panel header next to the entity name.
4. WHEN the AI briefing section renders investigative questions, THE Investigator_App SHALL display a Research_Button next to each question that recommends external research.
5. WHEN the user clicks a Research_Button, THE Investigator_App SHALL send the associated context (entity name, entity type, pattern summary, or question text) to the OSINT_Agent API endpoint.

### Requirement 2: Query Formulation

**User Story:** As an investigator, I want the system to automatically generate targeted search queries from my investigation context so that I get relevant external intelligence without manually crafting searches.

#### Acceptance Criteria

1. WHEN the OSINT_Agent receives a research request with entity context, THE OSINT_Agent SHALL formulate between 3 and 5 search queries derived from the entity name, entity type, known aliases, and connected entities.
2. WHEN the OSINT_Agent receives a research request with pattern context, THE OSINT_Agent SHALL formulate between 3 and 5 search queries derived from the pattern entities, relationship type, and pattern description.
3. WHEN the OSINT_Agent receives a research request with an investigative question, THE OSINT_Agent SHALL formulate between 3 and 5 search queries derived from the question text and associated entity names.
4. THE OSINT_Agent SHALL use Bedrock Claude to generate search queries that cover different investigative angles (public records, news coverage, regulatory filings, corporate associations).

### Requirement 3: Web Search and Content Extraction

**User Story:** As an investigator, I want the system to search the web and extract content from top results so that I receive synthesized intelligence from multiple public sources.

#### Acceptance Criteria

1. WHEN the OSINT_Agent has formulated search queries, THE OSINT_Agent SHALL execute each query against a web search API and retrieve the top 5 results per query.
2. WHEN search results are retrieved, THE OSINT_Agent SHALL fetch the full page content from each unique result URL.
3. IF a URL fetch fails or times out after 10 seconds, THEN THE OSINT_Agent SHALL skip that URL and continue processing remaining results.
4. WHEN page content is fetched, THE OSINT_Agent SHALL extract the main text content, stripping navigation, ads, and boilerplate HTML.
5. THE OSINT_Agent SHALL deduplicate results across queries by URL before content extraction.

### Requirement 4: AI Synthesis and Research Card Generation

**User Story:** As an investigator, I want an AI-synthesized summary of external findings so that I can quickly understand what is publicly known about an entity or pattern.

#### Acceptance Criteria

1. WHEN extracted content from web sources is available, THE OSINT_Agent SHALL send the content along with the original investigation context to Bedrock Claude for synthesis.
2. THE OSINT_Agent SHALL produce a Research_Card containing: an AI summary paragraph (200-400 words), a credibility assessment (HIGH, MEDIUM, or LOW with explanation), and between 3 and 5 source links each with a title and a one-line description.
3. WHEN Bedrock Claude generates the synthesis, THE OSINT_Agent SHALL instruct the model to summarize what is publicly known, identify corroborating evidence, identify contradicting evidence, and note information gaps.
4. IF no relevant web results are found for any query, THEN THE OSINT_Agent SHALL return a Research_Card with a summary stating that no significant public information was found and suggesting alternative search strategies.

### Requirement 5: Source Classification and Reliability Scoring

**User Story:** As an investigator, I want each source tagged by type and scored for reliability so that I can assess the quality of external intelligence at a glance.

#### Acceptance Criteria

1. WHEN a source URL is processed, THE Source_Classifier SHALL assign exactly one source type tag from the set: news, academic, government, social_media, legal_filing, corporate_record, blog.
2. THE Source_Classifier SHALL assign reliability weights as follows: government sources receive a weight of 0.95, academic sources receive 0.90, legal_filing sources receive 0.85, news sources from established outlets receive 0.80, corporate_record sources receive 0.70, social_media sources receive 0.40, and blog sources receive 0.30.
3. WHEN the Research_Card is rendered, THE Investigator_App SHALL display the source type tag as a colored badge next to each source link.
4. THE Credibility_Assessor SHALL compute the overall credibility rating by calculating the weighted average of source reliability scores across all sources in the Research_Card.

### Requirement 6: Contradiction Detection

**User Story:** As an investigator, I want the system to flag contradictions between internal case evidence and external public sources so that I can identify discrepancies that warrant further investigation.

#### Acceptance Criteria

1. WHEN the OSINT_Agent synthesizes external findings, THE Contradiction_Detector SHALL compare key claims from external sources against internal case evidence for the same entity or pattern.
2. WHEN a contradiction is detected, THE Contradiction_Detector SHALL include a contradiction alert in the Research_Card specifying the internal claim, the external claim, and the source of each.
3. IF no contradictions are detected, THEN THE Contradiction_Detector SHALL include a statement in the Research_Card confirming that external sources are consistent with internal evidence.
4. THE Contradiction_Detector SHALL retrieve internal evidence by querying the case documents and entity relationships from Aurora and Neptune for the relevant entity names.

### Requirement 7: Timeline Cross-Reference

**User Story:** As an investigator, I want external news and public record dates compared against my internal document timeline so that I can identify temporal correlations and gaps.

#### Acceptance Criteria

1. WHEN external sources contain date references for an entity, THE Timeline_Correlator SHALL extract those dates and compare them against the internal document timeline for the same entity.
2. WHEN temporal correlations are found (external event within 30 days of an internal document date), THE Timeline_Correlator SHALL include a timeline correlation section in the Research_Card listing matched date pairs with descriptions.
3. WHEN temporal gaps are found (external events with no corresponding internal documents), THE Timeline_Correlator SHALL flag those gaps as potential areas for further investigation.
4. THE Timeline_Correlator SHALL present timeline data in chronological order with clear labels distinguishing internal and external date sources.

### Requirement 8: Entity Enrichment

**User Story:** As an investigator, I want the system to automatically pull public records, news mentions, and corporate filings when I view an entity so that I have a comprehensive profile without manual searching.

#### Acceptance Criteria

1. WHEN a user opens an entity drill-down panel for a PERSON or ORGANIZATION entity, THE Entity_Enricher SHALL automatically trigger a background OSINT lookup for that entity.
2. THE Entity_Enricher SHALL retrieve and display: public records (corporate registrations, property records), recent news mentions (last 2 years), and corporate filings (SEC, state registrations) where available.
3. WHEN enrichment data is available, THE Investigator_App SHALL display an "External Intelligence" section in the entity drill-down panel below the existing AI Investigative Questions section.
4. IF the entity has been enriched within the last 24 hours, THEN THE Entity_Enricher SHALL serve the cached enrichment data from the Research_Cache instead of performing a new lookup.

### Requirement 9: Research Result Caching

**User Story:** As an investigator, I want research results cached so that repeated queries return instantly without redundant web searches.

#### Acceptance Criteria

1. WHEN the OSINT_Agent completes a research request, THE Research_Cache SHALL store the full Research_Card response keyed by a SHA-256 hash of the normalized query context (entity name + type + case_id or pattern summary + case_id).
2. WHEN a research request matches an existing cache entry less than 24 hours old, THE OSINT_Agent SHALL return the cached Research_Card without executing web searches.
3. WHEN a research request matches a cache entry older than 24 hours, THE OSINT_Agent SHALL execute a fresh research cycle and update the cache entry.
4. WHEN the user clicks a "Refresh" control on a Research_Card, THE OSINT_Agent SHALL bypass the cache and execute a fresh research cycle regardless of cache age.

### Requirement 10: Save to Case

**User Story:** As an investigator, I want to pin external research findings as evidence in my case file so that OSINT intelligence becomes part of the formal investigation record.

#### Acceptance Criteria

1. WHEN a Research_Card is displayed, THE Investigator_App SHALL include a "Save to Case" button on the card.
2. WHEN the user clicks "Save to Case," THE Findings_Service SHALL persist the Research_Card content as a finding with finding_type set to "osint_research," including the AI summary, source links, credibility assessment, and any contradiction alerts.
3. WHEN an OSINT finding is saved, THE Findings_Service SHALL tag the finding with the entity names and source type tags from the Research_Card.
4. WHEN an OSINT finding is saved, THE Investigator_App SHALL display a confirmation and the finding SHALL appear in the Research Notebook evidence list.

### Requirement 11: OSINT Research API Endpoint

**User Story:** As a platform developer, I want a dedicated API endpoint for OSINT research so that the frontend can trigger and retrieve research results through the existing API Gateway.

#### Acceptance Criteria

1. THE OSINT_Agent SHALL expose a POST endpoint at /case-files/{id}/osint-research that accepts a JSON body with research_type (entity, pattern, or question), context payload, and an optional force_refresh flag.
2. WHEN the endpoint receives a valid request, THE OSINT_Agent SHALL return a JSON response containing the Research_Card data within 30 seconds.
3. IF the request is missing required fields, THEN THE OSINT_Agent SHALL return a 400 error with a descriptive validation message.
4. IF an internal error occurs during research, THEN THE OSINT_Agent SHALL return a 500 error with an error code and log the full exception details.
5. THE OSINT_Agent SHALL support a GET endpoint at /case-files/{id}/osint-research/cache that returns all cached research results for a case.
