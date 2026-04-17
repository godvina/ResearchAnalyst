"""Deploy the EntityResolutionLambda by cloning config from GraphLoadLambda."""
import boto3
import json
import zipfile
import io
import os

REGION = "us-east-1"
TEMPLATE_LAMBDA = "ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg"
NEW_LAMBDA = "ResearchAnalystStack-EntityResolutionLambda"

lam = boto3.client("lambda", region_name=REGION)

# Get template Lambda config
print("Getting template Lambda config...")
template = lam.get_function_configuration(FunctionName=TEMPLATE_LAMBDA)
role = template["Role"]
vpc_config = template["VpcConfig"]
env_vars = template["Environment"]["Variables"]
runtime = template["Runtime"]

print(f"Role: {role}")
print(f"Runtime: {runtime}")
print(f"VPC: {vpc_config['VpcId']}")
print(f"Env vars: {len(env_vars)} vars")

# Build deployment zip from src/
print("\nBuilding deployment zip...")
src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
src_dir = os.path.abspath(src_dir)

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src_dir):
        # Skip __pycache__ and test dirs
        dirs[:] = [d for d in dirs if d != "__pycache__" and d != "frontend"]
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                arc_name = os.path.relpath(full_path, src_dir)
                zf.write(full_path, arc_name)

zip_bytes = zip_buffer.getvalue()
print(f"Zip size: {len(zip_bytes) / 1024:.1f} KB")

# Check if Lambda already exists
try:
    lam.get_function(FunctionName=NEW_LAMBDA)
    print(f"\nLambda {NEW_LAMBDA} exists — updating code...")
    lam.update_function_code(
        FunctionName=NEW_LAMBDA,
        ZipFile=zip_bytes,
    )
    print("Code updated.")
except lam.exceptions.ResourceNotFoundException:
    print(f"\nCreating Lambda {NEW_LAMBDA}...")
    lam.create_function(
        FunctionName=NEW_LAMBDA,
        Runtime=runtime,
        Role=role,
        Handler="lambdas.ingestion.entity_resolution_handler.handler",
        Code={"ZipFile": zip_bytes},
        Timeout=900,
        MemorySize=1024,
        VpcConfig={
            "SubnetIds": vpc_config["SubnetIds"],
            "SecurityGroupIds": vpc_config["SecurityGroupIds"],
        },
        Environment={"Variables": env_vars},
        Description="Entity resolution — fuzzy + LLM dedup for Neptune graph",
    )
    print("Lambda created.")

# Update the run script with the actual Lambda name
print(f"\nLambda ready: {NEW_LAMBDA}")
print("Run dry run: python scripts/run_entity_resolution.py")
print("Run execute: python scripts/run_entity_resolution.py --execute")
