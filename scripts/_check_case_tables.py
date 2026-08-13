"""Check both case_files and matters tables to find the ID mismatch."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"

def query(sql):
    r = client.execute_statement(resourceArn=C, secretArn=S, database=D, sql=sql)
    return r.get("records", [])

# Check if matters table exists
print("=== Tables with 'case' or 'matter' in name ===")
rows = query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND (table_name LIKE '%case%' OR table_name LIKE '%matter%')")
for row in rows:
    print(f"  {row[0].get('stringValue', '?')}")

# Check case_files IDs
print("\n=== case_files table (top 5 by entity_count) ===")
rows = query("SELECT case_id, topic_name, entity_count FROM case_files WHERE entity_count > 0 ORDER BY entity_count DESC LIMIT 5")
for row in rows:
    cid = row[0].get("stringValue", "?")
    name = row[1].get("stringValue", "?")
    cnt = row[2].get("longValue", 0)
    print(f"  {cid}: {name} ({cnt:,})")

# Check matters table
print("\n=== matters table ===")
try:
    rows = query("SELECT matter_id, matter_name FROM matters ORDER BY created_at DESC LIMIT 10")
    for row in rows:
        mid = row[0].get("stringValue", "?")
        name = row[1].get("stringValue", "?")
        print(f"  {mid}: {name}")
except Exception as e:
    print(f"  Error: {e}")

# THE KEY CHECK: does the API use matters or case_files?
# The API returned 7f05e8d5-3b1a-4c2d-9e6f-8a7b5c4d3e2f but entities has 7f05e8d5-4492-4f19-8894-25367606db96
print("\n=== Search for 7f05e8d5 prefix in both tables ===")
rows = query("SELECT case_id, topic_name FROM case_files WHERE case_id::text LIKE '7f05e8d5%'")
print("case_files with 7f05e8d5:")
for row in rows:
    print(f"  {row[0].get('stringValue', '?')}: {row[1].get('stringValue', '?')}")

try:
    rows = query("SELECT matter_id, matter_name FROM matters WHERE matter_id::text LIKE '7f05e8d5%'")
    print("matters with 7f05e8d5:")
    for row in rows:
        print(f"  {row[0].get('stringValue', '?')}: {row[1].get('stringValue', '?')}")
except Exception as e:
    print(f"matters table error: {e}")
