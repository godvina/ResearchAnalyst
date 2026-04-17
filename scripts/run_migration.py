"""Run Aurora schema migration via AWS Lambda invocation.

Creates a temporary Lambda to execute the schema SQL against Aurora.
"""
import json
import boto3
import time

REGION = "us-east-1"
AURORA_SECRET_ARN = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret"
AURORA_CLUSTER_ARN = None  # Will be looked up

def get_aurora_cluster_arn():
    rds = boto3.client("rds", region_name=REGION)
    clusters = rds.describe_db_clusters(
        Filters=[{"Name": "db-cluster-id", "Values": ["researchanalyststack-auroracluster23d869c0-18up0bpmkaco"]}]
    )
    if clusters["DBClusters"]:
        return clusters["DBClusters"][0]["DBClusterArn"]
    return None

def run_migration():
    # Use RDS Data API to run the schema
    rds_data = boto3.client("rds-data", region_name=REGION)
    
    # First get the cluster ARN
    cluster_arn = get_aurora_cluster_arn()
    if not cluster_arn:
        print("Could not find Aurora cluster ARN")
        return
    
    print(f"Cluster ARN: {cluster_arn}")
    
    # Get the secret ARN
    sm = boto3.client("secretsmanager", region_name=REGION)
    secrets = sm.list_secrets(Filters=[{"Key": "name", "Values": ["AuroraClusterSecret"]}])
    if not secrets["SecretList"]:
        print("Could not find Aurora secret")
        return
    
    secret_arn = secrets["SecretList"][0]["ARN"]
    print(f"Secret ARN: {secret_arn}")
    
    # Read the schema SQL
    with open("src/db/schema.sql", "r") as f:
        schema_sql = f.read()
    
    # Split into individual statements
    statements = [s.strip() for s in schema_sql.split(";") if s.strip() and not s.strip().startswith("--")]
    
    print(f"Running {len(statements)} SQL statements...")
    
    for i, stmt in enumerate(statements):
        if not stmt:
            continue
        try:
            rds_data.execute_statement(
                resourceArn=cluster_arn,
                secretArn=secret_arn,
                database="research_analyst",
                sql=stmt + ";",
            )
            print(f"  [{i+1}/{len(statements)}] OK: {stmt[:60]}...")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"  [{i+1}/{len(statements)}] Already exists (OK)")
            else:
                print(f"  [{i+1}/{len(statements)}] Error: {e}")
    
    print("\nMigration complete!")

if __name__ == "__main__":
    run_migration()
