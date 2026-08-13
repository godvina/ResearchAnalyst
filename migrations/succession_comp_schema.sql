-- =============================================================================
-- Executive Compensation Intelligence — Schema Extension
-- Extends succession.* schema with compensation estimates and process stages
-- Depends on: succession_schema.sql (succession schema + current_tenant_id() function)
-- =============================================================================

-- =============================================================================
-- TABLE: succession.compensation_estimates — Candidate compensation data
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.compensation_estimates (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    candidate_id      UUID NOT NULL,
    transaction_id    VARCHAR(100),
    base_salary       NUMERIC(12,2),
    bonus_amount      NUMERIC(12,2),
    equity_value      NUMERIC(12,2),
    benefits_value    NUMERIC(12,2),
    total_comp        NUMERIC(12,2) NOT NULL,
    currency          VARCHAR(3) DEFAULT 'USD',
    confidence        VARCHAR(10) CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
    lookup_version    VARCHAR(20),
    source            VARCHAR(50),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: succession.process_stages — Pipeline stage tracking with SLA
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.process_stages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    candidate_id      UUID NOT NULL,
    transaction_id    VARCHAR(100),
    stage             VARCHAR(20) NOT NULL CHECK (stage IN (
        'LONG_LIST','SHORT_LIST','APPROACH','SCREEN',
        'ASSESS','OFFER','CLOSE','ONBOARD'
    )),
    entered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exited_at         TIMESTAMPTZ,
    advanced_by       VARCHAR(100),
    notes             TEXT,
    sla_days          INT,
    is_breach         BOOLEAN DEFAULT false
);

-- =============================================================================
-- INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_comp_estimates_tenant_candidate
    ON succession.compensation_estimates (tenant_id, candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_process_stages_tenant_txn
    ON succession.process_stages (tenant_id, transaction_id, stage);

CREATE INDEX IF NOT EXISTS idx_process_stages_candidate
    ON succession.process_stages (tenant_id, candidate_id, entered_at DESC);

-- =============================================================================
-- ROW-LEVEL SECURITY — Tenant isolation
-- =============================================================================

-- compensation_estimates
ALTER TABLE succession.compensation_estimates ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.compensation_estimates
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- process_stages
ALTER TABLE succession.process_stages ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.process_stages
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- =============================================================================
-- GRANTS: Lambda database user permissions (matches succession_schema.sql pattern)
-- =============================================================================
GRANT USAGE ON SCHEMA succession TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA succession TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA succession TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA succession GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA succession GRANT ALL ON SEQUENCES TO postgres;

-- =============================================================================
-- END OF MIGRATION
-- =============================================================================
