-- Migration: 005_investigator_ai_first.sql
-- Investigator AI-First module tables

CREATE TABLE IF NOT EXISTS investigator_leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    entity_name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    lead_priority_score INT NOT NULL CHECK (lead_priority_score BETWEEN 0 AND 100),
    evidence_strength FLOAT DEFAULT 0.0,
    connection_density FLOAT DEFAULT 0.0,
    novelty FLOAT DEFAULT 0.0,
    prosecution_readiness FLOAT DEFAULT 0.0,
    ai_justification TEXT,
    recommended_actions JSONB DEFAULT '[]',
    decision_id UUID REFERENCES ai_decisions(decision_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_triage_results (
    triage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    document_id UUID NOT NULL,
    doc_type_classification VARCHAR(30) NOT NULL
        CHECK (doc_type_classification IN ('email', 'financial_record', 'legal_filing',
            'testimony', 'report', 'correspondence', 'other')),
    identified_entities JSONB DEFAULT '[]',
    high_priority_findings JSONB DEFAULT '[]',
    linked_leads JSONB DEFAULT '[]',
    prosecution_readiness_impact VARCHAR(20) DEFAULT 'neutral'
        CHECK (prosecution_readiness_impact IN ('strengthens', 'weakens', 'neutral')),
    decision_id UUID REFERENCES ai_decisions(decision_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS investigator_analysis_cache (
    cache_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE UNIQUE,
    analysis_result JSONB NOT NULL DEFAULT '{}',
    evidence_count_at_analysis INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'completed'
        CHECK (status IN ('processing', 'completed', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS investigator_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    last_session_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(case_id, user_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_investigator_leads_case ON investigator_leads(case_id);
CREATE INDEX IF NOT EXISTS idx_investigator_leads_score ON investigator_leads(lead_priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_triage_case ON evidence_triage_results(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_triage_doc_type ON evidence_triage_results(doc_type_classification);
CREATE INDEX IF NOT EXISTS idx_analysis_cache_case ON investigator_analysis_cache(case_id);
CREATE INDEX IF NOT EXISTS idx_investigator_sessions_case_user ON investigator_sessions(case_id, user_id);
