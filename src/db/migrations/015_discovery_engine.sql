BEGIN;

-- discovery_feedback: stores thumbs-up/down per discovery
CREATE TABLE IF NOT EXISTS discovery_feedback (
    feedback_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discovery_id    UUID NOT NULL,
    case_id         UUID NOT NULL,
    user_id         VARCHAR(255) NOT NULL,
    rating          SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    discovery_type  VARCHAR(50) NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_discovery_feedback_case ON discovery_feedback(case_id);

-- discovery_history: tracks generated batches per case
CREATE TABLE IF NOT EXISTS discovery_history (
    discovery_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL,
    batch_number    INTEGER NOT NULL,
    discoveries     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_discovery_history_case ON discovery_history(case_id);

COMMIT;
