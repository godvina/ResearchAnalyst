"""Check entities table directly via RDS Data API."""
import boto3
import json

rds = boto3.client('rds-data', region_name='us-east-1')

CLUSTER_ARN = 'arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststac-aborresearchanalystclust-vn50glqxujmv'
SECRET_ARN = 'arn:aws:secretsmanager:us-east-1:974220725866:secret:ResearchAnalystStack-AboRe-AboriginalSecret-kxaLGS0uGxzh'
DATABASE = 'research_analyst'

def query(sql):
    result = rds.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DATABASE,
        sql=sql
    )
    return result['records']

# 1. Total entity count
rows = query("SELECT COUNT(*) FROM entities")
print(f"Total entities in table: {rows[0][0].get('longValue', 0)}")

# 2. Count by case_file_id
rows = query("SELECT case_file_id, COUNT(*) as cnt FROM entities GROUP BY case_file_id ORDER BY cnt DESC LIMIT 10")
print("\nEntities by case_file_id (top 10):")
for row in rows:
    case_id = row[0].get('stringValue', str(row[0].get('longValue', '?')))
    count = row[1].get('longValue', 0)
    print(f"  {case_id}: {count:,}")

# 3. Check specific cases
test_ids = [
    '7f05e8d5-3b1a-4c2d-9e6f-8a7b5c4d3e2f',
    'ed0b6c27-1a2b-3c4d-5e6f-7a8b9c0d1e2f',
    '11111111-aaaa-bbbb-cccc-111111111111',
    '1354d90a-9c26-4c51-9370-f618570335a3',
]
print("\nEntity counts for specific cases:")
for cid in test_ids:
    rows = query(f"SELECT COUNT(*) FROM entities WHERE case_file_id = '{cid}'")
    count = rows[0][0].get('longValue', 0)
    print(f"  {cid[:8]}: {count:,}")

# 4. Check if there's a different schema or table
rows = query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%entit%'")
print("\nEntity-related tables:")
for row in rows:
    print(f"  {row[0].get('stringValue', '?')}")

# 5. Check schemas
rows = query("SELECT DISTINCT schemaname FROM pg_tables WHERE tablename = 'entities'")
print("\nSchemas containing 'entities' table:")
for row in rows:
    print(f"  {row[0].get('stringValue', '?')}")
