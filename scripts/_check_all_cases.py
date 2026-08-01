"""List all cases with their entity counts."""
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
C = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
S = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
D = "research_analyst"

rows = client.execute_statement(resourceArn=C, secretArn=S, database=D,
    sql="SELECT case_id, topic_name, entity_count, relationship_count FROM case_files ORDER BY entity_count DESC"
).get("records", [])

print(f"=== All Cases ({len(rows)}) ===")
for r in rows:
    cid = r[0].get("stringValue", "")
    name = r[1].get("stringValue", "")
    ents = r[2].get("longValue", r[2].get("isNull", 0))
    rels = r[3].get("longValue", r[3].get("isNull", 0))
    if isinstance(ents, bool): ents = 0
    if isinstance(rels, bool): rels = 0
    print(f"  {name:40s} {ents:>10,} entities  {rels:>10,} rels  ({cid[:8]})")
