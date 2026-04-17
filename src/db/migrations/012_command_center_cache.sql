-- Migration: 012_command_center_cache.sql
-- Case Intelligence Command Center — cache table for computed results.
-- 15-minute TTL caching to avoid recomputing indicators on every page load.

BEGIN;

CREATE TABLE IF NOT EXISTS command_center_cache (
    case_file_id UUID NOT NULL PRIMARY KEY,
    cached_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    command_center_data JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cc_cache_case
    ON command_center_cache(case_file_id);

COMMIT;
