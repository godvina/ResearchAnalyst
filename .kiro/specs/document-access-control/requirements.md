# Requirements: Document Access Control

## Introduction

Adds role-based document access control to the DOJ document analysis platform using hierarchical security labels. Currently, any authenticated user who can reach the API sees all documents across all cases. This MVP introduces a label-based access control model where documents are tagged with security labels at ingestion time, users are assigned clearance levels, and the API layer filters results based on the caller's clearance. Labels are assigned at the case (Matter) level with optional per-document overrides. The model is designed to evolve into a full data governance framework without requiring a rearchitecture.

## Glossary

- **Security_Label**: A classification tag assigned to a case or document indicating its sensitivity level. One of: "public", "restricted", "confidential", "top_secret". Labels form a strict hierarchy where higher levels subsume lower levels.
- **Label_Hierarchy**: The ordered ranking of security labels from least to most sensitive: public (0) < restricted (1) < confidential (2) < top_secret (3). A user with clearance at level N can access all documents at level N and below.
- **Clearance_Level**: A security label assigned to a user that determines the maximum sensitivity of documents the user can access. Uses the same values as Security_Label.
- **Case_Default_Label**: The security label assigned to a Matter (case) that all documents within that case inherit unless individually overridden.
- **Document_Label_Override**: An explicit security label assigned to a specific document that takes precedence over the Case_Default_Label.
- **Effective_Label**: The security label that applies to a given document — the Document_Label_Override if set, otherwise the Case_Default_Label.
- **Access_Control_Middleware**: The API-layer component that intercepts requests, resolves the caller's Clearance_Level, and filters query results to exclude documents with an Effective_Label above the caller's clearance.
- **Label_Audit_Entry**: An immutable record of a label change event, capturing who changed what label, from which value, to which value, and when.
- **Platform_User**: A user record in Aurora storing identity, role, and Clearance_Level for access control enforcement.
- **Default_Label**: The system-wide fallback label applied to cases and documents that have no explicit label assigned. Configurable, defaults to "restricted".

## Requirements

### Requirement 1: Security Label Model

**User Story:** As a platform administrator, I want a hierarchical security label model, so that document sensitivity is classified consistently and access decisions are straightforward.

#### Acceptance Criteria

1. THE System SHALL define exactly four security labels in strict hierarchical order: "public" (level 0), "restricted" (level 1), "confidential" (level 2), "top_secret" (level 3).
2. THE System SHALL store the label hierarchy as an enumerated type in Aurora PostgreSQL with an associated integer rank for comparison operations.
3. WHEN comparing two security labels, THE System SHALL use the integer rank so that a higher rank indicates higher sensitivity.
4. THE System SHALL enforce that every security label value stored in the database is one of the four defined labels.

### Requirement 2: Case-Level Default Label

**User Story:** As a case manager, I want to assign a default security label to a case (Matter), so that all documents ingested into that case automatically inherit the appropriate classification.

#### Acceptance Criteria

1. THE System SHALL add a `security_label` column to the `matters` table, defaulting to the system-wide Default_Label ("restricted").
2. WHEN a new Matter is created without an explicit security_label, THE System SHALL assign the Default_Label.
3. WHEN a Matter's security_label is changed, THE System SHALL NOT retroactively change the Effective_Label of documents that already have a Document_Label_Override.
4. THE System SHALL expose the Matter's security_label in the GET /matters/{id} and GET /case-files/{id} API responses.

### Requirement 3: Document-Level Label Override

**User Story:** As an investigator, I want to override the security label on individual documents, so that I can promote or demote specific documents independently of the case default.

#### Acceptance Criteria

1. THE System SHALL add a `security_label_override` column (nullable) to the `documents` table.
2. WHEN a document has a non-null security_label_override, THE System SHALL use that value as the Effective_Label.
3. WHEN a document has a null security_label_override, THE System SHALL use the parent Matter's security_label as the Effective_Label.
4. THE System SHALL provide a PUT /documents/{id}/security-label endpoint that accepts a `security_label` value and sets the document's security_label_override.
5. THE System SHALL provide a DELETE /documents/{id}/security-label endpoint that clears the document's security_label_override, reverting to the case default.

### Requirement 4: User Clearance Levels

**User Story:** As a platform administrator, I want to assign clearance levels to users, so that each user can only access documents at or below their clearance.

#### Acceptance Criteria

1. THE System SHALL create a `platform_users` table with: user_id (UUID PK), username (unique), display_name, role, clearance_level (security label enum, default "restricted"), created_at, updated_at.
2. THE System SHALL enforce that clearance_level is one of the four defined security labels.
3. THE System SHALL provide CRUD API endpoints for managing platform users: POST /admin/users, GET /admin/users, GET /admin/users/{id}, PUT /admin/users/{id}, DELETE /admin/users/{id}.
4. WHEN a user's clearance_level is updated, THE System SHALL record the change in the audit trail.

### Requirement 5: API-Layer Access Enforcement

**User Story:** As a security officer, I want the API to automatically filter results based on the caller's clearance level, so that users never see documents above their clearance.

#### Acceptance Criteria

1. THE Access_Control_Middleware SHALL resolve the caller's Clearance_Level from the request context (API Gateway authorizer claims or a user-id header mapped to the platform_users table).
2. WHEN any API endpoint returns document data, THE Access_Control_Middleware SHALL exclude documents whose Effective_Label rank exceeds the caller's Clearance_Level rank.
3. THE Access_Control_Middleware SHALL apply filtering to all document-returning endpoints including: GET /case-files/{id}, POST /case-files/{id}/search, GET /case-files/{id}/patterns, POST /case-files/{id}/ingest (response), GET /batch-loader/status, and all drill-down and cross-case endpoints.
4. WHEN a user requests a specific document by ID and the document's Effective_Label exceeds the user's Clearance_Level, THE System SHALL return a 403 Forbidden response.
5. THE Access_Control_Middleware SHALL add a SQL WHERE clause (or post-query filter) using: `COALESCE(d.security_label_override, m.security_label) <= user_clearance_rank` for Aurora queries.
6. IF the caller's identity cannot be resolved, THEN THE System SHALL deny access and return a 401 Unauthorized response.

### Requirement 6: Ingestion-Time Labeling

**User Story:** As a data manager, I want to specify a security label when ingesting documents, so that documents are classified from the moment they enter the system.

#### Acceptance Criteria

1. WHEN creating a new Matter via POST /organizations/{org_id}/matters or POST /case-files, THE System SHALL accept an optional `security_label` parameter.
2. WHEN ingesting documents via POST /case-files/{id}/ingest, THE System SHALL accept an optional `security_label` parameter that sets the Document_Label_Override on each ingested document.
3. WHEN the batch loader processes documents, THE System SHALL accept a `security_label` parameter in the POST /batch-loader/start request body and apply it as the Document_Label_Override on all documents in that batch.
4. WHEN no security_label is provided during ingestion, THE System SHALL leave the Document_Label_Override as null so the document inherits the Case_Default_Label.

### Requirement 7: Search Filtering

**User Story:** As an investigator, I want search results to respect security labels, so that I only see documents I am cleared to access.

#### Acceptance Criteria

1. WHEN performing semantic search via POST /case-files/{id}/search, THE System SHALL filter results to exclude documents whose Effective_Label exceeds the caller's Clearance_Level.
2. WHEN performing pattern discovery via POST /case-files/{id}/patterns, THE System SHALL exclude entities and relationships sourced exclusively from documents above the caller's Clearance_Level.
3. WHEN performing cross-case analysis via POST /cross-case/analyze, THE System SHALL apply label filtering independently to each case's documents.
4. WHEN querying Neptune for knowledge graph data, THE System SHALL cross-reference entity source_document_refs against the caller's accessible document set and exclude entities that have no accessible source documents.

### Requirement 8: Case Label Management

**User Story:** As a case manager, I want to view and change the default security label on a case, so that I can adjust classification as the investigation evolves.

#### Acceptance Criteria

1. THE System SHALL provide a PUT /matters/{id}/security-label endpoint that accepts a `security_label` value and updates the Matter's Case_Default_Label.
2. WHEN the Case_Default_Label is changed, THE System SHALL record a Label_Audit_Entry with: matter_id, previous_label, new_label, changed_by, changed_at.
3. THE System SHALL include the current security_label in all Matter list and detail API responses.
4. WHEN the Case_Default_Label is changed, THE System SHALL NOT modify any existing Document_Label_Override values.

### Requirement 9: Audit Trail

**User Story:** As a compliance officer, I want an immutable audit trail of all label changes, so that I can demonstrate chain of custody and review access control decisions.

#### Acceptance Criteria

1. THE System SHALL create a `label_audit_log` table with: audit_id (UUID PK), entity_type ("matter" or "document"), entity_id (UUID), previous_label, new_label, changed_by, changed_at, change_reason (optional text).
2. WHEN a Matter's security_label is changed, THE System SHALL insert a Label_Audit_Entry.
3. WHEN a document's security_label_override is set or cleared, THE System SHALL insert a Label_Audit_Entry.
4. WHEN a user's clearance_level is changed, THE System SHALL insert a Label_Audit_Entry with entity_type "user".
5. THE System SHALL provide a GET /admin/audit-log endpoint with filters for entity_type, entity_id, changed_by, and date range.
6. THE label_audit_log table SHALL be append-only — no UPDATE or DELETE operations SHALL be permitted on audit records.

### Requirement 10: Admin UI for Access Control Management

**User Story:** As a platform administrator, I want a UI to manage users, roles, clearance levels, and case labels, so that I can administer access control without direct database access.

#### Acceptance Criteria

1. THE System SHALL provide an admin page (admin.html) with sections for: user management, case label management, and audit log viewing.
2. THE admin page SHALL display a table of platform users with columns: username, display_name, role, clearance_level, and action buttons for edit and delete.
3. THE admin page SHALL provide a form to create new users with: username, display_name, role, and clearance_level fields.
4. THE admin page SHALL display a table of Matters with their current security_label and provide inline editing to change the label.
5. THE admin page SHALL display the audit log in reverse chronological order with filtering controls.

### Requirement 11: Backward Compatibility

**User Story:** As a platform operator, I want existing unlabeled data to work seamlessly with the new access control system, so that the platform continues functioning without a manual data migration.

#### Acceptance Criteria

1. THE database migration SHALL set the security_label column on all existing matters to the Default_Label ("restricted").
2. THE database migration SHALL leave security_label_override as null on all existing documents, so they inherit the case default.
3. ALL existing API endpoints SHALL continue to function for users with "restricted" or higher clearance without any client-side changes.
4. WHEN the Access_Control_Middleware encounters a request without user identity information, THE System SHALL fall back to treating the caller as having "restricted" clearance during a configurable transition period.
5. THE System SHALL support a configuration flag `ACCESS_CONTROL_ENABLED` (default true) that, when set to false, disables label filtering so the system behaves as before.

### Requirement 12: Schema Migration

**User Story:** As a platform operator, I want the access control schema applied as a non-breaking migration, so that existing data and services continue to work.

#### Acceptance Criteria

1. THE migration SHALL add the `security_label` column (TEXT, default "restricted") to the `matters` table.
2. THE migration SHALL add the `security_label_override` column (TEXT, nullable) to the `documents` table.
3. THE migration SHALL create the `platform_users` table as specified in Requirement 4.
4. THE migration SHALL create the `label_audit_log` table as specified in Requirement 9.
5. THE migration SHALL backfill all existing matters with security_label = "restricted".
6. THE migration SHALL create indexes on: documents(security_label_override), platform_users(username), label_audit_log(entity_type, entity_id), label_audit_log(changed_at).
7. ALL existing tables (organizations, matters, collections, documents, case_files) SHALL remain structurally intact apart from the new columns.

### Requirement 13: Pluggable Access Policy Provider

**User Story:** As a platform architect, I want the access control middleware to use a pluggable policy provider interface, so that customers can integrate their existing identity and governance systems (Active Directory, OIDC, AWS Verified Permissions, OPA) without refactoring the middleware.

#### Acceptance Criteria

1. THE System SHALL define an `AccessPolicyProvider` abstract interface with a single method: `check_access(user_context: dict, resource_context: dict) -> AccessDecision` where `AccessDecision` contains `allowed: bool` and `reason: str`.
2. THE System SHALL ship with a `LabelBasedProvider` as the default implementation that compares the user's Clearance_Level rank against the document's Effective_Label rank.
3. THE Access_Control_Middleware SHALL resolve access decisions by calling the configured `AccessPolicyProvider` rather than hardcoding label comparison logic.
4. THE System SHALL support configuring the active provider via an environment variable `ACCESS_POLICY_PROVIDER` (default "label_based"), enabling future providers like "oidc_claims", "verified_permissions", or "external_api" to be swapped in without code changes to the middleware.
5. THE `user_context` dict SHALL contain at minimum: user_id, username, clearance_level, role, and groups (list of group names, empty by default). The `resource_context` dict SHALL contain: document_id, case_id, effective_label, and security_label_override.
6. THE `LabelBasedProvider` SHALL ignore the groups field and base its decision solely on clearance_level vs effective_label rank comparison, consistent with Requirements 1 and 5.
7. THE System SHALL log every access denial (provider returned `allowed=False`) to the label_audit_log with entity_type "access_denied", including the user_id, resource_id, and the provider's reason string.
