-- Migration 010: Top pattern cache for investigative patterns
-- Caches Top 5 pattern results per case file with 15-minute TTL

CREATE TABLE IF NOT EXISTS top_pattern_cache (
    case_file_id UUID NOT NULL,
    cached_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    top_patterns JSONB NOT NULL,
    PRIMARY KEY (case_file_id)
);
