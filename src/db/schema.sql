-- Research Analyst Platform — Aurora Serverless v2 (PostgreSQL + pgvector) Schema
-- Requires: CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Case file metadata
CREATE TABLE case_files (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'created'
        CHECK (status IN ('created', 'ingesting', 'indexed', 'investigating', 'archived', 'error')),
    parent_case_id UUID REFERENCES case_files(case_id) ON DELETE SET NULL,
    s3_prefix VARCHAR(512) NOT NULL,
    neptune_subgraph_label VARCHAR(255) NOT NULL,
    document_count INT DEFAULT 0,
    entity_count INT DEFAULT 0,
    relationship_count INT DEFAULT 0,
    error_details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Cross-case graph metadata
CREATE TABLE cross_case_graphs (
    graph_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    neptune_subgraph_label VARCHAR(255) NOT NULL,
    analyst_notes TEXT DEFAULT '',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Many-to-many: cross-case graphs <-> case files
CREATE TABLE cross_case_graph_members (
    graph_id UUID REFERENCES cross_case_graphs(graph_id) ON DELETE CASCADE,
    case_id UUID REFERENCES case_files(case_id) ON DELETE CASCADE,
    PRIMARY KEY (graph_id, case_id)
);

-- Document metadata and embeddings (pgvector)
CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    source_filename VARCHAR(512),
    source_metadata JSONB,
    raw_text TEXT,
    sections JSONB,
    embedding vector(1536),  -- Bedrock Titan embedding dimension
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Findings log
CREATE TABLE findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    tagged_entities JSONB DEFAULT '[]',
    tagged_patterns JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Pattern reports
CREATE TABLE pattern_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    patterns JSONB NOT NULL,
    graph_patterns_count INT DEFAULT 0,
    vector_patterns_count INT DEFAULT 0,
    combined_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_case_files_status ON case_files(status);
CREATE INDEX idx_case_files_topic ON case_files USING gin(to_tsvector('english', topic_name));
CREATE INDEX idx_case_files_created ON case_files(created_at);
CREATE INDEX idx_case_files_parent ON case_files(parent_case_id);
CREATE INDEX idx_documents_case ON documents(case_file_id);
CREATE INDEX idx_documents_embedding ON documents USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_findings_case ON findings(case_file_id);
