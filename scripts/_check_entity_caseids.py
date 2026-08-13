"""Check what case_file_id values exist in the entities table."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"

# Get distinct case_file_id from entities table
r = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT case_file_id, COUNT(*) as cnt FROM entities GROUP BY case_file_id ORDER BY cnt DESC LIMIT 15")
print("Entities table - case_file_id values:")
for row in r.get("records", []):
    cid = row[0].get("stringValue", "?")
    cnt = row[1].get("longValue", 0)
    print(f"  {cid}: {cnt:,}")

# Compare with case_files table
print("\ncase_files table - case_id values:")
r2 = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT case_id, topic_name, entity_count FROM case_files WHERE entity_count > 0 ORDER BY entity_count DESC LIMIT 10")
for row in r2.get("records", []):
    cid = row[0].get("stringValue", "?")
    name = row[1].get("stringValue", "?")
    cnt = row[2].get("longValue", 0)
    print(f"  {cid}: {name} ({cnt:,} entities)")
