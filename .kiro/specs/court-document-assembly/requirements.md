# Requirements Document

## Introduction

The Court Document Assembly module is an AI-powered document generation layer that automatically produces court-ready legal documents from case evidence, statutory analysis, and precedent data. It sits primarily on the Prosecutor side of the Research Analyst application, drawing from investigator-gathered evidence stored in the Neptune knowledge graph, OpenSearch vector search, and Aurora PostgreSQL.

The module leverages the prosecutor-case-review spec's Evidence_Matrix, Case_Weakness_Analyzer, Precedent_Analysis_Service, Statute_Library, ai_decisions table, and DecisionWorkflowService. It also draws co-conspirator profiles and sub-case data from the conspiracy-network-discovery spec. Amazon Bedrock generates first drafts of all documents using the Senior_Legal_Analyst_Persona, and every document section flows through the three-state Decision_Workflow (AI_Proposed → Human_Confirmed → Human_Overridden) before finalization.

The module must handle cases with 3M+ documents by querying the indexed knowledge graph and evidence matrix rather than raw documents. Output formats include HTML (preview), PDF (court filing), and DOCX (editing).

## Glossary

- **Document_Assembly_Engine**: The core backend service that orchestrates AI-powered generation of court-ready legal documents from case evidence, statutory analysis, and precedent data
- **Indictment_Generator**: A service component that produces federal indictment documents structured per Federal Rules of Criminal Procedure Rule 7, containing caption, counts, factual basis, overt acts, and forfeiture allegations
- **Evidence_Summary_Report**: A comprehensive report organizing all case evidence by statutory element, including strength ratings, source document references with page numbers, and evidence chain documentation
- **Witness_List_Generator**: A service component that identifies witnesses from Neptune person entities with document co-occurrence and generates anticipated testimony summaries, credibility assessments, and impeachment flags
- **Exhibit_List_Generator**: A service component that produces a numbered exhibit index from case documents, categorized by type and linked to statutory elements with authentication notes
- **Sentencing_Memorandum_Generator**: A service component that produces sentencing memoranda with offense conduct narrative, criminal history, USSG guideline calculations, aggravating and mitigating factors, and government sentencing recommendations
- **Case_Brief_Generator**: A service component that produces internal prosecution memos containing case overview, investigation summary, evidence analysis, legal theory, anticipated defenses, and trial strategy recommendations
- **Discovery_Tracker**: A service component that tracks evidence production to defense counsel, categorizes documents by privilege and disclosure obligation, generates privilege log entries, and tracks production sets
- **Document_Template_System**: A template engine for common court filings (motions, responses, notices) that AI fills with case-specific details from the knowledge graph
- **Document_Section**: An individually reviewable unit of a generated document, each flowing through the three-state Decision_Workflow independently
- **Section_Decision_State**: The current state of a Document_Section in the Decision_Workflow: AI_Proposed (pending review), Human_Confirmed (attorney accepted), or Human_Overridden (attorney edited)
- **Attorney_Sign_Off**: A final approval action by a licensed attorney required before any generated document can be filed with the court, recorded with attorney identity and timestamp
- **Document_Draft**: A versioned instance of a generated document, with each version tracking which sections changed and who made the changes
- **Production_Set**: A batch of documents produced to defense counsel on a specific date, tracked with recipient, date, and document inventory
- **Privilege_Category**: A classification for case documents: Producible, Attorney_Client_Privilege, Work_Product, Brady_Material, or Jencks_Material
- **USSG_Calculator**: A component that computes applicable federal sentencing guideline ranges based on offense level, criminal history category, and specific offense characteristics
- **Court_Filing_Format**: Output formatting conforming to federal court standards including local rules for margins, fonts, line spacing, and page numbering
- **Senior_Legal_Analyst_Persona**: The AI reasoning persona used by Amazon Bedrock, instructed to reason as a seasoned federal prosecutor (AUSA) with proper legal terminology, case law citations, and federal sentencing guideline references (reused from prosecutor-case-review)
- **Decision_Workflow**: The three-state human-in-the-loop workflow (AI_Proposed → Human_Confirmed → Human_Overridden) from the prosecutor-case-review spec, applied to every generated document section

## Requirements

### Requirement 1: Indictment Document Generation

**User Story:** As a prosecutor, I want the system to auto-generate a federal indictment document from the evidence matrix and statute library, so that I can produce a court-ready indictment draft in minutes instead of days of manual preparation.

#### Acceptance Criteria

1. WHEN a prosecutor requests indictment generation for a case with one or more selected statutes, THE Indictment_Generator SHALL produce a complete indictment document structured per Federal Rules of Criminal Procedure Rule 7, containing a caption section, one count section per charge, a factual basis section for each count, an overt acts section, and a forfeiture allegations section
2. THE Indictment_Generator SHALL generate each section using Amazon Bedrock with the Senior_Legal_Analyst_Persona, citing specific evidence items from the Evidence_Matrix by document name and page reference
3. THE Indictment_Generator SHALL populate the caption section with case number, district court, defendant names extracted from Neptune person entities, and applicable statute citations from the Statute_Library
4. THE Indictment_Generator SHALL generate each count section by mapping the statutory elements from the Evidence_Matrix to specific factual allegations, including the date range of the offense, the identity of the defendant, and the specific statutory provision violated
5. THE Indictment_Generator SHALL generate the overt acts section by extracting chronologically ordered events from Neptune date and event entities linked to the defendant, with each overt act citing the supporting evidence document
6. THE Indictment_Generator SHALL generate the forfeiture allegations section by identifying assets and financial entities linked to the defendant in the Neptune knowledge graph and citing the applicable forfeiture statute
7. THE Indictment_Generator SHALL create each generated section as an independent AI_Proposed decision in the Decision_Workflow, allowing the prosecutor to review, confirm, or override each section individually before the document is assembled
8. THE Indictment_Generator SHALL require Attorney_Sign_Off from a licensed attorney before the indictment document is marked as final and available for filing

### Requirement 2: Evidence Summary Report Generation

**User Story:** As a prosecutor or paralegal, I want a comprehensive evidence summary organized by statutory element with strength ratings and source references, so that I can quickly assess the evidentiary support for each element of each charge.

#### Acceptance Criteria

1. WHEN a prosecutor requests an evidence summary report for a case and statute, THE Document_Assembly_Engine SHALL generate an Evidence_Summary_Report organized with one section per statutory element from the selected statute
2. THE Evidence_Summary_Report SHALL include for each statutory element: a list of supporting evidence items, the strength rating (green, yellow, or red) from the Evidence_Matrix, and the source document name with page reference for each evidence item
3. THE Evidence_Summary_Report SHALL include an evidence chain subsection for each evidence item, documenting how the evidence was obtained (source system), when it was processed (ingestion timestamp), and how it was analyzed (entity extraction, AI assessment)
4. THE Evidence_Summary_Report SHALL include AI-generated narrative summaries for each evidence category (documentary, testimonial, physical, digital), produced by Amazon Bedrock with the Senior_Legal_Analyst_Persona
5. THE Document_Assembly_Engine SHALL export the Evidence_Summary_Report in PDF format for court filing and DOCX format for editing
6. THE Document_Assembly_Engine SHALL generate the Evidence_Summary_Report for cases with up to 3,000,000 documents by querying the Evidence_Matrix and Neptune knowledge graph indices rather than scanning raw document content
7. THE Evidence_Summary_Report SHALL create each narrative summary section as an AI_Proposed decision in the Decision_Workflow for prosecutor review

### Requirement 3: Witness List and Testimony Summary Generation

**User Story:** As a prosecutor, I want the system to auto-generate a witness list with anticipated testimony summaries from the case knowledge graph, so that I can prepare for trial without manually reviewing every document for witness references.

#### Acceptance Criteria

1. WHEN a prosecutor requests a witness list for a case, THE Witness_List_Generator SHALL identify witnesses by querying Neptune for person entities that co-occur with case documents, filtering by document co-occurrence count of two or more
2. THE Witness_List_Generator SHALL classify each witness by role: victim, fact witness, expert witness, cooperating witness, or law enforcement, based on entity attributes and relationship types in the Neptune knowledge graph
3. THE Witness_List_Generator SHALL generate for each witness: the witness name, assigned role, an anticipated testimony summary, a list of documents the witness appears in with page references, and a credibility assessment
4. THE Witness_List_Generator SHALL generate anticipated testimony summaries using Amazon Bedrock with the Senior_Legal_Analyst_Persona, synthesizing the content of all documents mentioning the witness
5. THE Witness_List_Generator SHALL flag potential impeachment issues for each witness by querying the Case_Weakness_Analyzer for conflicting statements attributed to that witness
6. WHEN the Case_Weakness_Analyzer identifies conflicting statements for a witness, THE Witness_List_Generator SHALL include the specific conflicting document references and a summary of the inconsistency in the witness record
7. THE Witness_List_Generator SHALL create each anticipated testimony summary and credibility assessment as an AI_Proposed decision in the Decision_Workflow for prosecutor review
8. THE Witness_List_Generator SHALL support cases with up to 500,000 person entities by using paginated Neptune traversals that fetch entities in batches of 10,000

### Requirement 4: Exhibit List and Index Generation

**User Story:** As a prosecutor or paralegal, I want the system to auto-generate a numbered exhibit list from case documents with relevance mapping to statutory elements, so that I can prepare trial exhibits without manually cataloging every document.

#### Acceptance Criteria

1. WHEN a prosecutor requests an exhibit list for a case, THE Exhibit_List_Generator SHALL produce a numbered exhibit index from all case documents stored in Aurora and Neptune
2. THE Exhibit_List_Generator SHALL include for each exhibit: an assigned exhibit number, a description, the source (originating system or custodian), relevance to specific statutory elements from the Evidence_Matrix, and authentication notes
3. THE Exhibit_List_Generator SHALL categorize each exhibit by type: documentary, physical, digital, or testimonial, using Amazon Bedrock with the Senior_Legal_Analyst_Persona to classify based on document metadata and content
4. THE Exhibit_List_Generator SHALL link each exhibit to the statutory elements it supports by querying the element_assessments table for evidence-element mappings rated green or yellow
5. THE Exhibit_List_Generator SHALL generate authentication notes for each exhibit by analyzing the evidence chain metadata (source, ingestion method, processing steps) and flagging exhibits that may require additional foundation testimony
6. THE Exhibit_List_Generator SHALL create each exhibit categorization and authentication note as an AI_Proposed decision in the Decision_Workflow for prosecutor review
7. THE Exhibit_List_Generator SHALL export the exhibit list in PDF and DOCX formats with sequential exhibit numbering

### Requirement 5: Sentencing Memorandum Generation

**User Story:** As a prosecutor, I want the system to auto-generate a sentencing memorandum with guideline calculations and precedent citations, so that I can prepare sentencing recommendations grounded in data rather than starting from a blank page.

#### Acceptance Criteria

1. WHEN a prosecutor requests a sentencing memorandum for a case, THE Sentencing_Memorandum_Generator SHALL produce a document structured with the following sections: introduction, offense conduct narrative, criminal history, sentencing guideline calculations, aggravating factors, mitigating factors, and government sentencing recommendation
2. THE Sentencing_Memorandum_Generator SHALL generate the offense conduct narrative using Amazon Bedrock with the Senior_Legal_Analyst_Persona, synthesizing evidence from the Evidence_Matrix and Neptune knowledge graph into a chronological factual narrative citing specific evidence documents
3. THE USSG_Calculator SHALL compute the applicable sentencing guideline range by determining the base offense level from the statute of conviction, applying specific offense characteristics identified from case evidence, computing the total offense level with adjustments, and cross-referencing with the criminal history category
4. THE Sentencing_Memorandum_Generator SHALL cite specific precedent cases from the Precedent_Analysis_Service, including case name, citation, sentence imposed, and factual similarity to the current case
5. THE Sentencing_Memorandum_Generator SHALL extract aggravating factors from the Evidence_Matrix (evidence of leadership role, vulnerable victims, obstruction) and mitigating factors from case documents (cooperation, acceptance of responsibility, personal history)
6. THE Sentencing_Memorandum_Generator SHALL include a victim impact summary extracted from case documents mentioning victim entities in the Neptune knowledge graph
7. THE Sentencing_Memorandum_Generator SHALL create each generated section as an AI_Proposed decision in the Decision_Workflow for prosecutor review
8. THE Sentencing_Memorandum_Generator SHALL require Attorney_Sign_Off before the memorandum is marked as final

### Requirement 6: Internal Case Brief and Prosecution Memo Generation

**User Story:** As a prosecutor, I want the system to generate a comprehensive internal prosecution memo that synthesizes all case data into a cohesive narrative with risk assessment, so that I can brief supervisors and prepare trial strategy without manually compiling information from multiple sources.

#### Acceptance Criteria

1. WHEN a prosecutor requests a case brief for a case, THE Case_Brief_Generator SHALL produce an internal prosecution memo structured with the following sections: case overview, investigation summary, evidence analysis, legal theory, anticipated defenses, and trial strategy recommendations
2. THE Case_Brief_Generator SHALL generate the case overview section by querying Aurora case metadata, Neptune entity counts, and document statistics to produce a factual summary of the case scope and status
3. THE Case_Brief_Generator SHALL generate the evidence analysis section using Amazon Bedrock with the Senior_Legal_Analyst_Persona, synthesizing the Evidence_Matrix ratings, evidence strength distribution, and evidence gaps into a narrative assessment
4. THE Case_Brief_Generator SHALL generate the anticipated defenses section by querying the Case_Weakness_Analyzer for identified weaknesses and using Amazon Bedrock to predict likely defense arguments based on those weaknesses, with suggested counter-arguments
5. THE Case_Brief_Generator SHALL include a risk assessment section incorporating the Prosecution_Readiness_Score, weakness severity distribution, and an overall case risk rating of Low, Medium, or High
6. THE Case_Brief_Generator SHALL generate trial strategy recommendations using Amazon Bedrock with the Senior_Legal_Analyst_Persona, considering the evidence strength, identified weaknesses, and precedent analysis outcomes
7. THE Case_Brief_Generator SHALL create each generated section as an AI_Proposed decision in the Decision_Workflow for prosecutor review
8. THE Case_Brief_Generator SHALL mark the prosecution memo as internal work product, excluding it from discovery production tracking

### Requirement 7: Discovery Production Tracking

**User Story:** As a prosecutor or paralegal, I want the system to track what evidence has been produced to defense, categorize documents by privilege and disclosure obligation, and generate privilege logs, so that I can meet discovery obligations without manual tracking across thousands of documents.

#### Acceptance Criteria

1. THE Discovery_Tracker SHALL maintain a production status for every case document, tracking whether the document has been produced to defense, is pending review, or is withheld
2. THE Discovery_Tracker SHALL auto-categorize each case document into one of five Privilege_Categories using Amazon Bedrock with the Senior_Legal_Analyst_Persona: Producible, Attorney_Client_Privilege, Work_Product, Brady_Material, or Jencks_Material
3. WHEN a document is categorized as Brady_Material, THE Discovery_Tracker SHALL flag the document with a high-priority disclosure alert and record the flagging timestamp
4. WHEN a document is categorized as Jencks_Material, THE Discovery_Tracker SHALL link the document to the specific witness whose prior statement it contains
5. THE Discovery_Tracker SHALL generate privilege log entries for each withheld document, with AI-drafted privilege descriptions citing the applicable privilege doctrine and the basis for withholding
6. THE Discovery_Tracker SHALL track Production_Sets with the following metadata: production set number, date produced, recipient (defense counsel name), and a list of document identifiers included in the production
7. THE Discovery_Tracker SHALL provide a production status dashboard showing counts of documents in each Privilege_Category, total documents produced, total documents pending, and total documents withheld
8. THE Discovery_Tracker SHALL create each AI-generated privilege categorization as an AI_Proposed decision in the Decision_Workflow, requiring prosecutor confirmation before the categorization is finalized
9. IF a document's Privilege_Category is changed from Producible to a privileged category after it has already been produced, THEN THE Discovery_Tracker SHALL flag a potential waiver issue and alert the prosecutor

### Requirement 8: Document Template System

**User Story:** As a prosecutor, I want a template system for common court filings that AI fills with case-specific details, so that I can quickly generate motions, responses, and notices without retyping boilerplate language.

#### Acceptance Criteria

1. THE Document_Template_System SHALL provide templates for common federal court filings including: motion in limine, motion to compel, response to defense motion, notice of intent to use evidence, and plea agreement
2. THE Document_Template_System SHALL populate template placeholders with case-specific details from the Neptune knowledge graph, Aurora case metadata, and the Evidence_Matrix, including defendant names, case numbers, statute citations, and evidence references
3. THE Document_Template_System SHALL use Amazon Bedrock with the Senior_Legal_Analyst_Persona to generate case-specific legal argument sections within each template, citing relevant case law and statutory authority
4. THE Document_Template_System SHALL format all generated documents according to federal court filing standards, including proper margins, font (Times New Roman 12pt or equivalent), double spacing, and page numbering per local court rules
5. THE Document_Template_System SHALL maintain version control for document drafts, recording each version with a version number, timestamp, author identity, and a summary of changes from the previous version
6. THE Document_Template_System SHALL export generated documents in HTML format for preview, PDF format for court filing, and DOCX format for editing
7. THE Document_Template_System SHALL create each AI-generated legal argument section as an AI_Proposed decision in the Decision_Workflow for prosecutor review
8. THE Document_Template_System SHALL require Attorney_Sign_Off before any template-generated document is marked as final and available for filing

### Requirement 9: Document Assembly Backend Service

**User Story:** As a system component, I want a backend service that orchestrates document generation, section-level decision workflow, version control, and multi-format export, so that the frontend can request and manage document assembly through a consistent API.

#### Acceptance Criteria

1. THE Document_Assembly_Engine SHALL be implemented as a new service (document_assembly_service.py) following the existing Protocol/constructor-injection pattern used by element_assessment_service.py and decision_workflow_service.py
2. THE Document_Assembly_Engine SHALL accept a case identifier, document type, and optional parameters (statute identifier, defendant identifier) and return a Document_Draft containing all generated sections with their Decision_Workflow states
3. THE Document_Assembly_Engine SHALL query the Evidence_Matrix, Case_Weakness_Analyzer, Precedent_Analysis_Service, and Neptune knowledge graph to gather source data for document generation, rather than scanning raw document content
4. THE Document_Assembly_Engine SHALL invoke Amazon Bedrock with the Senior_Legal_Analyst_Persona for each document section, passing structured case data as context and receiving formatted legal prose
5. THE Document_Assembly_Engine SHALL store each Document_Draft in Aurora with version tracking, section-level Decision_Workflow state, and Attorney_Sign_Off status
6. THE Document_Assembly_Engine SHALL support multi-format export by rendering Document_Drafts to HTML (preview), PDF (court filing with Court_Filing_Format), and DOCX (editing)
7. IF Amazon Bedrock is unavailable during document generation, THEN THE Document_Assembly_Engine SHALL return a partial document containing sections that could be generated from structured data (caption, exhibit list, witness list) with a status message indicating that AI-generated narrative sections are unavailable
8. THE Document_Assembly_Engine SHALL be deployed as an AWS Lambda function accessible via API Gateway

### Requirement 10: Document Assembly API Routes

**User Story:** As a system component, I want API Gateway routes for generating documents, managing drafts, tracking discovery production, and exporting final documents, so that the frontend and other services can interact with the Document_Assembly_Engine.

#### Acceptance Criteria

1. THE API Gateway SHALL expose a POST /case-files/{id}/documents/generate route that triggers document generation for a specified document type and returns the Document_Draft with all sections and their Decision_Workflow states
2. THE API Gateway SHALL expose a GET /case-files/{id}/documents route that lists all Document_Drafts for a case, filterable by document type and status (draft, final, archived)
3. THE API Gateway SHALL expose a GET /case-files/{id}/documents/{doc_id} route that returns a specific Document_Draft with all sections, version history, and Decision_Workflow states
4. THE API Gateway SHALL expose a POST /case-files/{id}/documents/{doc_id}/sign-off route that records Attorney_Sign_Off for a document, requiring attorney identity and transitioning the document status to final
5. THE API Gateway SHALL expose a GET /case-files/{id}/documents/{doc_id}/export route that exports a Document_Draft in the requested format (HTML, PDF, or DOCX) specified via a format query parameter
6. THE API Gateway SHALL expose a GET /case-files/{id}/discovery route that returns the discovery production status dashboard with document counts by Privilege_Category and production history
7. THE API Gateway SHALL expose a POST /case-files/{id}/discovery/produce route that creates a new Production_Set, recording the production date, recipient, and list of document identifiers
8. THE API Gateway routes SHALL follow the existing Lambda handler dispatch pattern from the prosecutor-case-review spec, using dispatch_handler(event, context) with _build_*_service() constructors and response_helper for consistent responses

### Requirement 11: Document Assembly Frontend Page

**User Story:** As a prosecutor, I want a dedicated document assembly interface where I can generate, review, edit, and finalize court documents with section-level AI review workflow, so that I can manage the entire document preparation process in one place.

#### Acceptance Criteria

1. THE Document_Assembly_Page SHALL be implemented as document_assembly.html following the same layout patterns as prosecutor.html, accessible from the prosecutor navigation
2. THE Document_Assembly_Page SHALL include a document type selector allowing the prosecutor to choose from: Indictment, Evidence Summary Report, Witness List, Exhibit List, Sentencing Memorandum, Case Brief, and template-based filings
3. THE Document_Assembly_Page SHALL display each generated document with individually expandable sections, where each section shows its Decision_Workflow state badge (yellow for AI_Proposed, green for Human_Confirmed, blue for Human_Overridden)
4. THE Document_Assembly_Page SHALL provide Accept and Override buttons for each document section, following the same UI pattern as the prosecutor-case-review Evidence Matrix decision workflow
5. WHEN a prosecutor overrides a document section, THE Document_Assembly_Page SHALL display an inline text editor pre-populated with the AI-generated content, allowing the prosecutor to edit the section and submit the override with tracked changes
6. THE Document_Assembly_Page SHALL display an Attorney_Sign_Off panel that is enabled only when all sections of a document have been confirmed or overridden, showing the sign-off button with the attorney identity field
7. THE Document_Assembly_Page SHALL include export buttons for HTML preview, PDF download, and DOCX download for each document
8. THE Document_Assembly_Page SHALL include a Discovery Production tab showing the production status dashboard, privilege categorization review interface, and production set management

### Requirement 12: Document Version Control and Audit Trail

**User Story:** As a prosecutor, I want full version history and audit trail for every generated document, so that I can track changes, compare versions, and demonstrate the review process for court proceedings.

#### Acceptance Criteria

1. THE Document_Assembly_Engine SHALL create a new version of a Document_Draft each time any section is confirmed, overridden, or edited, recording the version number, timestamp, author identity, and a list of changed sections
2. THE Document_Assembly_Engine SHALL store the complete content of each document version in Aurora, allowing retrieval of any historical version
3. THE Document_Assembly_Engine SHALL record in the ai_decision_audit_log table every section-level state transition (AI_Proposed to Human_Confirmed, AI_Proposed to Human_Overridden) with the attorney identity, timestamp, and override rationale when applicable
4. THE Document_Assembly_Page SHALL provide a version history panel for each document, showing a chronological list of versions with the author, timestamp, and summary of changes
5. WHEN a prosecutor selects two versions in the version history panel, THE Document_Assembly_Page SHALL display a side-by-side comparison highlighting the differences between the two versions
6. THE Document_Assembly_Engine SHALL retain all document versions and audit records for the lifetime of the case, with no automatic deletion or archival

### Requirement 13: Scalability for Large Cases

**User Story:** As a system operator, I want the document assembly module to generate documents for cases with 3M+ documents without timeout or memory failures, so that the system can handle large-scale investigations.

#### Acceptance Criteria

1. THE Document_Assembly_Engine SHALL generate documents by querying pre-computed data from the Evidence_Matrix, element_assessments table, case_weaknesses table, and precedent_cases table rather than scanning raw document content
2. THE Document_Assembly_Engine SHALL use paginated queries when retrieving evidence items, witness entities, or exhibit records, fetching in batches of 1,000 records per query
3. WHEN a document generation request involves more than 10,000 evidence items, THE Document_Assembly_Engine SHALL return an initial response with status "processing" and complete the generation asynchronously, storing the result in Aurora for later retrieval
4. THE Document_Assembly_Engine SHALL limit Amazon Bedrock context windows to 100,000 tokens per invocation by summarizing large evidence sets into structured data before passing to the model
5. IF a document generation request exceeds the Lambda execution timeout of 900 seconds, THEN THE Document_Assembly_Engine SHALL save the partially generated document with completed sections and a status indicating which sections remain pending
