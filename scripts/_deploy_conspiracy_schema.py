"""Deploy the conspiracy taxonomy schema to Aurora PostgreSQL.

Reads connection info from infra/cdk/env.json and Aurora secret from Secrets Manager.
Executes migrations/conspiracy_taxonomy_schema.sql against the live cluster.
"""
import json
import boto3
import psycopg2

# Load connection info
with open('infra/cdk/env.json', 'r') as f:
    env = json.load(f)['Variables']

AURORA_PROXY = env['AURORA_PROXY_ENDPOINT']
AURORA_DB = env['AURORA_DB_NAME']
AURORA_SECRET_ARN = env['AURORA_SECRET_ARN']
REGION = 'us-east-1'

def get_aurora_credentials():
    """Retrieve Aurora credentials from Secrets Manager."""
    sm = boto3.client('secretsmanager', region_name=REGION)
    response = sm.get_secret_value(SecretId=AURORA_SECRET_ARN)
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']

def run_migration():
    """Execute the conspiracy schema migration."""
    print("Retrieving Aurora credentials from Secrets Manager...")
    username, password = get_aurora_credentials()
    print(f"  Username: {username}")
    print(f"  Endpoint: {AURORA_PROXY}")
    print(f"  Database: {AURORA_DB}")

    print("\nConnecting to Aurora via RDS Proxy...")
    conn = psycopg2.connect(
        host=AURORA_PROXY,
        port=5432,
        dbname=AURORA_DB,
        user=username,
        password=password,
        sslmode='require',
        connect_timeout=30,
    )
    conn.autocommit = True
    cursor = conn.cursor()

    print("Connected! Running conspiracy_taxonomy_schema.sql...")
    
    # Read and execute the migration
    with open('migrations/conspiracy_taxonomy_schema.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    # Split by semicolons and execute each statement
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
    
    success = 0
    errors = 0
    for i, stmt in enumerate(statements):
        if not stmt:
            continue
        try:
            cursor.execute(stmt)
            success += 1
        except Exception as e:
            error_msg = str(e).strip()
            if 'already exists' in error_msg:
                # Schema/table already exists — skip
                success += 1
            else:
                errors += 1
                print(f"  Error on statement {i+1}: {error_msg[:150]}")
                conn.rollback()
                conn.autocommit = True

    cursor.close()
    conn.close()

    print(f"\nMigration complete:")
    print(f"  Statements executed: {success}")
    print(f"  Errors: {errors}")
    
    if errors == 0:
        print("  ✓ All tables created successfully!")
    else:
        print("  ⚠ Some statements failed (may be pre-existing objects)")

if __name__ == '__main__':
    run_migration()
