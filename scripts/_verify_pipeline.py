"""Verify pipeline results in Aurora."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"
CASE = "7f05e8d5-4492-4f19-8894-25367606db96"

def q(sql):
    return client.execute_statement(resourceArn=C, secretArn=S, database=D, sql=sql).get("records", [])

print("=== Pre-computed Typology Scores ===")
rows = q(f"SELECT typology_module_id, overall_typology_score, match_strength FROM typology_precomputed_summary WHERE case_id = '{CASE}' ORDER BY overall_typology_score DESC")
for row in rows:
    module = row[0].get("stringValue", "")
    score = row[1].get("doubleValue", row[1].get("stringValue", 0))
    strength = row[2].get("stringValue", "")
    print(f"  {module:<25} score={score:<8} {strength}")

print(f"\nTotal typologies scored: {len(rows)}")

print("\n=== Summary Graph ===")
rows2 = q(f"SELECT hub_count FROM typology_summary_graph WHERE case_id = '{CASE}'")
if rows2:
    print(f"  Hub nodes: {rows2[0][0].get('longValue', 0)}")
else:
    print("  No summary graph found")

print("\n=== Pipeline Execution ===")
rows3 = q(f"SELECT status, started_at, completed_at FROM pipeline_executions WHERE case_id = '{CASE}' ORDER BY started_at DESC LIMIT 1")
if rows3:
    status = rows3[0][0].get("stringValue", "")
    started = rows3[0][1].get("stringValue", "")
    completed = rows3[0][2].get("stringValue", "")
    print(f"  Status: {status}")
    print(f"  Started: {started}")
    print(f"  Completed: {completed}")

print("\n=== Sub-category Detail (top 5 by score) ===")
rows4 = q(f"SELECT typology_module_id, sub_category_id, overall_score, match_strength FROM typology_precomputed_results WHERE case_id = '{CASE}' ORDER BY overall_score DESC LIMIT 5")
for row in rows4:
    module = row[0].get("stringValue", "")
    sub = row[1].get("stringValue", "")
    score = row[2].get("doubleValue", row[2].get("stringValue", 0))
    strength = row[3].get("stringValue", "")
    print(f"  {module}/{sub}: score={score} ({strength})")
