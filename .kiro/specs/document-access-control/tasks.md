# Implementation Plan: Document Access Control

## Overview

Adds hierarchical security-label-based access control to the DOJ document analysis platform. Implementation proceeds in dependency order: security label model and provider interface, then schema migration, then core services (AuditService, AccessControlService, middleware), then handler integration, then ingestion updates, then admin handler and frontend. Each step builds on the previous and wires into existing code.

## Tasks

- [x] 1. Security label model, provider interface, and default provider
  - [x] 1.1 Create security label model `src/models/access_control.py`
    - Define `SecurityLabel(IntEnum)` with PUBLIC=0, RESTRICTED=1, CONFIDENTIAL=2, TOP_SECRET=3
    - Define `AccessDecision(BaseModel)` with allowed: bool, reason: str
    - Define `UserContext(BaseModel)` with user_id, username, clearance_level, role, groups
    - Define `ResourceContext(BaseModel)` with document_id, case_id, effective_label, security_label_override
    - Define `PlatformUser(BaseModel)` with user_id, username, display_name, role, clearance_level, created_at, updated_at
    - Define `LabelAuditEntry(BaseModel)` with audit_id, entity_type, entity_id, previous_label, new_label, changed_by, changed_at, change_reason
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 9.1, 13.1, 13.5_

  - [x] 1.2 Create `AccessPolicyProvider` ABC in `src/services/access_policy_provider.py`
    - Define abstract `check_access(user_context: dict, resource_context: dict) -> AccessDecision`
    - _Requirements: 13.1, 13.3_

  - [x] 1.3 Create `LabelBasedProvider` in `src/services/label_based_provider.py`
    - Implement `check_access` comparing clearance_level rank vs effective_label rank
    - Return `AccessDecision(allowed=True, reason="clearance_sufficient")` when clearance >= effective
    - Return denial with descriptive reason when clearance < effective
    - Ignore groups field entirely
    - _Requirements: 13.2, 13.6_

  - [ ]* 1.4 Write property tests for security label model in `tests/unit/test_security_label_model.py`
    - **Property 1: Label hierarchy ordering is total and consistent**
    - **Validates: Requirements 1.3**

  - [ ]* 1.5 Write property tests for LabelBasedProvider in `tests/unit/test_label_based_provider.py`
    - **Property 5: Access filtering excludes documents above clearance**
    - **Validates: Requirements 5.2, 7.1, 7.3**

  - [ ]* 1.6 Write property test for LabelBasedProvider ignoring groups
    - **Property 13: LabelBasedProvider ignores groups**
    - **Validates: Requirements 13.6**

- [x] 2. Schema migration
  - [x] 2.1 Create migration `src/db/migrations/007_document_access_control.sql`
    - Add `security_label` TEXT column (default 'restricted') with CHECK constraint to `matters` table
    - Add `security_label_override` TEXT column (nullable) with CHECK constraint to `documents` table
    - Create `platform_users` table with user_id UUID PK, username UNIQUE, display_name, role, clearance_level with CHECK constraint, created_at, updated_at
    - Create `label_audit_log` table with audit_id UUID PK, entity_type CHECK, entity_id, previous_label, new_label, changed_by, changed_at, change_reason
    - Create indexes: documents(security_label_override), platform_users(username), label_audit_log(entity_type, entity_id), label_audit_log(changed_at)
    - Backfill existing matters with security_label = 'restricted'
    - _Requirements: 1.4, 2.1, 3.1, 4.1, 9.1, 9.6, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [ ]* 2.2 Write property test for label validation
    - **Property 2: Label validation rejects invalid values**
    - **Validates: Requirements 1.4, 4.2**

- [x] 3. Checkpoint — Ensure model, provider, and migration are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Audit service and access control service
  - [x] 4.1 Create `AuditService` in `src/services/audit_service.py`
    - Implement `log_label_change(entity_type, entity_id, previous_label, new_label, changed_by, change_reason)`
    - Implement `log_access_denial(user_id, resource_id, reason)` inserting entity_type='access_denied'
    - Implement `query_audit_log(entity_type, entity_id, changed_by, date_from, date_to, limit, offset)` returning reverse chronological results
    - No UPDATE or DELETE methods on audit entries
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 13.7_

  - [x] 4.2 Create `AccessControlService` in `src/services/access_control_service.py`
    - Implement `_load_provider()` reading ACCESS_POLICY_PROVIDER env var, defaulting to LabelBasedProvider
    - Implement `resolve_user_context(event)` extracting user identity from API Gateway authorizer claims or X-User-Id header, looking up platform_users
    - Implement `filter_documents(user_ctx, documents)` calling provider for each document, returning only allowed documents
    - Implement `check_document_access(user_ctx, document_id)` for single-document 403 checks
    - Implement `build_label_filter_clause(clearance_rank)` returning SQL WHERE fragment and params
    - Implement `get_accessible_document_ids(user_ctx, case_id)` returning set of accessible document IDs for Neptune filtering
    - Implement `log_access_denial(user_ctx, resource_ctx, reason)` delegating to AuditService
    - Respect ACCESS_CONTROL_ENABLED env var — bypass all filtering when false
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 7.4, 11.5, 13.3, 13.4, 13.7_

  - [ ]* 4.3 Write unit tests for AuditService in `tests/unit/test_audit_service.py`
    - Test log_label_change inserts correct audit entry
    - Test log_access_denial inserts entity_type='access_denied'
    - Test query_audit_log returns reverse chronological order
    - Test query_audit_log filters by entity_type, entity_id, changed_by, date range
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 4.4 Write unit tests for AccessControlService in `tests/unit/test_access_control_service.py`
    - Test resolve_user_context extracts user from event
    - Test filter_documents excludes documents above clearance
    - Test check_document_access returns denial for above-clearance documents
    - Test build_label_filter_clause returns correct SQL fragment
    - Test ACCESS_CONTROL_ENABLED=false bypasses filtering
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 11.5_

  - [ ]* 4.5 Write property test for effective label resolution
    - **Property 3: Effective label resolution**
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 4.6 Write property test for access control disabled bypass
    - **Property 11: ACCESS_CONTROL_ENABLED=false bypasses all filtering**
    - **Validates: Requirements 11.5**

  - [ ]* 4.7 Write property test for provider delegation
    - **Property 12: Provider delegation — middleware uses configured provider**
    - **Validates: Requirements 13.3**

  - [ ]* 4.8 Write property test for denial audit logging
    - **Property 14: Access denial audit logging**
    - **Validates: Requirements 13.7**

  - [ ]* 4.9 Write property test for context completeness
    - **Property 15: User and resource context completeness**
    - **Validates: Requirements 13.5**

- [x] 5. Access control middleware decorator
  - [x] 5.1 Create `src/services/access_control_middleware.py`
    - Implement `with_access_control(handler_fn)` decorator
    - Resolve user context and inject into event as `_user_context`
    - When ACCESS_CONTROL_ENABLED=false, pass through without filtering
    - When user identity unresolvable and TRANSITION_PERIOD_ENABLED=true, default to restricted clearance
    - When user identity unresolvable and TRANSITION_PERIOD_ENABLED=false, return 401
    - Implement `_build_access_control_service()` helper
    - _Requirements: 5.1, 5.6, 11.4, 11.5_

  - [ ]* 5.2 Write property test for single document access denial
    - **Property 6: Single document access returns 403 when above clearance**
    - **Validates: Requirements 5.4**

- [x] 6. Checkpoint — Ensure service layer and middleware work
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 7. Integrate middleware into existing handlers
  - [x] 7.1 Add access control to `src/lambdas/api/case_files.py`
    - Wrap `dispatch_handler` with `@with_access_control` or call resolve_user_context at entry
    - In `get_case_file_handler`, add label filtering to document data in response
    - In `list_case_files_handler`, include security_label in response
    - Pass user context to service calls that return document data
    - _Requirements: 2.4, 5.2, 5.3, 8.3_

  - [x] 7.2 Add access control to `src/lambdas/api/search.py`
    - Resolve user context from event
    - Inject `build_label_filter_clause` into SemanticSearchService queries
    - Post-filter search results through `filter_documents` for OpenSearch results
    - _Requirements: 5.3, 7.1_

  - [x] 7.3 Add access control to pattern, cross-case, and drill-down handlers
    - Update `src/lambdas/api/patterns.py` to filter pattern results by accessible documents
    - Update `src/lambdas/api/cross_case.py` to apply label filtering per case
    - Update `src/lambdas/api/drill_down.py` to filter drill-down results
    - For Neptune queries, use `get_accessible_document_ids` to cross-reference entity source_document_refs
    - _Requirements: 5.3, 7.2, 7.3, 7.4_

  - [x] 7.4 Add access control to pipeline and batch loader handlers
    - Update `src/lambdas/api/pipeline_config.py` dispatch to resolve user context
    - Update batch loader handler to filter document status results
    - _Requirements: 5.3_

  - [ ]* 7.5 Write property test for Neptune entity filtering
    - **Property 8: Neptune entity filtering by accessible documents**
    - **Validates: Requirements 7.2, 7.4**

  - [ ]* 7.6 Write property test for audit trail completeness
    - **Property 9: Audit trail completeness for label changes**
    - **Validates: Requirements 4.4, 8.2, 9.2, 9.3, 9.4**

  - [ ]* 7.7 Write property test for matter label change preserving overrides
    - **Property 4: Matter label change preserves document overrides**
    - **Validates: Requirements 2.3, 8.4**

- [ ] 8. Update ingestion to accept security_label parameter
  - [x] 8.1 Update ingestion handler and service
    - Modify `src/lambdas/ingestion/upload_handler.py` to accept optional `security_label` parameter in request body
    - Pass security_label through to ingestion service which sets `security_label_override` on each document
    - When no security_label provided, leave security_label_override as null
    - Update matter creation endpoints to accept optional `security_label` parameter
    - Update batch loader start endpoint to accept `security_label` parameter
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 8.2 Write property test for ingestion labeling round-trip
    - **Property 7: Ingestion labeling round-trip**
    - **Validates: Requirements 6.2, 6.3, 6.4**

- [x] 9. Checkpoint — Ensure handler integration and ingestion work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Admin handler and API routes
  - [x] 10.1 Create admin handler `src/lambdas/api/access_control_admin.py`
    - Implement `dispatch_handler` following existing pattern (case_files.py, pipeline_config.py)
    - POST /admin/users — create platform user with username, display_name, role, clearance_level
    - GET /admin/users — list platform users
    - GET /admin/users/{id} — get user details
    - PUT /admin/users/{id} — update user clearance_level and role, log audit entry
    - DELETE /admin/users/{id} — delete user
    - PUT /matters/{id}/security-label — update case default label, log audit entry, do not modify document overrides
    - PUT /documents/{id}/security-label — set document label override, log audit entry
    - DELETE /documents/{id}/security-label — clear document label override, log audit entry
    - GET /admin/audit-log — query audit log with filters (entity_type, entity_id, changed_by, date_from, date_to), return reverse chronological
    - _Requirements: 3.4, 3.5, 4.2, 4.3, 4.4, 8.1, 8.2, 8.3, 8.4, 9.5, 10.1_

  - [ ]* 10.2 Write unit tests for admin handler in `tests/unit/test_access_control_admin.py`
    - Test user CRUD endpoints return correct response shapes
    - Test PUT /matters/{id}/security-label updates label and creates audit entry
    - Test PUT /documents/{id}/security-label sets override
    - Test DELETE /documents/{id}/security-label clears override
    - Test GET /admin/audit-log returns filtered results in reverse chronological order
    - Test validation rejects invalid security label values
    - _Requirements: 3.4, 3.5, 4.3, 8.1, 9.5_

  - [ ]* 10.3 Write property test for audit log ordering
    - **Property 10: Audit log reverse chronological ordering**
    - **Validates: Requirements 10.5**

  - [x] 10.4 Add API Gateway routes for admin endpoints in `infra/api_gateway/api_definition.yaml`
    - Add routes for /admin/users, /admin/users/{id}, /matters/{id}/security-label, /documents/{id}/security-label, /admin/audit-log
    - Wire to AccessControlAdminLambdaArn
    - Add CORS OPTIONS handlers for each route
    - _Requirements: 4.3, 8.1, 9.5_

  - [x] 10.5 Wire admin handler dispatch into case_files.py or create standalone Lambda entry
    - Add routing for /admin/* and /matters/*/security-label and /documents/*/security-label paths
    - _Requirements: 4.3, 8.1_

- [ ] 11. Admin UI and navigation
  - [x] 11.1 Create admin page `src/frontend/admin.html`
    - Follow existing dark-theme DOJ styling from investigator.html
    - User Management tab: table of platform_users with inline edit for clearance_level and role, create user form, delete confirmation
    - Case Labels tab: table of matters with current security_label, inline dropdown to change label, document count per label level
    - Audit Log tab: reverse-chronological table with filters for entity_type, entity_id, changed_by, date range, pagination
    - All API calls use fetch() pattern hitting /admin/* endpoints
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 11.2 Update navigation bar in existing frontend pages
    - Add "Admin" link to header nav in investigator.html and other frontend pages
    - Link to admin.html
    - _Requirements: 10.1_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after core model, service layer, handler integration, and frontend
- Property tests validate universal correctness properties from the design document
- The implementation uses Python throughout, matching the existing codebase
- ACCESS_CONTROL_ENABLED=false provides a kill switch for rollback safety
