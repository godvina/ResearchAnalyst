# Requirements Document

## Introduction

The Proof Engine evaluates whether findings from the Taxonomy Engine meet a configurable standard of proof. It sits downstream of pattern detection and ACH (Analysis of Competing Hypotheses) scoring, acting as the final quality gate before a finding is marked as proven, unproven, or insufficient. Different investigation types demand different evidentiary standards — a scientific claim requires falsifiability and replication, a criminal finding requires chain of custody and corroboration, while a journalistic finding requires two independent sources and right of reply. The Proof Engine generates a checklist of required evidence items for the selected standard, scores each item against available evidence using Bedrock Claude Sonnet, and produces a structured verdict with reasoning. Verdicts are stored in Aurora and exposed via API for downstream consumption by frontends, reports, and cross-tenant pattern detection.

## Glossary

- **Proof_Engine**: The subsystem that evaluates findings against a configurable standard of proof, generating evidence checklists, scores, and verdicts
- **Standard_of_Proof**: A named evidentiary framework defining what constitutes sufficient proof for a given domain (e.g., scientific, criminal_legal, intelligence)
- **Evidence_Checklist**: A list of required evidence items generated for a specific finding + standard combination, where each item represents one criterion that must be satisfied
- **Checklist_Item**: A single evidence requirement within a checklist, containing a description, weight, and critical flag
- **Critical_Item**: A checklist item marked as mandatory — if unsatisfied, no positive verdict can be issued regardless of overall score
- **Verdict**: The final determination for a finding: PROVEN, UNPROVEN, or INSUFFICIENT_EVIDENCE
- **Finding**: A pattern match, cross-theory connection, or analytical conclusion produced by the Taxonomy Engine or Cross-Pattern Agent
- **Overall_Score**: The weighted sum of all checklist item scores for a given finding evaluation, ranging from 0.0 to 1.0
- **Proof_Threshold**: The minimum overall score required for a PROVEN verdict (defined per standard)
- **Tenant**: An isolated research community within the platform, each with its own default proof standard and configuration
- **Re_Evaluation**: The process of re-scoring a finding when new evidence becomes available, generating a new verdict that supersedes the previous one

## Requirements

### Requirement 1: Standard of Proof Registry

**User Story:** As a platform operator, I want a registry of configurable proof standards, so that each investigation type applies the evidentiary framework appropriate to its domain.

#### Acceptance Criteria

1. THE Proof_Engine SHALL support a minimum of 6 named Standards_of_Proof: `scientific`, `criminal_legal`, `civil_legal`, `intelligence`, `financial_audit`, and `journalistic`
2. WHEN a Standard_of_Proof is registered, THE Proof_Engine SHALL store its definition containing: standard_name, description, checklist_item_definitions (array), item_weights (array), critical_item_flags (array), and proof_threshold (float between 0.0 and 1.0)
3. THE Proof_Engine SHALL store all Standard_of_Proof definitions in a `proof_standards` table in Aurora PostgreSQL with a JSONB column for checklist_item_definitions
4. WHEN a new Standard_of_Proof is added to the `proof_standards` table, THE Proof_Engine SHALL make it available for selection without requiring code changes or redeployment
5. THE Proof_Engine SHALL allow Standards_of_Proof to be selected per tenant via tenant configuration, and per investigation type within a tenant
6. WHEN a Standard_of_Proof definition is updated, THE Proof_Engine SHALL NOT retroactively change existing verdicts but SHALL apply the updated definition only to new evaluations

### Requirement 2: Evidence Checklist Generation

**User Story:** As a research analyst, I want the system to generate a specific evidence checklist for each finding based on the selected proof standard, so that I know exactly what evidence is required to prove or disprove the finding.

#### Acceptance Criteria

1. WHEN a finding is submitted for evaluation with the `scientific` standard, THE Proof_Engine SHALL generate a checklist containing: falsifiable hypothesis stated, statistical significance demonstrated, replication by independent party, peer critique addressed, and alternative explanations eliminated
2. WHEN a finding is submitted for evaluation with the `criminal_legal` standard, THE Proof_Engine SHALL generate a checklist containing: chain of custody documented, independent corroboration obtained, no credible alternative explanation, consistent witness statements, and evidence authenticated
3. WHEN a finding is submitted for evaluation with the `civil_legal` standard, THE Proof_Engine SHALL generate a checklist containing: balance of probability established, positive evidence presented, and more likely than not demonstrated
4. WHEN a finding is submitted for evaluation with the `intelligence` standard, THE Proof_Engine SHALL generate a checklist containing: minimum source count met, source independence verified, diagnostic evidence identified, alternative hypotheses eliminated, and confidence level assigned
5. WHEN a finding is submitted for evaluation with the `financial_audit` standard, THE Proof_Engine SHALL generate a checklist containing: materiality threshold exceeded, substantive testing performed, adequate sampling achieved, and management assertion consistency verified
6. WHEN a finding is submitted for evaluation with the `journalistic` standard, THE Proof_Engine SHALL generate a checklist containing: two independent sources confirmed, subject right of reply offered, legal review completed, and public interest established
7. WHEN a checklist is generated, THE Proof_Engine SHALL associate each item with the weight and critical flag defined in the Standard_of_Proof registry for that standard

### Requirement 3: Evidence Evaluation and Scoring

**User Story:** As a research analyst, I want each evidence checklist item automatically scored against available evidence, so that I get an objective assessment of how well a finding meets its proof standard.

#### Acceptance Criteria

1. WHEN an Evidence_Checklist is generated for a finding, THE Proof_Engine SHALL score each Checklist_Item as: satisfied (1.0), partial (0.5), or unsatisfied (0.0) based on the available evidence associated with that finding
2. THE Proof_Engine SHALL perform scoring by invoking Amazon Bedrock Claude Sonnet with a prompt containing the checklist item description, the finding details, and all available evidence, requesting a score and justification
3. WHEN all Checklist_Items are scored, THE Proof_Engine SHALL calculate the Overall_Score as the weighted sum of item scores divided by the sum of all weights, producing a value between 0.0 and 1.0
4. IF a Checklist_Item is marked as a Critical_Item in the Standard_of_Proof definition, THEN THE Proof_Engine SHALL require that item to score 1.0 (satisfied) for any PROVEN verdict regardless of the Overall_Score
5. WHEN scoring is complete, THE Proof_Engine SHALL store per-item scores with justification text (maximum 500 characters per item) explaining why each score was assigned
6. THE Proof_Engine SHALL complete evaluation of a single finding (checklist generation + scoring + verdict) within 30 seconds of initiation

### Requirement 4: Verdict Generation

**User Story:** As a research analyst, I want a clear verdict for each finding with structured reasoning, so that I can understand not just the conclusion but the evidence basis behind it.

#### Acceptance Criteria

1. WHEN the Overall_Score is greater than or equal to the Proof_Threshold AND all Critical_Items score 1.0 (satisfied), THE Proof_Engine SHALL assign the verdict PROVEN
2. WHEN the available evidence actively contradicts the finding (as determined by Bedrock Claude Sonnet analysis), THE Proof_Engine SHALL assign the verdict UNPROVEN regardless of the Overall_Score
3. WHEN the Overall_Score is below the Proof_Threshold AND the evidence does not actively contradict the finding, THE Proof_Engine SHALL assign the verdict INSUFFICIENT_EVIDENCE
4. WHEN a verdict is assigned, THE Proof_Engine SHALL generate structured reasoning containing: the verdict, the Overall_Score, a list of satisfied items with justifications, a list of unsatisfied or partial items with justifications, and which Critical_Items (if any) were not met
5. WHEN a verdict of INSUFFICIENT_EVIDENCE is assigned, THE Proof_Engine SHALL include in the reasoning a list of specific evidence items that, if obtained, would move the finding toward PROVEN
6. THE Proof_Engine SHALL NOT assign a verdict of PROVEN if any Critical_Item scores below 1.0, even if the Overall_Score exceeds the Proof_Threshold

### Requirement 5: Storage and API

**User Story:** As a frontend developer, I want verdict data stored persistently and accessible via REST API, so that dashboards and reports can display proof status for any finding.

#### Acceptance Criteria

1. THE Proof_Engine SHALL store verdicts in Aurora PostgreSQL in a `proof_verdicts` table with columns: id (UUID), finding_id (UUID), standard_used (VARCHAR), checklist_items (JSONB), scores (JSONB), overall_score (FLOAT), verdict (VARCHAR), reasoning (JSONB), evaluated_at (TIMESTAMP), and tenant_id (VARCHAR)
2. THE Proof_Engine SHALL expose a GET endpoint at `/proof/{finding_id}` that returns the most recent verdict for the specified finding including: verdict, overall_score, standard_used, checklist_items with scores, reasoning, and evaluated_at
3. THE Proof_Engine SHALL expose a POST endpoint at `/proof/evaluate` that accepts a JSON body containing finding_id (required) and standard_override (optional), triggers evaluation, and returns the generated verdict
4. WHEN a POST to `/proof/evaluate` is received with a standard_override, THE Proof_Engine SHALL use the overridden standard instead of the tenant default for that evaluation
5. WHEN new evidence becomes available for a finding that has a previous verdict, THE Proof_Engine SHALL support re-evaluation via the POST `/proof/evaluate` endpoint, storing the new verdict alongside (not replacing) the previous verdict
6. WHEN GET `/proof/{finding_id}` is called for a finding with multiple evaluations, THE Proof_Engine SHALL return the most recent verdict by default, with an optional `?history=true` parameter to return all historical verdicts ordered by evaluated_at descending

### Requirement 6: Tenant Configuration

**User Story:** As a platform operator, I want each tenant to declare its default proof standard, so that findings are automatically evaluated against the appropriate evidentiary framework without manual selection.

#### Acceptance Criteria

1. THE Proof_Engine SHALL read tenant configuration from `src/config/tenants/{tenant_name}.json` where each file contains a `default_proof_standard` field specifying one of the registered Standards_of_Proof
2. WHEN the `ancient_mysteries` tenant submits a finding for evaluation without a standard override, THE Proof_Engine SHALL apply the `scientific` standard
3. WHEN the `conspiracy_theories` tenant submits a finding for evaluation without a standard override, THE Proof_Engine SHALL apply the `intelligence` standard
4. WHEN the `crime` tenant submits a finding for evaluation without a standard override, THE Proof_Engine SHALL apply the `criminal_legal` standard
5. WHEN a POST to `/proof/evaluate` includes a standard_override field, THE Proof_Engine SHALL use the specified standard regardless of the tenant's default configuration
6. IF a tenant configuration file does not contain a `default_proof_standard` field, THEN THE Proof_Engine SHALL default to the `intelligence` standard and log a warning indicating the tenant has no configured proof standard
