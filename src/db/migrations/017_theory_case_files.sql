-- Migration 017: Theory Case File persistence
-- Stores AI-generated 12-section case files for theories

CREATE TABLE IF NOT EXISTS theory_case_files (
    case_file_content_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theory_id UUID NOT NULL REFERENCES theories(theory_id) ON DELETE CASCADE,
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_edited_at TIMESTAMP WITH TIME ZONE,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (theory_id)
);

CREATE INDEX IF NOT EXISTS idx_tcf_theory ON theory_case_files(theory_id);
CREATE INDEX IF NOT EXISTS idx_tcf_case ON theory_case_files(case_file_id);

-- Add promoted_sub_case_id to theories table for promote-to-sub-case feature
ALTER TABLE theories ADD COLUMN IF NOT EXISTS promoted_sub_case_id UUID REFERENCES case_files(case_id);
