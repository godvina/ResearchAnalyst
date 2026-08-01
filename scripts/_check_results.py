"""Check what's actually in the precomputed results table."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"
CASE = "7f05e8d5-4492-4f19-8894-25367606db96"

def q(sql):
    return client.execute_statement(resourceArn=C, secretArn=S, database=D, sql=sql).get("records", [])

print("=== typology_precomputed_results ===")
rows = q(f"SELECT typology_module_id, sub_category_id, overall_score, match_strength FROM typology_precomputed_results WHERE case_id = '{CASE}' LIMIT 15")
print(f"  Total rows: {len(rows)}")
for row in rows[:10]:
    vals = [f.get("stringValue", f.get("doubleValue", f.get("longValue", ""))) for f in row]
    print(f"  {vals}")

print("\n=== typology_precomputed_summary ===")
rows2 = q(f"SELECT typology_module_id, overall_typology_score, match_strength FROM typology_precomputed_summary WHERE case_id = '{CASE}' LIMIT 15")
print(f"  Total rows: {len(rows2)}")
for row in rows2:
    vals = [f.get("stringValue", f.get("doubleValue", f.get("longValue", ""))) for f in row]
    print(f"  {vals}")

print("\n=== pipeline_executions (latest) ===")
rows3 = q(f"SELECT status, started_at, completed_at FROM pipeline_executions WHERE case_id = '{CASE}' ORDER BY started_at DESC LIMIT 3")
for row in rows3:
    vals = [f.get("stringValue", "") for f in row]
    print(f"  {vals}")
