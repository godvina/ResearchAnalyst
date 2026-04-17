-- Migration: Add search_tier column to case_files table
-- Supports multi-backend search (standard = Aurora pgvector, enterprise = OpenSearch Serverless)
-- All existing rows automatically get 'standard' via DEFAULT

ALTER TABLE case_files
    ADD COLUMN search_tier VARCHAR(20) NOT NULL DEFAULT 'standard'
    CHECK (search_tier IN ('standard', 'enterprise'));
