"""Update entity_count in case_files for the large case."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"

client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="UPDATE case_files SET entity_count = 248314 WHERE case_id = '7f05e8d5-4492-4f19-8894-25367606db96'")
print("Updated 7f05e8d5... entity_count = 248,314")

client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="UPDATE case_files SET entity_count = 15670 WHERE case_id = 'ed0b6c27-3b6b-4255-b9d0-efe8f4383a99'")
print("Updated ed0b6c27... entity_count = 15,670")

# Verify
r = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT case_id, topic_name, entity_count FROM case_files WHERE entity_count > 0 ORDER BY entity_count DESC LIMIT 5")
print("\nVerification:")
for row in r.get("records", []):
    vals = [f.get("stringValue", f.get("longValue", "")) for f in row]
    print(f"  {vals}")
