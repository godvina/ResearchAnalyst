# Requirements Document

## Introduction

The Investigator AI-First module enhances the existing investigator interface (investigator.html) with an AI-first, human-in-the-loop pattern mirroring the prosecutor-case-review spec. When an investigator loads a case, AI automatically analyzes all ingested evidence and presents a comprehensive case briefing with ranked findings, investigative leads, evidence triage, hypotheses, and subpoena recommendations. The investigator confirms or overrides every AI recommendation through the three-state Decision_Workflow (AI_Proposed → Human_Confirmed → Human_Overridden) reused from the prosecutor-case-review spec.

The module focuses on building the case from the investigator's perspective — discovering leads, triaging evidence, generating hypotheses, and recommending legal process — rather than the prosecutor's focus on charging decisions and statutory element mapping. It extends the existing chat_service.py, hypothesis_testing_service.py, case_assessment_service.py, and pattern_discovery_service.py, and reuses the DecisionWorkflowService and ai_decisions table from the prosecutor-case-review spec.

The system leverages the existing Neptune knowledge graph (77K+ entities, 1.87M+ edges, scaling to millions), OpenSearch Serverless for vector search, Aurora PostgreSQL for metadata, and Amazon Bedrock (Claude) for AI analysis. The module must scale to cases with 3M+ documents.

## Glossary

- **Investigator_AI_Engine**: The core backend service that orchestrates automatic case analysis on load, producing a comprehensive AI briefing with ranked findings, leads, hypotheses, and recommendations from the investigator's perspective
- **Case_Briefing**: A structured AI-generated summary presented when an investigator opens a case, containing document analysis statistics, persons of interest count, financial patterns, communication networks, geographic clusters, key findings ranked by significance, strongest investigative leads, evidence gaps, and recommended next steps
- **Investigative_Lead**: A ranked item representing a promising direction for investigation, scored by evidence strength, connection density, novelty, and prosecution readiness, with AI justification and recommended investigative actions
- **Lead_Priority_Score**: A composite score (0–100) ranking an investigative lead by four weighted factors: evidence strength (0.30), connection density (0.25), novelty (0.25), and prosecution readiness (0.20)
- **Evidence_Triage_Result**: A structured classification of a newly ingested document containing document type, identified entities and relationships, high-priority findings, links to existing investigative threads, and prosecution readiness impact assessment
- **Document_Type_Classification**: A category assigned to each document during triage: financial_record, communication, legal_filing, witness_statement, law_enforcement_report, media_report, or other
- **Investigative_Hypothesis**: A proactive AI-generated hypothesis based on evidence patterns, containing the hypothesis statement, supporting evidence citations, confidence level (High, Medium, Low), and recommended investigative actions
- **Subpoena_Recommendation**: An AI-generated recommendation for a subpoena or warrant, containing the target (person, organization, or record type), custodian, legal basis with evidence citations, expected evidentiary value (High, Medium, Low), and priority ranking
- **Session_Briefing**: An AI-generated summary of changes since the investigator's last session, including new findings, updated scores, new leads, and recommended next actions
- **Evidence_Coverage_Map**: A visual representation showing which investigative areas (people, organizations, financial connections, communications, physical evidence, timeline, geographic scope) are well-covered versus gaps
- **Senior_Legal_Analyst_Persona**: The AI reasoning persona used by Amazon Bedrock, instructed to reason as a seasoned federal investigative analyst with proper legal terminology, evidence citation practices, and investigative methodology references (reused from prosecutor-case-review)
- **Decision_Workflow**: The three-state human-in-the-loop workflow (AI_Proposed → Human_Confirmed → Human_Overridden) from the prosecutor-case-review spec, applied to every AI finding, lead, triage decision, hypothesis, and recommendation
- **DecisionWorkflowService**: The existing backend service from the prosecutor-case-review spec that manages decision state transitions and audit trail in the ai_decisions Aurora table
- **Structured_Chat_Response**: A chat response formatted as tables, lists, or entity cards rather than unstructured text paragraphs
- **Action_Trigger**: A command issued through the chat interface that creates a tracked action in the Decision_Workflow, such as flagging a person, creating a lead, or generating a subpoena list

## Requirements

### Requirement 1: AI Case Briefing on Load

**User Story:** As an investigator, I want AI to automatically analyze all ingested evidence when I open a case and present a comprehensive briefing with key findings, so that I have an expert starting point before manual review.

#### Acceptance Criteria

1. WHEN an investigator opens a case in the investigator interface, THE Investigator_AI_Engine SHALL automatically analyze all case evidence from Neptune, OpenSearch, and Aurora and produce a Case_Briefing within 60 seconds for cases with up to 100,000 documents
2. THE Case_Briefing SHALL include document analysis statistics (total documents analyzed, entity counts by type, relationship counts), persons of interest count, financial pattern count, communication network count, and geographic cluster count
3. THE Case_Briefing SHALL include key findings ranked by significance, where significance is determined by evidence strength, novelty, and connection density computed from the Neptune knowledge graph
4. THE Case_Briefing SHALL include the three strongest investigative leads with AI justification citing specific evidence documents and entity connections
5. THE Case_Briefing SHALL include identified evidence gaps by comparing entity types present in the case against expected entity types for the investigation category
6. THE Case_Briefing SHALL include recommended next steps as actionable investigative actions, each linked to specific evidence gaps or leads
7. THE Investigator_AI_Engine SHALL use Amazon Bedrock with the Senior_Legal_Analyst_Persona to generate the Case_Briefing narrative, citing specific documents and entities by name
8. THE Investigator_AI_Engine SHALL create each key finding and recommended next step as an AI_Proposed decision in the Decision_Workflow, requiring investigator confirmation or override
9. IF Amazon Bedrock is unavailable during case load, THEN THE Investigator_AI_Engine SHALL produce a partial Case_Briefing containing only statistics and entity counts derived from Aurora and Neptune queries, with a status message indicating that AI analysis is unavailable

### Requirement 2: AI-Driven Lead Prioritization

**User Story:** As an investigator, I want AI to rank investigative leads by priority based on evidence strength, connection density, novelty, and prosecution readiness, so that I can focus on the most promising directions first.

#### Acceptance Criteria

1. WHEN the Case_Briefing is generated, THE Investigator_AI_Engine SHALL produce a ranked list of Investigative_Leads ordered by Lead_Priority_Score
2. THE Investigator_AI_Engine SHALL compute each Lead_Priority_Score as a weighted composite of four factors: evidence strength (weight 0.30, measured as the number of documents supporting the lead divided by total case documents, capped at 1.0), connection density (weight 0.25, measured as the entity's degree centrality in the Neptune subgraph normalized to 0–1), novelty (weight 0.25, measured as 1.0 minus the ratio of previously flagged evidence to total evidence for the lead), and prosecution readiness (weight 0.20, derived from the existing Prosecution_Readiness_Score for statutes associated with the case)
3. THE Investigator_AI_Engine SHALL include for each Investigative_Lead: the lead subject (entity name and type), the Lead_Priority_Score, an AI justification paragraph citing specific evidence documents and entity connections, and a list of recommended investigative actions
4. THE Investigator_AI_Engine SHALL create each Investigative_Lead as an AI_Proposed decision in the Decision_Workflow with decision_type "investigative_lead"
5. WHEN an investigator confirms or overrides a lead priority, THE system SHALL record the decision through the DecisionWorkflowService with the investigator's identity and override rationale when applicable
6. WHEN new evidence is added to a case, THE Investigator_AI_Engine SHALL recalculate Lead_Priority_Scores for affected leads and create updated AI_Proposed decisions for leads whose score changed by more than 10 points

### Requirement 3: Automated Evidence Triage

**User Story:** As an investigator, I want AI to automatically classify, link, and prioritize new evidence as it is ingested, so that I can immediately understand the impact of each new document without manual review.

#### Acceptance Criteria

1. WHEN a new document is ingested into a case (uploaded and entity-extracted), THE Investigator_AI_Engine SHALL automatically produce an Evidence_Triage_Result for the document
2. THE Evidence_Triage_Result SHALL include a Document_Type_Classification assigned by Amazon Bedrock based on document content and metadata, classifying the document as one of: financial_record, communication, legal_filing, witness_statement, law_enforcement_report, media_report, or other
3. THE Evidence_Triage_Result SHALL include a list of key entities and relationships identified in the document, linked to existing entities in the Neptune knowledge graph
4. THE Evidence_Triage_Result SHALL include high-priority findings flagged by Amazon Bedrock, such as direct admissions, financial irregularities, or contradictions with existing evidence, with each finding citing the specific document passage
5. THE Evidence_Triage_Result SHALL include links to existing investigative threads by matching new entities and relationships against existing Investigative_Leads
6. THE Evidence_Triage_Result SHALL include a prosecution readiness impact assessment indicating whether the new document strengthens, weakens, or has no effect on the current Prosecution_Readiness_Score for each associated statute
7. THE Investigator_AI_Engine SHALL create each Document_Type_Classification and each high-priority finding as an AI_Proposed decision in the Decision_Workflow with decision_type "evidence_triage"
8. WHEN an investigator overrides a Document_Type_Classification, THE system SHALL update the classification and record the override rationale through the DecisionWorkflowService

### Requirement 4: Investigative Hypothesis Generation

**User Story:** As an investigator, I want AI to proactively generate investigative hypotheses based on evidence patterns, so that I can discover non-obvious connections and pursue leads that manual review might miss.

#### Acceptance Criteria

1. WHEN the Case_Briefing is generated, THE Investigator_AI_Engine SHALL produce a list of Investigative_Hypotheses based on patterns detected in the Neptune knowledge graph and OpenSearch document corpus
2. THE Investigator_AI_Engine SHALL generate hypotheses for financial patterns (money laundering indicators, shell company networks, unusual transaction patterns), communication patterns (frequency anomalies, timing correlations, network clustering), geographic patterns (co-location events, travel patterns), and temporal patterns (event clustering, timeline anomalies)
3. THE Investigator_AI_Engine SHALL include for each Investigative_Hypothesis: the hypothesis statement, a list of supporting evidence citations (document names and entity references), a confidence level of High, Medium, or Low, and a list of recommended investigative actions (subpoenas, record requests, interviews)
4. THE Investigator_AI_Engine SHALL extend the existing hypothesis_testing_service.py by adding a generate_hypotheses method that uses Amazon Bedrock with the Senior_Legal_Analyst_Persona to propose hypotheses from pattern data, complementing the existing evaluate method that tests investigator-stated hypotheses
5. THE Investigator_AI_Engine SHALL create each Investigative_Hypothesis as an AI_Proposed decision in the Decision_Workflow with decision_type "investigative_hypothesis"
6. WHEN an investigator confirms a hypothesis, THE system SHALL transition the decision to Human_Confirmed and add the hypothesis to the active investigation threads
7. WHEN an investigator overrides a hypothesis, THE system SHALL record the override rationale and mark the hypothesis as dismissed in the Decision_Workflow

### Requirement 5: Smart Subpoena and Warrant Recommendations

**User Story:** As an investigator, I want AI to recommend subpoenas and warrants based on evidence gaps and investigative leads, so that I can efficiently pursue the legal process needed to fill evidence gaps.

#### Acceptance Criteria

1. WHEN the Case_Briefing is generated, THE Investigator_AI_Engine SHALL produce a list of Subpoena_Recommendations based on identified evidence gaps and active Investigative_Leads
2. THE Investigator_AI_Engine SHALL include for each Subpoena_Recommendation: the target (person name, organization name, or record type), the custodian (entity holding the records), the legal basis citing specific existing evidence documents and applicable statutes, the expected evidentiary value rated as High, Medium, or Low, and a priority ranking
3. THE Investigator_AI_Engine SHALL generate Subpoena_Recommendations using Amazon Bedrock with the Senior_Legal_Analyst_Persona, citing specific evidence gaps and explaining how the requested records would address those gaps
4. THE Investigator_AI_Engine SHALL extend the existing chat_service.py subpoena_list intent handler to incorporate AI-generated recommendations from the Investigator_AI_Engine rather than generating recommendations only from the chat prompt context
5. THE Investigator_AI_Engine SHALL create each Subpoena_Recommendation as an AI_Proposed decision in the Decision_Workflow with decision_type "subpoena_recommendation"
6. WHEN an investigator confirms a Subpoena_Recommendation, THE system SHALL transition the decision to Human_Confirmed and make the recommendation available for export as a structured subpoena request document
7. WHEN new evidence is added that addresses an existing Subpoena_Recommendation's evidence gap, THE Investigator_AI_Engine SHALL update the recommendation's priority and expected evidentiary value

### Requirement 6: AI-Enhanced Case Progress Dashboard

**User Story:** As an investigator, I want an enhanced dashboard with AI-generated insights showing case strength, evidence coverage, timeline, and session changes, so that I can quickly assess case status and know where to focus next.

#### Acceptance Criteria

1. THE investigator interface SHALL display the existing case strength score from case_assessment_service.py alongside an AI-generated narrative explaining the score's basis, citing specific evidence strengths and weaknesses
2. THE investigator interface SHALL display an Evidence_Coverage_Map showing coverage status (covered or gap) for each investigative area: people, organizations, financial connections, communication patterns, physical evidence, timeline, and geographic scope, reusing the existing _compute_evidence_coverage method from case_assessment_service.py
3. THE investigator interface SHALL display an auto-generated timeline of key events extracted from date and event entities in the Neptune knowledge graph, ordered chronologically with linked source documents
4. THE investigator interface SHALL display a Session_Briefing summarizing changes since the investigator's last session, including new findings count, updated lead scores, new evidence ingested, and recommended next actions
5. THE investigator interface SHALL display the Prosecution_Readiness_Score widget from the prosecutor-case-review spec (Requirement 6), showing per-statute readiness scores and missing statutory elements
6. THE Investigator_AI_Engine SHALL generate the case strength narrative and Session_Briefing using Amazon Bedrock with the Senior_Legal_Analyst_Persona
7. THE Investigator_AI_Engine SHALL create the AI-generated case strength narrative as an AI_Proposed decision in the Decision_Workflow with decision_type "case_narrative"
8. WHEN new evidence is added to a case, THE investigator interface SHALL update the Evidence_Coverage_Map and case strength score within 30 seconds

### Requirement 7: Enhanced Ad-Hoc Q&A

**User Story:** As an investigator, I want the chat interface to return structured responses, support action triggers, maintain context-aware follow-ups, and query the knowledge graph directly, so that I can investigate efficiently without switching between multiple tools.

#### Acceptance Criteria

1. THE ChatService SHALL format responses for entity-related queries as Structured_Chat_Responses containing tables with columns for entity name, entity type, document count, and connection count, rather than unstructured text paragraphs
2. THE ChatService SHALL support Action_Triggers from chat messages matching the patterns "Flag [entity]", "Create lead for [entity]", and "Generate subpoena list for [entity]", where each action creates an AI_Proposed decision in the Decision_Workflow
3. WHEN an Action_Trigger is executed, THE ChatService SHALL confirm the action to the investigator with a structured response showing the created decision identifier, decision type, and current state (AI_Proposed)
4. THE ChatService SHALL maintain context-aware follow-ups by tracking the current investigation focus (active entity, active lead, active hypothesis) in the conversation context and tailoring responses to reference the current focus
5. THE ChatService SHALL support network-aware queries matching the pattern "Who else was at [location] on [date]?" by querying Neptune for co-location relationships filtered by location and date entities, returning results with document references
6. THE ChatService SHALL support evidence-aware queries matching the pattern "What documents mention both [entity A] and [entity B]?" by querying OpenSearch for documents containing both entities, returning results with relevance scores and excerpts
7. THE ChatService SHALL extend the existing chat_service.py by adding new intent patterns and command handlers for structured responses, action triggers, network-aware queries, and evidence-aware queries, without modifying the existing intent classification for non-enhanced queries
8. WHEN an Action_Trigger creates a decision through the Decision_Workflow, THE ChatService SHALL include the decision state badge color (yellow for AI_Proposed) in the chat response

### Requirement 8: Human-in-the-Loop for All AI Decisions

**User Story:** As an investigator, I want every AI finding, lead, triage decision, hypothesis, and recommendation tracked through a three-state decision workflow with full audit trail, so that I maintain accountability and control over all AI-assisted conclusions.

#### Acceptance Criteria

1. THE system SHALL reuse the existing DecisionWorkflowService and ai_decisions Aurora table from the prosecutor-case-review spec for all investigator AI decisions, extending the decision_type values to include "case_briefing_finding", "investigative_lead", "evidence_triage", "investigative_hypothesis", "subpoena_recommendation", and "case_narrative"
2. THE system SHALL track every AI recommendation in one of three states: AI_Proposed (pending investigator review), Human_Confirmed (investigator accepted), or Human_Overridden (investigator changed the recommendation)
3. WHEN an investigator confirms an AI recommendation, THE DecisionWorkflowService SHALL record the confirmation timestamp and the confirming investigator's identity
4. WHEN an investigator overrides an AI recommendation, THE DecisionWorkflowService SHALL require the investigator to enter an override rationale explaining why the AI recommendation was changed
5. THE investigator interface SHALL display each AI recommendation with the recommendation text, an expandable AI Reasoning section containing the full justification, an Accept button, an Override button that opens a rationale form, and a confidence indicator badge
6. THE investigator interface SHALL visually distinguish the three states using color-coded badges: yellow for AI_Proposed, green for Human_Confirmed, and blue for Human_Overridden
7. THE system SHALL store a complete Decision_Audit_Trail of all AI recommendations, human confirmations, and human overrides with timestamps, investigator identity, and rationale in the existing ai_decision_audit_log Aurora table

### Requirement 9: Investigator AI Engine Backend Service

**User Story:** As a system component, I want a backend service that orchestrates automatic case analysis, lead prioritization, evidence triage, hypothesis generation, and subpoena recommendations, so that the investigator frontend and chat interface can access AI-first analysis through a consistent API.

#### Acceptance Criteria

1. THE Investigator_AI_Engine SHALL be implemented as a new service (investigator_ai_engine.py) following the existing Protocol/constructor-injection pattern used by hypothesis_testing_service.py and case_assessment_service.py
2. THE Investigator_AI_Engine SHALL accept a case identifier and return a complete analysis result containing the Case_Briefing, ranked Investigative_Leads, Investigative_Hypotheses, and Subpoena_Recommendations
3. THE Investigator_AI_Engine SHALL query Neptune using batched Gremlin traversals with the entity_label(case_id) subgraph convention used by all existing services
4. THE Investigator_AI_Engine SHALL query OpenSearch for document context and evidence retrieval using the existing case index naming convention
5. THE Investigator_AI_Engine SHALL query Aurora for case metadata, document records, entity records, and existing assessment data using the existing ConnectionManager pattern
6. THE Investigator_AI_Engine SHALL coordinate with the existing case_assessment_service.py for strength scoring and evidence coverage, hypothesis_testing_service.py for hypothesis evaluation, pattern_discovery_service.py for pattern detection, and the DecisionWorkflowService for decision tracking
7. IF Neptune is unavailable during analysis, THEN THE Investigator_AI_Engine SHALL return a partial result containing only Aurora and OpenSearch-derived findings with a status message indicating that graph analysis is unavailable
8. THE Investigator_AI_Engine SHALL be deployed as an AWS Lambda function accessible via API Gateway

### Requirement 10: Investigator AI API Routes

**User Story:** As a system component, I want API Gateway routes for triggering AI analysis, retrieving briefings, managing leads, and handling evidence triage, so that the frontend and chat service can interact with the Investigator_AI_Engine.

#### Acceptance Criteria

1. THE API Gateway SHALL expose a POST /case-files/{id}/investigator-analysis route that triggers full AI analysis for a case and returns the Case_Briefing with all AI_Proposed decisions
2. THE API Gateway SHALL expose a GET /case-files/{id}/investigator-analysis route that retrieves the cached analysis result for a case, including the Case_Briefing, Investigative_Leads, Investigative_Hypotheses, and Subpoena_Recommendations
3. THE API Gateway SHALL expose a GET /case-files/{id}/investigative-leads route that returns the ranked list of Investigative_Leads, filterable by minimum Lead_Priority_Score and decision state (ai_proposed, human_confirmed, human_overridden)
4. THE API Gateway SHALL expose a GET /case-files/{id}/evidence-triage route that returns Evidence_Triage_Results for recently ingested documents, filterable by Document_Type_Classification and decision state
5. THE API Gateway SHALL expose a GET /case-files/{id}/ai-hypotheses route that returns Investigative_Hypotheses, filterable by confidence level and decision state
6. THE API Gateway SHALL expose a GET /case-files/{id}/subpoena-recommendations route that returns Subpoena_Recommendations, filterable by priority and decision state
7. THE API Gateway SHALL expose a GET /case-files/{id}/session-briefing route that returns the Session_Briefing for the current investigator, computed from changes since the investigator's last recorded session timestamp
8. THE API Gateway routes SHALL follow the existing Lambda handler dispatch pattern from the prosecutor-case-review spec, using dispatch_handler(event, context) with _build_*_service() constructors and response_helper for consistent responses

### Requirement 11: Investigator Frontend AI Enhancement

**User Story:** As an investigator, I want the existing investigator.html interface enhanced with AI briefing panels, lead management, evidence triage views, hypothesis cards, and subpoena recommendation lists, so that I can access all AI-first capabilities without leaving the investigator interface.

#### Acceptance Criteria

1. THE investigator interface SHALL add a new "AI Briefing" tab that displays the Case_Briefing when a case is loaded, including statistics, key findings, top leads, evidence gaps, and recommended next steps
2. THE investigator interface SHALL add a new "Leads" tab that displays the ranked list of Investigative_Leads with Lead_Priority_Score bars, AI justification expandable sections, recommended actions, and Accept/Override buttons following the Decision_Workflow pattern
3. THE investigator interface SHALL add a new "Evidence Triage" tab that displays Evidence_Triage_Results for recently ingested documents, showing Document_Type_Classification badges, identified entities, high-priority findings, and linked investigative threads with Accept/Override buttons
4. THE investigator interface SHALL add a new "Hypotheses" tab that displays Investigative_Hypotheses with confidence level badges, supporting evidence citations, recommended actions, and Accept/Override buttons
5. THE investigator interface SHALL add a new "Subpoenas" tab that displays Subpoena_Recommendations with target, custodian, legal basis, expected value badges, and Accept/Override buttons
6. THE investigator interface SHALL display Decision_Workflow state badges on all AI recommendations: yellow for AI_Proposed, green for Human_Confirmed, and blue for Human_Overridden
7. THE investigator interface SHALL maintain the existing tabs (Case Dashboard, Graph Explorer, Pipeline Monitor, Chatbot) and add the new AI-first tabs alongside them
8. THE investigator interface SHALL use the existing green accent color (#48bb78) for all new AI-first components, maintaining visual consistency with the existing investigator interface

### Requirement 12: Scalability for Large Cases

**User Story:** As a system operator, I want the investigator AI module to analyze cases with 3M+ documents without timeout or memory failures, so that the system can handle large-scale investigations.

#### Acceptance Criteria

1. THE Investigator_AI_Engine SHALL generate the Case_Briefing by querying pre-computed data from the existing pattern_reports, case_hypotheses, and entity tables rather than scanning raw document content
2. THE Investigator_AI_Engine SHALL use paginated queries when retrieving entities, documents, or relationships, fetching in batches of 1,000 records per query
3. WHEN a case analysis request involves more than 100,000 documents, THE Investigator_AI_Engine SHALL return an initial response with status "processing" and complete the analysis asynchronously, storing the result in Aurora for later retrieval
4. THE Investigator_AI_Engine SHALL limit Amazon Bedrock context windows to 100,000 tokens per invocation by summarizing large evidence sets into structured data before passing to the model
5. THE Investigator_AI_Engine SHALL cache analysis results in Aurora and serve cached results on subsequent page loads, recomputing only when new evidence has been added since the last analysis
