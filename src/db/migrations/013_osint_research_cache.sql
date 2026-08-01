BEGIN;

CREATE TABLE IF NOT EXISTS osint_research_cache (
    cache_key         VARCHAR(64) PRIMARY KEY,  -- SHA-256 hex
    case_id           UUID NOT NULL,
    research_type     VARCHAR(20) NOT NULL,     -- entity, pattern, question
    context_summary   TEXT NOT NULL,            -- human-readable context label
    research_card     JSONB NOT NULL,           -- full Research Card JSON
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_osint_cache_case_id ON osint_research_cache(case_id);
CREATE INDEX IF NOT EXISTS idx_osint_cache_updated ON osint_research_cache(updated_at);

COMMIT;
