-- Migration: 006_matter_collection_hierarchy.sql
-- Matter-Collection Hierarchy (Multi-Tenant) — replaces flat case_files model
-- with Organization > Matter > Collection > Document hierarchy.
--
-- Depends on: case_files(case_id) from src/db/schema.sql
--             documents(document_id) from src/db/schema.sql

BEGIN;

-- ============================================================================
-- 1. Organizations table (tenant boundary)
-- ============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_name TEXT NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 2. Matters table (replaces case_files for new code)
-- ============================================================================
CREATE TABLE IF NOT EXISTS matters (
    matter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    matter_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    matter_type TEXT NOT NULL DEFAULT 'investigation',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    s3_prefix TEXT NOT NULL,
    neptune_subgraph_label TEXT NOT NULL,
    total_documents INTEGER DEFAULT 0,
    total_entities INTEGER DEFAULT 0,
    total_relationships INTEGER DEFAULT 0,
    search_tier TEXT DEFAULT 'standard',
    error_details TEXT
);

-- ============================================================================
-- 3. Collections table (tracked data loads within a Matter)
-- ============================================================================
CREATE TABLE IF NOT EXISTS collections (
    collection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id UUID NOT NULL REFERENCES matters(matter_id),
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    collection_name TEXT NOT NULL,
    source_description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'staging',
    document_count INTEGER DEFAULT 0,
    entity_count INTEGER DEFAULT 0,
    relationship_count INTEGER DEFAULT 0,
    uploaded_by TEXT DEFAULT '',
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    promoted_at TIMESTAMP WITH TIME ZONE,
    chain_of_custody JSONB DEFAULT '[]',
    s3_prefix TEXT NOT NULL
);

-- ============================================================================
-- 4. Promotion snapshots (records of collection-to-matter merges)
-- ============================================================================
CREATE TABLE IF NOT EXISTS promotion_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(collection_id),
    matter_id UUID NOT NULL REFERENCES matters(matter_id),
    entities_added INTEGER NOT NULL DEFAULT 0,
    relationships_added INTEGER NOT NULL DEFAULT 0,
    promoted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    promoted_by TEXT DEFAULT ''
);

-- ============================================================================
-- 5. Add org_id, matter_id, collection_id to documents table
-- ============================================================================
ALTER TABLE documents ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(org_id);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS matter_id UUID REFERENCES matters(matter_id);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS collection_id UUID REFERENCES collections(collection_id);

-- ============================================================================
-- 6. Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_matters_org_id ON matters(org_id);
CREATE INDEX IF NOT EXISTS idx_matters_status ON matters(status);
CREATE INDEX IF NOT EXISTS idx_collections_matter_id ON collections(matter_id);
CREATE INDEX IF NOT EXISTS idx_collections_org_id ON collections(org_id);
CREATE INDEX IF NOT EXISTS idx_collections_status ON collections(status);

-- ============================================================================
-- 7. Data migration: create default org, convert case_files → matters + collections
-- ============================================================================

-- 7a. Create default organization for existing deployment
INSERT INTO organizations (org_id, org_name, settings)
SELECT gen_random_uuid(), 'Default Organization', '{}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM organizations LIMIT 1);

-- 7b. Convert each case_files row into a Matter under the default org
INSERT INTO matters (
    matter_id, org_id, matter_name, description, status, matter_type,
    created_by, created_at, last_activity, s3_prefix, neptune_subgraph_label,
    total_documents, total_entities, total_relationships, search_tier, error_details
)
SELECT
    cf.case_id,                                    -- reuse case_id as matter_id
    (SELECT org_id FROM organizations LIMIT 1),    -- default org
    cf.topic_name,                                 -- matter_name = topic_name
    cf.description,
    cf.status,
    'investigation',                               -- default matter_type
    '',                                            -- created_by unknown
    cf.created_at,
    cf.last_activity,
    cf.s3_prefix,
    cf.neptune_subgraph_label,                     -- preserve Neptune labels
    cf.document_count,
    cf.entity_count,
    cf.relationship_count,
    COALESCE(cf.search_tier, 'standard'),
    cf.error_details
FROM case_files cf
WHERE NOT EXISTS (
    SELECT 1 FROM matters m WHERE m.matter_id = cf.case_id
);

-- 7c. Create a Collection for each migrated Matter (one collection per case_file)
INSERT INTO collections (
    collection_id, matter_id, org_id, collection_name, source_description,
    status, document_count, entity_count, relationship_count,
    uploaded_by, uploaded_at, promoted_at, chain_of_custody, s3_prefix
)
SELECT
    gen_random_uuid(),
    cf.case_id,                                    -- matter_id = case_id
    (SELECT org_id FROM organizations LIMIT 1),    -- default org
    cf.topic_name || ' - Initial Load',            -- collection_name
    'Migrated from case_files',                    -- source_description
    'promoted',                                    -- already merged data
    cf.document_count,
    cf.entity_count,
    cf.relationship_count,
    '',                                            -- uploaded_by unknown
    cf.created_at,
    cf.created_at,                                 -- promoted_at = created_at
    '[]'::jsonb,
    cf.s3_prefix                                   -- preserve original S3 prefix
FROM case_files cf
WHERE NOT EXISTS (
    SELECT 1 FROM collections c WHERE c.matter_id = cf.case_id
);

-- 7d. Backfill org_id and matter_id on existing documents
UPDATE documents d
SET
    org_id = (SELECT org_id FROM organizations LIMIT 1),
    matter_id = d.case_file_id
WHERE d.org_id IS NULL
  AND d.case_file_id IS NOT NULL;

-- 7e. Backfill collection_id on existing documents (assign to the migrated collection)
UPDATE documents d
SET collection_id = c.collection_id
FROM collections c
WHERE d.matter_id = c.matter_id
  AND d.collection_id IS NULL;

COMMIT;
