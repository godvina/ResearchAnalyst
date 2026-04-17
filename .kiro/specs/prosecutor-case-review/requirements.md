# Requirements Document

## Introduction

The Prosecutor Case Review module is the first module in the Prosecutors (DOJ) / Legal section of the Research Analyst application. It provides prosecutors with a comprehensive Case Review & Charging Analysis workspace, parallel to the existing Investigator section. The module enables element-by-element evidence mapping against federal statutes, AI-powered charging decision support, automated case weakness detection, precedent-based case comparison, and a prosecution readiness bridge to the investigator interface. The system leverages the existing Neptune knowledge graph, OpenSearch vector search, Aurora PostgreSQL metadata, and Amazon Bedrock AI analysis infrastructure.

## Glossary

- **Evidence_Matrix**: A grid-based UI component that maps case evidence items (columns) to statutory elements (rows) for a given federal statute, with AI-assessed color-coded support ratings
- **Statutory_Element**: A discrete legal requirement that must be proven to sustain a conviction under a specific federal statute (e.g., "interstate commerce" under 18 U.S.C. § 1591)
- **Statute_Library**: A seed database of common federal statutes and their required elements stored in Aurora PostgreSQL
- **Prosecution_Readiness_Score**: A percentage (0–100) indicating how many statutory elements for a given charge have sufficient supporting evidence
- **Charging_Decision_Workspace**: A UI panel where prosecutors annotate charges, assess risks, track decisions, and export charging memos
- **Case_Weakness_Analyzer**: An automated analysis engine that scans case evidence for credibility issues, missing corroboration, suppression risks, and Brady material
- **Precedent_Matcher**: A service that finds historically similar cases using Neptune entity graph traversal and OpenSearch semantic search
- **Brady_Material**: Exculpatory or impeaching evidence that the prosecution is constitutionally required to disclose to the defense
- **Suppression_Risk**: A flag indicating evidence that may be excluded at trial due to potential Fourth Amendment violations
- **Weakness_Severity**: A classification level for case weaknesses: Critical, Warning, or Info
- **Prosecutor_Page**: The new prosecutor.html frontend page, parallel to the existing investigator.html
- **Investigator_Readiness_Widget**: A UI component added to the existing investigator.html that displays real-time prosecution readiness scores mapped to specific statute elements
- **Element_Assessment_Service**: A backend service that uses Amazon Bedrock to evaluate whether a specific evidence item supports a specific statutory element
- **Precedent_Analysis_Service**: A backend service extending cross_case_service.py to match cases by charge type, evidence patterns, defendant profile, and aggravating/mitigating factors
- **Charging_Memo**: An exportable document summarizing the charging decision, rationale, selected charges, risk assessment, and approving attorney
- **AI_Proposed**: Initial state of an AI recommendation pending human review, displayed with a yellow badge in the Prosecutor_Page
- **Human_Confirmed**: State after a prosecutor accepts an AI recommendation, displayed with a green badge in the Prosecutor_Page
- **Human_Overridden**: State after a prosecutor changes an AI recommendation and provides an override rationale, displayed with a blue badge in the Prosecutor_Page
- **Decision_Audit_Trail**: A complete chronological history of all AI recommendations, human confirmations, and human overrides for a case, stored in the ai_decisions table
- **Senior_Legal_Analyst_Persona**: The AI reasoning persona used by Amazon Bedrock, instructed to write and reason like a seasoned federal prosecutor (AUSA) with proper legal terminology, case law pattern citations, and federal sentencing guideline references

## Requirements

### Requirement 1: Statute Library Management

**User Story:** As a prosecutor, I want a library of federal statutes with their required elements, so that I can select applicable statutes and map evidence to each element.

#### Acceptance Criteria

1. THE Statute_Library SHALL store federal statute records containing the statute citation, title, and an ordered list of required Statutory_Elements
2. THE Statute_Library SHALL be seeded with common federal statutes including 18 U.S.C. § 1591 (Sex Trafficking), 18 U.S.C. § 1341 (Mail Fraud), 18 U.S.C. § 1343 (Wire Fraud), 18 U.S.C. § 2241 (Aggravated Sexual Abuse), 18 U.S.C. § 1951 (Hobbs Act Robbery), and 18 U.S.C. § 846 (Drug Conspiracy)
3. WHEN a prosecutor selects a statute for a case, THE Statute_Library SHALL return the complete list of Statutory_Elements required for conviction under that statute
4. THE Statute_Library SHALL store each Statutory_Element with a unique identifier, display name, and description of what must be proven

### Requirement 2: Element-by-Element Evidence Matrix

**User Story:** As a prosecutor, I want to see a grid mapping evidence to statutory elements for each applicable statute, so that I can assess which elements are supported and which have gaps.

#### Acceptance Criteria

1. WHEN a prosecutor opens a case with a selected statute, THE Evidence_Matrix SHALL display a grid with rows representing Statutory_Elements and columns representing evidence items from the case
2. THE Evidence_Matrix SHALL auto-populate evidence columns from existing case data stored in Neptune entities, Aurora documents, and OpenSearch vectors
3. WHEN the Evidence_Matrix is populated, THE Element_Assessment_Service SHALL use Amazon Bedrock to analyze each evidence-element pair and assign a support rating of green (strong support), yellow (partial support), or red (no support)
4. THE Evidence_Matrix SHALL display each cell with the corresponding color-coded support rating
5. WHEN a prosecutor manually links additional evidence to an element, THE Evidence_Matrix SHALL update the corresponding cell assessment
6. THE Evidence_Matrix SHALL compute and display an overall Prosecution_Readiness_Score as a percentage for each selected statute, calculated as the number of elements rated green or yellow divided by the total number of elements
7. WHEN a case is loaded in the Prosecutor_Page, THE Element_Assessment_Service SHALL automatically run AI analysis using the Senior_Legal_Analyst_Persona to pre-populate the Evidence_Matrix with initial ratings and legal justifications for each evidence-element pair, so that the prosecutor has an expert starting point before manual review
8. THE Evidence_Matrix SHALL display each AI-generated rating with its corresponding legal justification, and each rating SHALL follow the three-state Decision_Audit_Trail workflow (AI_Proposed, Human_Confirmed, Human_Overridden)

### Requirement 3: Charging Decision Workspace

**User Story:** As a prosecutor, I want a workspace to annotate charges, assess risks, and track charging decisions, so that I can document the rationale for each charge and export a formal memo.

#### Acceptance Criteria

1. THE Charging_Decision_Workspace SHALL allow prosecutors to add free-text notes and annotations for each charge under consideration
2. THE Charging_Decision_Workspace SHALL display risk assessment flags including Brady_Material flags, witness credibility scores, and Suppression_Risk indicators for each charge
3. WHEN a primary charge has one or more elements rated red in the Evidence_Matrix, THE Element_Assessment_Service SHALL use Amazon Bedrock to suggest up to five alternative charges ranked by estimated likelihood of conviction
4. THE Charging_Decision_Workspace SHALL record the selected charge, written rationale, and approving attorney name for each charging decision
5. WHEN a prosecutor requests a charging memo export, THE Charging_Decision_Workspace SHALL generate a Charging_Memo document containing the case summary, selected charges, evidence mapping summary, risk assessment, rationale, and approving attorney
6. WHEN sufficient evidence has been mapped to statutory elements for a case, THE Element_Assessment_Service SHALL use the Senior_Legal_Analyst_Persona to draft an initial charging recommendation with full legal reasoning, citing relevant precedent patterns and sentencing guidelines, for the prosecutor to review
7. THE Charging_Decision_Workspace SHALL present the AI-drafted charging recommendation as an AI_Proposed decision, and the prosecutor SHALL confirm or override the recommendation through the three-state Decision_Audit_Trail workflow before the recommendation is finalized

### Requirement 4: Case Weakness Analyzer

**User Story:** As a prosecutor, I want the system to automatically flag weaknesses in my case, so that I can address credibility issues, missing corroboration, suppression risks, and Brady material before trial.

#### Acceptance Criteria

1. WHEN a case is opened in the Prosecutor_Page, THE Case_Weakness_Analyzer SHALL run automatically and produce a list of identified weaknesses
2. THE Case_Weakness_Analyzer SHALL flag witness credibility issues by detecting conflicting statements across documents in the case
3. THE Case_Weakness_Analyzer SHALL flag missing corroboration by identifying critical statutory elements supported by only a single evidence source
4. THE Case_Weakness_Analyzer SHALL flag Suppression_Risks by identifying evidence with potential Fourth Amendment issues using Amazon Bedrock analysis
5. THE Case_Weakness_Analyzer SHALL flag Brady_Material by identifying exculpatory evidence that the defense could use
6. THE Case_Weakness_Analyzer SHALL assign a Weakness_Severity level of Critical, Warning, or Info to each identified weakness
7. THE Case_Weakness_Analyzer SHALL link each identified weakness to the specific evidence items and Statutory_Elements it affects
8. THE Case_Weakness_Analyzer SHALL include legal reasoning in each weakness flag, citing relevant case law or procedural rules that make the weakness legally significant (e.g., citing Brady v. Maryland for disclosure obligations, or Mapp v. Ohio for suppression risks)

### Requirement 5: Case Precedent Analysis

**User Story:** As a prosecutor, I want to find historically similar cases and see sentencing outcomes with specific precedent citations, so that I can make informed charging and plea decisions based on precedent.

#### Acceptance Criteria

1. WHEN a prosecutor requests precedent analysis for a case, THE Precedent_Matcher SHALL find the top 10 matching precedent cases using Neptune entity graph traversal and OpenSearch semantic search
2. THE Precedent_Matcher SHALL match cases by charge type, evidence patterns, defendant profile, and aggravating or mitigating factors
3. THE Precedent_Matcher SHALL return a similarity score (0–100) for each matched precedent case
4. THE Precedent_Analysis_Service SHALL compute a ruling distribution analysis showing percentages for Guilty, Not Guilty, Plea Deal, Dismissed, and Settled outcomes across matched precedents
5. THE Precedent_Analysis_Service SHALL use Amazon Bedrock with the Senior_Legal_Analyst_Persona to generate a sentencing advisory that cites specific precedent cases by name, references applicable federal sentencing guideline sections, and explains the reasoning for the likely sentence, fine or penalty, supervised release recommendation, and precedent match percentage
6. THE Prosecutor_Page SHALL render the precedent analysis using the existing DOJ Case Analysis UI layout from docs/reference-ui/doj-case-analysis.html

### Requirement 6: Investigator-Side Prosecution Readiness Score

**User Story:** As an investigator, I want to see a real-time prosecution readiness score mapped to specific statute elements while building a case, so that I know which elements are covered and which are missing.

#### Acceptance Criteria

1. THE Investigator_Readiness_Widget SHALL be added to the existing investigator.html interface
2. WHILE an investigator is viewing a case, THE Investigator_Readiness_Widget SHALL display the current Prosecution_Readiness_Score for each statute associated with the case
3. THE Investigator_Readiness_Widget SHALL display which Statutory_Elements are covered and which are missing, with a message in the format: "You have N/M elements covered for § XXXX. Missing: [element1], [element2]"
4. WHEN new evidence is added to a case, THE Investigator_Readiness_Widget SHALL recalculate and update the Prosecution_Readiness_Score within 30 seconds
5. THE Investigator_Readiness_Widget SHALL use the Element_Assessment_Service to map evidence to statute elements, extending the existing case_assessment_service.py strength score

### Requirement 7: Prosecutor Frontend Page

**User Story:** As a prosecutor, I want a dedicated frontend page parallel to the investigator interface, so that I can access all prosecution-specific tools in one place.

#### Acceptance Criteria

1. THE Prosecutor_Page SHALL be implemented as prosecutor.html following the same layout patterns as investigator.html
2. THE Prosecutor_Page SHALL include tabbed navigation for Evidence Matrix, Charging Decisions, Case Weaknesses, and Precedent Analysis
3. THE Prosecutor_Page SHALL include a case sidebar listing cases available for prosecution review
4. THE Prosecutor_Page SHALL share the same DOJ header styling and color scheme as the existing investigator.html, using an orange accent color (#f6ad55) to distinguish the prosecutor section from the investigator section (green accent #48bb78)

### Requirement 8: Element Assessment Backend Service

**User Story:** As a system component, I want a backend service that evaluates evidence-element pairs using AI, so that the Evidence Matrix and Readiness Widget can display accurate support ratings.

#### Acceptance Criteria

1. THE Element_Assessment_Service SHALL accept a case identifier, a Statutory_Element identifier, and an evidence item identifier, and return a support rating of green, yellow, or red with a confidence score (0–100) and a reasoning summary
2. THE Element_Assessment_Service SHALL use Amazon Bedrock to analyze the relevance and strength of the evidence item against the Statutory_Element description
3. THE Element_Assessment_Service SHALL reuse the claim decomposition pattern from hypothesis_testing_service.py, treating each Statutory_Element as a testable claim
4. IF Amazon Bedrock is unavailable, THEN THE Element_Assessment_Service SHALL return a rating of yellow with a confidence score of 0 and a reasoning summary indicating that AI analysis is unavailable
5. THE Element_Assessment_Service SHALL be deployed as an AWS Lambda function accessible via API Gateway

### Requirement 9: Precedent Analysis Backend Service

**User Story:** As a system component, I want a backend service that finds matching precedent cases and generates sentencing advisories, so that the Precedent Analysis UI can display relevant comparisons.

#### Acceptance Criteria

1. THE Precedent_Analysis_Service SHALL extend the existing cross_case_service.py entity matching to include case characteristic matching by charge type, evidence patterns, defendant profile, and aggravating or mitigating factors
2. THE Precedent_Analysis_Service SHALL combine Neptune graph-based entity similarity with OpenSearch semantic search similarity to compute a composite similarity score for each precedent case
3. THE Precedent_Analysis_Service SHALL use Amazon Bedrock to generate a sentencing advisory based on the outcomes of matched precedent cases
4. IF fewer than three precedent cases match with a similarity score above 50, THEN THE Precedent_Analysis_Service SHALL include a disclaimer that the advisory is based on limited precedent data
5. THE Precedent_Analysis_Service SHALL be deployed as an AWS Lambda function accessible via API Gateway

### Requirement 10: Case Weakness Analysis Backend Service

**User Story:** As a system component, I want a backend service that analyzes case evidence for weaknesses, so that the Case Weakness Analyzer UI can display actionable flags.

#### Acceptance Criteria

1. THE Case_Weakness_Analyzer SHALL query Aurora documents and Neptune entity relationships to detect conflicting statements across documents attributed to the same witness entity
2. THE Case_Weakness_Analyzer SHALL query the Evidence_Matrix data to identify Statutory_Elements supported by only one evidence source
3. THE Case_Weakness_Analyzer SHALL use Amazon Bedrock to analyze evidence collection methods described in documents and flag potential Fourth Amendment Suppression_Risks
4. THE Case_Weakness_Analyzer SHALL use Amazon Bedrock to identify potential Brady_Material by scanning case evidence for exculpatory content
5. IF the Case_Weakness_Analyzer identifies a weakness with Weakness_Severity of Critical, THEN THE Case_Weakness_Analyzer SHALL include a recommended remediation action in the weakness record
6. THE Case_Weakness_Analyzer SHALL be deployed as an AWS Lambda function accessible via API Gateway

### Requirement 11: AI-First Case Analysis Engine

**User Story:** As a prosecutor, I want AI to automatically analyze a case when it is loaded and make initial recommendations for statutes, evidence mapping, and charging decisions with professional legal justification, so that I have an expert starting point to review and refine.

#### Acceptance Criteria

1. WHEN a case is opened in the Prosecutor_Page, THE Element_Assessment_Service SHALL automatically analyze all case evidence and recommend the most applicable statutes, ranked by strength of evidence match, with a legal justification for each recommendation written using the Senior_Legal_Analyst_Persona
2. WHEN new evidence is added to a case, THE Element_Assessment_Service SHALL automatically categorize the evidence against the selected statute's elements, assign it to the most relevant elements, and provide a brief justification citing the specific evidentiary basis and confidence level (e.g., "Document 'Financial_Records_2019.pdf' mapped to Element 3 (Interstate Commerce) — contains wire transfer records between NY and FL jurisdictions, establishing interstate nexus. Confidence: High.")
3. THE Element_Assessment_Service SHALL generate an initial charging recommendation memo with full legal reasoning, citing relevant precedent patterns and sentencing guidelines, when sufficient evidence has been mapped to statutory elements
4. THE Element_Assessment_Service SHALL use Amazon Bedrock with a system prompt that instructs the model to reason as a senior federal prosecutor (AUSA), using proper legal terminology, citing case law patterns, and referencing federal sentencing guidelines
5. THE Element_Assessment_Service SHALL assign a confidence level of High, Medium, or Low to each recommendation, reflecting the strength of the underlying evidence
6. WHEN the Element_Assessment_Service recommends statutes, THE Element_Assessment_Service SHALL explain why alternative statutes were considered and rejected, providing comparative analysis

### Requirement 12: Human-in-the-Loop Decision Workflow

**User Story:** As a prosecutor, I want to review, confirm, or override every AI recommendation with my own rationale captured, so that I maintain full control and accountability over all case decisions.

#### Acceptance Criteria

1. THE system SHALL track every AI recommendation in one of three states: AI_Proposed (pending human review), Human_Confirmed (prosecutor accepted), or Human_Overridden (prosecutor changed the recommendation)
2. WHEN a prosecutor confirms an AI recommendation, THE system SHALL record the confirmation timestamp and the confirming attorney's identity
3. WHEN a prosecutor overrides an AI recommendation, THE system SHALL require the prosecutor to enter an override rationale explaining why the AI recommendation was changed
4. THE system SHALL store a complete Decision_Audit_Trail of all AI recommendations, human confirmations, and human overrides with timestamps, attorney identity, and rationale in the ai_decisions Aurora table
5. THE Prosecutor_Page SHALL display each AI recommendation with the recommendation text, an expandable Legal Reasoning section containing the full AI justification, an Accept button, an Override button that opens a rationale form, and a confidence indicator badge
6. THE Prosecutor_Page SHALL visually distinguish the three states using color-coded badges: yellow for AI_Proposed, green for Human_Confirmed, and blue for Human_Overridden
7. THE system SHALL allow prosecutors to view the full decision history for any recommendation, showing the original AI proposal, any overrides, and the final decision
