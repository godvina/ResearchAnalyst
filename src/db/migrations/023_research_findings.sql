-- Migration: 023_research_findings.sql
--
-- Research Findings — persistent store for AI research results linked to taxonomy nodes.
-- Enables findings to feed back into the Pattern Library (evidence accumulation over time).
-- Supports the "concept research → site investigation → taxonomy enrichment" loop.

CREATE TABLE IF NOT EXISTS research_findings (
    finding_id       UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    context_key      VARCHAR(512) NOT NULL,
    finding_type     VARCHAR(50) NOT NULL CHECK (finding_type IN ('concept_briefing', 'site_investigation', 'manual_annotation')),
    evidence_status  VARCHAR(20) NOT NULL CHECK (evidence_status IN ('unexplored', 'inconclusive', 'probable', 'confirmed', 'negative')),
    finding_data     JSONB NOT NULL DEFAULT '{}',
    query            VARCHAR(500) DEFAULT '',
    location         VARCHAR(500) DEFAULT '',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for looking up findings by taxonomy node
CREATE INDEX IF NOT EXISTS idx_findings_context_key ON research_findings (context_key);

-- Index for prefix-based queries (all findings under a domain)
CREATE INDEX IF NOT EXISTS idx_findings_context_prefix ON research_findings USING btree (context_key varchar_pattern_ops);

-- Index for filtering by type
CREATE INDEX IF NOT EXISTS idx_findings_type ON research_findings (finding_type);

-- Index for temporal queries (recent findings first)
CREATE INDEX IF NOT EXISTS idx_findings_created ON research_findings (created_at DESC);

-- Composite index for common query pattern: all findings for a node ordered by recency
CREATE INDEX IF NOT EXISTS idx_findings_node_recent ON research_findings (context_key, created_at DESC);

COMMENT ON TABLE research_findings IS 'Persists AI research results (concept briefings + site investigations) linked to taxonomy nodes for evidence accumulation';
COMMENT ON COLUMN research_findings.context_key IS 'Taxonomy path linking this finding to a Pattern Library node';
COMMENT ON COLUMN research_findings.finding_type IS 'Type of research that produced this finding';
COMMENT ON COLUMN research_findings.evidence_status IS 'Confidence level: drives map dot colors and priority ranking';
COMMENT ON COLUMN research_findings.finding_data IS 'Full JSON payload of the research result (concept briefing or OSINT report)';
