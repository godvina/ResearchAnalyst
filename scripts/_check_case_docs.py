"""Check actual document counts for a case from Aurora documents table."""
import boto3, json, os

CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"  # Epstein Combined

rds = boto3.client("rds-data", region_name="us-east-1")
DB_ARN = os.environ.get("DB_ARN", "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster")
SECRET_ARN = os.environ.get("SECRET_ARN", "")
DB_NAME = "research_analyst"

# Find the secret ARN
sm = boto3.client("secretsmanager", region_name="us-east-1")
secrets = sm.list_secrets(MaxResults=20)
for s in secrets["SecretList"]:
    if "aurora" in s["Name"].lower() or "research" in s["Name"].lower():
        SECRET_ARN = s["ARN"]
        break

if not SECRET_ARN:
    print("Could not find Aurora secret ARN")
    exit(1)

# Query document count
resp = rds.execute_statement(
    resourceArn=DB_ARN, secretArn=SECRET_ARN, database=DB_NAME,
    sql=f"SELECT COUNT(*) FROM documents WHERE case_file_id = '{CASE_ID}'"
)
doc_count = resp["records"][0][0].get("longValue", 0)
print(f"Epstein Combined ({CASE_ID[:8]}): {doc_count} documents in Aurora")

# Also check the case_files metadata
resp2 = rds.execute_statement(
    resourceArn=DB_ARN, secretArn=SECRET_ARN, database=DB_NAME,
    sql=f"SELECT document_count, entity_count, topic_name FROM case_files WHERE case_id = '{CASE_ID}'"
)
if resp2["records"]:
    r = resp2["records"][0]
    print(f"  case_files.document_count = {r[0].get('longValue', 0)}")
    print(f"  case_files.entity_count = {r[1].get('longValue', 0)}")
    print(f"  case_files.topic_name = {r[2].get('stringValue', '?')}")

# Update the count
print(f"\nUpdating document_count to {doc_count}...")
rds.execute_statement(
    resourceArn=DB_ARN, secretArn=SECRET_ARN, database=DB_NAME,
    sql=f"UPDATE case_files SET document_count = {doc_count} WHERE case_id = '{CASE_ID}'"
)
print("Done.")
