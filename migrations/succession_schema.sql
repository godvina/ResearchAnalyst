-- =============================================================================
-- Executive Succession Planning Module — Aurora PostgreSQL Schema
-- Deploys within existing research_analyst database
-- Schema: succession.*
-- All tables use Row-Level Security with tenant_id isolation
-- =============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS succession;

-- -----------------------------------------------------------------------------
-- Helper function: current tenant ID from session variable
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION succession.current_tenant_id() RETURNS uuid AS $$
  SELECT current_setting('app.current_tenant')::uuid;
$$ LANGUAGE sql STABLE;

-- =============================================================================
-- TABLE 1: succession.tenants — Organization/tenant registry
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.tenants (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                  VARCHAR(255) NOT NULL,
    cognito_pool_id       VARCHAR(100),
    data_residency_region VARCHAR(20) DEFAULT 'us-east-1',
    settings              JSONB DEFAULT '{}',
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE 2: succession.role_configurations — Weight matrices per sector-country-role
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.role_configurations (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                UUID NOT NULL REFERENCES succession.tenants(id),
    sector                   VARCHAR(20) NOT NULL CHECK (sector IN ('PRIVATE', 'GOVERNMENT', 'MILITARY')),
    country                  VARCHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2
    role_type                VARCHAR(100) NOT NULL,
    context                  VARCHAR(20) DEFAULT 'baseline' CHECK (context IN ('baseline', 'crisis', 'growth')),
    universal_core           JSONB NOT NULL,        -- weights for 5 core attributes
    cultural_flex            JSONB DEFAULT '{}',    -- GLOBE/Hofstede adjustments
    sector_params            JSONB DEFAULT '{}',    -- sector-specific adjustments
    master_variable_weights  JSONB NOT NULL,        -- 15 variables, each 1-10
    universal_core_thresholds JSONB NOT NULL,       -- minimum scores for 5 core attributes
    is_custom                BOOLEAN DEFAULT false,
    created_by               UUID,
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);

-- Partial unique index: only one default config per (tenant, sector, country, role, context)
CREATE UNIQUE INDEX IF NOT EXISTS uq_role_config_default
    ON succession.role_configurations (tenant_id, sector, country, role_type, context)
    WHERE is_custom = false;

-- =============================================================================
-- TABLE 3: succession.scoring_decisions — Full audit trail (partitioned by quarter)
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.scoring_decisions (
    id                    UUID DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL,
    candidate_id          UUID NOT NULL,
    role_config_id        UUID REFERENCES succession.role_configurations(id),
    composite_score       NUMERIC(5,2) NOT NULL CHECK (composite_score BETWEEN 0 AND 100),
    layer_breakdown       JSONB NOT NULL,         -- universal_core, cultural_flex, sector_parameter contributions
    criterion_scores      JSONB NOT NULL,         -- 25 criteria, each 1-10
    master_variable_scores JSONB,                 -- 15 variables
    threshold_violations  JSONB DEFAULT '[]',
    weights_applied       JSONB NOT NULL,
    model_version         VARCHAR(50) DEFAULT '1.0.0',
    below_minimum         BOOLEAN DEFAULT false,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create quarterly partitions for current and next year
CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2025_q1
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2025_q2
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2025_q3
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2025_q4
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');

CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2026_q1
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2026_q2
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2026_q3
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');

CREATE TABLE IF NOT EXISTS succession.scoring_decisions_2026_q4
    PARTITION OF succession.scoring_decisions
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

-- Indexes on scoring_decisions
CREATE INDEX IF NOT EXISTS idx_scoring_decisions_tenant_candidate
    ON succession.scoring_decisions (tenant_id, candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_scoring_decisions_tenant_role_config
    ON succession.scoring_decisions (tenant_id, role_config_id, created_at DESC);

-- =============================================================================
-- TABLE 4: succession.human_overrides — EU AI Act Article 14 compliance
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.human_overrides (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            UUID NOT NULL,
    scoring_decision_id  UUID,  -- References scoring_decisions (partitioned, so no FK constraint)
    candidate_id         UUID NOT NULL,
    action               VARCHAR(20) NOT NULL CHECK (action IN ('ADVANCE', 'ELIMINATE', 'HOLD', 'OVERRIDE_SCORE')),
    rationale            TEXT NOT NULL,
    overridden_by        UUID NOT NULL,           -- Cognito user ID
    authenticated_at     TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE 5: succession.assessment_ingestions — Platform scores and mappings
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.assessment_ingestions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    candidate_id     UUID NOT NULL,
    platform         VARCHAR(50) NOT NULL,         -- SHL, Hogan, Korn_Ferry, DDI
    raw_scores       JSONB NOT NULL,
    mapped_criteria  JSONB NOT NULL,               -- mapped to 25-criteria framework
    mapping_coverage NUMERIC(4,2),                 -- percentage of dimensions mapped
    is_stale         BOOLEAN DEFAULT false,
    ingested_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at       TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 months')
);

CREATE INDEX IF NOT EXISTS idx_assessment_ingestions_tenant_candidate_platform
    ON succession.assessment_ingestions (tenant_id, candidate_id, platform);

-- =============================================================================
-- TABLE 6: succession.consent_records — GDPR/CCPA/PDPA consent
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.consent_records (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL,
    candidate_id      UUID NOT NULL,
    purpose           VARCHAR(100) NOT NULL,
    regulation        VARCHAR(20) NOT NULL,         -- GDPR, CCPA, PDPA, PDPL
    consent_given     BOOLEAN NOT NULL,
    consent_timestamp TIMESTAMPTZ NOT NULL,
    withdrawn_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consent_records_tenant_candidate_regulation
    ON succession.consent_records (tenant_id, candidate_id, regulation);

-- =============================================================================
-- TABLE 7: succession.data_rights_requests — Erasure/access/opt-out tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.data_rights_requests (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL,
    candidate_id  UUID NOT NULL,
    request_type  VARCHAR(20) NOT NULL CHECK (request_type IN ('ERASURE', 'ACCESS', 'OPT_OUT')),
    regulation    VARCHAR(20) NOT NULL,
    received_at   TIMESTAMPTZ NOT NULL,
    deadline_at   TIMESTAMPTZ NOT NULL,
    completed_at  TIMESTAMPTZ,
    status        VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE')),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE 8: succession.bias_reports — Four-fifths rule and chi-squared results
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.bias_reports (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                 UUID NOT NULL,
    role_config_id            UUID,
    four_fifths_results       JSONB,
    chi_squared_results       JSONB,
    protected_characteristics JSONB,               -- gender, age, nationality, ethnicity, education
    flagged                   BOOLEAN DEFAULT false,
    generated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE 9: succession.confirmation_pipeline — US Senate confirmation stages
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.confirmation_pipeline (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL,
    candidate_id  UUID NOT NULL,
    stage         VARCHAR(30) NOT NULL CHECK (stage IN ('FBI_CHECK', 'IRS_REVIEW', 'OGE_DISCLOSURE', 'COMMITTEE_HEARING', 'FLOOR_VOTE')),
    entered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,
    days_elapsed  INT GENERATED ALWAYS AS (EXTRACT(DAY FROM (COALESCE(completed_at, NOW()) - entered_at))::int) STORED,
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS idx_confirmation_pipeline_tenant_candidate_stage
    ON succession.confirmation_pipeline (tenant_id, candidate_id, stage);

-- =============================================================================
-- TABLE 10: succession.saved_scenarios — Named what-if simulations
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.saved_scenarios (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    name             VARCHAR(200) NOT NULL,
    description      TEXT,
    weight_overrides JSONB NOT NULL,
    result_rankings  JSONB,
    base_config_id   UUID REFERENCES succession.role_configurations(id),
    created_by       UUID NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE 11: succession.pipeline_candidates — Internal candidate pipeline tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.pipeline_candidates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    candidate_id    UUID NOT NULL,
    role_id         UUID NOT NULL,
    scenario        VARCHAR(20) NOT NULL CHECK (scenario IN ('EMERGENCY', 'ACCELERATED', 'PLANNED')),
    readiness_score NUMERIC(5,2) CHECK (readiness_score BETWEEN 0 AND 100),
    nine_box_position VARCHAR(20),
    assigned_at     TIMESTAMPTZ DEFAULT NOW(),
    last_evaluated  TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_candidates_tenant_candidate_role
    ON succession.pipeline_candidates (tenant_id, candidate_id, role_id);

-- =============================================================================
-- TABLE 12: succession.development_plans — Gap analysis and milestones
-- =============================================================================
CREATE TABLE IF NOT EXISTS succession.development_plans (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL,
    candidate_id            UUID NOT NULL,
    target_role_id          UUID NOT NULL,
    gaps                    JSONB NOT NULL,         -- criteria below threshold
    milestones              JSONB NOT NULL,         -- assigned developmental experiences
    milestones_completed    INT DEFAULT 0,
    milestones_total        INT DEFAULT 0,
    progress_pct            NUMERIC(5,2) GENERATED ALWAYS AS (
                                CASE WHEN milestones_total > 0
                                     THEN (milestones_completed::numeric / milestones_total * 100)
                                     ELSE 0
                                END
                            ) STORED,
    time_to_readiness_months INT,
    confidence              VARCHAR(10) CHECK (confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- ROW-LEVEL SECURITY — Tenant isolation on ALL tables
-- =============================================================================

-- tenants (RLS on id, not tenant_id)
ALTER TABLE succession.tenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.tenants
    USING (id = succession.current_tenant_id())
    WITH CHECK (id = succession.current_tenant_id());

-- role_configurations
ALTER TABLE succession.role_configurations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.role_configurations
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- scoring_decisions
ALTER TABLE succession.scoring_decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.scoring_decisions
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- human_overrides
ALTER TABLE succession.human_overrides ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.human_overrides
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- assessment_ingestions
ALTER TABLE succession.assessment_ingestions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.assessment_ingestions
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- consent_records
ALTER TABLE succession.consent_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.consent_records
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- data_rights_requests
ALTER TABLE succession.data_rights_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.data_rights_requests
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- bias_reports
ALTER TABLE succession.bias_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.bias_reports
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- confirmation_pipeline
ALTER TABLE succession.confirmation_pipeline ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.confirmation_pipeline
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- saved_scenarios
ALTER TABLE succession.saved_scenarios ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.saved_scenarios
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- pipeline_candidates
ALTER TABLE succession.pipeline_candidates ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.pipeline_candidates
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- development_plans
ALTER TABLE succession.development_plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON succession.development_plans
    USING (tenant_id = succession.current_tenant_id())
    WITH CHECK (tenant_id = succession.current_tenant_id());

-- =============================================================================
-- TRIGGER: Max 50 custom configurations per tenant
-- =============================================================================
CREATE OR REPLACE FUNCTION succession.check_custom_config_limit()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_custom = true THEN
        IF (SELECT COUNT(*) FROM succession.role_configurations
            WHERE tenant_id = NEW.tenant_id AND is_custom = true) >= 50 THEN
            RAISE EXCEPTION 'Maximum 50 custom configurations per tenant';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_custom_config_limit ON succession.role_configurations;
CREATE TRIGGER enforce_custom_config_limit
    BEFORE INSERT ON succession.role_configurations
    FOR EACH ROW EXECUTE FUNCTION succession.check_custom_config_limit();

-- =============================================================================
-- TRIGGER: Auto-update updated_at timestamp
-- =============================================================================
CREATE OR REPLACE FUNCTION succession.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON succession.role_configurations;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON succession.role_configurations
    FOR EACH ROW EXECUTE FUNCTION succession.update_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON succession.development_plans;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON succession.development_plans
    FOR EACH ROW EXECUTE FUNCTION succession.update_updated_at();

-- =============================================================================
-- GRANTS: Lambda database user permissions
-- =============================================================================
GRANT USAGE ON SCHEMA succession TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA succession TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA succession TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA succession GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA succession GRANT ALL ON SEQUENCES TO postgres;

-- =============================================================================
-- END OF MIGRATION
-- =============================================================================
