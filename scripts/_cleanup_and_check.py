"""Clean up stuck pipeline rows and check actual data."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"

# Clean up stuck running rows
r = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="UPDATE pipeline_executions SET status = 'failed', completed_at = NOW() WHERE status = 'running'")
print(f"Cleaned up stuck running rows: {r.get('numberOfRecordsUpdated', 0)}")

# Check total precomputed results
r2 = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT COUNT(*) FROM typology_precomputed_results")
count = r2["records"][0][0].get("longValue", 0)
print(f"Total precomputed_results rows: {count}")

# Check total summary rows
r3 = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT COUNT(*) FROM typology_precomputed_summary")
count3 = r3["records"][0][0].get("longValue", 0)
print(f"Total precomputed_summary rows: {count3}")

# Check pipeline executions
r4 = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT status, COUNT(*) FROM pipeline_executions GROUP BY status")
print(f"\nPipeline execution statuses:")
for row in r4.get("records", []):
    print(f"  {row[0].get('stringValue','')}: {row[1].get('longValue',0)}")
