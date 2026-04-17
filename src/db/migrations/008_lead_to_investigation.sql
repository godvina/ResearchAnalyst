-- Migration: 008_lead_to_investigation.sql
-- Lead-to-Investigation: adds lead tracking columns to matters table.
-- Additive only — no existing columns or tables are modified or dropped.
--
-- Depends on: matters table from 006_matter_collection_hierarchy.sql

BEGIN;

-- 1. Lead metadata (full lead JSON subset stored as JSONB)
ALTER TABLE matters ADD COLUMN IF NOT EXISTS lead_metadata JSONB;

-- 2. Lead processing status (null for non-lead matters)
ALTER TABLE matters ADD COLUMN IF NOT EXISTS lead_status TEXT;

-- 3. Lead ID for lookup (unique per lead-sourced matter)
ALTER TABLE matters ADD COLUMN IF NOT EXISTS lead_id TEXT;

-- 4. Unique index on lead_id (allows NULL — only lead-sourced matters have a value)
CREATE UNIQUE INDEX IF NOT EXISTS idx_matters_lead_id
    ON matters(lead_id) WHERE lead_id IS NOT NULL;

-- 5. Index on lead_status for status queries
CREATE INDEX IF NOT EXISTS idx_matters_lead_status
    ON matters(lead_status) WHERE lead_status IS NOT NULL;

COMMIT;
