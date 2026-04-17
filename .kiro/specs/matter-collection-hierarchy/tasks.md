# Implementation Plan: Matter-Collection Hierarchy (Multi-Tenant)

## Overview

Replaces the flat `case_files` model with Organization > Matter > Collection > Document hierarchy. Implementation proceeds bottom-up: schema migration, then Pydantic models, then services (Organization → Matter → Collection → Promotion → Ingestion v2 → Compat shim), then S3/Neptune updates, then API handlers, and finally frontend changes. Each step builds on the previous and wires into existing code.

## Tasks

- [x] 1. Aurora schema migration and Pydantic models
  - [x] 1.1 Create Aurora migration `src/db/migrations/006_matter_collection_hierarchy.sql`
    - Create `organizations` table (org_id UUID PK, org_name, settings JSONB, created_at)
    - Create `matters` table with all columns from design (matter_id, org_id FK, matter_name, description, status, matter_type, created_by, created_at, last_activity, s3_prefix, neptune_subgraph_label, total_documents, total_entities, total_relationships, search_tier, error_details)
    - Create `collections` table with all columns (collection_id, matter_id FK, org_id FK, collection_name, source_description, status, document_count, entity_count, relationship_count, uploaded_by, uploaded_at, promoted_at, chain_of_custody JSONB, s3_prefix)
    - Create `promotion_snapshots` table (snapshot_id, collection_id FK, matter_id FK, entities_added, relationships_added, promoted_at, promoted_by)
    - Add `org_id`, `matter_id`, `collection_id` columns to `documents` table
    - Create indexes: idx_matters_org_id, idx_matters_status, idx_collections_matter_id, idx_collections_org_id, idx_collections_status
    - Include data migration: create default org, convert case_files rows to matters + collections
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 1.2 Create Pydantic models in `src/models/hierarchy.py`
    - Define `Organization`, `MatterStatus`, `Matter`, `CollectionStatus`, `Collection`, `PromotionSnapshot` models per design
    - Export new models from `src/models/__init__.py`
    - _Requirements: 1.1, 2.1, 3.1, 3.2, 5.3_

  - [ ]* 1.3 Write property test for entity creation round trip
    - **Property 1: Entity creation round trip**
    - **Validates: Requirements 1.1, 2.1, 3.1**

  - [ ]* 1.4 Write property test for collection status state machine
    - **Property 7: Collection status state machine**
    - **Validates: Requirements 3.2, 3.3, 3.4**

- [x] 2. Checkpoint — Ensure migration and models are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. S3 helper and Neptune updates
  - [x] 3.1 Add new S3 path builders to `src/storage/s3_helper.py`
    - Add `org_matter_collection_prefix(org_id, matter_id, collection_id)` returning `orgs/{org_id}/matters/{matter_id}/collections/{collection_id}/`
    - Add `build_collection_key(org_id, matter_id, collection_id, prefix_type, filename)` for new hierarchy paths
    - Keep existing `case_prefix()` and `build_key()` for legacy path resolution
    - Add `resolve_document_path(case_id, org_id, matter_id, collection_id, prefix_type, filename)` that tries new path first, falls back to legacy
    - _Requirements: 10.1, 10.2_

  - [ ]* 3.2 Write property test for S3 prefix format
    - **Property 8: S3 prefix format**
    - **Validates: Requirements 3.5, 10.1**

  - [ ]* 3.3 Write property test for legacy S3 path resolution
    - **Property 16: Legacy S3 path resolution**
    - **Validates: Requirements 10.2**

  - [x] 3.4 Add Neptune staging subgraph support to `src/db/neptune.py`
    - Add `collection_staging_label(collection_id)` returning `Entity_{collection_id}`
    - Add `NODE_PROP_MATTER_ID = "matter_id"` and `NODE_PROP_COLLECTION_ID = "collection_id"` constants
    - Keep `NODE_PROP_CASE_FILE_ID` for backward compat
    - _Requirements: 2.3, 6.5_

  - [ ]* 3.5 Write property test for Neptune subgraph label format
    - **Property 5: Neptune subgraph label format**
    - **Validates: Requirements 2.3**

- [x] 4. OrganizationService and MatterService
  - [x] 4.1 Create `src/services/organization_service.py`
    - Implement `OrganizationService` with `create_organization`, `get_organization`, `update_settings`, `list_organizations`
    - All methods use `ConnectionManager` for Aurora queries
    - _Requirements: 1.1, 1.4_

  - [ ]* 4.2 Write property test for organization settings round trip
    - **Property 4: Organization settings round trip**
    - **Validates: Requirements 1.4, 9.2**

  - [x] 4.3 Create `src/services/matter_service.py`
    - Implement `MatterService` with `create_matter`, `get_matter`, `list_matters`, `update_status`, `delete_matter`, `get_aggregated_counts`
    - All queries filter by `org_id` for tenant isolation
    - `create_matter` generates UUID, builds s3_prefix and neptune_subgraph_label
    - `get_aggregated_counts` sums counts from promoted collections
    - _Requirements: 1.2, 1.3, 2.1, 2.3, 2.4_

  - [ ]* 4.4 Write property test for tenant data isolation
    - **Property 3: Tenant data isolation**
    - **Validates: Requirements 1.3**

  - [ ]* 4.5 Write property test for org-id propagation through hierarchy
    - **Property 2: Org-id propagation through hierarchy**
    - **Validates: Requirements 1.2, 4.1**

- [x] 5. CollectionService and PromotionService
  - [x] 5.1 Create `src/services/collection_service.py`
    - Implement `CollectionService` with `create_collection`, `get_collection`, `list_collections`, `update_status`, `reject_collection`
    - `create_collection` generates UUID, builds s3_prefix using new hierarchy path, sets status to "staging"
    - `update_status` enforces valid state transitions (staging→processing→qa_review; qa_review→promoted/rejected; promoted→archived only)
    - `reject_collection` sets status to "rejected" only if current status is "qa_review"
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.4, 5.5_

  - [ ]* 5.2 Write property test for collection CRUD round trip
    - **Property 15: Collection CRUD round trip**
    - **Validates: Requirements 8.3**

  - [x] 5.3 Create `src/services/promotion_service.py`
    - Implement `PromotionService` with `promote_collection` and `get_promotion_snapshot`
    - `promote_collection`: verify collection is in qa_review, lock row, copy entities from staging subgraph (`Entity_{collection_id}`) to matter subgraph (`Entity_{matter_id}`), merge duplicates, update collection status to "promoted", create promotion_snapshot, update matter aggregated counts
    - On Neptune failure: leave collection in qa_review, clean up partial staging data, allow retry
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 5.4 Write property test for promotion irreversibility
    - **Property 11: Promotion irreversibility**
    - **Validates: Requirements 5.4**

  - [ ]* 5.5 Write property test for promotion snapshot accuracy
    - **Property 10: Promotion snapshot accuracy**
    - **Validates: Requirements 5.3**

  - [ ]* 5.6 Write property test for matter aggregated counts
    - **Property 6: Matter aggregated counts equal sum of promoted collections**
    - **Validates: Requirements 2.4, 5.2, 7.4**

  - [ ]* 5.7 Write property test for rejection does not merge entities
    - **Property 12: Rejection does not merge entities**
    - **Validates: Requirements 5.5**

- [x] 6. Checkpoint — Ensure all service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. IngestionService v2 and CaseFileCompatService
  - [x] 7.1 Create `src/services/ingestion_service_v2.py`
    - Implement `IngestionServiceV2` extending `IngestionService`
    - Override `upload_documents(matter_id, org_id, files, collection_name, source_description)` to create a Collection in staging, write to new S3 path `orgs/{org_id}/matters/{mid}/collections/{cid}/raw/`
    - Override `process_batch(collection_id, document_ids)` to load entities into staging subgraph (`Entity_{collection_id}`), transition collection to qa_review on success
    - Store `org_id`, `matter_id`, `collection_id` on each document row
    - _Requirements: 3.3, 3.4, 3.5, 4.1, 10.1_

  - [ ]* 7.2 Write property test for promotion merges entities into matter graph
    - **Property 9: Promotion merges entities into matter graph**
    - **Validates: Requirements 5.1**

  - [x] 7.3 Create `src/services/case_file_compat_service.py`
    - Implement `CaseFileCompatService` wrapping `MatterService`
    - Map `get_case_file(case_id)` → `get_matter(matter_id)` with field translation (matter_id→case_id, matter_name→topic_name)
    - Map `list_case_files()` → `list_matters()` with same field translation
    - Map `update_status(case_id, status)` → `update_status(matter_id, status)` translating CaseFileStatus↔MatterStatus
    - _Requirements: 6.6, 8.2_

  - [ ]* 7.4 Write property test for backward-compatible API alias
    - **Property 14: Backward-compatible API alias**
    - **Validates: Requirements 8.2**

  - [ ]* 7.5 Write property test for migration preserves data and labels
    - **Property 13: Migration preserves data and labels**
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5**

- [x] 8. API handlers and routing
  - [x] 8.1 Create `src/lambdas/api/organizations.py`
    - Implement `dispatch_handler` with GET/POST for `/organizations` and GET/PATCH for `/organizations/{id}`
    - Wire to `OrganizationService`
    - _Requirements: 8.1_

  - [x] 8.2 Create `src/lambdas/api/matters.py`
    - Implement handlers for `/organizations/{org_id}/matters` (list/create) and `/matters/{id}` (get/update/delete)
    - Include collection sub-routes: `/matters/{id}/collections` (list/create), `/matters/{id}/collections/{cid}` (get), `/matters/{id}/collections/{cid}/promote`, `/matters/{id}/collections/{cid}/reject`
    - Wire to `MatterService`, `CollectionService`, `PromotionService`
    - _Requirements: 8.1, 8.3_

  - [x] 8.3 Add backward-compatible `/case-files/*` aliases in `src/lambdas/api/case_files.py`
    - Update `dispatch_handler` to delegate to `CaseFileCompatService` which wraps `MatterService`
    - Existing endpoints continue to work, returning responses with `case_id`/`topic_name` field names
    - _Requirements: 8.2_

  - [x] 8.4 Update API Gateway definition `infra/api_gateway/api_definition.yaml`
    - Add routes for `/organizations`, `/organizations/{org_id}/matters`, `/matters/{id}`, `/matters/{id}/collections`, `/matters/{id}/collections/{cid}`, `/matters/{id}/collections/{cid}/promote`, `/matters/{id}/collections/{cid}/reject`
    - _Requirements: 8.1, 8.3_

- [x] 9. Frontend sidebar and collection management
  - [x] 9.1 Update `src/frontend/investigator.html` sidebar
    - Replace case_files listing with Matters as primary navigation
    - Show matter_name, status badge, aggregated counts in sidebar items
    - Add Collections tab within Matter detail view showing status badges per collection
    - Add QA review controls (Promote/Reject buttons) on collection detail
    - Show Matter header with aggregated counts from promoted collections
    - _Requirements: 2.5, 7.1, 7.2, 7.3, 7.4_

  - [x] 9.2 Add organization display_labels support to frontend
    - Read `display_labels` from organization settings
    - Replace hardcoded "Matter"/"Collection" labels with configurable terms
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)`
- The migration (1.1) includes data migration from case_files → matters + collections
- Legacy S3 paths and Neptune labels remain functional throughout
- CaseFileCompatService ensures existing analysis modules (AI Briefing, Prosecutor, Network Discovery, Document Assembly) work without changes
