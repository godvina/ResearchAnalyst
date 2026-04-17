import boto3
c = boto3.client('rds-data', region_name='us-east-1')
r = c.execute_statement(
    resourceArn='arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco',
    secretArn='arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL',
    database='research_analyst',
    sql="SELECT case_id::text, topic_name, document_count, entity_count, relationship_count FROM case_files ORDER BY entity_count DESC LIMIT 15")
for row in r['records']:
    cid = row[0]['stringValue'][:12]
    name = (row[1].get('stringValue') or '?')[:40]
    docs = row[2].get('longValue', 0)
    ents = row[3].get('longValue', 0)
    rels = row[4].get('longValue', 0)
    print(f"{cid} | {name:40s} | docs:{docs:6d} | ents:{ents:6d} | rels:{rels:6d}")
