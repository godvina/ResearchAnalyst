"""Deploy updated Lambda code to all functions without CDK.

Packages the src/ directory into a zip and updates each Lambda function.
Also sets OPENSEARCH_ENDPOINT and OPENSEARCH_COLLECTION_ID env vars.
"""
import boto3
import zipfile
import os
import io

REGION = "us-east-1"
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
OPENSEARCH_ENDPOINT = "https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com"
OPENSEARCH_COLLECTION_ID = "u260nrrtc0q87ji8iu0k"
OPENSEARCH_VPCE_URL = ""  # Use AOSS-managed VPC endpoint with private DNS


def create_zip():
    """Create a zip of the src/ directory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SRC_DIR):
            # Skip __pycache__ and .pyc files
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, f)
                arc_name = os.path.relpath(full_path, SRC_DIR)
                zf.write(full_path, arc_name)
    buf.seek(0)
    return buf.read()


def main():
    lam = boto3.client("lambda", region_name=REGION)
    
    # Find all Research Analyst Lambda functions
    functions = []
    paginator = lam.get_paginator("list_functions")
    for page in paginator.paginate():
        for fn in page["Functions"]:
            if "ResearchAnalystStack" in fn["FunctionName"]:
                functions.append(fn["FunctionName"])
    
    if not functions:
        print("No ResearchAnalystStack Lambda functions found!")
        return
    
    print(f"Found {len(functions)} Lambda functions:")
    for fn in functions:
        print(f"  {fn}")
    
    # Create zip
    print("\nPackaging src/ directory...")
    zip_bytes = create_zip()
    print(f"  Zip size: {len(zip_bytes) / 1024:.0f} KB")
    
    # Update each function
    for fn_name in functions:
        print(f"\nUpdating {fn_name}...")
        
        # Update code
        try:
            lam.update_function_code(
                FunctionName=fn_name,
                ZipFile=zip_bytes,
            )
            print(f"  Code updated.")
        except Exception as e:
            print(f"  Code update failed: {e}")
            continue
        
        # Wait for update to complete
        waiter = lam.get_waiter("function_updated_v2")
        waiter.wait(FunctionName=fn_name, WaiterConfig={"Delay": 5, "MaxAttempts": 30})
        
        # Update environment variables to include OPENSEARCH_ENDPOINT
        try:
            config = lam.get_function_configuration(FunctionName=fn_name)
            env_vars = config.get("Environment", {}).get("Variables", {})
            env_vars["OPENSEARCH_ENDPOINT"] = OPENSEARCH_ENDPOINT
            env_vars["OPENSEARCH_COLLECTION_ID"] = OPENSEARCH_COLLECTION_ID
            # Remove VPCE URL - AOSS-managed VPC endpoint handles DNS routing
            env_vars.pop("OPENSEARCH_VPCE_URL", None)
            
            lam.update_function_configuration(
                FunctionName=fn_name,
                Environment={"Variables": env_vars},
            )
            print(f"  Env vars updated (OPENSEARCH_ENDPOINT set).")
        except Exception as e:
            print(f"  Env var update failed: {e}")
        
        # Wait for config update
        waiter.wait(FunctionName=fn_name, WaiterConfig={"Delay": 5, "MaxAttempts": 30})
    
    print("\nAll Lambda functions updated!")


if __name__ == "__main__":
    main()
