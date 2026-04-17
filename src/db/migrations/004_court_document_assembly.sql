-- Migration: 004_court_document_assembly.sql
-- Court Document Assembly module tables

-- Document drafts (indictments, evidence summaries, witness lists, etc.)
CREATE TABLE IF NOT EXISTS document_drafts (
    draft_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    document_type VARCHAR(30) NOT NULL
        CHECK (document_type IN ('indictment', 'evidence_summary', 'witness_list',
            'exhibit_list', 'sentencing_memorandum', 'case_brief',
            'motion_in_limine', 'motion_to_compel', 'response_to_motion',
            'notice_of_evidence', 'plea_agreement')),
    title VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'processing', 'final', 'archived')),
    statute_id UUID,
    defendant_id VARCHAR(500),
    is_work_product BOOLEAN DEFAULT FALSE,
    attorney_id VARCHAR(200),
    attorney_name VARCHAR(300),
    sign_off_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document sections (each section is an independent AI decision)
CREATE TABLE IF NOT EXISTS document_sections (
    section_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES document_drafts(draft_id) ON DELETE CASCADE,
    section_type VARCHAR(100) NOT NULL,
    section_order INT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    decision_id UUID REFERENCES ai_decisions(decision_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(draft_id, section_order)
);

-- Document versions (version control with content snapshots)
CREATE TABLE IF NOT EXISTS document_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES document_drafts(draft_id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    content_snapshot JSONB NOT NULL DEFAULT '{}',
    changed_sections JSONB DEFAULT '[]',
    author_id VARCHAR(200),
    author_name VARCHAR(300),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(draft_id, version_number)
);

-- Document templates (for template-based filings)
CREATE TABLE IF NOT EXISTS document_templates (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_type VARCHAR(30) NOT NULL
        CHECK (template_type IN ('motion_in_limine', 'motion_to_compel',
            'response_to_motion', 'notice_of_evidence', 'plea_agreement')),
    template_name VARCHAR(300) NOT NULL,
    template_content TEXT NOT NULL DEFAULT '',
    section_definitions JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Discovery documents (privilege categorization and production tracking)
CREATE TABLE IF NOT EXISTS discovery_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    document_id UUID NOT NULL,
    privilege_category VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (privilege_category IN ('non_privileged', 'attorney_client',
            'work_product', 'brady_material', 'jencks_material', 'pending')),
    production_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (production_status IN ('pending', 'produced', 'withheld')),
    privilege_description TEXT,
    privilege_doctrine TEXT,
    linked_witness_id VARCHAR(500),
    disclosure_alert BOOLEAN DEFAULT FALSE,
    disclosure_alert_at TIMESTAMP WITH TIME ZONE,
    waiver_flag BOOLEAN DEFAULT FALSE,
    decision_id UUID REFERENCES ai_decisions(decision_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(case_id, document_id)
);

-- Production sets (batches of documents produced to defense)
CREATE TABLE IF NOT EXISTS production_sets (
    production_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    production_number INT NOT NULL,
    recipient VARCHAR(500) NOT NULL,
    document_ids JSONB NOT NULL DEFAULT '[]',
    document_count INT NOT NULL DEFAULT 0,
    production_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(case_id, production_number)
);

-- USSG sentencing guidelines reference data
CREATE TABLE IF NOT EXISTS ussg_guidelines (
    guideline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statute_citation VARCHAR(100) NOT NULL,
    base_offense_level INT NOT NULL CHECK (base_offense_level BETWEEN 1 AND 43),
    specific_offense_characteristics JSONB DEFAULT '[]',
    chapter_adjustments JSONB DEFAULT '[]',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_document_drafts_case ON document_drafts(case_id);
CREATE INDEX IF NOT EXISTS idx_document_drafts_type ON document_drafts(document_type);
CREATE INDEX IF NOT EXISTS idx_document_drafts_status ON document_drafts(status);
CREATE INDEX IF NOT EXISTS idx_document_sections_draft ON document_sections(draft_id);
CREATE INDEX IF NOT EXISTS idx_document_sections_decision ON document_sections(decision_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_draft ON document_versions(draft_id);
CREATE INDEX IF NOT EXISTS idx_discovery_documents_case ON discovery_documents(case_id);
CREATE INDEX IF NOT EXISTS idx_discovery_documents_category ON discovery_documents(privilege_category);
CREATE INDEX IF NOT EXISTS idx_discovery_documents_status ON discovery_documents(production_status);
CREATE INDEX IF NOT EXISTS idx_production_sets_case ON production_sets(case_id);
CREATE INDEX IF NOT EXISTS idx_ussg_guidelines_statute ON ussg_guidelines(statute_citation);
