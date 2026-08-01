-- Migration: 008_procurement_collusion_detection.sql
-- Procurement Collusion Detection module — adds tables for bid records,
-- contract statistics, collusion analysis results, red flags, collusion
-- rings, and a quarantine table for malformed ingestion records.
--
-- Depends on: case_files(case_id) from src/db/schema.sql
--             ai_decisions(decision_id) from 002_prosecutor_case_review.sql

BEGIN;

-- ============================================================================
-- 1. Procurement bid records
-- ============================================================================
CREATE TABLE IF NOT EXISTS procurement_bids (
    bid_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    record_id VARCHAR(200),
    vendor_id VARCHAR(200) NOT NULL,
    vendor_name VARCHAR(500) NOT NULL,
    contract_id VARCHAR(200) NOT NULL,
    bid_amount NUMERIC(15, 2) NOT NULL CHECK (bid_amount > 0),
    submission_timestamp TIMESTAMP WITH TIME ZONE,
    specifications_met BOOLEAN DEFAULT TRUE,
    award_status VARCHAR(20) NOT NULL CHECK (award_status IN ('won', 'lost', 'withdrawn')),
    government_estimate NUMERIC(15, 2),
    naics_codes JSONB DEFAULT '[]',
    geographic_region VARCHAR(200),
    raw_data JSONB DEFAULT '{}',
    batch_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_bids_case ON procurement_bids(case_id);
CREATE INDEX IF NOT EXISTS idx_procurement_bids_vendor ON procurement_bids(vendor_id);
CREATE INDEX IF NOT EXISTS idx_procurement_bids_contract ON procurement_bids(contract_id);
CREATE INDEX IF NOT EXISTS idx_procurement_bids_amount ON procurement_bids(bid_amount);
CREATE INDEX IF NOT EXISTS idx_procurement_bids_timestamp ON procurement_bids(submission_timestamp);

-- ============================================================================
-- 2. Contract summary statistics (precomputed per contract)
-- ============================================================================
CREATE TABLE IF NOT EXISTS contract_statistics (
    stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    contract_id VARCHAR(200) NOT NULL,
    bid_count INT NOT NULL DEFAULT 0,
    price_min NUMERIC(15, 2),
    price_max NUMERIC(15, 2),
    price_mean NUMERIC(15, 2),
    price_stddev NUMERIC(15, 2),
    price_cv NUMERIC(8, 4),
    winner_margin_pct NUMERIC(8, 4),
    government_estimate NUMERIC(15, 2),
    winning_bid_to_estimate_ratio NUMERIC(8, 4),
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(case_id, contract_id)
);

CREATE INDEX IF NOT EXISTS idx_contract_statistics_case ON contract_statistics(case_id);

-- ============================================================================
-- 3. Collusion analysis results (cached per investigation)
-- ============================================================================
CREATE TABLE IF NOT EXISTS collusion_analyses (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    analysis_status VARCHAR(20) NOT NULL DEFAULT 'completed'
        CHECK (analysis_status IN ('processing', 'completed', 'partial', 'failed')),
    pcsf_score NUMERIC(5, 2) CHECK (pcsf_score >= 0 AND pcsf_score <= 100),
    pcsf_breakdown JSONB DEFAULT '{}',
    total_contracts_analyzed INT DEFAULT 0,
    total_bids_analyzed INT DEFAULT 0,
    total_vendors_analyzed INT DEFAULT 0,
    total_patterns_detected INT DEFAULT 0,
    total_red_flags INT DEFAULT 0,
    total_collusion_rings INT DEFAULT 0,
    bid_rigging_patterns JSONB DEFAULT '[]',
    price_anomalies JSONB DEFAULT '[]',
    communication_patterns JSONB DEFAULT '[]',
    financial_flow_patterns JSONB DEFAULT '[]',
    collusion_rings JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_collusion_analyses_case ON collusion_analyses(case_id);
CREATE INDEX IF NOT EXISTS idx_collusion_analyses_status ON collusion_analyses(analysis_status);

-- ============================================================================
-- 4. Red flags (individual PCSF-aligned indicators)
-- ============================================================================
CREATE TABLE IF NOT EXISTS antitrust_red_flags (
    flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    analysis_id UUID REFERENCES collusion_analyses(analysis_id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL CHECK (category IN (
        'bid_rigging', 'pricing', 'communication', 'financial',
        'market_allocation', 'bid_suppression', 'behavioral'
    )),
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('Critical', 'High', 'Medium', 'Low')),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    evidence_refs JSONB DEFAULT '[]',
    involved_vendors JSONB DEFAULT '[]',
    involved_contracts JSONB DEFAULT '[]',
    pcsf_taxonomy_code VARCHAR(50),
    ai_legal_reasoning TEXT,
    decision_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_red_flags_case ON antitrust_red_flags(case_id);
CREATE INDEX IF NOT EXISTS idx_red_flags_severity ON antitrust_red_flags(severity);
CREATE INDEX IF NOT EXISTS idx_red_flags_category ON antitrust_red_flags(category);
CREATE INDEX IF NOT EXISTS idx_red_flags_analysis ON antitrust_red_flags(analysis_id);

-- ============================================================================
-- 5. Collusion rings (identified vendor groups)
-- ============================================================================
CREATE TABLE IF NOT EXISTS collusion_rings (
    ring_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    analysis_id UUID REFERENCES collusion_analyses(analysis_id) ON DELETE CASCADE,
    ring_name VARCHAR(500),
    member_vendors JSONB NOT NULL DEFAULT '[]',
    member_roles JSONB DEFAULT '{}',
    pcsf_score NUMERIC(5, 2) CHECK (pcsf_score >= 0 AND pcsf_score <= 100),
    scheme_type VARCHAR(50) CHECK (scheme_type IN (
        'complementary_bidding', 'bid_rotation', 'market_allocation',
        'bid_suppression', 'mixed'
    )),
    affected_contracts JSONB DEFAULT '[]',
    timeline JSONB DEFAULT '[]',
    evidence_summary JSONB DEFAULT '{}',
    ai_legal_reasoning TEXT,
    decision_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_collusion_rings_case ON collusion_rings(case_id);
CREATE INDEX IF NOT EXISTS idx_collusion_rings_analysis ON collusion_rings(analysis_id);

-- ============================================================================
-- 6. Procurement quarantine (failed ingestion records)
-- ============================================================================
CREATE TABLE IF NOT EXISTS procurement_quarantine (
    quarantine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    batch_id UUID,
    raw_record JSONB NOT NULL,
    failure_reason VARCHAR(500) NOT NULL,
    source_file VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_quarantine_case ON procurement_quarantine(case_id);
CREATE INDEX IF NOT EXISTS idx_procurement_quarantine_batch ON procurement_quarantine(batch_id);

COMMIT;
