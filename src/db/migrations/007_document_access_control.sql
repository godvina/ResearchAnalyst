-- Migration: 007_document_access_control.sql
-- Document Access Control — adds hierarchical security-label-based access
-- control with platform users, per-document label overrides, and an
-- append-only audit log.
--
-- Depends on: matters(matter_id) from 006_matter_collection_hierarchy.sql
--             documents(document_id) from src/db/schema.sql

BEGIN;

-- ============================================================================
-- 1. Add security_label to matters table (case-level default label)
-- ============================================================================
ALTER TABLE matters ADD COLUMN IF NOT EXISTS security_label TEXT DEFAULT 'restricted'
    CHECK (security_label IN ('public', 'restricted', 'confidential', 'top_secret'));

-- ============================================================================
-- 2. Add security_label_override to documents table (per-document override)
-- ============================================================================
ALTER TABLE documents ADD COLUMN IF NOT EXISTS security_label_override TEXT
    CHECK (security_label_override IS NULL OR
           security_label_override IN ('public', 'restricted', 'confidential', 'top_secret'));

-- ============================================================================
-- 3. Platform users table (identity and clearance for access control)
-- ============================================================================
CREATE TABLE IF NOT EXISTS platform_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'analyst',
    clearance_level TEXT NOT NULL DEFAULT 'restricted'
        CHECK (clearance_level IN ('public', 'restricted', 'confidential', 'top_secret')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 4. Label audit log table (append-only trail of all label changes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS label_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('matter', 'document', 'user', 'access_denied')),
    entity_id UUID NOT NULL,
    previous_label TEXT,
    new_label TEXT,
    changed_by TEXT NOT NULL DEFAULT 'system',
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    change_reason TEXT
);

-- ============================================================================
-- 5. Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_documents_security_label_override
    ON documents(security_label_override);
CREATE INDEX IF NOT EXISTS idx_platform_users_username
    ON platform_users(username);
CREATE INDEX IF NOT EXISTS idx_label_audit_log_entity
    ON label_audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_label_audit_log_changed_at
    ON label_audit_log(changed_at);

-- ============================================================================
-- 6. Backfill existing matters with default label
-- ============================================================================
UPDATE matters SET security_label = 'restricted' WHERE security_label IS NULL;

COMMIT;
