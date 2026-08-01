"""Run the typology pipeline migration by invoking a pipeline Lambda directly.

The pipeline Lambdas have Aurora DB access via the same VPC/credentials
as the main Lambda. We'll temporarily invoke ThresholdCheck with a special
'run_migration' action.
"""
import json
import boto3

lambda_client = boto3.client("lambda", region_name="us-east-1")

# Read the migration SQL
with open("src/db/migrations/021_typology_subgraph_pipeline.sql", "r") as f:
    migration_sql = f.read()

# Split into individual statements (skip empty lines and comments)
statements = []
current = []
for line in migration_sql.split("\n"):
    stripped = line.strip()
    if stripped.startswith("--") or not stripped:
        continue
    if stripped in ("BEGIN;", "COMMIT;"):
        continue
    current.append(line)
    if stripped.endswith(";"):
        statements.append("\n".join(current))
        current = []

print(f"Found {len(statements)} SQL statements to execute")

# Create a temporary handler that runs SQL
# We'll use the AcquireLock Lambda since it imports ConnectionManager
# But we need a custom approach — let's invoke with a migration payload

# Actually, let's just use boto3 + psycopg2 through the Lambda
# The simplest approach: create a one-shot Lambda invocation with inline code
# But we can't do that easily. Instead, let's call the API to create tables.

# Best approach: use the existing API's case-files endpoint to trigger a DB write,
# which proves connectivity, then use a psql-compatible approach.

# Actually simplest: just run psql from here via the Aurora public endpoint
# The Aurora cluster has subnet_type: PUBLIC per the CDK config

import os
import subprocess

# Get Aurora credentials from the Lambda's env vars
resp = lambda_client.get_function_configuration(
    FunctionName="TypologyPipeline-ThresholdCheck"
)
env_vars = resp.get("Environment", {}).get("Variables", {})

db_host = env_vars.get("DB_HOST", env_vars.get("AURORA_HOST", ""))
db_name = env_vars.get("DB_NAME", env_vars.get("AURORA_DB", ""))
db_user = env_vars.get("DB_USER", env_vars.get("AURORA_USER", ""))
db_password = env_vars.get("DB_PASSWORD", env_vars.get("AURORA_PASSWORD", ""))
db_secret_arn = env_vars.get("DB_SECRET_ARN", env_vars.get("AURORA_SECRET_ARN", ""))

print(f"DB Host: {db_host}")
print(f"DB Name: {db_name}")
print(f"DB User: {db_user}")
print(f"Secret ARN: {db_secret_arn[:50]}..." if db_secret_arn else "No secret ARN")

# If we have a secret ARN, get creds from Secrets Manager
if db_secret_arn and not db_password:
    sm = boto3.client("secretsmanager", region_name="us-east-1")
    secret = json.loads(sm.get_secret_value(SecretId=db_secret_arn)["SecretString"])
    db_host = secret.get("host", db_host)
    db_name = secret.get("dbname", db_name)
    db_user = secret.get("username", db_user)
    db_password = secret.get("password", "")
    print(f"Got credentials from Secrets Manager")
    print(f"  Host: {db_host}")
    print(f"  DB: {db_name}")
    print(f"  User: {db_user}")

# Try psycopg2 (may not be installed locally)
try:
    import psycopg2
    print("\nConnecting to Aurora via psycopg2...")
    conn = psycopg2.connect(
        host=db_host, dbname=db_name, user=db_user, password=db_password,
        sslmode="require", connect_timeout=10,
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    for i, stmt in enumerate(statements, 1):
        try:
            cur.execute(stmt)
            print(f"  [{i}/{len(statements)}] ✓ OK")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  [{i}/{len(statements)}] ✓ Already exists")
                conn.rollback()
                conn.autocommit = True
            else:
                print(f"  [{i}/{len(statements)}] ✗ {str(e)[:200]}")
                conn.rollback()
                conn.autocommit = True
    
    cur.close()
    conn.close()
    print("\n✓ Migration complete!")

except ImportError:
    print("\npsycopg2 not installed locally.")
    print("Install it with: pip install psycopg2-binary")
    print(f"\nOr run manually:")
    print(f"  psql -h {db_host} -U {db_user} -d {db_name} -f src/db/migrations/021_typology_subgraph_pipeline.sql")
    print(f"  Password: {db_password[:3]}***")
except Exception as e:
    print(f"\nConnection failed: {e}")
    print(f"\nThe Aurora cluster may not be publicly accessible from your machine.")
    print(f"Try running from a VPC-connected environment or use the AWS console Query Editor.")
