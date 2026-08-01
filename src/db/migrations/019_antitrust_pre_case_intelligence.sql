-- Migration 019: Antitrust Pre-Case Intelligence
-- Creates tables for the pre-case intelligence module supporting lead intake,
-- AI classification, OSINT data gathering, prosecution readiness assessment,
-- bulk ingestion tracking, conflict-of-interest detection, and immutable audit logging.
-- ADDITIVE ONLY — does not modify any existing tables. Must not break demo case ed0b6c27.

BEGIN;

-- 1. Pre-Case Leads — core lead records for the pre-investigation workflow
CREATE TABLE IF NOT EXISTS pre_case_leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    summary TEXT,
    source_type TEXT NOT NULL CHECK (source_type IN ('tip', 'whistleblower', 'news', 'anomaly', 'referral')),
    source_content JSONB NOT NULL,
    case_type TEXT CHECK (case_type IN ('procurement_collusion', 'price_fixing', 'market_allocation', 'merger_review', 'monopolization', 'criminal_cartel')),
    classification_confidence INTEGER CHECK (classification_confidence BETWEEN 0 AND 100),
    pre_assessment_score INTEGER CHECK (pre_assessment_score BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'intake' CHECK (status IN ('intake', 'classifying', 'gathering', 'assessing', 'monitoring', 'promoted', 'closed')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    assigned_analyst TEXT,
    monitoring_frequency TEXT DEFAULT 'weekly' CHECK (monitoring_frequency IN ('daily', 'weekly', 'monthly')),
    promoted_case_id UUID,
    closure_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Pre-Case Classifications — AI classification results with decision workflow
CREATE TABLE IF NOT EXISTS pre_case_classifications (
    classification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES pre_case_leads(lead_id),
    case_type TEXT NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    reasoning TEXT NOT NULL,
    alternatives JSONB,
    model_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    decision_status TEXT NOT NULL DEFAULT 'ai_proposed' CHECK (decision_status IN ('ai_proposed', 'human_confirmed', 'human_overridden')),
    reviewer_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Pre-Case OSINT Data — provenance records for gathered public data
CREATE TABLE IF NOT EXISTS pre_case_osint_data (
    osint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES pre_case_leads(lead_id),
    source_name TEXT NOT NULL,
    source_url TEXT,
    retrieval_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    data_format TEXT NOT NULL,
    reliability_rating TEXT NOT NULL CHECK (reliability_rating IN ('official_government', 'court_record', 'corporate_filing', 'news_media')),
    raw_data_s3_path TEXT NOT NULL,
    extracted_entities JSONB,
    response_hash TEXT NOT NULL
);

-- 4. Pre-Case Assessments — prosecution readiness scoring and recommendations
CREATE TABLE IF NOT EXISTS pre_case_assessments (
    assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES pre_case_leads(lead_id),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    recommendation TEXT NOT NULL CHECK (recommendation IN ('open_investigation', 'need_more_evidence', 'insufficient_basis')),
    evidence_matrix JSONB NOT NULL,
    evidence_gaps JSONB,
    legal_reasoning TEXT NOT NULL,
    statutes_cited JSONB,
    scoring_framework TEXT NOT NULL,
    model_version TEXT NOT NULL,
    decision_status TEXT NOT NULL DEFAULT 'ai_proposed' CHECK (decision_status IN ('ai_proposed', 'human_confirmed', 'human_overridden')),
    reviewer_id TEXT,
    reviewer_reasoning TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Pre-Case Audit Log — immutable record of all actions on leads
CREATE TABLE IF NOT EXISTS pre_case_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES pre_case_leads(lead_id),
    action_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    action_detail JSONB NOT NULL,
    previous_state JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Pre-Case Bulk Ingestion Jobs — tracking Redshift bulk load operations
CREATE TABLE IF NOT EXISTS pre_case_bulk_ingestion_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    s3_path TEXT NOT NULL,
    target_table TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'resuming')),
    rows_loaded BIGINT DEFAULT 0,
    rows_rejected BIGINT DEFAULT 0,
    rejection_reasons JSONB,
    resume_point TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Pre-Case Conflict Flags — detected conflicts of interest from Form 990 cross-referencing
CREATE TABLE IF NOT EXISTS pre_case_conflict_flags (
    flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES pre_case_leads(lead_id),
    nonprofit_entity TEXT NOT NULL,
    conflicted_party TEXT NOT NULL,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN ('board_overlap', 'related_organization', 'financial_interest')),
    procurement_awards JSONB NOT NULL,
    dollar_amount NUMERIC(15, 2),
    detection_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for query performance
CREATE INDEX idx_leads_status_case_type ON pre_case_leads(status, case_type);
CREATE INDEX idx_leads_analyst ON pre_case_leads(assigned_analyst);
CREATE INDEX idx_leads_score ON pre_case_leads(pre_assessment_score);
CREATE INDEX idx_osint_lead_source ON pre_case_osint_data(lead_id, source_name);
CREATE INDEX idx_audit_lead_time ON pre_case_audit_log(lead_id, created_at);
CREATE INDEX idx_classifications_lead ON pre_case_classifications(lead_id);
CREATE INDEX idx_assessments_lead ON pre_case_assessments(lead_id);
CREATE INDEX idx_bulk_jobs_status ON pre_case_bulk_ingestion_jobs(status);
CREATE INDEX idx_conflict_flags_lead ON pre_case_conflict_flags(lead_id);

-- Immutable audit log rules — prevent modification or deletion of audit records
CREATE RULE prevent_audit_update AS ON UPDATE TO pre_case_audit_log DO INSTEAD NOTHING;
CREATE RULE prevent_audit_delete AS ON DELETE TO pre_case_audit_log DO INSTEAD NOTHING;

COMMIT;
