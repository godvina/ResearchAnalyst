-- Migration: 022_ai_level_summaries.sql
-- AI Level Summaries — cache table for Bedrock-generated taxonomy level summaries.
-- Stores generated summaries with TTL-based expiration for the Pattern Library
-- 5-level drill-down (Domain → Typology → Method → Signature → Precedent Case).
--
-- Depends on: none (standalone table)

BEGIN;

-- AI-generated summary cache keyed by taxonomy context path
CREATE TABLE IF NOT EXISTS ai_level_summaries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_key             VARCHAR(512) NOT NULL UNIQUE,
    taxonomy_level          VARCHAR(20) NOT NULL
        CHECK (taxonomy_level IN ('domain', 'typology', 'method', 'signature', 'precedent_case')),
    summary_text            TEXT NOT NULL,
    model_id                VARCHAR(128) NOT NULL DEFAULT 'anthropic.claude-3-haiku-20240307-v1:0',
    prompt_token_count      INT NOT NULL DEFAULT 0,
    completion_token_count  INT NOT NULL DEFAULT 0,
    generated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at              TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookup by context key (covers cache-hit path)
CREATE INDEX IF NOT EXISTS idx_ai_level_summaries_context_key
    ON ai_level_summaries(context_key);

-- Expiry queries for cleanup and stale detection
CREATE INDEX IF NOT EXISTS idx_ai_level_summaries_expires_at
    ON ai_level_summaries(expires_at);

-- Filter/aggregate by taxonomy level
CREATE INDEX IF NOT EXISTS idx_ai_level_summaries_level
    ON ai_level_summaries(taxonomy_level);

COMMIT;
