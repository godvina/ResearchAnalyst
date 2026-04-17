# Investigative Intelligence Platform — Data Governance & Access Control

**Document Version:** 1.0
**Date:** April 14, 2026
**Author:** Emerging Tech Solutions
**Classification:** AWS Internal / NDA

---

## Executive Summary

The Investigative Intelligence Platform processes sensitive evidence — documents, financial records, images, and entity relationships — using AI-powered analysis on AWS. Data governance is a first-class architectural concern, not an afterthought. The platform is designed with defense-in-depth: encryption at every layer, network isolation, label-based access control, immutable audit trails, and a config-driven deployment system that enforces compliance controls appropriate to each environment.

This document describes the data governance architecture as built, the two primary access control models available for customer deployment, and the questions needed to determine the right approach for a given agency.

---

## 1. Data Residency & Isolation

All data processing occurs entirely within the customer's AWS account. No data leaves the account boundary.

| Principle | Implementation |
|-----------|---------------|
| Data stays in-account | All storage (S3, Aurora, Neptune) is deployed within the customer's VPC and AWS account. No cross-account data sharing. |
| No public internet egress for data | Bedrock LLM calls route through VPC Interface Endpoints (AWS PrivateLink). Document content never traverses the public internet. |
| Region-bound | All resources deploy to a single region. GovCloud deployments use `us-gov-west-1`. No cross-region replication unless explicitly configured. |
| Partition-aware | IAM policies use `${AWS::Partition}` for ARN construction, supporting both commercial (`aws`) and GovCloud (`aws-us-gov`) partitions from a single codebase. |

### Network Isolation

- All databases (Aurora, Neptune) reside in private subnets with no public IP addresses.
- Lambda functions execute within the VPC and access AWS services exclusively through VPC Endpoints.
- Security groups enforce least-privilege network access between Lambda functions and data stores.
- VPC Flow Logs capture all network traffic for forensic analysis (enabled via deployment config).

---

## 2. Encryption

| Layer | Mechanism | Configuration |
|-------|-----------|---------------|
| S3 (data lake) | SSE-S3 (demo) or SSE-KMS with customer-managed CMK (production) | Config-driven: `encryption.kms_key_arn` |
| Aurora (PostgreSQL) | Encrypted at rest via AWS-managed or customer-managed KMS key | Enabled by default on Aurora Serverless v2 |
| Neptune (knowledge graph) | Encrypted at rest via KMS | Enabled by default on Neptune Serverless |
| Secrets Manager | Encrypted with KMS | AWS-managed or customer CMK |
| In transit | TLS 1.2+ enforced on all connections | Config-driven: `encryption.enforce_tls` |
| Bedrock API calls | TLS via VPC PrivateLink | Automatic — VPC endpoint enforces TLS |
| CloudTrail logs | Optional KMS encryption | Config-driven: `encryption.kms_key_arn` |
| Lambda DLQ (SQS) | Optional KMS encryption | Config-driven: `encryption.kms_key_arn` |

In production (GovCloud Tier 3), all encryption uses customer-managed KMS keys. The customer retains full control over key rotation, access policies, and key deletion.

---

## 3. Access Control Models

The platform supports two access control approaches. The right choice depends on the customer's organizational structure, existing identity infrastructure, and the sensitivity of the data being analyzed.

### Option A: Label-Based Access Control (Currently Implemented)

Label-based access control assigns a security classification to every document and entity, then compares it against the user's clearance level at query time.

**How it works:**

1. Every document has a `security_label` (PUBLIC, RESTRICTED, CONFIDENTIAL, TOP_SECRET) assigned during ingestion or by an administrator.
2. Documents can have a `security_label_override` that takes precedence over the base label.
3. Each user has a `clearance_level` in their profile (same four-tier hierarchy).
4. At query time, the platform computes `effective_label = COALESCE(security_label_override, security_label)` for each document.
5. The access policy provider compares: if `user.clearance_level >= document.effective_label`, access is granted. Otherwise, the document is filtered from results and the denial is logged to the immutable audit trail.

**Architecture:**

```
API Request → Access Control Middleware → Resolve User Identity
                                              ↓
                                        User Context (clearance, role, groups)
                                              ↓
                                        Execute Query → Raw Results
                                              ↓
                                        Label-Based Filter (per document)
                                              ↓
                                        Filtered Results → Response
                                              ↓ (on denial)
                                        Audit Log (immutable)
```

**Components built:**

- `SecurityLabel` enum: PUBLIC(0) < RESTRICTED(1) < CONFIDENTIAL(2) < TOP_SECRET(3)
- `AccessControlService`: Resolves user identity, filters documents, builds SQL filter clauses
- `LabelBasedProvider`: Pluggable policy provider that compares clearance rank vs. effective label rank
- `AccessControlMiddleware`: Lambda decorator that injects user context into every API request
- `AuditService`: Immutable append-only audit trail for label changes and access denials
- Kill switch: `ACCESS_CONTROL_ENABLED` environment variable for gradual rollout
- Transition period: `TRANSITION_PERIOD_ENABLED` flag allows fallback to restricted-clearance anonymous access during migration

**Strengths:**
- Simple to understand and implement
- Maps naturally to government classification hierarchies (UNCLASSIFIED → SECRET → TOP SECRET)
- Document-level granularity
- No database schema changes required — labels are metadata columns on existing tables
- Pluggable provider architecture allows swapping in custom access policies

**Limitations:**
- Coarse-grained: a user either sees a document or doesn't. No partial access.
- Doesn't natively support team-based or case-based isolation (e.g., "only the Epstein task force can see Epstein case data").
- Label assignment is manual or rule-based — requires a classification workflow.

---

### Option B: Row-Level Security (RLS) — Recommended for Production

Row-Level Security enforces access control at the database layer. PostgreSQL's native RLS policies filter rows before they reach the application, providing defense-in-depth that cannot be bypassed by application bugs.

**How it would work:**

1. Aurora PostgreSQL RLS policies are defined on the `documents`, `entities`, and `case_files` tables.
2. Each row includes ownership metadata: `case_id`, `team_id`, or `classification_level`.
3. The application sets a session variable (e.g., `SET app.current_user_id = 'analyst-001'`) at connection time via RDS Proxy.
4. PostgreSQL evaluates RLS policies on every SELECT, INSERT, UPDATE, DELETE — the application never sees rows the user isn't authorized for.
5. Combined with label-based control for classification-level filtering.

**Example RLS policy:**

```sql
-- Users can only see documents in cases they are assigned to
CREATE POLICY case_member_access ON documents
    FOR SELECT
    USING (
        case_file_id IN (
            SELECT case_id FROM case_assignments
            WHERE user_id = current_setting('app.current_user_id')
        )
    );

-- Combine with classification label check
CREATE POLICY classification_access ON documents
    FOR SELECT
    USING (
        security_label <= (
            SELECT clearance_level FROM platform_users
            WHERE user_id = current_setting('app.current_user_id')
        )
    );
```

**Strengths:**
- Database-enforced — cannot be bypassed by application code
- Supports team-based, case-based, and classification-based isolation simultaneously
- Fine-grained: different policies for SELECT vs. INSERT vs. UPDATE
- Native PostgreSQL feature — no custom middleware required for enforcement
- Scales to multi-tenant deployments where teams must not see each other's cases

**Limitations:**
- Requires schema additions (`case_assignments` table, session variable management)
- More complex to configure and test
- RDS Proxy session pinning considerations for `SET` commands
- Requires careful policy design to avoid performance impact on large tables

---

### Option C: Hybrid (Recommended)

Combine both approaches for defense-in-depth:

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Database | Row-Level Security | Case-based and team-based isolation. Users only see cases they're assigned to. |
| Application | Label-Based Access Control | Classification-level filtering within accessible cases. Handles edge cases like label overrides and cross-case analysis. |
| API | Authentication + RBAC | Identity verification and role-based feature access (Investigator, Analyst, Admin, Read-Only). |
| Audit | Immutable Audit Trail | All access decisions, label changes, and denials logged for compliance. |

---

## 4. Discovery Questions for the Customer

Use these questions to determine the right access control model and data governance requirements:

### Organizational Structure

1. **How many distinct teams or task forces will use the platform simultaneously?**
   - Single team → Label-based access control may be sufficient.
   - Multiple teams with case isolation requirements → Row-Level Security is needed.

2. **Do teams need to be prevented from seeing each other's cases, or is cross-case visibility acceptable?**
   - Strict isolation → RLS with case-based policies.
   - Shared visibility with classification controls → Label-based is sufficient.

3. **What roles exist in your investigative workflow?** (e.g., Lead Investigator, Analyst, Prosecutor, Read-Only Reviewer, Administrator)
   - This determines the RBAC role hierarchy.

### Classification & Sensitivity

4. **Does your agency use a formal classification hierarchy for evidence?** (e.g., UNCLASSIFIED, CUI, SECRET, TOP SECRET)
   - If yes → Map directly to the platform's SecurityLabel hierarchy.
   - If no → Define a custom label set during deployment.

5. **Can classification labels change over time?** (e.g., evidence reclassified during investigation)
   - If yes → The platform's label override and audit trail support this natively.

6. **Are there documents that specific individuals must never see, regardless of their clearance level?** (e.g., conflict-of-interest exclusions)
   - If yes → RLS with user-level exclusion policies, not just clearance-based.

### Identity & Authentication

7. **What identity provider does your agency use?** (e.g., AWS SSO, Okta, Azure AD, PIV/CAC card via SAML)
   - This determines the API Gateway authentication integration (Cognito, IAM, or custom authorizer).

8. **Do users authenticate with PIV/CAC smart cards?**
   - If yes → SAML federation through the agency's IdP into Cognito or IAM.

9. **Is there an existing user directory we should integrate with, or should the platform manage its own user registry?**
   - Existing directory → Federated identity with attribute mapping.
   - Self-managed → Platform's `platform_users` table with admin UI.

### Compliance & Audit

10. **What audit retention requirements apply?** (e.g., 7 years for federal records)
    - Determines CloudTrail log retention, audit table archival policy, and S3 lifecycle rules.

11. **Do you require audit logs to be tamper-evident?** (e.g., signed, write-once storage)
    - If yes → CloudTrail log file validation + S3 Object Lock (WORM).

12. **Are there specific NIST 800-53 controls that must be documented?**
    - The platform addresses AC (Access Control), AU (Audit), SC (System Communications), IA (Identification/Authentication), MP (Media Protection), and SI (System Integrity).

### Data Lifecycle

13. **What is the expected data retention period for ingested evidence?**
    - Determines S3 lifecycle policies and Aurora archival strategy.

14. **Is there a requirement to purge or redact data after a case is closed?**
    - If yes → Implement case archival workflow with cascading deletes across Aurora, Neptune, and S3.

15. **Can AI-generated analysis (theories, case files, entity extractions) be deleted independently of source evidence?**
    - This affects the data model relationship between source documents and derived intelligence.

---

## 5. Audit Trail Architecture

The platform maintains an immutable, append-only audit trail for all security-relevant events.

### What is audited:

| Event | Details Captured |
|-------|-----------------|
| Document access granted | User ID, document ID, case ID, clearance level, timestamp |
| Document access denied | User ID, document ID, reason (e.g., "clearance_restricted_insufficient_for_top_secret"), timestamp |
| Security label changed | Entity type, entity ID, previous label, new label, changed by, reason, timestamp |
| AI decision proposed | Decision ID, case ID, decision type, AI rationale, confidence score |
| AI decision confirmed | Decision ID, confirming attorney/analyst, timestamp |
| AI decision overridden | Decision ID, overriding user, new rationale, timestamp |

### Audit integrity:

- The `label_audit_log` table is append-only. No UPDATE or DELETE operations are exposed through the service layer.
- Each entry has a UUID `audit_id` and UTC timestamp.
- Entries are queryable by entity type, entity ID, user, and date range.
- In production, CloudTrail provides a second independent audit layer for all AWS API calls.

### Human-in-the-Loop Decision Audit:

AI-generated decisions (entity classifications, theory assessments, recommended actions) follow a three-state workflow:

```
AI_Proposed → Human_Confirmed → (final)
           → Human_Overridden → (final, with rationale)
```

Every state transition is logged with the actor, timestamp, and rationale. This ensures that no AI-generated conclusion is treated as authoritative without human review — a critical requirement for investigative and legal contexts.

---

## 6. AI Data Governance

### Bedrock Data Processing

- All Bedrock inference calls use VPC PrivateLink endpoints. Document content is sent to Bedrock for entity extraction and embedding generation but never leaves the AWS network.
- Bedrock does not store or train on customer data (per AWS Bedrock service terms).
- The platform uses on-demand inference, not fine-tuned models. No customer data is used to customize model weights.
- Model selection is config-driven. Production deployments restrict to FedRAMP-High approved models only. The `config/bedrock_models.json` registry tracks model compliance status and allows provider exclusion per customer policy.

### AI-Generated Content Governance

- All AI-generated analysis (theories, case files, intelligence briefings) is clearly attributed as AI-generated in the UI and data model.
- AI outputs are stored separately from source evidence in dedicated tables (`theories`, `theory_case_files`, `investigator_analysis_cache`).
- The human-in-the-loop decision workflow ensures AI conclusions require human confirmation before being treated as findings.
- Investigators can edit, override, or reject any AI-generated content.

---

## 7. Infrastructure Security Controls

These controls are config-driven and enforced at deployment time:

| Control | Demo (Tier 1) | GovCloud Production (Tier 3) | Config Key |
|---------|---------------|-------------------------------|------------|
| VPC isolation | Public subnets | Private subnets + NAT | `vpc.subnet_type` |
| Encryption at rest | AWS-managed | Customer KMS CMK | `encryption.kms_key_arn` |
| TLS enforcement | Default | Enforced (TLS 1.2+) | `encryption.enforce_tls` |
| VPC Flow Logs | Disabled | Enabled | `logging.vpc_flow_logs` |
| CloudTrail | Disabled | Enabled | `logging.cloudtrail` |
| API throttling | 100 burst / 50 rps | Configurable | `api.throttle_burst_limit` |
| CORS origins | All origins | Restricted to frontend domain | `api.cors_allow_origins` |
| S3 removal policy | DESTROY (dev cleanup) | RETAIN (data protection) | `s3.removal_policy` |
| Bedrock IAM scope | Wildcard (`foundation-model/*`) | Specific model ARNs | `bedrock.llm_model_id` |
| API access logging | Disabled | Enabled (CloudWatch) | `api.access_logging` |
| Lambda DLQ | Disabled | Enabled (SQS) | Automatic in production |
| X-Ray tracing | Disabled | Enabled | Automatic in production |
| Resource tagging | Environment only | Compliance=FedRAMP-High, DataClassification=CUI | `tags` |

---

## 8. Compliance Alignment

| NIST 800-53 Control Family | Platform Implementation |
|----------------------------|------------------------|
| AC (Access Control) | Label-based access control, RBAC roles, API Gateway authentication, RLS (roadmap) |
| AU (Audit & Accountability) | Immutable audit trail, CloudTrail, API Gateway access logs, VPC Flow Logs |
| SC (System & Communications Protection) | TLS 1.2+ enforced, VPC isolation, private subnets, VPC endpoints (PrivateLink) |
| IA (Identification & Authentication) | Secrets Manager for DB credentials, Cognito/SAML federation (roadmap), PIV/CAC support (roadmap) |
| MP (Media Protection) | KMS encryption at rest (S3, Aurora, Neptune), S3 bucket policies denying non-TLS |
| SI (System & Information Integrity) | AWS-managed Lambda runtime (no custom OS), parameterized SQL (no injection), HTML escaping |
| CM (Configuration Management) | Config-driven CDK deployment, version-controlled infrastructure as code |
| CP (Contingency Planning) | S3 removal policy RETAIN, Aurora automated backups, multi-AZ deployment |

---

## 9. Recommendation

For a federal investigative agency with multiple teams working on separate cases:

**Deploy the Hybrid model (Option C):**
1. Row-Level Security at the database layer for case-based team isolation
2. Label-Based Access Control at the application layer for classification filtering
3. Cognito or SAML-federated authentication at the API layer
4. Immutable audit trail across all layers

This provides defense-in-depth where no single layer failure can expose unauthorized data. The label-based access control is already implemented and tested. Row-Level Security and authentication are the two remaining production hardening items, estimated at 2-3 weeks of development.

---

*This document is intended for internal AWS and customer stakeholder review. It describes architectural capabilities and design decisions, not a certified compliance assessment.*
