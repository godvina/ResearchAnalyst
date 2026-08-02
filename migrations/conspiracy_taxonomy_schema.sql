-- Conspiracy Theory Taxonomy Schema
-- Creates the 'conspiracy' schema with all tables for the universal taxonomy,
-- document tracking, signature matching, ACH scoring, validation, and auditing.
-- Run against Aurora PostgreSQL in account 974220725866, us-east-1.

CREATE SCHEMA IF NOT EXISTS conspiracy;

-- ============================================================
-- 5-LEVEL TAXONOMY HIERARCHY
-- (Domain → Typology → Method → Signature → Precedent Case)
-- ============================================================

CREATE TABLE conspiracy.domains (
    domain_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(128) NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE conspiracy.typologies (
    typology_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id       UUID NOT NULL REFERENCES conspiracy.domains(domain_id),
    name            VARCHAR(128) NOT NULL,
    description     TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(domain_id, name)
);

CREATE TABLE conspiracy.methods (
    method_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    typology_id     UUID NOT NULL REFERENCES conspiracy.typologies(typology_id),
    name            VARCHAR(128) NOT NULL,
    description     TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(typology_id, name)
);

CREATE TABLE conspiracy.signatures (
    signature_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    method_id       UUID NOT NULL REFERENCES conspiracy.methods(method_id),
    context_key     VARCHAR(512) NOT NULL UNIQUE,
    description     VARCHAR(512) NOT NULL,
    vector_text     VARCHAR(512) NOT NULL,
    indicators      JSONB NOT NULL DEFAULT '[]',
    precedent_cases JSONB NOT NULL DEFAULT '[]',
    status          VARCHAR(32) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'universal_confirmed', 'deprecated')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE conspiracy.precedent_cases (
    case_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signature_id    UUID NOT NULL REFERENCES conspiracy.signatures(signature_id),
    description     TEXT NOT NULL,
    source_theory   VARCHAR(64) NOT NULL,
    source_reference TEXT,
    confirmed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- DOCUMENT TRACKING
-- ============================================================

CREATE TABLE conspiracy.documents (
    document_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_name     VARCHAR(64) NOT NULL,
    source_file     TEXT NOT NULL,
    source_type     VARCHAR(16) NOT NULL
                    CHECK (source_type IN ('pdf', 'xml', 'csv', 'json', 'html', 'tiff', 'jpeg', 'fasta')),
    s3_key          TEXT NOT NULL,
    content_hash    VARCHAR(64),
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SIGNATURE MATCHING
-- ============================================================

CREATE TABLE conspiracy.signature_matches (
    match_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES conspiracy.documents(document_id),
    signature_id    UUID NOT NULL REFERENCES conspiracy.signatures(signature_id),
    similarity_score FLOAT NOT NULL CHECK (similarity_score BETWEEN 0.0 AND 1.0),
    matched_excerpt TEXT CHECK (char_length(matched_excerpt) <= 1000),
    theory_name     VARCHAR(64) NOT NULL,
    assigned_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, signature_id)
);

-- ============================================================
-- ACH SCORING (Analysis of Competing Hypotheses)
-- ============================================================

CREATE TABLE conspiracy.ach_scores (
    ach_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id        UUID NOT NULL REFERENCES conspiracy.signature_matches(match_id),
    document_id     UUID NOT NULL REFERENCES conspiracy.documents(document_id),
    hypothesis_id   VARCHAR(32) NOT NULL
                    CHECK (hypothesis_id IN ('h_conspiracy', 'h_official', 'h_coincidence', 'h_hybrid')),
    score           SMALLINT NOT NULL CHECK (score BETWEEN -2 AND 2),
    reasoning       TEXT NOT NULL,
    scored_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(match_id, hypothesis_id)
);

CREATE TABLE conspiracy.ach_document_summary (
    document_id         UUID PRIMARY KEY REFERENCES conspiracy.documents(document_id),
    dominant_hypothesis VARCHAR(32) NOT NULL,
    conspiracy_total    INTEGER DEFAULT 0,
    official_total      INTEGER DEFAULT 0,
    coincidence_total   INTEGER DEFAULT 0,
    hybrid_total        INTEGER DEFAULT 0,
    confidence_delta    FLOAT,
    computed_at         TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- REPRODUCIBILITY SCORES (Scientific methodology)
-- ============================================================

CREATE TABLE conspiracy.reproducibility_scores (
    signature_id        UUID PRIMARY KEY REFERENCES conspiracy.signatures(signature_id),
    independent_sources INTEGER NOT NULL DEFAULT 0,
    source_theories     JSONB NOT NULL DEFAULT '[]',
    format_diversity    INTEGER NOT NULL DEFAULT 0,
    reproducibility_score FLOAT NOT NULL DEFAULT 0.0,
    last_updated        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- THEORY-SPECIFIC PATTERNS (below 3-theory threshold)
-- ============================================================

CREATE TABLE conspiracy.theory_specific_patterns (
    pattern_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_name     VARCHAR(64) NOT NULL,
    description     TEXT NOT NULL,
    source_theories JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PROCESSING STATUS (Sequential validation gating)
-- ============================================================

CREATE TABLE conspiracy.processing_status (
    theory_name         VARCHAR(64) PRIMARY KEY,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'validated', 'failed')),
    documents_processed INTEGER DEFAULT 0,
    signatures_matched  INTEGER DEFAULT 0,
    cross_connections   INTEGER DEFAULT 0,
    match_rate          FLOAT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    gap_analysis        JSONB
);

-- Seed processing status for all 10 theories
INSERT INTO conspiracy.processing_status (theory_name) VALUES
    ('bermuda_triangle'),
    ('princess_diana'),
    ('flat_earth'),
    ('ufos_uaps'),
    ('jfk_assassination'),
    ('nine_eleven'),
    ('covid_lab_leak'),
    ('moon_landing'),
    ('vaccine_conspiracies'),
    ('new_world_order');

-- ============================================================
-- UNCLASSIFIED DOCUMENTS (below 0.80 threshold)
-- ============================================================

CREATE TABLE conspiracy.unclassified_documents (
    document_id         UUID PRIMARY KEY REFERENCES conspiracy.documents(document_id),
    highest_score       FLOAT NOT NULL,
    nearest_signature   UUID REFERENCES conspiracy.signatures(signature_id),
    logged_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SKIPPED FILES (unrecognized formats)
-- ============================================================

CREATE TABLE conspiracy.skipped_files (
    id              SERIAL PRIMARY KEY,
    file_path       TEXT NOT NULL,
    detected_format VARCHAR(32),
    theory_name     VARCHAR(64),
    reason          TEXT,
    logged_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- AUDIT LOG
-- ============================================================

CREATE TABLE conspiracy.taxonomy_audit (
    audit_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action          VARCHAR(16) NOT NULL
                    CHECK (action IN ('add', 'remove', 'reclassify', 'update')),
    level           VARCHAR(16) NOT NULL
                    CHECK (level IN ('domain', 'typology', 'method', 'signature', 'precedent_case')),
    context_key     VARCHAR(512),
    old_value       TEXT,
    new_value       TEXT,
    reason          TEXT,
    modified_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PROOF ENGINE (Standards of Proof)
-- ============================================================

CREATE TABLE conspiracy.proof_standards (
    standard_name       VARCHAR(64) PRIMARY KEY,
    description         TEXT NOT NULL,
    checklist_items     JSONB NOT NULL,
    item_weights        JSONB NOT NULL,
    critical_items      JSONB NOT NULL,
    proof_threshold     FLOAT NOT NULL CHECK (proof_threshold BETWEEN 0.0 AND 1.0),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE conspiracy.proof_verdicts (
    verdict_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id      UUID NOT NULL,
    tenant_id       VARCHAR(64) NOT NULL,
    standard_used   VARCHAR(64) NOT NULL REFERENCES conspiracy.proof_standards(standard_name),
    checklist_items JSONB NOT NULL,
    scores          JSONB NOT NULL,
    overall_score   FLOAT NOT NULL CHECK (overall_score BETWEEN 0.0 AND 1.0),
    verdict         VARCHAR(32) NOT NULL
                    CHECK (verdict IN ('PROVEN', 'UNPROVEN', 'INSUFFICIENT_EVIDENCE')),
    reasoning       JSONB NOT NULL,
    evaluated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Seed the 6 proof standards
INSERT INTO conspiracy.proof_standards (standard_name, description, checklist_items, item_weights, critical_items, proof_threshold) VALUES
('scientific', 'Scientific method: hypothesis, significance, replication, peer review, alternative elimination',
 '["Falsifiable hypothesis stated", "Statistical significance demonstrated (p<0.05)", "Independent replication achieved or achievable", "Peer critique addressed", "Alternative explanations systematically eliminated"]',
 '[0.15, 0.25, 0.25, 0.15, 0.20]',
 '["Statistical significance demonstrated (p<0.05)", "Alternative explanations systematically eliminated"]',
 0.70),

('criminal_legal', 'Beyond reasonable doubt: chain of custody, corroboration, no alternative, consistent witnesses, authenticated evidence',
 '["Chain of custody documented", "Independent corroboration obtained", "No credible alternative explanation remaining", "Witness statements consistent and uncoerced", "Evidence authenticated"]',
 '[0.20, 0.25, 0.25, 0.15, 0.15]',
 '["Chain of custody documented", "No credible alternative explanation remaining"]',
 0.85),

('civil_legal', 'Preponderance of evidence: more likely than not',
 '["Balance of probability established", "Positive evidence presented", "More likely than not demonstrated"]',
 '[0.35, 0.35, 0.30]',
 '["More likely than not demonstrated"]',
 0.55),

('intelligence', 'Analytic confidence: source count, independence, diagnostic evidence, alternatives eliminated',
 '["Minimum source count met (2+)", "Source independence verified", "Diagnostic evidence identified", "Alternative hypotheses eliminated via ACH", "Confidence level assigned (Low/Mod/High)"]',
 '[0.20, 0.20, 0.25, 0.20, 0.15]',
 '["Diagnostic evidence identified"]',
 0.65),

('financial_audit', 'Reasonable assurance: materiality, substantive testing, sampling, management consistency',
 '["Materiality threshold exceeded", "Substantive testing performed", "Adequate sampling achieved", "Management assertion consistency verified"]',
 '[0.25, 0.30, 0.20, 0.25]',
 '["Substantive testing performed"]',
 0.75),

('journalistic', 'Publication standard: two sources, right of reply, legal review, public interest',
 '["Two independent sources confirmed", "Subject right of reply offered", "Legal review completed", "Public interest established"]',
 '[0.30, 0.25, 0.20, 0.25]',
 '["Two independent sources confirmed"]',
 0.70);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_sig_matches_theory ON conspiracy.signature_matches(theory_name);
CREATE INDEX idx_sig_matches_signature ON conspiracy.signature_matches(signature_id);
CREATE INDEX idx_documents_theory ON conspiracy.documents(theory_name);
CREATE INDEX idx_documents_hash ON conspiracy.documents(content_hash);
CREATE INDEX idx_signatures_status ON conspiracy.signatures(status);
CREATE INDEX idx_signatures_method ON conspiracy.signatures(method_id);
CREATE INDEX idx_processing_status ON conspiracy.processing_status(status);
CREATE INDEX idx_ach_scores_doc ON conspiracy.ach_scores(document_id);
CREATE INDEX idx_ach_scores_hypothesis ON conspiracy.ach_scores(hypothesis_id);
CREATE INDEX idx_repro_score ON conspiracy.reproducibility_scores(reproducibility_score DESC);
CREATE INDEX idx_proof_verdicts_finding ON conspiracy.proof_verdicts(finding_id);
CREATE INDEX idx_proof_verdicts_tenant ON conspiracy.proof_verdicts(tenant_id);
CREATE INDEX idx_audit_modified ON conspiracy.taxonomy_audit(modified_at DESC);
