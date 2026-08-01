-- Migration: 024_extend_taxonomy_level_check.sql
-- Extend the taxonomy_level CHECK constraint to include research-related levels.

ALTER TABLE ai_level_summaries DROP CONSTRAINT IF EXISTS ai_level_summaries_taxonomy_level_check;

ALTER TABLE ai_level_summaries ADD CONSTRAINT ai_level_summaries_taxonomy_level_check
    CHECK (taxonomy_level IN ('domain', 'typology', 'method', 'signature', 'precedent_case', 'concept_research', 'research'));
