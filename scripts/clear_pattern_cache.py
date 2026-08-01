"""Clear the top_pattern_cache and command_center_cache for a specific case."""
import boto3
import sys

CASE_ID = sys.argv[1] if len(sys.argv) > 1 else "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
DB_NAME = "research_analyst"

rds = boto3.client("rds", region_name="us-east-1")
clusters = rds.describe_db_clusters()
cluster_arn = None
for c in clusters["DBClusters"]:
    if "researchanalyst" in c["DBClusterIdentifier"].lower():
        cluster_arn = c["DBClusterArn"]
        break

if not cluster_arn:
    print("ERROR: Could not find Aurora cluster")
    sys.exit(1)

print(f"Cluster: {cluster_arn}")
client = boto3.client("rds-data", region_name="us-east-1")

for table in ["top_pattern_cache", "command_center_cache"]:
    resp = client.execute_statement(
        resourceArn=cluster_arn,
        secretArn=SECRET_ARN,
        database=DB_NAME,
        sql=f"DELETE FROM {table} WHERE case_file_id = '{CASE_ID}'"
    )
    print(f"Deleted {resp.get('numberOfRecordsUpdated', 0)} row(s) from {table}")
