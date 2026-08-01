"""Check entity_count for the 345K case."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"
CASE = "7f05e8d5-4492-4f19-8894-25367606db96"

# Check entity_count in case_files
r = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql=f"SELECT entity_count FROM case_files WHERE case_id = '{CASE}'")
print("case_files entity_count:", r.get("records", []))

# Check if entity_count column exists
r2 = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'case_files' AND column_name LIKE '%entity%'")
print("entity columns:", r2.get("records", []))

# Check what columns case_files has
r3 = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT column_name FROM information_schema.columns WHERE table_name = 'case_files' ORDER BY ordinal_position")
print("case_files columns:", [row[0].get("stringValue", "") for row in r3.get("records", [])])
