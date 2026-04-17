-- Migration 008: Investigation Findings (Research Notebook)
-- Stores saved search results, AI assessments, and investigator notes

CREATE TABLE IF NOT EXISTS investigation_findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL DEFAULT 'investigator',
    query TEXT,
    finding_type VARCHAR(50) NOT NULL DEFAULT 'search_result',
    title VARCHAR(500),
    summary TEXT,
    full_assessment JSONB,
    source_citations JSONB DEFAULT '[]'::jsonb,
    entity_names JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    investigator_notes TEXT,
    confidence_level VARCHAR(50),
    is_key_evidence BOOLEAN DEFAULT FALSE,
    needs_follow_up BOOLEAN DEFAULT FALSE,
    s3_artifact_key VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_findings_case_id ON investigation_findings(case_id);
CREATE INDEX IF NOT EXISTS idx_findings_entity_names ON investigation_findings USING GIN(entity_names);
CREATE INDEX IF NOT EXISTS idx_findings_tags ON investigation_findings USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_findings_created_at ON investigation_findings(case_id, created_at DESC);
