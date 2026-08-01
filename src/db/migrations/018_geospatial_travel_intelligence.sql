-- Migration 018: Geospatial Travel Intelligence — IPS Engine tables
-- Stores computed Investigative Priority Score (IPS) results and computation run tracking.
-- The IPS algorithm combines graph topology signals (30%), prosecutorial evidence signals (40%),
-- and AI insight signals (30%) into a transparent 0-100 score for each detected pattern.

-- 1. IPS Results — one row per detected pattern per computation run
CREATE TABLE IF NOT EXISTS case_ips_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL,
    pattern_index INTEGER NOT NULL,
    pattern_type VARCHAR(30) NOT NULL,

    -- IPS Scores
    ips_total DOUBLE PRECISION NOT NULL DEFAULT 0,
    ips_partial BOOLEAN NOT NULL DEFAULT false,

    -- Layer 1: Graph Topology (each 0-25, total 0-100)
    l1_betweenness DOUBLE PRECISION NOT NULL DEFAULT 0,
    l1_temporal_clustering DOUBLE PRECISION NOT NULL DEFAULT 0,
    l1_cross_type_bridge DOUBLE PRECISION NOT NULL DEFAULT 0,
    l1_isolation_anomaly DOUBLE PRECISION NOT NULL DEFAULT 0,
    l1_total DOUBLE PRECISION NOT NULL DEFAULT 0,

    -- Layer 2: Prosecutorial Evidence (each 0-20, total 0-100)
    l2_the_act DOUBLE PRECISION NOT NULL DEFAULT 0,
    l2_the_means DOUBLE PRECISION NOT NULL DEFAULT 0,
    l2_the_network DOUBLE PRECISION NOT NULL DEFAULT 0,
    l2_the_pattern DOUBLE PRECISION NOT NULL DEFAULT 0,
    l2_the_gap DOUBLE PRECISION NOT NULL DEFAULT 0,
    l2_total DOUBLE PRECISION NOT NULL DEFAULT 0,

    -- Layer 3: AI Insight (0-100)
    l3_ai_insight DOUBLE PRECISION NOT NULL DEFAULT 0,

    -- Pattern Data
    title VARCHAR(255) NOT NULL,
    narrative TEXT NOT NULL,
    icon VARCHAR(10) DEFAULT '📊',
    priority VARCHAR(10) NOT NULL DEFAULT 'medium',
    persons JSONB NOT NULL DEFAULT '[]'::jsonb,
    locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    pattern_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Evidence Gaps
    evidence_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Facilitator flag
    is_facilitator BOOLEAN NOT NULL DEFAULT false,

    -- Timestamps
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '1 hour')
);

CREATE INDEX IF NOT EXISTS idx_ips_results_case ON case_ips_results(case_file_id);
CREATE INDEX IF NOT EXISTS idx_ips_results_case_time ON case_ips_results(case_file_id, computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_ips_results_type ON case_ips_results(pattern_type);
CREATE INDEX IF NOT EXISTS idx_ips_results_score ON case_ips_results(ips_total DESC);


-- 2. IPS Computation Runs — tracks execution state for monitoring and cache invalidation
CREATE TABLE IF NOT EXISTS ips_computation_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL,
    execution_arn VARCHAR(512),
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    layer1_completed BOOLEAN DEFAULT false,
    layer2_completed BOOLEAN DEFAULT false,
    anomalies_completed BOOLEAN DEFAULT false,
    layer3_completed BOOLEAN DEFAULT false,
    patterns_detected INTEGER DEFAULT 0,
    error_details TEXT
);

CREATE INDEX IF NOT EXISTS idx_ips_runs_case ON ips_computation_runs(case_file_id, started_at DESC);
