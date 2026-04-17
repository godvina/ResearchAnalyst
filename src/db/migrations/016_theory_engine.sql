-- Migration 016: Theory-Driven Investigation Engine
-- Creates the theories table for ACH-based theory management

CREATE TABLE IF NOT EXISTS theories (
    theory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    theory_type VARCHAR(20) NOT NULL
        CHECK (theory_type IN ('financial', 'temporal', 'relational', 'behavioral', 'structural')),
    overall_score INTEGER NOT NULL DEFAULT 50
        CHECK (overall_score >= 0 AND overall_score <= 100),
    evidence_consistency INTEGER NOT NULL DEFAULT 50
        CHECK (evidence_consistency >= 0 AND evidence_consistency <= 100),
    evidence_diversity INTEGER NOT NULL DEFAULT 50
        CHECK (evidence_diversity >= 0 AND evidence_diversity <= 100),
    predictive_power INTEGER NOT NULL DEFAULT 50
        CHECK (predictive_power >= 0 AND predictive_power <= 100),
    contradiction_strength INTEGER NOT NULL DEFAULT 50
        CHECK (contradiction_strength >= 0 AND contradiction_strength <= 100),
    evidence_gaps INTEGER NOT NULL DEFAULT 50
        CHECK (evidence_gaps >= 0 AND evidence_gaps <= 100),
    supporting_entities JSONB NOT NULL DEFAULT '[]',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    verdict VARCHAR(20)
        CHECK (verdict IS NULL OR verdict IN ('confirmed', 'refuted', 'inconclusive')),
    created_by VARCHAR(50) NOT NULL DEFAULT 'ai',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scored_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_theories_case ON theories(case_file_id);
CREATE INDEX IF NOT EXISTS idx_theories_score ON theories(overall_score);
