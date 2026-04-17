# Requirements Document

## Introduction

The Conspiracy Network Discovery module is an AI-powered analysis layer that automatically discovers co-conspirators, criminal networks, and hidden patterns within a case's evidence. It sits on both the Investigator and Prosecutor sides of the Research Analyst application, extending the existing Neptune knowledge graph (77K+ entities, 1.87M+ edges), OpenSearch vector search, Aurora PostgreSQL, and Amazon Bedrock AI infrastructure.

The module runs graph algorithms (community detection, centrality scoring, anomaly detection) on case subgraphs to identify clusters of entities forming potential conspiracy networks. It ranks individuals by a composite "involvement score," generates co-conspirator profiles with AI legal reasoning, proposes sub-cases for investigation, detects hidden patterns across financial, communication, geographic, and temporal dimensions, and provides an interactive network visualization. All AI-identified persons of interest flow through the three-state decision workflow (AI_Proposed → Human_Confirmed → Human_Overridden) from the prosecutor-case-review spec.

The system must scale to 3M+ documents (Epstein case scale) and automatically surface findings such as: "Based on flight logs, financial records, and witness testimony, these 47 individuals have evidence patterns consistent with co-conspirator involvement."

## Glossary

- **Network_Discovery_Engine**: The core backend service that orchestrates graph algorithm execution, involvement scoring, and co-conspirator identification on a case's Neptune subgraph
- **Involvement_Score**: A composite score (0–100) ranking an individual's potential involvement in a conspiracy, derived from connection count to the primary subject, document co-occurrence frequency, financial transaction patterns, communication patterns, and geographic co-location
- **Co_Conspirator_Profile**: A structured dossier generated for each person of interest, containing identity information, connection strength, evidence summary, relationship map, potential charges, risk level, and AI legal justification
- **Connection_Strength**: A score (1–100) measuring the strength of an individual's connection to the primary subject, computed from edge weight, path count, and co-occurrence frequency in the Neptune graph
- **Risk_Level**: A classification of evidence strength for a person of interest: High (strong direct evidence), Medium (circumstantial or indirect evidence), or Low (peripheral involvement)
- **Sub_Case**: A new case file spawned from a parent case when a co-conspirator has sufficient evidence for independent investigation, inheriting relevant evidence via cross-case edges in Neptune
- **Case_Initiation_Brief**: An AI-generated document for a proposed sub-case containing proposed charges, key evidence summary, recommended investigative steps, and legal reasoning
- **Network_Graph_Visualization**: An interactive frontend component displaying the conspiracy network as nodes (persons of interest) and edges (relationships), color-coded by Risk_Level
- **Pattern_Detector**: A service component that identifies hidden patterns across financial, communication, geographic, and temporal dimensions within case evidence
- **Primary_Subject**: The main target of investigation in a case, identified as the entity with the highest centrality score or explicitly designated by the investigator
- **Community_Cluster**: A group of tightly connected entities identified by community detection algorithms on the case subgraph, representing a potential conspiracy sub-network
- **Senior_Legal_Analyst_Persona**: The AI reasoning persona used by Amazon Bedrock, instructed to reason as a seasoned federal prosecutor (AUSA) with proper legal terminology, case law citations, and federal sentencing guideline references (reused from prosecutor-case-review)
- **Decision_Workflow**: The three-state human-in-the-loop workflow (AI_Proposed → Human_Confirmed → Human_Overridden) from the prosecutor-case-review spec, applied to every AI-identified person of interest and network finding
- **Conspiracy_Network_Page**: The frontend page (network_discovery.html) accessible from both Investigator and Prosecutor interfaces for viewing network analysis results

## Requirements

### Requirement 1: Automated Network Analysis

**User Story:** As an investigator or prosecutor, I want the system to automatically run graph algorithms on the case knowledge graph and identify clusters of entities forming potential conspiracy networks, so that I can discover co-conspirators and hidden connections without manual graph exploration.

#### Acceptance Criteria

1. WHEN a case is opened in the Conspiracy_Network_Page, THE Network_Discovery_Engine SHALL automatically execute community detection on the case's Neptune subgraph to identify Community_Clusters of tightly connected entities
2. WHEN community detection completes, THE Network_Discovery_Engine SHALL execute centrality scoring (betweenness centrality, degree centrality, and PageRank) on the case's Neptune subgraph to rank entities by structural importance
3. WHEN centrality scoring completes, THE Network_Discovery_Engine SHALL execute anomaly detection on relationship patterns to identify entities with unusual connection patterns relative to the case subgraph baseline
4. THE Network_Discovery_Engine SHALL combine community detection, centrality scoring, and anomaly detection results to produce a ranked list of persons of interest, ordered by Involvement_Score
5. THE Network_Discovery_Engine SHALL compute each Involvement_Score as a weighted composite of five factors: number of connections to the Primary_Subject (weight 0.25), frequency of co-occurrence in documents (weight 0.25), financial transaction patterns (weight 0.20), communication patterns (weight 0.15), and geographic co-location (weight 0.15)
6. WHEN the ranked list of persons of interest is produced, THE Network_Discovery_Engine SHALL invoke Amazon Bedrock with the Senior_Legal_Analyst_Persona to generate a legal reasoning summary for each person explaining why the individual warrants investigation, citing specific evidence and applicable statutes
7. THE Network_Discovery_Engine SHALL create each AI-identified person of interest as an AI_Proposed decision in the Decision_Workflow, requiring human confirmation or override before the person is formally flagged for investigation
8. THE Network_Discovery_Engine SHALL complete analysis for case subgraphs containing up to 100,000 entity nodes within 120 seconds by using batched Gremlin traversals and caching intermediate results

### Requirement 2: Co-Conspirator Profile Generation

**User Story:** As an investigator or prosecutor, I want the system to generate a detailed co-conspirator profile for each identified person of interest, so that I can assess the strength of evidence and determine next investigative steps.

#### Acceptance Criteria

1. WHEN a person of interest is identified by the Network_Discovery_Engine, THE Network_Discovery_Engine SHALL generate a Co_Conspirator_Profile containing the person's name, known aliases, and entity type
2. THE Co_Conspirator_Profile SHALL include a Connection_Strength score (1–100) to the Primary_Subject, computed from Neptune edge weights, shortest path distance, and number of distinct connection paths
3. THE Co_Conspirator_Profile SHALL include an evidence summary listing each document that mentions the person, the context of each mention (extracted via OpenSearch), and the total document count
4. THE Co_Conspirator_Profile SHALL include a relationship map listing all entities the person connects to in the Neptune subgraph, with relationship types and edge weights
5. WHEN the Co_Conspirator_Profile is generated, THE Network_Discovery_Engine SHALL invoke Amazon Bedrock with the Senior_Legal_Analyst_Persona to recommend potential applicable statutes based on the person's evidence pattern, citing specific evidence items and legal reasoning
6. THE Co_Conspirator_Profile SHALL include a Risk_Level classification of High, Medium, or Low, assigned based on the following criteria: High when the person has direct evidence in three or more document types and Connection_Strength above 70, Medium when the person has evidence in two document types or Connection_Strength between 40 and 70, and Low when the person has evidence in one document type and Connection_Strength below 40
7. THE Co_Conspirator_Profile SHALL include a full AI justification paragraph generated by Bedrock, structured as: "[Person] appears in [N] documents, has [M] financial connections to the primary subject, was present at [K] locations during relevant time periods, and is referenced in [J] witness statements. Under [statute citation], their role as [role] is supported by [evidence citations]."

### Requirement 3: Sub-Case Spawning

**User Story:** As a prosecutor, I want the system to propose new sub-cases when a co-conspirator has sufficient evidence for independent investigation, so that I can efficiently manage parallel investigations linked to the parent case.

#### Acceptance Criteria

1. WHEN a Co_Conspirator_Profile has a Risk_Level of High and the profile has been confirmed through the Decision_Workflow as Human_Confirmed, THE Network_Discovery_Engine SHALL propose a Sub_Case for that individual
2. WHEN a Sub_Case is proposed, THE Network_Discovery_Engine SHALL identify and link all relevant evidence from the parent case to the Sub_Case, including documents mentioning the individual, entities connected to the individual, and relationships pertaining to the individual in the Neptune subgraph
3. WHEN a Sub_Case is proposed, THE Network_Discovery_Engine SHALL invoke Amazon Bedrock with the Senior_Legal_Analyst_Persona to generate a Case_Initiation_Brief containing proposed charges with statute citations, a key evidence summary with document references, and recommended investigative steps
4. THE Network_Discovery_Engine SHALL link the Sub_Case to the parent case in the Neptune knowledge graph via cross-case edges using the existing cross_case_service.py infrastructure
5. THE Sub_Case proposal SHALL be created as an AI_Proposed decision in the Decision_Workflow, requiring prosecutor confirmation before the Sub_Case is formally created
6. WHEN a Sub_Case is created, THE Network_Discovery_Engine SHALL copy the relevant subset of the parent case's Neptune subgraph entities and relationships into the Sub_Case's subgraph, preserving provenance links back to the parent case

### Requirement 4: Hidden Pattern Detection

**User Story:** As an investigator, I want the system to automatically detect hidden patterns across financial, communication, geographic, and temporal dimensions within case evidence, so that I can identify suspicious activity that manual review would miss.

#### Acceptance Criteria

1. THE Pattern_Detector SHALL analyze financial entities and relationships in the Neptune subgraph to detect unusual transaction patterns, shell company networks, and money laundering indicators, flagging each pattern with a confidence score (0–100) and linking it to specific evidence documents
2. THE Pattern_Detector SHALL analyze communication entities (phone numbers, email addresses) in the Neptune subgraph to detect frequency anomalies, timing patterns, and encrypted communication indicators, flagging each pattern with a confidence score and linking it to specific evidence documents
3. THE Pattern_Detector SHALL analyze location entities in the Neptune subgraph to detect travel patterns, co-location events (two or more persons of interest at the same location within the same time window), and venue clustering, flagging each pattern with a confidence score and linking it to specific evidence documents
4. THE Pattern_Detector SHALL analyze date and event entities in the Neptune subgraph to detect event clustering, timeline anomalies, and suspicious timing correlations between entities, flagging each pattern with a confidence score and linking it to specific evidence documents
5. WHEN a pattern is detected, THE Pattern_Detector SHALL invoke Amazon Bedrock with the Senior_Legal_Analyst_Persona to generate a reasoning summary explaining the legal significance of the pattern and citing the specific evidence that supports the finding
6. THE Pattern_Detector SHALL create each detected pattern as an AI_Proposed decision in the Decision_Workflow, requiring human confirmation or override before the pattern is included in case analysis reports
7. THE Pattern_Detector SHALL extend the existing pattern_discovery_service.py by adding financial, communication, geographic, and temporal pattern detection methods alongside the existing centrality and community detection capabilities

### Requirement 5: Network Visualization

**User Story:** As an investigator or prosecutor, I want an interactive network graph showing the conspiracy network with color-coded risk levels and filterable relationships, so that I can visually explore connections and drill into individual profiles.

#### Acceptance Criteria

1. THE Conspiracy_Network_Page SHALL display an interactive network graph where nodes represent persons of interest and edges represent relationships (financial, communication, geographic, legal)
2. THE Conspiracy_Network_Page SHALL color-code each node by Risk_Level: red for High, yellow for Medium, and green for Low
3. WHEN a user clicks on a node in the network graph, THE Conspiracy_Network_Page SHALL display the full Co_Conspirator_Profile for that person of interest in a detail panel
4. THE Conspiracy_Network_Page SHALL provide filter controls to filter the network graph by relationship type, time period, and minimum evidence strength (Connection_Strength threshold)
5. THE Conspiracy_Network_Page SHALL reuse the existing Neptune ego graph visualization pattern from the investigator interface (graph_explorer.py) for rendering the network graph
6. THE Conspiracy_Network_Page SHALL display the Decision_Workflow state badge (yellow for AI_Proposed, green for Human_Confirmed, blue for Human_Overridden) on each node in the network graph
7. THE Conspiracy_Network_Page SHALL support graph layouts including force-directed and hierarchical, selectable by the user

### Requirement 6: Investigative Q&A Integration

**User Story:** As an investigator, I want to ask natural-language questions about the conspiracy network through the existing chat interface and receive structured answers with evidence citations, so that I can quickly explore network connections without navigating multiple screens.

#### Acceptance Criteria

1. WHEN an investigator asks a network-related question through the chat interface, THE ChatService SHALL classify the intent and route to network-specific query handlers for questions about persons of interest, connections between individuals, financial links, and travel patterns
2. WHEN the ChatService receives a question matching the pattern "Who is on [subject]'s [list type]?", THE ChatService SHALL query the Network_Discovery_Engine for persons of interest matching the criteria and return a structured list with names, Connection_Strength scores, evidence citation counts, and confidence levels
3. WHEN the ChatService receives a question matching the pattern "Who traveled with [person] to [location]?", THE ChatService SHALL query Neptune for co-location relationships filtered by the specified person and location, and return results with document references
4. WHEN the ChatService receives a question matching the pattern "Show me the financial connections between [Person A] and [Person B]", THE ChatService SHALL query Neptune for financial relationship paths between the two entities and return the graph path with transaction details and document references
5. THE ChatService SHALL format network-related responses as structured data (tables and lists with columns for name, role, evidence count, and confidence) rather than unstructured text paragraphs
6. WHEN the ChatService receives a command matching the pattern "Flag [person] for investigation", THE ChatService SHALL create an AI_Proposed decision in the Decision_Workflow for the specified person and confirm the action to the investigator
7. WHEN the ChatService receives a command matching the pattern "Create sub-case for [person]", THE ChatService SHALL trigger the Sub_Case spawning workflow for the specified person and return the Sub_Case identifier and Case_Initiation_Brief summary
8. THE ChatService SHALL extend the existing chat_service.py by adding new intent patterns and command handlers for network-related queries, without modifying the existing intent classification for non-network queries

### Requirement 7: Human-in-the-Loop Decision Workflow for Network Findings

**User Story:** As a prosecutor, I want every AI-identified person of interest, network pattern, and sub-case proposal to go through the three-state decision workflow with full audit trail, so that I maintain accountability and control over all network analysis conclusions.

#### Acceptance Criteria

1. THE Network_Discovery_Engine SHALL create an AI_Proposed decision in the existing ai_decisions Aurora table for each identified person of interest, each detected pattern, and each proposed Sub_Case, using the decision_type values "person_of_interest", "network_pattern", and "sub_case_proposal" respectively
2. WHEN a prosecutor confirms a person of interest through the Decision_Workflow, THE system SHALL transition the decision to Human_Confirmed and record the confirmation timestamp and confirming attorney identity
3. WHEN a prosecutor overrides a person of interest through the Decision_Workflow, THE system SHALL transition the decision to Human_Overridden and require the prosecutor to enter an override rationale
4. THE Conspiracy_Network_Page SHALL display Accept and Override buttons for each AI_Proposed person of interest, pattern, and Sub_Case proposal, following the same UI pattern as the prosecutor-case-review Evidence Matrix
5. THE system SHALL include the Senior_Legal_Analyst_Persona legal reasoning in every AI_Proposed decision record, so that prosecutors can review the AI's justification before confirming or overriding
6. THE system SHALL reuse the existing DecisionWorkflowService from the prosecutor-case-review spec for all decision state management, extending it only with the new decision_type values specific to network discovery

### Requirement 8: Network Discovery Backend Service

**User Story:** As a system component, I want a backend service that orchestrates graph algorithm execution, involvement scoring, profile generation, and sub-case spawning, so that the frontend and chat interface can access network analysis results through a consistent API.

#### Acceptance Criteria

1. THE Network_Discovery_Engine SHALL be implemented as a new service (network_discovery_service.py) following the existing Protocol/constructor-injection pattern used by entity_resolution_service.py and cross_case_service.py
2. THE Network_Discovery_Engine SHALL accept a case identifier and return a complete network analysis result containing the ranked list of persons of interest with Co_Conspirator_Profiles, detected patterns, and proposed Sub_Cases
3. THE Network_Discovery_Engine SHALL query Neptune using batched Gremlin traversals with the entity_label(case_id) subgraph convention used by all existing services
4. THE Network_Discovery_Engine SHALL query OpenSearch for document co-occurrence data and evidence context using the existing case index naming convention
5. THE Network_Discovery_Engine SHALL query Aurora for case metadata, document records, and entity records using the existing ConnectionManager pattern
6. IF Neptune is unavailable during analysis, THEN THE Network_Discovery_Engine SHALL return a partial result containing only Aurora and OpenSearch-derived findings with a status message indicating that graph analysis is unavailable
7. THE Network_Discovery_Engine SHALL be deployed as an AWS Lambda function accessible via API Gateway, with routes for triggering analysis, retrieving results, and managing individual Co_Conspirator_Profiles
8. THE Network_Discovery_Engine SHALL support incremental analysis: WHEN new evidence is added to a case that has existing network analysis results, THE Network_Discovery_Engine SHALL update the existing analysis with new findings rather than recomputing from scratch

### Requirement 9: Scalability for Large Case Files

**User Story:** As a system operator, I want the network discovery module to handle cases with 3M+ documents and 500TB+ of data without timeout or memory failures, so that the system can analyze large-scale investigations like the Epstein case.

#### Acceptance Criteria

1. THE Network_Discovery_Engine SHALL process case subgraphs containing up to 500,000 entity nodes by using paginated Gremlin traversals that fetch entities in batches of 10,000 nodes
2. THE Network_Discovery_Engine SHALL compute Involvement_Scores using approximate algorithms (approximate betweenness centrality via sampling, approximate PageRank with configurable iteration count) when the case subgraph exceeds 50,000 entity nodes
3. THE Network_Discovery_Engine SHALL cache intermediate analysis results (community clusters, centrality scores, pattern detections) in Aurora to avoid recomputation on subsequent page loads
4. THE Network_Discovery_Engine SHALL support asynchronous analysis execution: WHEN a case subgraph exceeds 50,000 entity nodes, THE Network_Discovery_Engine SHALL return an analysis_status of "processing" and complete the analysis asynchronously, storing results in Aurora for later retrieval
5. IF a Gremlin traversal exceeds the 120-second timeout, THEN THE Network_Discovery_Engine SHALL return partial results from completed algorithm stages and log the timeout for the incomplete stage

### Requirement 10: Network Discovery API Routes

**User Story:** As a system component, I want API Gateway routes for triggering network analysis, retrieving results, and managing co-conspirator profiles, so that the frontend and chat service can interact with the Network_Discovery_Engine.

#### Acceptance Criteria

1. THE API Gateway SHALL expose a POST /case-files/{id}/network-analysis route that triggers network analysis for a case and returns the analysis result or an analysis_status of "processing" for large cases
2. THE API Gateway SHALL expose a GET /case-files/{id}/network-analysis route that retrieves the cached network analysis result for a case, including the ranked list of persons of interest, detected patterns, and proposed Sub_Cases
3. THE API Gateway SHALL expose a GET /case-files/{id}/persons-of-interest route that returns the list of identified persons of interest with their Co_Conspirator_Profiles, filterable by Risk_Level and minimum Involvement_Score
4. THE API Gateway SHALL expose a GET /case-files/{id}/persons-of-interest/{person_id} route that returns the full Co_Conspirator_Profile for a specific person of interest
5. THE API Gateway SHALL expose a POST /case-files/{id}/sub-cases route that creates a Sub_Case for a confirmed person of interest, returning the new case identifier and Case_Initiation_Brief
6. THE API Gateway SHALL expose a GET /case-files/{id}/network-patterns route that returns detected hidden patterns, filterable by pattern type (financial, communication, geographic, temporal)
7. THE API Gateway routes SHALL follow the existing Lambda handler dispatch pattern from the prosecutor-case-review spec, using dispatch_handler(event, context) with _build_*_service() constructors and response_helper for consistent responses
