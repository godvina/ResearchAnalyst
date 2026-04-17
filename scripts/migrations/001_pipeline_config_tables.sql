-- Migration 001: Pipeline Configuration Tables
-- Feature: configurable-pipeline
-- Requirements: 1.1, 1.2, 14.12, 18.8, 19.4, 19.5
--
-- Creates tables for per-case pipeline configuration, pipeline run tracking,
-- sample run snapshots, chat conversations, investigator findings/activity,
-- and adds portfolio management columns to case_files.

BEGIN;

-- ============================================================================
-- 1. system_default_config (Req 1.2)
-- Stores the platform-wide default pipeline configuration.
-- Exactly one row should have is_active = TRUE at any time.
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_default_config (
    config_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version         INTEGER NOT NULL,
    config_json     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Partial unique constraint: only one active system default at a time
CREATE UNIQUE INDEX IF NOT EXISTS uq_system_default_active
    ON system_default_config (is_active) WHERE (is_active = TRUE);

-- Fast lookup for the active system default
CREATE INDEX IF NOT EXISTS idx_system_default_active
    ON system_default_config (is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 2. pipeline_configs (Req 1.1)
-- Stores per-case pipeline configuration with versioning.
-- Each case has at most one active config (is_active = TRUE).
-- ============================================================================
CREATE TABLE IF NOT EXISTS pipeline_configs (
    config_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    config_json     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_pipeline_config_version UNIQUE (case_id, version)
);

-- Partial unique constraint: only one active config per case
CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_config_active
    ON pipeline_configs (case_id, is_active) WHERE (is_active = TRUE);

-- Fast lookup for a case's active config
CREATE INDEX IF NOT EXISTS idx_pipeline_configs_case_active
    ON pipeline_configs (case_id, is_active) WHERE is_active = TRUE;

-- Version history lookup (newest first)
CREATE INDEX IF NOT EXISTS idx_pipeline_configs_case_version
    ON pipeline_configs (case_id, version DESC);

-- ============================================================================
-- 3. pipeline_runs (Req 1.1)
-- Tracks each pipeline execution (full or sample) with the effective config
-- snapshot, aggregate metrics, and cost estimates.
-- ============================================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    config_version      INTEGER NOT NULL,
    effective_config    JSONB NOT NULL,
    is_sample_run       BOOLEAN NOT NULL DEFAULT FALSE,
    document_ids        TEXT[] NOT NULL,
    document_count      INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    step_statuses       JSONB NOT NULL DEFAULT '{}',
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_by          TEXT NOT NULL,
    sf_execution_arn    TEXT,
    -- Aggregate metrics (populated on completion)
    total_entities      INTEGER,
    total_relationships INTEGER,
    entity_type_counts  JSONB,
    avg_confidence      FLOAT,
    noise_ratio         FLOAT,
    docs_per_minute     FLOAT,
    avg_entities_per_doc FLOAT,
    failed_doc_count    INTEGER DEFAULT 0,
    failure_rate        FLOAT,
    estimated_cost_usd  FLOAT,
    total_input_tokens  INTEGER,
    total_output_tokens INTEGER,
    quality_score       FLOAT,
    quality_breakdown   JSONB
);

-- Recent runs per case (newest first)
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_case
    ON pipeline_runs (case_id, started_at DESC);

-- Sample runs lookup
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_sample
    ON pipeline_runs (case_id, is_sample_run) WHERE is_sample_run = TRUE;

-- ============================================================================
-- 4. pipeline_step_results (Req 1.1)
-- Per-step, per-document results within a pipeline run.
-- ============================================================================
CREATE TABLE IF NOT EXISTS pipeline_step_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    step_name       TEXT NOT NULL CHECK (step_name IN ('parse', 'extract', 'embed', 'graph_load', 'store_artifact')),
    document_id     TEXT,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,
    metrics_json    JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT,
    CONSTRAINT uq_step_result UNIQUE (run_id, step_name, document_id)
);

-- Step results lookup by run and step
CREATE INDEX IF NOT EXISTS idx_step_results_run
    ON pipeline_step_results (run_id, step_name);

-- ============================================================================
-- 5. sample_run_snapshots (Req 1.1)
-- Stores entity/relationship snapshots from sample runs for comparison.
-- ============================================================================
CREATE TABLE IF NOT EXISTS sample_run_snapshots (
    snapshot_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    case_id         UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    config_version  INTEGER NOT NULL,
    snapshot_name   TEXT,
    entities        JSONB NOT NULL DEFAULT '[]',
    relationships   JSONB NOT NULL DEFAULT '[]',
    quality_metrics JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Snapshots per case (newest first)
CREATE INDEX IF NOT EXISTS idx_snapshots_case
    ON sample_run_snapshots (case_id, created_at DESC);

-- ============================================================================
-- 6. chat_conversations (Req 14.12)
-- Stores chatbot conversation history for audit trail purposes.
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES case_files(case_id),
    user_id         TEXT NOT NULL DEFAULT 'investigator',
    messages        JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Conversations per case (most recent first)
CREATE INDEX IF NOT EXISTS idx_chat_case
    ON chat_conversations (case_id, updated_at DESC);

-- ============================================================================
-- 7. investigator_findings (Req 19.4)
-- Stores investigator notes, leads, and findings across cases.
-- ============================================================================
CREATE TABLE IF NOT EXISTS investigator_findings (
    finding_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id     UUID NOT NULL REFERENCES case_files(case_id),
    user_id     TEXT NOT NULL,
    finding_type TEXT NOT NULL DEFAULT 'note'
        CHECK (finding_type IN ('note', 'suspicious', 'lead', 'evidence_gap', 'recommendation')),
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    entity_refs TEXT[],
    document_refs TEXT[],
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Findings per case (newest first)
CREATE INDEX IF NOT EXISTS idx_findings_case
    ON investigator_findings (case_id, created_at DESC);

-- Findings per user (newest first)
CREATE INDEX IF NOT EXISTS idx_findings_user
    ON investigator_findings (user_id, created_at DESC);

-- ============================================================================
-- 8. investigator_activity (Req 19.5)
-- Tracks investigator actions (searches, entity views, etc.) for activity feed.
-- ============================================================================
CREATE TABLE IF NOT EXISTS investigator_activity (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id     UUID NOT NULL REFERENCES case_files(case_id),
    user_id     TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_detail JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Activity per user (newest first)
CREATE INDEX IF NOT EXISTS idx_activity_user
    ON investigator_activity (user_id, created_at DESC);

-- ============================================================================
-- 9. ALTER TABLE case_files — Portfolio management columns (Req 18.8)
-- Adds priority, assignment, categorization, activity tracking, and
-- strength scoring columns for the Case Portfolio Dashboard.
-- ============================================================================
ALTER TABLE case_files ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'medium'
    CHECK (priority IN ('critical', 'high', 'medium', 'low'));
ALTER TABLE case_files ADD COLUMN IF NOT EXISTS assigned_to TEXT;
ALTER TABLE case_files ADD COLUMN IF NOT EXISTS case_category TEXT;
ALTER TABLE case_files ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE case_files ADD COLUMN IF NOT EXISTS strength_score INTEGER;

-- ============================================================================
-- 10. triage_queue (Req 23.6)
-- Stores unclassified documents awaiting manual assignment or new case creation.
-- ============================================================================
CREATE TABLE IF NOT EXISTS triage_queue (
    triage_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         TEXT NOT NULL,
    filename            TEXT NOT NULL,
    s3_key              TEXT,
    classification_json JSONB NOT NULL DEFAULT '{}',
    suggested_case_id   UUID REFERENCES case_files(case_id),
    confidence          FLOAT DEFAULT 0.0,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'assigned', 'new_case')),
    assigned_case_id    UUID REFERENCES case_files(case_id),
    assigned_by         TEXT,
    assigned_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_triage_status ON triage_queue (status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_triage_created ON triage_queue (created_at DESC);

COMMIT;
