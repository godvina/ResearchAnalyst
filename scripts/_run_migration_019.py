"""Run migration 019 directly via RDS Data API."""
import boto3
import sys

REGION = "us-east-1"
CLUSTER_ID = "researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
DATABASE = "research_analyst"

rds = boto3.client("rds", region_name=REGION)
cluster = rds.describe_db_clusters(DBClusterIdentifier=CLUSTER_ID)["DBClusters"][0]
cluster_arn = cluster["DBClusterArn"]
print(f"Cluster ARN: {cluster_arn}")
print(f"HTTP Endpoint: {cluster.get('HttpEndpointEnabled', False)}")

sm = boto3.client("secretsmanager", region_name=REGION)
secrets = sm.list_secrets(Filters=[{"Key": "name", "Values": ["AuroraClusterSecret"]}])
secret_arn = secrets["SecretList"][0]["ARN"]

rds_data = boto3.client("rds-data", region_name=REGION)

# Check if table already exists
result = rds_data.execute_statement(
    resourceArn=cluster_arn,
    secretArn=secret_arn,
    database=DATABASE,
    sql="SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'pre_case_leads'",
)
exists = result["records"][0][0]["longValue"] > 0
print(f"pre_case_leads already exists: {exists}")

if exists:
    print("Migration 019 already applied. Skipping.")
    sys.exit(0)

# Read migration file
with open("src/db/migrations/019_antitrust_pre_case_intelligence.sql", "r") as f:
    sql_content = f.read()

# Remove BEGIN/COMMIT (Data API auto-commits)
sql_content = sql_content.replace("BEGIN;", "").replace("COMMIT;", "")

# Remove comment-only lines
lines = sql_content.split("\n")
clean_lines = [l for l in lines if not l.strip().startswith("--")]
sql_content = "\n".join(clean_lines)

# Split into individual statements on semicolons that end a statement
# (not inside parentheses)
statements = []
current = []
paren_depth = 0
for line in sql_content.split("\n"):
    for char in line:
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
    current.append(line)
    # A semicolon at paren_depth 0 ends a statement
    if line.rstrip().endswith(";") and paren_depth == 0:
        stmt = "\n".join(current).strip().rstrip(";").strip()
        if stmt:
            statements.append(stmt)
        current = []
        paren_depth = 0

# Add any remaining
if current:
    stmt = "\n".join(current).strip().rstrip(";").strip()
    if stmt:
        statements.append(stmt)

print(f"\nRunning {len(statements)} SQL statements...")

for i, stmt in enumerate(statements):
    if not stmt or stmt.startswith("--"):
        continue
    try:
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=DATABASE,
            sql=stmt + ";",
        )
        print(f"  [{i+1}/{len(statements)}] OK")
    except Exception as e:
        err = str(e)
        if "already exists" in err.lower():
            print(f"  [{i+1}/{len(statements)}] Already exists (OK)")
        else:
            print(f"  [{i+1}/{len(statements)}] ERROR: {err[:150]}")

print("\nMigration 019 complete!")
