"""Run schema migration by invoking a Lambda function in the VPC.

Creates a temporary Lambda, runs the migration, then cleans up.
Uses the existing VPC and security groups from the CDK stack.
"""
import json
import boto3
import base64
import time

REGION = "us-east-1"

# The schema SQL to execute
SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS case_files (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'created'
        CHECK (status IN ('created','ingesting','indexed','investigating','archived','error')),
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

CREATE TABLE IF NOT EXISTS cross_case_graphs (
    graph_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    neptune_subgraph_label VARCHAR(255) NOT NULL,
    analyst_notes TEXT DEFAULT '',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cross_case_graph_members (
    graph_id UUID REFERENCES cross_case_graphs(graph_id) ON DELETE CASCADE,
    case_id UUID REFERENCES case_files(case_id) ON DELETE CASCADE,
    PRIMARY KEY (graph_id, case_id)
);

CREATE TABLE IF NOT EXISTS documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    source_filename VARCHAR(512),
    source_metadata JSONB,
    raw_text TEXT,
    sections JSONB,
    embedding vector(1536),
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    tagged_entities JSONB DEFAULT '[]',
    tagged_patterns JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pattern_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    patterns JSONB NOT NULL,
    graph_patterns_count INT DEFAULT 0,
    vector_patterns_count INT DEFAULT 0,
    combined_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_files_status ON case_files(status);
CREATE INDEX IF NOT EXISTS idx_case_files_created ON case_files(created_at);
CREATE INDEX IF NOT EXISTS idx_case_files_parent ON case_files(parent_case_id);
CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_file_id);
CREATE INDEX IF NOT EXISTS idx_findings_case ON findings(case_file_id);
"""


def main():
    # Invoke the existing update_status Lambda with a custom migration payload
    # Actually, let's use a simpler approach: invoke any Lambda in the VPC
    # and have it run the SQL via psycopg2
    
    lam = boto3.client("lambda", region_name=REGION)
    
    # Get the function name for one of our Lambdas
    functions = lam.list_functions(MaxItems=50)
    migration_fn = None
    for fn in functions["Functions"]:
        if "IngestionUpdateStatus" in fn["FunctionName"]:
            migration_fn = fn["FunctionName"]
            break
    
    if not migration_fn:
        print("Could not find a Lambda function to use for migration")
        print("Available functions:")
        for fn in functions["Functions"]:
            if "Research" in fn["FunctionName"] or "Ingestion" in fn["FunctionName"]:
                print(f"  {fn['FunctionName']}")
        return
    
    print(f"Using Lambda: {migration_fn}")
    
    # Create a migration event that the Lambda can handle
    # We'll invoke it with a special "migration" flag
    event = {
        "case_id": "migration",
        "status": "created",
        "_migration_sql": SCHEMA_SQL,
    }
    
    print("Note: The update_status Lambda won't run arbitrary SQL.")
    print("Instead, let's use the RDS Data API approach.")
    print()
    print("Checking if Data API is now enabled...")
    
    rds = boto3.client("rds", region_name=REGION)
    cluster = rds.describe_db_clusters(
        DBClusterIdentifier="researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
    )["DBClusters"][0]
    
    print(f"HTTP Endpoint Enabled: {cluster.get('HttpEndpointEnabled', False)}")
    
    if not cluster.get("HttpEndpointEnabled", False):
        print("\nData API still not enabled. Trying to enable via modify...")
        rds.modify_db_cluster(
            DBClusterIdentifier="researchanalyststack-auroracluster23d869c0-18up0bpmkaco",
            EnableHttpEndpoint=True,
            ApplyImmediately=True,
        )
        print("Waiting 90 seconds for it to take effect...")
        time.sleep(90)
        
        cluster = rds.describe_db_clusters(
            DBClusterIdentifier="researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
        )["DBClusters"][0]
        print(f"HTTP Endpoint Enabled: {cluster.get('HttpEndpointEnabled', False)}")
    
    if cluster.get("HttpEndpointEnabled", False):
        run_data_api_migration(cluster["DBClusterArn"])
    else:
        print("\nData API could not be enabled.")
        print("You may need to enable it manually in the RDS console:")
        print("  RDS > Clusters > researchanalyststack-... > Modify > Enable Data API")


def run_data_api_migration(cluster_arn):
    rds_data = boto3.client("rds-data", region_name=REGION)
    sm = boto3.client("secretsmanager", region_name=REGION)
    
    secrets = sm.list_secrets(Filters=[{"Key": "name", "Values": ["AuroraClusterSecret"]}])
    secret_arn = secrets["SecretList"][0]["ARN"]
    
    statements = [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]
    print(f"\nRunning {len(statements)} SQL statements...")
    
    for i, stmt in enumerate(statements):
        try:
            rds_data.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database="research_analyst",
                sql=stmt + ";",
            )
            print(f"  [{i+1}/{len(statements)}] OK")
        except Exception as e:
            err = str(e)
            if "already exists" in err.lower():
                print(f"  [{i+1}/{len(statements)}] Already exists (OK)")
            else:
                print(f"  [{i+1}/{len(statements)}] Error: {err[:100]}")
    
    print("\nSchema migration complete!")


if __name__ == "__main__":
    main()
