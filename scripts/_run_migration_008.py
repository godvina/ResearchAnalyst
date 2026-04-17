"""Run migration 008: investigation_findings table."""
import boto3

REGION = "us-east-1"
CLUSTER_ARN = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"

SQL = """
CREATE TABLE IF NOT EXISTS investigation_findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL DEFAULT 'investigator',
    query TEXT,
    finding_type VARCHAR(50) NOT NULL DEFAULT 'search_result',
    title VARCHAR(500),
    summary TEXT,
    full_assessment JSONB,
    source_citations JSONB DEFAULT '[]'::jsonb,
    entity_names JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    investigator_notes TEXT,
    confidence_level VARCHAR(50),
    is_key_evidence BOOLEAN DEFAULT FALSE,
    needs_follow_up BOOLEAN DEFAULT FALSE,
    s3_artifact_key VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_findings_case_id ON investigation_findings(case_id);
CREATE INDEX IF NOT EXISTS idx_findings_entity_names ON investigation_findings USING GIN(entity_names);
CREATE INDEX IF NOT EXISTS idx_findings_tags ON investigation_findings USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_findings_created_at ON investigation_findings(case_id, created_at DESC);
"""

def main():
    sm = boto3.client("secretsmanager", region_name=REGION)
    secrets = sm.list_secrets(Filters=[{"Key": "name", "Values": ["AuroraClusterSecret"]}])
    secret_arn = secrets["SecretList"][0]["ARN"]

    rds_data = boto3.client("rds-data", region_name=REGION)
    stmts = [s.strip() for s in SQL.split(";") if s.strip()]
    print(f"Running {len(stmts)} statements...")
    for i, stmt in enumerate(stmts):
        try:
            rds_data.execute_statement(
                resourceArn=CLUSTER_ARN, secretArn=secret_arn,
                database="research_analyst", sql=stmt + ";",
            )
            print(f"  [{i+1}] OK")
        except Exception as e:
            err = str(e)
            if "already exists" in err.lower():
                print(f"  [{i+1}] Already exists")
            else:
                print(f"  [{i+1}] Error: {err[:200]}")
    print("Done!")

if __name__ == "__main__":
    main()
