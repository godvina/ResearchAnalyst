"""Run SQL migrations via RDS Data API against the correct Aurora cluster."""
import boto3
import sys
import re

CLUSTER_ARN = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
DATABASE = "research_analyst"

client = boto3.client('rds-data', region_name='us-east-1')

for sql_file in sys.argv[1:]:
    print(f"\n=== Running {sql_file} ===")
    with open(sql_file) as f:
        sql = f.read()
    # Split by semicolons, skip empty
    statements = [s.strip() for s in sql.split(';') if s.strip() and len(s.strip()) > 10]
    ok = 0
    for i, stmt in enumerate(statements):
        try:
            client.execute_statement(
                resourceArn=CLUSTER_ARN, secretArn=SECRET_ARN,
                database=DATABASE, sql=stmt)
            ok += 1
            print(f"  [{i+1}/{len(statements)}] OK")
        except Exception as e:
            err = str(e)[:100]
            if 'already exists' in err:
                ok += 1
                print(f"  [{i+1}/{len(statements)}] EXISTS (ok)")
            else:
                print(f"  [{i+1}/{len(statements)}] ERROR: {err}")
    print(f"  {ok}/{len(statements)} statements applied")
