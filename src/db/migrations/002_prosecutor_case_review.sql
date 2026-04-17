-- Migration: 002_prosecutor_case_review.sql
-- Prosecutor Case Review module — 9 new tables for statute library,
-- element assessments, charging decisions, case weaknesses, precedent cases,
-- and AI decision audit trail.
--
-- Depends on: case_files(case_id) from src/db/schema.sql

BEGIN;

-- ============================================================================
-- 1. Statute library: federal statutes and their required elements
-- ============================================================================
CREATE TABLE IF NOT EXISTS statutes (
    statute_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citation VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 2. Statutory elements: discrete legal requirements per statute
-- ============================================================================
CREATE TABLE IF NOT EXISTS statutory_elements (
    element_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statute_id UUID NOT NULL REFERENCES statutes(statute_id) ON DELETE CASCADE,
    display_name VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    element_order INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (statute_id, element_order)
);

-- ============================================================================
-- 3. Case-statute association: which statutes are selected for a case
-- NOTE: case_files(case_id) FK — depends on case_files table from schema.sql.
--       If running this migration before case_files exists, comment out the
--       REFERENCES clause and add the FK constraint after case_files is created.
-- ============================================================================
CREATE TABLE IF NOT EXISTS case_statutes (
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    statute_id UUID NOT NULL REFERENCES statutes(statute_id) ON DELETE CASCADE,
    selected_by VARCHAR(255),
    selected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (case_id, statute_id)
);

-- ============================================================================
-- 4. Element assessments: evidence-element pair ratings
-- NOTE: case_id references case_files(case_id) — see note on table 3.
-- ============================================================================
CREATE TABLE IF NOT EXISTS element_assessments (
    assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    element_id UUID NOT NULL REFERENCES statutory_elements(element_id) ON DELETE CASCADE,
    evidence_id VARCHAR(255) NOT NULL,
    evidence_type VARCHAR(50) NOT NULL,
    rating VARCHAR(10) NOT NULL CHECK (rating IN ('green', 'yellow', 'red')),
    confidence INT NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    reasoning TEXT,
    assessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (case_id, element_id, evidence_id)
);

-- ============================================================================
-- 5. Charging decisions: prosecutor annotations and decisions
-- NOTE: case_id references case_files(case_id) — see note on table 3.
-- ============================================================================
CREATE TABLE IF NOT EXISTS charging_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    statute_id UUID NOT NULL REFERENCES statutes(statute_id) ON DELETE CASCADE,
    decision VARCHAR(50) NOT NULL CHECK (decision IN ('charge', 'decline', 'pending')),
    rationale TEXT,
    approving_attorney VARCHAR(255),
    notes TEXT,
    risk_flags JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 6. Case weaknesses: flagged issues
-- NOTE: case_id references case_files(case_id) — see note on table 3.
-- ============================================================================
CREATE TABLE IF NOT EXISTS case_weaknesses (
    weakness_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    weakness_type VARCHAR(50) NOT NULL
        CHECK (weakness_type IN ('conflicting_statements', 'missing_corroboration',
                                  'suppression_risk', 'brady_material')),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    description TEXT NOT NULL,
    affected_elements JSONB DEFAULT '[]',
    affected_evidence JSONB DEFAULT '[]',
    remediation TEXT,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 7. Precedent case outcomes (seed data for matching)
-- ============================================================================
CREATE TABLE IF NOT EXISTS precedent_cases (
    precedent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_reference VARCHAR(255) NOT NULL,
    charge_type VARCHAR(255) NOT NULL,
    ruling VARCHAR(50) NOT NULL
        CHECK (ruling IN ('guilty', 'not_guilty', 'plea_deal', 'dismissed', 'settled')),
    sentence TEXT,
    judge VARCHAR(255),
    jurisdiction VARCHAR(100),
    case_summary TEXT,
    key_factors JSONB DEFAULT '[]',
    aggravating_factors JSONB DEFAULT '[]',
    mitigating_factors JSONB DEFAULT '[]',
    filed_date DATE,
    resolved_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 8. AI decisions: tracks every AI recommendation through three-state workflow
-- NOTE: case_id references case_files(case_id) — see note on table 3.
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,  -- REFERENCES case_files(case_id) ON DELETE CASCADE
    decision_type VARCHAR(100) NOT NULL,
    state VARCHAR(30) NOT NULL DEFAULT 'ai_proposed'
        CHECK (state IN ('ai_proposed', 'human_confirmed', 'human_overridden')),
    recommendation_text TEXT NOT NULL,
    legal_reasoning TEXT,
    confidence VARCHAR(10) NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    source_service VARCHAR(100),
    related_entity_id VARCHAR(255),
    related_entity_type VARCHAR(50),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    confirmed_by VARCHAR(255),
    overridden_at TIMESTAMP WITH TIME ZONE,
    overridden_by VARCHAR(255),
    override_rationale TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 9. AI decision audit log: chronological history of all state transitions
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_decision_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES ai_decisions(decision_id) ON DELETE CASCADE,
    previous_state VARCHAR(30),
    new_state VARCHAR(30) NOT NULL,
    actor VARCHAR(255) NOT NULL,
    rationale TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX idx_statutory_elements_statute ON statutory_elements(statute_id);
CREATE INDEX idx_case_statutes_case ON case_statutes(case_id);
CREATE INDEX idx_element_assessments_case ON element_assessments(case_id);
CREATE INDEX idx_element_assessments_element ON element_assessments(element_id);
CREATE INDEX idx_charging_decisions_case ON charging_decisions(case_id);
CREATE INDEX idx_case_weaknesses_case ON case_weaknesses(case_id);
CREATE INDEX idx_case_weaknesses_type ON case_weaknesses(weakness_type);
CREATE INDEX idx_precedent_cases_charge ON precedent_cases(charge_type);
CREATE INDEX idx_ai_decisions_case ON ai_decisions(case_id);
CREATE INDEX idx_ai_decisions_state ON ai_decisions(state);
CREATE INDEX idx_ai_decisions_type ON ai_decisions(decision_type);
CREATE INDEX idx_ai_decision_audit_log_decision ON ai_decision_audit_log(decision_id);

COMMIT;
