"""Check which cases are large (>100K entities) and whether they have precomputed data."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"

# Find large cases
rows = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT case_id, topic_name, entity_count FROM case_files WHERE entity_count > 50000 ORDER BY entity_count DESC"
).get("records", [])

print("=== Large Cases (>50K entities) ===")
for r in rows:
    cid = r[0].get("stringValue", "")
    name = r[1].get("stringValue", "")
    count = r[2].get("longValue", 0)
    
    # Check if precomputed data exists
    precomp = client.execute_statement(resourceArn=C, secretArn=S, database=D,
        sql=f"SELECT COUNT(*) FROM typology_precomputed_summary WHERE case_id = '{cid}'"
    ).get("records", [[{}]])
    precomp_count = precomp[0][0].get("longValue", 0)
    
    status = "✅ precomputed" if precomp_count > 0 else "❌ NO precomputed data"
    print(f"  {name}: {count:,} entities - {status} ({cid})")
