# Requirements: Matter-Collection Hierarchy (Multi-Tenant)

## Introduction

Replaces the flat `case_files` table with a multi-tenant hierarchy: Organization > Matter > Collection > Document. This is the foundational data architecture for supporting multiple customers, proper data load management, and domain-agnostic analysis.

## Glossary

- **Organization**: A tenant/customer (e.g., DOJ, FBI, Law Firm X). All data is scoped to an organization.
- **Matter**: The primary analysis unit — an investigation, case, contract review, or audit. Replaces `case_files`.
- **Collection**: A batch of documents from a specific source at a specific time. Tracks provenance and supports QA before merging into the Matter.
- **Promotion**: The act of merging a Collection's entities into the Matter's Neptune subgraph after QA review.

## Requirements

### Requirement 1: Organization (Tenant) Management

**User Story:** As a platform operator, I want each customer isolated in their own Organization, so that data from one customer is never visible to another.

#### Acceptance Criteria
1. THE system SHALL store organizations with: org_id (UUID PK), org_name, settings (JSONB), created_at.
2. ALL data (matters, collections, documents, analyses) SHALL reference an org_id.
3. WHEN a user queries any endpoint, THE system SHALL filter results by the user's org_id.
4. THE system SHALL support organization-level settings: default_pipeline_config, display_labels, modules_enabled.


### Requirement 2: Matter as Primary Analysis Unit

**User Story:** As an investigator, I want one Matter per real-world case that aggregates all data loads, so that I analyze the complete picture rather than fragmented batches.

#### Acceptance Criteria
1. THE system SHALL store matters with: matter_id (UUID PK), org_id FK, matter_name, description, status, matter_type, created_by, created_at.
2. ALL analysis modules (AI Briefing, Prosecutor, Network Discovery, Document Assembly) SHALL operate at the Matter level.
3. THE Neptune subgraph label SHALL be per-Matter (Entity_{matter_id}) — all entities from all promoted Collections share one graph.
4. THE Matter SHALL maintain aggregated counts: total_documents, total_entities, total_relationships (computed from promoted Collections).
5. THE frontend sidebar SHALL display Matters as the primary navigation unit.

### Requirement 3: Collection (Data Load) Management

**User Story:** As a data manager, I want each batch upload tracked as a separate Collection with provenance, so that I can QA each load before it affects the investigation.

#### Acceptance Criteria
1. THE system SHALL store collections with: collection_id (UUID PK), matter_id FK, collection_name, source_description, status, document_count, entity_count, relationship_count, uploaded_by, uploaded_at, promoted_at, chain_of_custody (JSONB).
2. Collection status SHALL be one of: staging, processing, qa_review, promoted, rejected, archived.
3. WHEN documents are uploaded, THE system SHALL create a Collection in "staging" status.
4. WHEN processing completes, THE system SHALL transition the Collection to "qa_review" status.
5. THE Collection SHALL track its own S3 prefix: orgs/{org_id}/matters/{matter_id}/collections/{collection_id}/raw/.


### Requirement 4: Document Linkage

**User Story:** As an investigator, I want every document traceable to its source Collection and Matter, so that I maintain chain of custody.

#### Acceptance Criteria
1. THE documents table SHALL have: collection_id FK, matter_id FK (denormalized for query performance), org_id FK.
2. ALL existing document fields SHALL be preserved (file_name, file_size, content, embedding, etc.).

### Requirement 5: Collection Promotion Workflow

**User Story:** As an investigator, I want to review a Collection's extraction quality before merging it into the case, so that bad data doesn't corrupt my analysis.

#### Acceptance Criteria
1. WHEN an investigator clicks "Promote", THE system SHALL merge the Collection's entities into the Matter's Neptune subgraph.
2. WHEN promoted, THE system SHALL recalculate Matter-level aggregated counts.
3. WHEN promoted, THE system SHALL create a snapshot recording: entities_added, relationships_added, timestamp.
4. Promotion SHALL be irreversible (Collection can be archived but not un-promoted).
5. WHEN an investigator clicks "Reject", THE system SHALL mark the Collection as rejected without merging.

### Requirement 6: Schema Migration

**User Story:** As a platform operator, I want existing data migrated to the new schema without data loss, so that the platform continues working.

#### Acceptance Criteria
1. THE migration SHALL create a default Organization for the current deployment.
2. THE migration SHALL convert each unique topic_name into a Matter.
3. THE migration SHALL convert each case_files row into a Collection under the appropriate Matter.
4. THE migration SHALL preserve all existing document, entity, and relationship data.
5. Neptune subgraph labels SHALL remain unchanged (already per-case, which becomes per-Matter).
6. ALL existing frontend pages and services SHALL continue to work after migration.


### Requirement 7: Frontend Changes

**User Story:** As an investigator, I want to see Matters in the sidebar and manage Collections within each Matter, so that I understand my data structure.

#### Acceptance Criteria
1. THE sidebar SHALL show Matters (not case_files) as the primary navigation.
2. WITHIN a Matter, THE system SHALL show a Collections tab with status badges.
3. THE Collection detail view SHALL show: document list, entity extraction results, QA review controls.
4. THE Matter header SHALL show aggregated counts from all promoted Collections.
5. THE sidebar SHALL include a "+ New" button that opens an inline form to create a Matter with name, description, and type (investigation, contract_review, audit, litigation).
6. THE Collections tab SHALL include a "+ New Collection" button that opens an inline form to create a Collection with name and source description.
7. WHEN a new Matter is created via the form, THE system SHALL call POST /organizations/{org_id}/matters and auto-select the new Matter in the sidebar.
8. WHEN a new Collection is created via the form, THE system SHALL call POST /matters/{id}/collections and refresh the Collections list.

### Requirement 8: API Changes

**User Story:** As a developer, I want clean API endpoints for the new hierarchy while maintaining backward compatibility.

#### Acceptance Criteria
1. THE system SHALL provide endpoints: /organizations, /organizations/{id}/matters, /matters/{id}/collections.
2. THE existing /case-files endpoints SHALL become aliases for /matters (backward compatibility).
3. Collection CRUD: create, list, get, promote, reject.
4. Matter-level analysis endpoints SHALL remain unchanged.

### Requirement 9: Domain-Agnostic Design

**User Story:** As a platform operator, I want the same hierarchy to work for legal investigations, contract management, and supply chain audits.

#### Acceptance Criteria
1. THE schema SHALL use generic terms (matter, collection) not domain-specific terms.
2. THE Organization settings SHALL include display_labels (JSONB) for customizing UI terminology.
3. WHEN display_labels defines "matter_label" as "Contract Review", THE frontend SHALL display that label.

### Requirement 10: S3 Storage Structure

**User Story:** As a platform operator, I want S3 paths organized by the new hierarchy for clean data management.

#### Acceptance Criteria
1. New uploads SHALL use: s3://bucket/orgs/{org_id}/matters/{matter_id}/collections/{collection_id}/raw/.
2. Existing S3 paths SHALL continue to work during and after migration.
