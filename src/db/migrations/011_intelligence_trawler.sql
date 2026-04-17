-- Migration: 011_intelligence_trawler.sql
-- Intelligence Trawler & Alerts — adds trawler alerts, scan history,
-- and per-case trawl configuration tables.
--
-- Depends on: case_files(case_id) from src/db/schema.sql

BEGIN;

-- ============================================================================
-- 1. Trawler Alerts
-- ============================================================================
CREATE TABLE IF NOT EXISTS trawler_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    scan_id UUID,
    alert_type VARCHAR(30) NOT NULL
        CHECK (alert_type IN (
            'new_connection', 'pattern_change', 'entity_spike',
            'new_evidence_match', 'cross_case_overlap', 'temporal_anomaly',
            'network_expansion', 'external_lead'
        )),
    severity VARCHAR(10) NOT NULL
        CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    entity_names JSONB DEFAULT '[]'::jsonb,
    evidence_refs JSONB DEFAULT '[]'::jsonb,
    source_type VARCHAR(10) NOT NULL DEFAULT 'internal'
        CHECK (source_type IN ('internal', 'osint')),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    is_dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trawler_alerts_case
    ON trawler_alerts(case_id);
CREATE INDEX IF NOT EXISTS idx_trawler_alerts_case_unread
    ON trawler_alerts(case_id)
    WHERE is_read = FALSE AND is_dismissed = FALSE;
CREATE INDEX IF NOT EXISTS idx_trawler_alerts_type
    ON trawler_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_trawler_alerts_severity
    ON trawler_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_trawler_alerts_source
    ON trawler_alerts(source_type);
CREATE INDEX IF NOT EXISTS idx_trawler_alerts_created
    ON trawler_alerts(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trawler_alerts_entities
    ON trawler_alerts USING GIN(entity_names);
CREATE INDEX IF NOT EXISTS idx_trawler_alerts_dedup
    ON trawler_alerts(case_id, alert_type, created_at)
    WHERE is_dismissed = FALSE;

-- ============================================================================
-- 2. Trawl Scans (audit trail)
-- ============================================================================
CREATE TABLE IF NOT EXISTS trawl_scans (
    scan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    alerts_generated INTEGER DEFAULT 0,
    scan_status VARCHAR(15) NOT NULL DEFAULT 'running'
        CHECK (scan_status IN ('running', 'completed', 'failed', 'partial')),
    scan_type VARCHAR(15) NOT NULL DEFAULT 'full'
        CHECK (scan_type IN ('full', 'targeted')),
    phase_timings JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    pattern_baseline JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_trawl_scans_case
    ON trawl_scans(case_id);
CREATE INDEX IF NOT EXISTS idx_trawl_scans_case_time
    ON trawl_scans(case_id, started_at DESC);

-- ============================================================================
-- 3. Trawl Configuration (per-case)
-- ============================================================================
CREATE TABLE IF NOT EXISTS trawl_configs (
    case_id UUID PRIMARY KEY,
    enabled_alert_types JSONB DEFAULT '["new_connection","pattern_change","entity_spike","new_evidence_match","cross_case_overlap","temporal_anomaly","network_expansion"]'::jsonb,
    min_severity VARCHAR(10) DEFAULT 'low'
        CHECK (min_severity IN ('critical', 'high', 'medium', 'low')),
    external_trawl_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMIT;
