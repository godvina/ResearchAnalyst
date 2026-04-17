# Requirements Document

## Introduction

The investigator.html single-page application has grown to 16 tabs with significant overlap, broken features, dead-end displays, and no guided investigative workflow. This feature consolidates the UI into 7 focused tabs following the Palantir Gotham investigative pattern: Lead Intake → Subject Research → Evidence Collection → Connection Mapping → Case Assessment → Reporting. The consolidation merges Case Investigations + AI Briefing + Leads into a Case Dashboard, introduces a new Lead Investigation tab (the critical missing workflow piece), deduplicates the Evidence tab, preserves Timeline and Map, merges three pipeline tabs into one, and keeps Portfolio. Backend services remain unchanged; this is primarily a frontend restructure with two backend fixes: wiring AIResearchAgent for external search scope and adding an "Investigate Entity" action that calls the existing investigative search API.

## Glossary

- **Investigator_UI**: The investigator.html single-page application serving the investigator workflow
- **Tab_Bar**: The horizontal navigation bar containing the 7 workflow tabs
- **Case_Dashboard_Tab**: The consolidated first tab merging Case Investigations, AI Briefing, Leads, Evidence Triage, Hypotheses, and Subpoenas into a unified case command center
- **Lead_Investigation_Tab**: The new tab providing a lead queue with status workflow, investigative search per lead, batch assessment, and lead import
- **Evidence_Library_Tab**: The deduplicated evidence browser (removing the duplicate from Case Investigations sub-tab and the standalone Evidence tab, creating one clean tab)
- **Timeline_Tab**: The existing timeline visualization tab (preserved as-is)
- **Map_Tab**: The existing geospatial evidence map tab (preserved as-is)
- **Pipeline_Tab**: The consolidated operations tab merging Ingestion Pipeline, Pipeline Config, and Pipeline Monitor into one tab with sub-sections
- **Portfolio_Tab**: The existing case portfolio overview tab (preserved as-is)
- **Entity_Dossier_Panel**: A slide-out panel that appears when any entity name is clicked anywhere in the app, showing the entity's full profile: photo, document mentions, graph neighborhood, timeline events, prior findings, and an "Investigate" button
- **AI_Briefing_Section**: The section within Case_Dashboard_Tab that displays the AI-generated case analysis with finding cards, narrative, and statistics
- **Lead_Card**: A UI card in the Lead_Investigation_Tab showing entity name, score, AI justification, and status badge
- **Lead_Status**: The workflow state of a lead: New, Investigating, Assessed, or Closed
- **InvestigativeSearchService**: The existing backend orchestrator that runs entity extraction, document search, graph context, and AI synthesis to produce an Intelligence Brief
- **AIResearchAgent**: The existing backend service that uses Bedrock to generate external research on subjects
- **LeadIngestionService**: The existing backend service for lead intake and validation
- **InvestigatorAIEngine**: The existing backend service that generates case analysis, leads, hypotheses, subpoenas, and evidence triage
- **PatternDiscoveryService**: The existing backend service for pattern detection via graph traversal and vector similarity
- **CrossCaseService**: The existing backend service for cross-case entity matching
- **FindingsService**: The existing backend service for Research Notebook CRUD (save/list/update/delete findings)
- **Intelligence_Brief**: The structured response from InvestigativeSearchService containing executive summary, evidence, graph connections, AI analysis, evidence gaps, and next steps
- **Case_Viability_Rating**: The assessment result from lead_assessment API: viable, promising, or insufficient

## Requirements

### Requirement 1: Tab Bar Consolidation from 16 to 7 Tabs

**User Story:** As an investigator, I want a clean 7-tab workflow so that I can follow a logical investigative progression without being overwhelmed by 16 tabs.

#### Acceptance Criteria

1. THE Investigator_UI SHALL display exactly 7 tabs in the Tab_Bar in this order: 📋 Case Dashboard, 🎯 Lead Investigation, 🔍 Evidence Library, 📅 Timeline, 🗺️ Map, ⚙️ Pipeline, 📊 Portfolio
2. WHEN the Investigator_UI loads, THE Tab_Bar SHALL activate the Case_Dashboard_Tab by default
3. THE Investigator_UI SHALL remove the following tabs from the Tab_Bar: standalone Cross-Case Analysis, standalone Ingestion Pipeline, standalone Pipeline Config, standalone Pipeline Monitor, New Case Wizard, My Workbench, standalone Leads, standalone Evidence Triage, standalone Hypotheses, standalone Subpoenas, standalone AI Briefing, standalone Evidence
4. THE Investigator_UI SHALL remove the HTML content divs for all removed standalone tabs (tab-crosscase, tab-pipeline, tab-pipeconfig, tab-pipemonitor, tab-wizard, tab-workbench, tab-leads, tab-triage, tab-hypotheses, tab-subpoenas, tab-aibriefing, tab-evidence)
5. THE switchTab function SHALL update the allTabs array to contain only the 7 new tab identifiers: dashboard, leadinvestigation, evidencelibrary, timeline, map, pipeline, portfolio

### Requirement 2: Case Dashboard Tab — AI Briefing Section

**User Story:** As an investigator, I want the AI Briefing to auto-load when I select a case so that I immediately see what the AI found without navigating to a separate tab.

#### Acceptance Criteria

1. WHEN a case is selected, THE Case_Dashboard_Tab SHALL auto-fetch the AI Briefing from the InvestigatorAIEngine `/case-files/{id}/investigator-analysis` endpoint and display it in the AI_Briefing_Section at the top of the dashboard
2. THE AI_Briefing_Section SHALL display the executive summary narrative, case statistics (document count, entity count, relationship count, active leads), and a grid of finding cards
3. WHEN a finding card is clicked, THE Case_Dashboard_Tab SHALL expand the finding detail inline showing AI justification, confidence breakdown, related entities, and a mini knowledge graph via the entity-neighborhood API
4. THE AI_Briefing_Section SHALL display a "🔎 Investigate" button on each finding card that triggers an investigative search on that entity via `POST /case-files/{id}/investigative-search`
5. WHEN the "Investigate" button is clicked, THE Case_Dashboard_Tab SHALL display the resulting Intelligence_Brief in a slide-out panel with evidence citations, graph connections, AI analysis, evidence gaps, and recommended next steps
6. IF the AI Briefing API returns an error or times out, THEN THE AI_Briefing_Section SHALL display a graceful fallback message with a "Retry" button while rendering the rest of the dashboard normally
7. WHILE the AI Briefing is loading, THE AI_Briefing_Section SHALL display a loading skeleton with animated placeholders

### Requirement 3: Case Dashboard Tab — Search Bar and Research Notebook

**User Story:** As an investigator, I want the search bar and Research Notebook from Case Investigations preserved in the dashboard so that I can search and save findings without losing existing functionality.

#### Acceptance Criteria

1. THE Case_Dashboard_Tab SHALL include the existing search bar with Internal/External scope toggle that calls `POST /case-files/{id}/investigative-search`
2. THE Case_Dashboard_Tab SHALL include the existing Research Notebook panel that displays saved findings from the FindingsService with title, summary, tags, date, and confidence badge
3. THE Case_Dashboard_Tab SHALL include the existing "Save Finding" button on Intelligence Brief results that saves to the FindingsService via `POST /case-files/{id}/findings`
4. WHEN the External scope is selected, THE search bar SHALL pass `search_scope: "internal_external"` to the investigative search API, and the AIResearchAgent SHALL produce external research results in the cross-reference report

### Requirement 4: Case Dashboard Tab — Collapsible Intelligence Sections

**User Story:** As an investigator, I want Evidence Triage, Hypotheses, and Subpoena Recommendations accessible as collapsible sections within the dashboard so that I can view all AI intelligence in one place.

#### Acceptance Criteria

1. THE Case_Dashboard_Tab SHALL include a collapsible "Evidence Triage" section that fetches data from `/case-files/{id}/evidence-triage` when expanded
2. THE Case_Dashboard_Tab SHALL include a collapsible "AI Hypotheses" section that fetches data from `/case-files/{id}/ai-hypotheses` when expanded
3. THE Case_Dashboard_Tab SHALL include a collapsible "Subpoena Recommendations" section that fetches data from `/case-files/{id}/subpoena-recommendations` when expanded
4. THE Case_Dashboard_Tab SHALL include a collapsible "Top Patterns" section that fetches the top 5 patterns from the PatternDiscoveryService when expanded
5. WHEN a collapsible section is expanded for the first time for the current case, THE Case_Dashboard_Tab SHALL fetch the data lazily and cache the result for subsequent toggles
6. IF any section data fetch fails, THEN THE Case_Dashboard_Tab SHALL display a graceful fallback message for that section while rendering the remaining sections normally

### Requirement 5: Lead Investigation Tab — Lead Queue

**User Story:** As an investigator, I want a dedicated Lead Investigation tab with a lead queue showing AI-generated leads and manually imported leads so that I can systematically work through investigative leads.

#### Acceptance Criteria

1. WHEN the Lead_Investigation_Tab is activated and a case is selected, THE Lead_Investigation_Tab SHALL fetch leads from `/case-files/{id}/investigative-leads` and display them as Lead_Cards in a scrollable queue
2. THE Lead_Card SHALL display the entity name, lead score as a color-coded badge (green above 70, yellow 40-70, red below 40), a one-line AI justification, and a Lead_Status badge (New, Investigating, Assessed, Closed)
3. THE Lead_Investigation_Tab SHALL sort leads by score descending by default, with options to sort by status or name
4. WHEN no leads exist for the selected case, THE Lead_Investigation_Tab SHALL display an empty state message with a prompt to run AI Briefing first or import leads manually

### Requirement 6: Lead Investigation Tab — Investigate Lead Action

**User Story:** As an investigator, I want to click a lead and run a full investigative search so that I can assess whether the lead is worth pursuing.

#### Acceptance Criteria

1. WHEN an investigator clicks a Lead_Card, THE Lead_Investigation_Tab SHALL update the lead's status to "Investigating" and call `POST /case-files/{id}/investigative-search` with the lead entity name as the query and `search_scope: "internal_external"`
2. WHEN the investigative search completes, THE Lead_Investigation_Tab SHALL display the Intelligence_Brief in an expanded panel below the Lead_Card showing: executive summary, evidence citations, graph connections, AI analysis, evidence gaps, and recommended next steps
3. WHEN the investigative search completes, THE Lead_Investigation_Tab SHALL update the lead's status to "Assessed" and display the confidence level as a badge (strong_case in green, needs_more_evidence in yellow, insufficient in red)
4. IF the investigative search fails or times out, THEN THE Lead_Investigation_Tab SHALL display an error message with a "Retry" button and revert the lead status to "New"

### Requirement 7: Lead Investigation Tab — Lead Assessment with Viability Rating

**User Story:** As an investigator, I want to run a deep-dive lead assessment that evaluates all subjects and computes case viability so that I can prioritize which leads to pursue.

#### Acceptance Criteria

1. THE Lead_Investigation_Tab SHALL provide an "Assess Lead" button on each Lead_Card that calls `POST /case-files/{id}/lead-assessment` with the lead's subjects
2. WHEN the lead assessment completes, THE Lead_Investigation_Tab SHALL display the Case_Viability_Rating (viable in green, promising in yellow, insufficient in red) and the consolidated summary
3. WHEN the lead assessment completes, THE Lead_Investigation_Tab SHALL display cross-subject connections found between the lead's subjects
4. THE Lead_Investigation_Tab SHALL provide an "Investigate All" button that batch-runs lead assessment on all leads with status "New", processing them sequentially and updating each Lead_Card as results arrive

### Requirement 8: Lead Investigation Tab — Lead Import

**User Story:** As an investigator, I want to manually import leads via JSON paste or a simple form so that I can add leads from external sources.

#### Acceptance Criteria

1. THE Lead_Investigation_Tab SHALL provide an "Import Lead" button that opens a modal with two input modes: JSON paste and simple form
2. WHEN the JSON paste mode is selected, THE import modal SHALL accept a JSON object with fields: name (required), type (person or organization), context (optional text), and aliases (optional array)
3. WHEN the simple form mode is selected, THE import modal SHALL display input fields for: entity name (required), entity type dropdown (person/organization), context textarea, and aliases comma-separated input
4. WHEN a lead is imported, THE Lead_Investigation_Tab SHALL add the lead to the queue with status "New" and score 0, and persist the lead locally in the browser session state
5. IF the imported lead JSON is malformed or missing the required name field, THEN THE import modal SHALL display a validation error message without closing the modal

### Requirement 9: Lead Investigation Tab — Lead Status Workflow

**User Story:** As an investigator, I want leads to progress through a status workflow (New → Investigating → Assessed → Closed) so that I can track which leads have been worked.

#### Acceptance Criteria

1. THE Lead_Card SHALL display the current Lead_Status as a colored badge: New (blue), Investigating (amber), Assessed (green or red based on viability), Closed (gray)
2. WHEN an investigator clicks "Close Lead" on an assessed lead, THE Lead_Investigation_Tab SHALL update the lead status to "Closed" and move the lead to a collapsed "Closed Leads" section at the bottom of the queue
3. THE Lead_Investigation_Tab SHALL persist lead statuses in browser localStorage keyed by case ID so that statuses survive page refreshes
4. WHEN the selected case changes, THE Lead_Investigation_Tab SHALL load the lead statuses for the new case from localStorage

### Requirement 10: Entity Dossier Slide-Out Panel

**User Story:** As an investigator, I want to click any entity name anywhere in the app and see a full dossier so that I can quickly research any person, organization, or location without navigating away from my current context.

#### Acceptance Criteria

1. WHEN an investigator clicks any entity name rendered in the Case_Dashboard_Tab, Lead_Investigation_Tab, Evidence_Library_Tab, Timeline_Tab, or Map_Tab, THE Investigator_UI SHALL open the Entity_Dossier_Panel as a slide-out overlay from the right side of the screen
2. THE Entity_Dossier_Panel SHALL display the following sections: entity photo (if available from entity-photos API), entity type and aliases, document mentions (list of documents where the entity appears), graph neighborhood visualization (from `/case-files/{id}/entity-neighborhood` API with 2 hops), timeline events involving the entity, and prior findings from the Research Notebook matching the entity name
3. THE Entity_Dossier_Panel SHALL include an "🔎 Investigate" button that runs `POST /case-files/{id}/investigative-search` with the entity name as the query and displays the Intelligence_Brief inline within the dossier
4. THE Entity_Dossier_Panel SHALL include a close button and support closing via the Escape key
5. IF the entity-neighborhood API returns no graph data, THEN THE Entity_Dossier_Panel SHALL display "No graph connections found" in the graph section while rendering all other sections normally

### Requirement 11: Evidence Library Tab Deduplication

**User Story:** As an investigator, I want a single Evidence Library tab so that evidence is not confusingly split between two locations.

#### Acceptance Criteria

1. THE Evidence_Library_Tab SHALL contain all functionality from the existing standalone Evidence tab: document listing, classification toggle, entity badges, document preview, Rekognition label filtering, media type filtering, and evidence detail modal
2. THE Investigator_UI SHALL remove the evidence library sub-tab from the old Case Investigations tab content
3. THE Investigator_UI SHALL remove the standalone Evidence tab (tab-evidence div) from the HTML
4. THE Evidence_Library_Tab SHALL appear in the third position in the Tab_Bar

### Requirement 12: Pipeline Tab Consolidation

**User Story:** As an administrator, I want Pipeline, Config, and Monitor merged into one tab so that pipeline operations are in one place.

#### Acceptance Criteria

1. THE Pipeline_Tab SHALL display three sub-sections accessible via sub-navigation buttons: Pipeline Status, Pipeline Config, and Pipeline Monitor
2. THE Pipeline_Tab SHALL default to the Pipeline Status sub-section when activated
3. THE Pipeline Status sub-section SHALL contain all existing functionality from the Ingestion Pipeline tab
4. THE Pipeline Config sub-section SHALL contain all existing functionality from the Pipeline Config tab
5. THE Pipeline Monitor sub-section SHALL contain all existing functionality from the Pipeline Monitor tab
6. THE Investigator_UI SHALL remove the standalone Pipeline Config tab (tab-pipeconfig div) and Pipeline Monitor tab (tab-pipemonitor div) from the HTML

### Requirement 13: Preserve Timeline Tab

**User Story:** As an investigator, I want the Timeline tab to remain unchanged so that the working timeline visualization is not disrupted.

#### Acceptance Criteria

1. THE Timeline_Tab SHALL retain all existing functionality including event timeline rendering, AI analysis, and event detail panel
2. THE Timeline_Tab SHALL appear in the fourth position in the Tab_Bar

### Requirement 14: Preserve Map Tab

**User Story:** As an investigator, I want the Map tab to remain unchanged so that the working geospatial evidence map is not disrupted.

#### Acceptance Criteria

1. THE Map_Tab SHALL retain all existing functionality including map rendering, evidence markers, location clustering, and map detail overlay
2. THE Map_Tab SHALL appear in the fifth position in the Tab_Bar

### Requirement 15: Preserve Portfolio Tab

**User Story:** As an investigator, I want the Portfolio tab to remain unchanged so that the case overview continues to work.

#### Acceptance Criteria

1. THE Portfolio_Tab SHALL retain all existing functionality including case portfolio overview and case statistics
2. THE Portfolio_Tab SHALL appear in the seventh position in the Tab_Bar
3. THE Portfolio_Tab SHALL include a "New Case" button that opens the case creation wizard as a modal dialog, replacing the removed standalone New Case Wizard tab

### Requirement 16: Cross-Tab Case Context Sharing

**User Story:** As an investigator, I want the selected case to persist across all tabs so that I do not have to re-select the case when switching tabs.

#### Acceptance Criteria

1. WHEN a case is selected in the Case_Dashboard_Tab sidebar, THE Investigator_UI SHALL store the selected case identifier and case metadata in a shared session state variable accessible to all tabs
2. WHEN the investigator switches to any tab, THE active tab SHALL use the shared case identifier to load case-specific data
3. IF no case is selected, THEN THE Investigator_UI SHALL display a prompt in each tab instructing the investigator to select a case from the Case Dashboard
4. WHEN the selected case changes, THE Investigator_UI SHALL clear cached data in all tabs and reset lead statuses display

### Requirement 17: External Search Scope Fix

**User Story:** As an investigator, I want the Internal+External search toggle to actually produce external research results so that I get cross-referenced intelligence from both internal evidence and external sources.

#### Acceptance Criteria

1. WHEN `search_scope` is set to `"internal_external"`, THE InvestigativeSearchService SHALL invoke the AIResearchAgent to generate external research for each extracted entity
2. WHEN external research results are available, THE InvestigativeSearchService SHALL pass the results to `_generate_cross_reference_report()` and include the cross-reference report in the Intelligence_Brief response
3. THE cross-reference report SHALL categorize each finding as `confirmed_internally`, `external_only`, or `needs_research`
4. WHEN the frontend receives a cross-reference report, THE Intelligence_Brief display SHALL render a "Cross-Reference Report" section showing each finding with its category badge and source attribution
5. IF the AIResearchAgent fails or times out within the 25-second budget, THEN THE InvestigativeSearchService SHALL return the internal-only results with a note that external research was unavailable

### Requirement 18: Removed Tab Cleanup

**User Story:** As an investigator, I want broken and empty tab content removed so that I do not encounter error states or placeholder content.

#### Acceptance Criteria

1. THE Investigator_UI SHALL remove the My Workbench tab content (tab-workbench div) from the HTML
2. THE Investigator_UI SHALL remove the New Case Wizard tab content (tab-wizard div) from the HTML, with the wizard form relocated to a modal accessible from the Portfolio_Tab
3. THE Investigator_UI SHALL remove the standalone Leads tab content (tab-leads div) from the HTML, with lead functionality relocated to the Lead_Investigation_Tab
4. THE Investigator_UI SHALL remove the standalone Cross-Case Analysis tab content (tab-crosscase div) from the HTML
5. THE Investigator_UI SHALL migrate any working JavaScript functions from removed tabs that are needed by the consolidated tabs, preserving function signatures and behavior

### Requirement 19: Tab Workflow Progression Indicators

**User Story:** As an investigator, I want visual cues showing which tabs have data loaded for the current case so that I know which steps of the workflow are ready.

#### Acceptance Criteria

1. WHEN a tab has successfully loaded data for the current case, THE Tab_Bar SHALL display a small green indicator dot on that tab
2. WHEN the selected case changes, THE Tab_Bar SHALL reset all indicator dots
3. THE indicator dot SHALL use a green color (#238636) consistent with the existing UI theme

### Requirement 20: Future Phase Notation — Intelligence Trawler

**User Story:** As a product owner, I want the Intelligence Trawler (persistent monitoring/alerting) noted as the priority Phase 2 feature so that the team knows what comes next.

#### Acceptance Criteria

1. THE requirements document SHALL note that the Intelligence Trawler (persistent collection, standing queries, automated alerts on new intelligence) is the priority feature to build immediately after this consolidation
2. THE requirements document SHALL note that Court-Ready Export, Investigation Playbooks, Collaboration, Audit Trail, Data Lineage, and Role-Based Dashboards are future roadmap items from the Palantir Gotham gap analysis

## Future Phase Notes

### Phase 2 — Intelligence Trawler (PRIORITY — build immediately after consolidation)
Persistent collection / standing query system: investigator sets monitors on entities or findings, EventBridge scheduled Lambda re-runs investigative search periodically, diffs results, auto-saves new findings to Research Notebook, sends SNS/SES alerts when new intelligence surfaces. Reuses 100% of Phase 1 InvestigativeSearchService and FindingsService infrastructure.

### Future Roadmap — Palantir Gotham Gap Analysis
- Court-Ready Export & Reporting (spec exists, needs frontend)
- Investigation Playbooks / Workflow Automation (AI-guided investigation templates)
- Collaboration & Annotations (multi-user shared workspaces, comment threads)
- Full Audit Trail & Provenance (chain of custody, immutable event log)
- Data Lineage & Processing Provenance (visual trace from finding to source document)
- Role-Based Dashboards & Views (analyst/supervisor/prosecutor role switching)
