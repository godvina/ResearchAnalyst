-- Migration: 003_conspiracy_network_discovery.sql
-- Conspiracy Network Discovery module — 4 new tables for network analysis
-- results, co-conspirator profiles, detected patterns, and sub-case proposals.
--
-- Depends on: case_files(case_id) from src/db/schema.sql
--             ai_decisions(decision_id) from 002_prosecutor_case_review.sql

BEGIN;

-- ============================================================================
-- 1. Cached network analysis results
-- ============================================================================
CREATE TABLE IF NOT EXISTS network_analyses (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    analysis_status VARCHAR(20) NOT NULL DEFAULT 'completed'
        CHECK (analysis_status IN ('processing', 'completed', 'partial', 'failed')),
    primary_subject VARCHAR(500),
    total_entities_analyzed INT NOT NULL DEFAULT 0,
    total_communities INT NOT NULL DEFAULT 0,
    total_persons_of_interest INT NOT NULL DEFAULT 0,
    total_patterns_detected INT NOT NULL DEFAULT 0,
    algorithm_config JSONB DEFAULT '{}',
    community_clusters JSONB DEFAULT '[]',
    centrality_scores JSONB DEFAULT '{}',
    anomaly_entities JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================================
-- 2. Co-conspirator profiles
-- ============================================================================
CREATE TABLE IF NOT EXISTS conspirator_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES network_analyses(analysis_id) ON DELETE CASCADE,
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    entity_name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    aliases JSONB DEFAULT '[]',
    involvement_score INT NOT NULL CHECK (involvement_score BETWEEN 0 AND 100),
    involvement_breakdown JSONB NOT NULL DEFAULT '{}',
    connection_strength INT NOT NULL CHECK (connection_strength BETWEEN 0 AND 100),
    risk_level VARCHAR(10) NOT NULL CHECK (risk_level IN ('high', 'medium', 'low')),
    evidence_summary JSONB DEFAULT '[]',
    relationship_map JSONB DEFAULT '[]',
    document_type_count INT NOT NULL DEFAULT 0,
    potential_charges JSONB DEFAULT '[]',
    ai_legal_reasoning TEXT,
    decision_id UUID REFERENCES ai_decisions(decision_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 3. Detected network patterns (financial, communication, geographic, temporal)
-- ============================================================================
CREATE TABLE IF NOT EXISTS network_patterns (
    pattern_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES network_analyses(analysis_id) ON DELETE CASCADE,
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    pattern_type VARCHAR(20) NOT NULL
        CHECK (pattern_type IN ('financial', 'communication', 'geographic', 'temporal')),
    description TEXT NOT NULL,
    confidence_score INT NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    entities_involved JSONB NOT NULL DEFAULT '[]',
    evidence_documents JSONB NOT NULL DEFAULT '[]',
    ai_reasoning TEXT,
    decision_id UUID REFERENCES ai_decisions(decision_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 4. Sub-case proposals
-- ============================================================================
CREATE TABLE IF NOT EXISTS sub_case_proposals (
    proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    profile_id UUID NOT NULL REFERENCES conspirator_profiles(profile_id) ON DELETE CASCADE,
    sub_case_id UUID,  -- REFERENCES case_files(case_id), NULL until confirmed and created
    proposed_charges JSONB DEFAULT '[]',
    evidence_summary TEXT,
    investigative_steps JSONB DEFAULT '[]',
    case_initiation_brief TEXT,
    decision_id UUID REFERENCES ai_decisions(decision_id),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'confirmed', 'created', 'rejected')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX idx_network_analyses_case ON network_analyses(case_id);
CREATE INDEX idx_network_analyses_status ON network_analyses(analysis_status);
CREATE INDEX idx_conspirator_profiles_case ON conspirator_profiles(case_id);
CREATE INDEX idx_conspirator_profiles_analysis ON conspirator_profiles(analysis_id);
CREATE INDEX idx_conspirator_profiles_risk ON conspirator_profiles(risk_level);
CREATE INDEX idx_conspirator_profiles_score ON conspirator_profiles(involvement_score DESC);
CREATE INDEX idx_network_patterns_case ON network_patterns(case_id);
CREATE INDEX idx_network_patterns_type ON network_patterns(pattern_type);
CREATE INDEX idx_sub_case_proposals_parent ON sub_case_proposals(parent_case_id);
CREATE INDEX idx_sub_case_proposals_status ON sub_case_proposals(status);

COMMIT;
