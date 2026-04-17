BEGIN;

CREATE TABLE IF NOT EXISTS research_conversations (
    conversation_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id           UUID NOT NULL,
    subject_name      VARCHAR(500) NOT NULL,
    subject_type      VARCHAR(100) DEFAULT 'person',
    messages          JSONB NOT NULL DEFAULT '[]',
    research_context  JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_conv_case ON research_conversations(case_id);

COMMIT;
