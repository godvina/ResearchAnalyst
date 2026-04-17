"""Add search_tier column to case_files table via RDS Data API."""
import boto3
import time

REGION = "us-east-1"
CLUSTER_ID = "researchanalyststack-auroracluster23d869c0-18up0bpmkaco"

MIGRATION_SQL = """
ALTER TABLE case_files
ADD COLUMN IF NOT EXISTS search_tier VARCHAR(20) NOT NULL DEFAULT 'standard'
    CHECK (search_tier IN ('standard', 'enterprise'));
"""


def main():
    rds = boto3.client("rds", region_name=REGION)
    cluster = rds.describe_db_clusters(DBClusterIdentifier=CLUSTER_ID)["DBClusters"][0]
    cluster_arn = cluster["DBClusterArn"]

    if not cluster.get("HttpEndpointEnabled", False):
        print("Data API not enabled. Enabling...")
        rds.modify_db_cluster(
            DBClusterIdentifier=CLUSTER_ID,
            EnableHttpEndpoint=True,
            ApplyImmediately=True,
        )
        print("Waiting 90s for Data API to activate...")
        time.sleep(90)

    rds_data = boto3.client("rds-data", region_name=REGION)
    sm = boto3.client("secretsmanager", region_name=REGION)
    secrets = sm.list_secrets(Filters=[{"Key": "name", "Values": ["AuroraClusterSecret"]}])
    secret_arn = secrets["SecretList"][0]["ARN"]

    print("Running migration: ADD search_tier column...")
    try:
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database="research_analyst",
            sql=MIGRATION_SQL,
        )
        print("Migration complete — search_tier column added.")
    except Exception as e:
        err = str(e)
        if "already exists" in err.lower() or "duplicate" in err.lower():
            print("Column already exists — migration already applied.")
        else:
            print(f"Error: {err}")

    # Verify
    result = rds_data.execute_statement(
        resourceArn=cluster_arn,
        secretArn=secret_arn,
        database="research_analyst",
        sql="SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name = 'case_files' AND column_name = 'search_tier';",
    )
    if result.get("records"):
        print(f"Verified: {result['records']}")
    else:
        print("Warning: search_tier column not found in information_schema.")


if __name__ == "__main__":
    main()
