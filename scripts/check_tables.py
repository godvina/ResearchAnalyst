import boto3
c = boto3.client('rds-data', region_name='us-east-1')
r = c.execute_statement(
    resourceArn='arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco',
    secretArn='arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL',
    database='research_analyst',
    sql="SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
for row in r['records']:
    print(row[0]['stringValue'])
