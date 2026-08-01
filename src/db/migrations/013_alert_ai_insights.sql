-- Migration: 013_alert_ai_insights.sql
-- Intelligence Evolution — adds AI insight column to trawler_alerts
-- and indicator_snapshot column to trawl_scans.
--
-- Depends on: 011_intelligence_trawler.sql

BEGIN;

-- 1. AI-generated insight per alert
ALTER TABLE trawler_alerts ADD COLUMN IF NOT EXISTS ai_insight TEXT;

-- 2. Command Center indicator snapshot at scan time
ALTER TABLE trawl_scans ADD COLUMN IF NOT EXISTS indicator_snapshot JSONB DEFAULT '{}'::jsonb;

COMMIT;
