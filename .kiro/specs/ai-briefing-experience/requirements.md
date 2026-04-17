# Requirements Document

## Introduction

The AI Briefing Experience feature addresses two critical issues in the investigator case analysis page: (1) the POST /case-files/{id}/investigator-analysis API times out at API Gateway's hard 29-second limit because `analyze_case()` performs Neptune queries, multiple Bedrock invocations, and Aurora writes in a single synchronous call, and (2) the briefing is a flat wall of text with no interactivity — investigators cannot drill into findings, view supporting evidence, or confirm/dismiss AI recommendations inline.

This feature decomposes the analysis into a two-phase async pattern that fits within API Gateway's 29-second constraint, then layers a 3-level progressive disclosure UI on top — modeled after professional legal investigation tools (Palantir Gotham, Relativity, Nuix, i2 Analyst's Notebook, CaseMap) — so investigators can move from executive summary to finding detail to supporting documents without leaving the briefing tab.

All changes EXTEND existing services and the investigator.html page. No existing working backend code is rewritten.

## Glossary

- **Briefing_API**: The Lambda handler at `src/lambdas/api/investigator_analysis.py` that dispatches POST and GET requests for `/case-files/{id}/investigator-analysis`
- **AI_Engine**: The `InvestigatorAIEngine` class in `src/services/investigator_ai_engine.py` that orchestrates case analysis
- **Briefing_Frontend**: The AI Briefing tab rendering code in `src/frontend/investigator.html` (functions `loadAIBriefing`, `renderBriefing`, and related)
- **Decision_Service**: The `DecisionWorkflowService` in `src/services/decision_workflow_service.py` managing the AI_Proposed → Human_Confirmed → Human_Overridden state machine
- **Search_API**: The existing POST `/case-files/{id}/search` endpoint for semantic search with pgvector
- **Neptune_Graph**: The Amazon Neptune graph database storing entities and relationships queryable via Gremlin
- **Analysis_Cache**: The `investigator_analysis_cache` table in Aurora that stores completed analysis results
- **Finding**: A single key finding (lead, hypothesis, or pattern) surfaced by the AI_Engine in the briefing
- **Detail_Panel**: An expandable UI panel within the Briefing_Frontend that shows AI reasoning, confidence, related entities, and a mini knowledge graph for a single Finding
- **Supporting_Documents_View**: A UI panel within the Detail_Panel that shows semantic search results with highlighted relevant passages for a Finding
- **Confirm_Dismiss_Toggle**: A UI control on each Finding card that allows the investigator to transition the associated decision through the Decision_Service workflow

## Requirements

### Requirement 1: Async Analysis Trigger (P0 — Timeout Fix)

**User Story:** As an investigator, I want the AI briefing to load reliably regardless of case size, so that I am not blocked by API Gateway timeouts when analyzing large cases.

#### Acceptance Criteria

1. WHEN an investigator triggers a new analysis via POST `/case-files/{id}/investigator-analysis`, THE Briefing_API SHALL return an HTTP 202 response with `{"status": "processing", "case_id": "<id>"}` within 5 seconds, before any Bedrock invocations or Neptune queries begin
2. WHEN the Briefing_API returns a 202 processing response, THE Briefing_API SHALL initiate the full analysis asynchronously by invoking the AI_Engine via a separate Lambda invocation or Step Functions execution
3. WHEN a cached completed analysis exists in the Analysis_Cache and the evidence count has not changed, THE Briefing_API SHALL return the cached result with HTTP 200 without triggering a new analysis
4. IF the asynchronous analysis fails, THEN THE AI_Engine SHALL write an error status to the Analysis_Cache with a human-readable error message
5. WHEN the Briefing_Frontend polls for analysis status and receives `{"status": "processing"}`, THE Briefing_Frontend SHALL display a progress indicator with an estimated wait message and poll every 3 seconds until status changes to "completed" or "error"
6. WHEN the Briefing_Frontend receives `{"status": "error"}`, THE Briefing_Frontend SHALL display the error message with a "Retry Analysis" button

### Requirement 2: Level 1 — Executive Summary View

**User Story:** As an investigator, I want to see a professional executive summary with case statistics, narrative, and clickable finding cards, so that I can quickly assess the state of a case.

#### Acceptance Criteria

1. THE Briefing_Frontend SHALL render the executive summary as the default Level 1 view, displaying case statistics (document count, entity count, relationship count, active leads), the analyst narrative, and a grid of Finding cards
2. THE Briefing_Frontend SHALL render each Finding card with the entity name, entity type, lead priority score as a color-coded badge (green above 70, yellow 40–70, red below 40), a one-line AI justification summary, and the current decision state (AI_Proposed, Human_Confirmed, or Human_Overridden)
3. WHEN an investigator clicks a Finding card, THE Briefing_Frontend SHALL expand the Detail_Panel for that Finding (Level 2 transition)
4. THE Briefing_Frontend SHALL format the executive summary using professional legal software styling: serif section headers, muted color palette, clear visual hierarchy with section dividers, and DOJ-appropriate typography

### Requirement 3: Level 2 — Finding Detail Panel

**User Story:** As an investigator, I want to click a finding and see the AI's reasoning, confidence breakdown, related entities, and a mini knowledge graph, so that I can evaluate the finding's merit before acting on it.

#### Acceptance Criteria

1. WHEN an investigator clicks a Finding card to open the Detail_Panel, THE Briefing_Frontend SHALL display: the full AI justification text, a confidence score breakdown showing evidence_strength, connection_density, novelty, and prosecution_readiness as labeled progress bars, and a list of related entities from the Neptune_Graph
2. WHEN the Detail_Panel opens for a Finding, THE Briefing_Frontend SHALL query the Neptune_Graph (via an API endpoint) for entities connected to the Finding's entity within 2 hops and render a mini knowledge graph visualization using vis-network
3. THE Detail_Panel SHALL include a "View Supporting Documents" button that transitions to the Supporting_Documents_View (Level 3)
4. THE Detail_Panel SHALL be rendered as an expandable section below the Finding card, without navigating away from the briefing page
5. IF the Neptune_Graph query returns no connected entities, THEN THE Briefing_Frontend SHALL display a message "No graph connections found for this entity" in place of the mini knowledge graph

### Requirement 4: Level 3 — Supporting Documents View

**User Story:** As an investigator, I want to see the actual documents that support a finding with relevant passages highlighted, so that I can verify the AI's conclusions against primary sources.

#### Acceptance Criteria

1. WHEN an investigator clicks "View Supporting Documents" in the Detail_Panel, THE Briefing_Frontend SHALL call the Search_API with the Finding's entity name as the query and the current case ID, requesting the top 10 results
2. THE Supporting_Documents_View SHALL display each search result as a document card showing: document title, document type badge, relevance score, and an excerpt with matching terms highlighted using the existing `<mark>` styling
3. WHEN an investigator clicks a document card in the Supporting_Documents_View, THE Briefing_Frontend SHALL open the existing drill-down panel with the full document context
4. IF the Search_API returns zero results, THEN THE Briefing_Frontend SHALL display "No supporting documents found for this finding. The entity may have been extracted from graph relationships rather than document text."

### Requirement 5: Confirm/Dismiss Toggle on Findings

**User Story:** As an investigator, I want to confirm or dismiss each AI finding directly from the briefing, so that I can record my assessment without switching to a separate workflow page.

#### Acceptance Criteria

1. THE Briefing_Frontend SHALL render a Confirm_Dismiss_Toggle on each Finding card that has an associated decision_id, showing the current decision state
2. WHEN an investigator clicks "Confirm" on a Finding in AI_Proposed state, THE Briefing_Frontend SHALL call the Decision_Service confirm endpoint (PUT `/decisions/{decision_id}/confirm`) and update the Finding card's state badge to "Human_Confirmed" without reloading the entire briefing
3. WHEN an investigator clicks "Dismiss" on a Finding in AI_Proposed state, THE Briefing_Frontend SHALL call the Decision_Service override endpoint (PUT `/decisions/{decision_id}/override`) with a rationale of "Dismissed by investigator from briefing" and update the Finding card's state badge to "Human_Overridden"
4. WHILE a Finding's decision state is Human_Confirmed or Human_Overridden, THE Confirm_Dismiss_Toggle SHALL display the resolved state as a read-only badge and hide the action buttons
5. IF the Decision_Service returns a 409 Conflict (decision already transitioned), THEN THE Briefing_Frontend SHALL refresh the Finding card's state from the server and display a brief notification "Decision already updated"

### Requirement 6: Entity Neighborhood API Endpoint

**User Story:** As an investigator, I want the briefing to fetch graph neighborhood data for a specific entity, so that the Detail_Panel can render a mini knowledge graph without loading the full case graph.

#### Acceptance Criteria

1. WHEN a GET request is made to `/case-files/{id}/entity-neighborhood?entity_name={name}&hops={n}`, THE Briefing_API SHALL query the Neptune_Graph for the specified entity and return all entities and edges within the requested hop count (default 2, maximum 3)
2. THE entity neighborhood response SHALL include for each node: entity name, entity type, and degree count; and for each edge: source name, target name, and relationship type
3. IF the specified entity is not found in the Neptune_Graph, THEN THE Briefing_API SHALL return an HTTP 200 with an empty nodes array and empty edges array
4. THE Briefing_API SHALL complete the Neptune_Graph query and return the response within 10 seconds for entities with up to 500 connections

### Requirement 7: Polling-Based Status Retrieval

**User Story:** As an investigator, I want to check the status of an in-progress analysis without triggering a new one, so that the frontend can poll efficiently until the briefing is ready.

#### Acceptance Criteria

1. WHEN a GET request is made to `/case-files/{id}/investigator-analysis`, THE Briefing_API SHALL return the current analysis status from the Analysis_Cache: either `{"status": "completed", ...full result...}`, `{"status": "processing"}`, or `{"status": "error", "error_message": "..."}`, without triggering any new analysis work
2. THE Briefing_API SHALL return the GET response within 1 second since the GET handler only reads from the Analysis_Cache
3. WHEN the Analysis_Cache contains no entry for the case, THE Briefing_API SHALL return HTTP 404 to indicate no analysis has been initiated
