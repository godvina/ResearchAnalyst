"""Deploy the Typology Subgraph Pipeline infrastructure.

Creates 6 Lambda functions for the pipeline, updates the Step Functions
state machine, runs the Aurora migration, and seeds the OpenSearch index.

Usage:
    python scripts/deploy_typology_pipeline.py

Prerequisites:
    - AWS credentials configured (mwinit or env vars)
    - Aurora cluster accessible
    - OPENSEARCH_ENDPOINT env var set
    - Main Lambda already deployed with latest src/ code

This script is idempotent — safe to run multiple times.
"""

import json
import os
import io
import sys
import time
import zipfile

import boto3
from botocore.config import Config

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REGION = "us-east-1"
ACCOUNT_ID = "974220725866"
S3_BUCKET = "research-analyst-data-lake-974220725866"

# The existing main Lambda — we'll reuse its role, VPC config, and layers
MAIN_LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

# Pipeline Lambda names
PIPELINE_LAMBDAS = {
    "ThresholdCheck": {
        "handler": "lambdas.pipeline.threshold_check.handler",
        "timeout": 60,
        "memory": 512,
        "description": "Typology Pipeline: Check if case requires pre-computation",
    },
    "AcquireLock": {
        "handler": "lambdas.pipeline.acquire_lock.handler",
        "timeout": 30,
        "memory": 256,
        "description": "Typology Pipeline: Acquire concurrency lock",
    },
    "ReleaseLock": {
        "handler": "lambdas.pipeline.release_lock.handler",
        "timeout": 30,
        "memory": 256,
        "description": "Typology Pipeline: Release concurrency lock",
    },
    "ExtractSubgraph": {
        "handler": "lambdas.pipeline.extract_subgraph.handler",
        "timeout": 300,
        "memory": 1024,
        "description": "Typology Pipeline: Extract typology-specific subgraph from Neptune",
    },
    "ScoreTypology": {
        "handler": "lambdas.pipeline.score_typology.handler",
        "timeout": 300,
        "memory": 1024,
        "description": "Typology Pipeline: Score subgraph via k-NN + Bedrock",
    },
    "BuildSummaryGraph": {
        "handler": "lambdas.pipeline.build_summary_graph.handler",
        "timeout": 120,
        "memory": 512,
        "description": "Typology Pipeline: Build cross-typology summary graph",
    },
}

STEP_FUNCTION_NAME = "TypologySubgraphPipeline"
STEP_FUNCTION_DEF_PATH = "infra/step_functions/typology_subgraph_pipeline.json"

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

lambda_client = boto3.client("lambda", region_name=REGION, config=Config(retries={"max_attempts": 3}))
sfn_client = boto3.client("stepfunctions", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)
iam_client = boto3.client("iam", region_name=REGION)


def get_main_lambda_config():
    """Get the role, VPC config, and env vars from the existing main Lambda."""
    print("  Reading config from main Lambda...")
    resp = lambda_client.get_function_configuration(FunctionName=MAIN_LAMBDA_NAME)
    return {
        "role": resp["Role"],
        "vpc_config": resp.get("VpcConfig", {}),
        "environment": resp.get("Environment", {}).get("Variables", {}),
        "runtime": resp.get("Runtime", "python3.12"),
        "layers": [l["Arn"] for l in resp.get("Layers", [])],
    }


def build_lambda_zip():
    """Build a zip of src/ for Lambda deployment (same as main Lambda code)."""
    print("  Building Lambda zip from src/...")
    zip_buffer = io.BytesIO()
    src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith((".pyc", ".pyo")):
                    continue
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, src_dir)
                zf.write(filepath, arcname)

    zip_buffer.seek(0)
    return zip_buffer.read()


def upload_zip_to_s3(zip_bytes):
    """Upload Lambda zip to S3."""
    key = "deploy/typology-pipeline-lambda.zip"
    print(f"  Uploading zip to s3://{S3_BUCKET}/{key} ({len(zip_bytes) / 1024 / 1024:.1f} MB)...")
    s3_client.put_object(Bucket=S3_BUCKET, Key=key, Body=zip_bytes)
    return key


def create_or_update_lambda(name, config, main_config, s3_key):
    """Create or update a single pipeline Lambda function."""
    function_name = f"TypologyPipeline-{name}"
    print(f"  {function_name}...")

    # Build VPC config (reuse main Lambda's VPC)
    vpc = main_config["vpc_config"]
    vpc_config = {}
    if vpc.get("SubnetIds"):
        vpc_config = {
            "SubnetIds": vpc["SubnetIds"],
            "SecurityGroupIds": vpc["SecurityGroupIds"],
        }

    # Environment vars from main Lambda + any overrides
    env_vars = dict(main_config["environment"])

    try:
        # Try to get existing function
        lambda_client.get_function(FunctionName=function_name)
        # Update existing
        lambda_client.update_function_code(
            FunctionName=function_name,
            S3Bucket=S3_BUCKET,
            S3Key=s3_key,
        )
        time.sleep(2)
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Timeout=config["timeout"],
            MemorySize=config["memory"],
            Handler=config["handler"],
            Environment={"Variables": env_vars},
            Description=config["description"],
        )
        print(f"    ✓ Updated")
    except lambda_client.exceptions.ResourceNotFoundException:
        # Create new
        create_params = {
            "FunctionName": function_name,
            "Runtime": main_config["runtime"],
            "Role": main_config["role"],
            "Handler": config["handler"],
            "Code": {"S3Bucket": S3_BUCKET, "S3Key": s3_key},
            "Timeout": config["timeout"],
            "MemorySize": config["memory"],
            "Description": config["description"],
            "Environment": {"Variables": env_vars},
        }
        if vpc_config:
            create_params["VpcConfig"] = vpc_config
        if main_config["layers"]:
            create_params["Layers"] = main_config["layers"]

        lambda_client.create_function(**create_params)
        print(f"    ✓ Created")

    return f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{function_name}"


def create_or_update_step_function(lambda_arns):
    """Create or update the Step Functions state machine."""
    print("\n[3/5] Creating Step Functions state machine...")

    # Read the ASL definition
    def_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), STEP_FUNCTION_DEF_PATH)
    with open(def_path, "r") as f:
        definition = f.read()

    # Replace placeholder ARNs with actual ARNs
    for name, arn in lambda_arns.items():
        placeholder = f"arn:aws:lambda:us-east-1:974220725866:function:TypologyPipeline-{name}"
        definition = definition.replace(placeholder, arn)

    # Check if state machine exists
    sm_arn = f"arn:aws:states:{REGION}:{ACCOUNT_ID}:stateMachine:{STEP_FUNCTION_NAME}"
    try:
        sfn_client.describe_state_machine(stateMachineArn=sm_arn)
        # Update
        sfn_client.update_state_machine(
            stateMachineArn=sm_arn,
            definition=definition,
        )
        print(f"  ✓ Updated state machine: {STEP_FUNCTION_NAME}")
    except sfn_client.exceptions.StateMachineDoesNotExist:
        # Create — need a role
        role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/StepFunctions-TypologyPipeline-Role"
        try:
            sfn_client.create_state_machine(
                name=STEP_FUNCTION_NAME,
                definition=definition,
                roleArn=role_arn,
                type="STANDARD",
            )
            print(f"  ✓ Created state machine: {STEP_FUNCTION_NAME}")
        except Exception as e:
            print(f"  ⚠ Could not create state machine (create role first): {str(e)[:200]}")
            print(f"    Save the definition and create manually in the console.")
            # Write the resolved definition for manual use
            resolved_path = "infra/step_functions/typology_subgraph_pipeline_resolved.json"
            with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), resolved_path), "w") as f:
                f.write(definition)
            print(f"    Resolved definition saved to: {resolved_path}")

    return sm_arn


def run_aurora_migration():
    """Run the Aurora migration using the existing connection pattern."""
    print("\n[4/5] Running Aurora migration...")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
        from db.connection import ConnectionManager
        cm = ConnectionManager()

        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "src", "db", "migrations", "021_typology_subgraph_pipeline.sql",
        )
        with open(migration_path, "r") as f:
            sql = f.read()

        with cm.cursor() as cur:
            cur.execute(sql)
        print("  ✓ Migration applied (4 tables created)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  ✓ Tables already exist (migration previously applied)")
        else:
            print(f"  ⚠ Migration failed: {str(e)[:300]}")
            print("    You may need to run it manually via psql.")


def seed_opensearch_index():
    """Seed the typology-patterns OpenSearch index."""
    print("\n[5/5] Seeding OpenSearch typology-patterns index...")
    endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    if not endpoint:
        print("  ⚠ OPENSEARCH_ENDPOINT not set — skipping seed.")
        print("    Set it and run: python -m src.db.seeds.typology_patterns_index")
        return

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
        from db.seeds.typology_patterns_index import seed_typology_patterns
        seed_typology_patterns()
        print("  ✓ Index seeded with prosecution pattern embeddings")
    except Exception as e:
        print(f"  ⚠ Seed failed: {str(e)[:300]}")
        print("    Run manually: python -m src.db.seeds.typology_patterns_index")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  TYPOLOGY SUBGRAPH PIPELINE — DEPLOYMENT")
    print("=" * 60)

    # Step 1: Get main Lambda config
    print("\n[1/5] Reading main Lambda configuration...")
    main_config = get_main_lambda_config()
    print(f"  Role: {main_config['role'][:60]}...")
    print(f"  VPC subnets: {len(main_config['vpc_config'].get('SubnetIds', []))} subnets")
    print(f"  Env vars: {len(main_config['environment'])} variables")

    # Step 2: Build and deploy Lambda functions
    print("\n[2/5] Deploying 6 pipeline Lambda functions...")
    zip_bytes = build_lambda_zip()
    s3_key = upload_zip_to_s3(zip_bytes)

    lambda_arns = {}
    for name, config in PIPELINE_LAMBDAS.items():
        arn = create_or_update_lambda(name, config, main_config, s3_key)
        lambda_arns[name] = arn
        time.sleep(1)  # Rate limit

    print(f"\n  All 6 Lambdas deployed. ARNs:")
    for name, arn in lambda_arns.items():
        print(f"    {name}: {arn}")

    # Step 3: Step Functions
    sm_arn = create_or_update_step_function(lambda_arns)

    # Step 4: Aurora migration
    run_aurora_migration()

    # Step 5: OpenSearch seed
    seed_opensearch_index()

    # Summary
    print("\n" + "=" * 60)
    print("  DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"\n  Step Function ARN: {sm_arn}")
    print(f"\n  To test manually:")
    print(f"    python scripts/emit_ingestion_complete.py <case_id>")
    print(f"    — or —")
    print(f"    aws stepfunctions start-execution \\")
    print(f'      --state-machine-arn {sm_arn} \\')
    print(f'      --input \'{{"case_id": "<YOUR-345K-CASE-ID>", "trigger_source": "manual"}}\'')
    print()


if __name__ == "__main__":
    main()
