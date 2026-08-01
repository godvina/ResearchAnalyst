"""Run migration via RDS Data API (HttpEndpointEnabled=True on Aurora).

This is the correct pattern for running migrations against Aurora when
you're not in the VPC. See lessons-learned.md Issue 20.
"""
import boto3
import json

CLUSTER_ARN = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
DATABASE = "research_analyst"

client = boto3.client("rds-data", region_name="us-east-1")

# Read migration file
with open("src/db/migrations/021_typology_subgraph_pipeline.sql", "r") as f:
    content = f.read()

# Parse into individual statements (skip BEGIN/COMMIT, comments, empty lines)
statements = []
current = []
for line in content.split("\n"):
    stripped = line.strip()
    if not stripped or stripped.startswith("--"):
        continue
    if stripped in ("BEGIN;", "COMMIT;"):
        continue
    current.append(line)
    if stripped.endswith(";"):
        statements.append("\n".join(current))
        current = []

print(f"Running {len(statements)} SQL statements via RDS Data API...\n")

for i, stmt in enumerate(statements, 1):
    # Truncate for display
    display = stmt.replace("\n", " ")[:80]
    try:
        resp = client.execute_statement(
            resourceArn=CLUSTER_ARN,
            secretArn=SECRET_ARN,
            database=DATABASE,
            sql=stmt,
        )
        print(f"  [{i}/{len(statements)}] ✓ {display}...")
    except Exception as e:
        err = str(e)
        if "already exists" in err.lower():
            print(f"  [{i}/{len(statements)}] ✓ Already exists")
        else:
            print(f"  [{i}/{len(statements)}] ✗ ERROR: {err[:200]}")

print("\n✓ Migration complete!")
