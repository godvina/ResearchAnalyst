-- Migration 009: Entity and Relationship tables in Aurora
-- Provides relational storage for entities alongside Neptune graph storage.
-- Enables SQL analytics, cross-case queries, entity-document provenance,
-- and efficient aggregation at scale (3M+ docs, 10M+ entities).

-- 1. Entities table — one row per unique entity per case
CREATE TABLE IF NOT EXISTS entities (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL,
    document_id UUID,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'unknown',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    source_document_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (case_file_id, canonical_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_entities_case ON entities(case_file_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name_trgm ON entities USING gin (canonical_name gin_trgm_ops);

-- 2. Relationships table — one row per unique relationship per case
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL,
    source_entity TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'co-occurrence',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (case_file_id, source_entity, target_entity, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_relationships_case ON relationships(case_file_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_entity);

-- 3. Entity-document links — tracks which documents mention which entities
CREATE TABLE IF NOT EXISTS entity_document_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    document_id UUID NOT NULL,
    case_file_id UUID NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_edl_entity ON entity_document_links(entity_id);
CREATE INDEX IF NOT EXISTS idx_edl_document ON entity_document_links(document_id);
CREATE INDEX IF NOT EXISTS idx_edl_case ON entity_document_links(case_file_id);
