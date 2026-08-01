-- Migration 012: Signal Mining Tables
-- Feature: investigative-signal-mining
-- Creates tables for IoV-based signal mining findings and monitoring configuration.
-- Does NOT modify any existing pre_case tables (demo case ed0b6c27 safe).

-- ============================================================
-- Table: signal_mining_findings
-- Stores individual investigative findings scored against IoV taxonomies.
-- Supports tree structure via parent_finding_id self-reference.
-- ============================================================

CREATE TABLE IF NOT EXISTS signal_mining_findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL,
    parent_finding_id UUID REFERENCES signal_mining_findings(finding_id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    source_url TEXT,
    signal_strength INT NOT NULL CHECK (signal_strength BETWEEN 0 AND 100),
    tier VARCHAR(10) NOT NULL CHECK (tier IN ('HIGH', 'MEDIUM', 'LOW')),
    matched_indicators JSONB NOT NULL DEFAULT '[]',
    drill_down_depth INT NOT NULL DEFAULT 0 CHECK (drill_down_depth BETWEEN 0 AND 3),
    directive_text TEXT,
    raw_data JSONB DEFAULT '{}',
    is_alert BOOLEAN DEFAULT FALSE,
    alert_dismissed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for signal_mining_findings
CREATE INDEX IF NOT EXISTS idx_smf_lead_id ON signal_mining_findings(lead_id);
CREATE INDEX IF NOT EXISTS idx_smf_parent ON signal_mining_findings(parent_finding_id);
CREATE INDEX IF NOT EXISTS idx_smf_signal_strength ON signal_mining_findings(lead_id, signal_strength DESC);
CREATE INDEX IF NOT EXISTS idx_smf_alerts ON signal_mining_findings(lead_id, is_alert, alert_dismissed);

-- ============================================================
-- Table: signal_mining_monitoring
-- Stores per-lead monitoring configuration for continuous scanning.
-- ============================================================

CREATE TABLE IF NOT EXISTS signal_mining_monitoring (
    monitoring_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    frequency VARCHAR(10) NOT NULL DEFAULT 'weekly'
        CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    last_scan_at TIMESTAMP WITH TIME ZONE,
    next_scan_at TIMESTAMP WITH TIME ZONE,
    scan_count INT NOT NULL DEFAULT 0,
    last_scan_status VARCHAR(20) DEFAULT 'none'
        CHECK (last_scan_status IN ('none', 'success', 'partial', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for signal_mining_monitoring
CREATE INDEX IF NOT EXISTS idx_smm_lead ON signal_mining_monitoring(lead_id);
CREATE INDEX IF NOT EXISTS idx_smm_next_scan ON signal_mining_monitoring(enabled, next_scan_at);
