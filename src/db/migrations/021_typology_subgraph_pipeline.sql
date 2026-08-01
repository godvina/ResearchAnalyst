-- Migration 021: Typology Subgraph Pipeline tables
-- Stores precomputed typology scoring results, aggregated summaries,
-- cross-typology graph data, and pipeline execution tracking.

BEGIN;

-- =============================================================================
-- 1. typology_precomputed_results
--    One row per case × typology × sub-category
-- =============================================================================
CREATE TABLE IF NOT EXISTS typology_precomputed_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    typology_module_id VARCHAR(50) NOT NULL,       -- e.g. 'sex_trafficking'
    sub_category_id VARCHAR(50) NOT NULL,          -- e.g. 'financial_control'
    overall_score FLOAT NOT NULL,                  -- 0.0-1.0
    match_strength VARCHAR(20) NOT NULL,           -- 'strong','moderate','weak'
    cosine_similarity FLOAT,                       -- raw k-NN score
    flag_score FLOAT,                              -- weighted flag evaluation score 0-100
    key_entities JSONB NOT NULL DEFAULT '[]',      -- top 10 entities for this sub-category
    subgraph_summary JSONB NOT NULL DEFAULT '{}',  -- { entity_count, edge_count, hub_entities }
    narrative TEXT,                                 -- Bedrock synthesis, null if weak/pending
    synthesis_status VARCHAR(20) DEFAULT 'completed', -- 'completed','pending','failed'
    is_stale BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(case_id, typology_module_id, sub_category_id)
);

-- =============================================================================
-- 2. typology_precomputed_summary
--    One row per case × typology (aggregated across sub-categories)
-- =============================================================================
CREATE TABLE IF NOT EXISTS typology_precomputed_summary (
    case_id UUID NOT NULL,
    typology_module_id VARCHAR(50) NOT NULL,
    overall_typology_score FLOAT NOT NULL,         -- average of sub-category scores
    match_strength VARCHAR(20) NOT NULL,
    dominant_sub_category VARCHAR(50),
    flags_triggered INTEGER DEFAULT 0,
    total_flags INTEGER DEFAULT 0,
    key_entities JSONB NOT NULL DEFAULT '[]',
    narrative TEXT,
    is_stale BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(case_id, typology_module_id)
);

-- =============================================================================
-- 3. typology_summary_graph
--    One row per case — cross-typology entity/edge graph
-- =============================================================================
CREATE TABLE IF NOT EXISTS typology_summary_graph (
    case_id UUID PRIMARY KEY,
    nodes JSONB NOT NULL,                          -- [{name, type, typologies: [{id, match_strength}], degree}]
    edges JSONB NOT NULL,                          -- [{from, to, type, typology_source}]
    hub_count INTEGER NOT NULL,
    cross_typology_entities JSONB,                 -- entities appearing in 3+ typologies
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_stale BOOLEAN DEFAULT FALSE
);

-- =============================================================================
-- 4. pipeline_executions
--    Tracking + concurrency lock (one running execution per case)
-- =============================================================================
CREATE TABLE IF NOT EXISTS pipeline_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running', -- 'running','completed','failed','partial'
    trigger_source VARCHAR(50),                    -- 'ingestion','manual','incremental'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    per_typology_timing JSONB,                     -- {typology_id: {extract_ms, score_ms, status}}
    error_message TEXT
);

-- Partial unique index: only one running execution per case at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_exec_running
    ON pipeline_executions(case_id)
    WHERE status = 'running';

-- =============================================================================
-- Additional indexes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_typology_results_case
    ON typology_precomputed_results(case_id);

CREATE INDEX IF NOT EXISTS idx_typology_results_stale
    ON typology_precomputed_results(case_id, is_stale)
    WHERE is_stale = TRUE;

CREATE INDEX IF NOT EXISTS idx_pipeline_exec_case
    ON pipeline_executions(case_id, status);

COMMIT;
