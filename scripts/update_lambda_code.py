"""Direct Lambda code update — zips src/ and pushes to all Lambda functions."""
import io
import os
import zipfile
import boto3

REGION = "us-east-1"
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
LAMBDA_DEPS_DIR = os.path.join(os.path.dirname(__file__), "..", "lambda-deps")

lam = boto3.client("lambda", region_name=REGION)


def build_zip():
    """Create in-memory zip of src/ directory (flattened to root)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SRC_DIR):
            # Skip __pycache__, .pyc
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, SRC_DIR)
                zf.write(full, arcname)
        # Also include lambda-deps if present (aenum etc.)
        if os.path.isdir(LAMBDA_DEPS_DIR):
            for root, dirs, files in os.walk(LAMBDA_DEPS_DIR):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for f in files:
                    if f.endswith(".pyc"):
                        continue
                    full = os.path.join(root, f)
                    arcname = os.path.relpath(full, LAMBDA_DEPS_DIR)
                    zf.write(full, arcname)
    buf.seek(0)
    return buf.read()


def get_stack_lambdas():
    """Find all Lambda functions belonging to ResearchAnalystStack."""
    functions = []
    paginator = lam.get_paginator("list_functions")
    for page in paginator.paginate():
        for fn in page["Functions"]:
            if "ResearchAnalyst" in fn["FunctionName"]:
                functions.append(fn["FunctionName"])
    return sorted(functions)


def main():
    print("Building zip from src/ ...")
    zip_bytes = build_zip()
    size_mb = len(zip_bytes) / (1024 * 1024)
    print(f"Zip size: {size_mb:.1f} MB")

    if size_mb > 50:
        print("ERROR: Zip too large for direct upload (>50MB). Need S3 upload path.")
        return

    functions = get_stack_lambdas()
    print(f"\nFound {len(functions)} Lambda functions:")
    for fn in functions:
        print(f"  {fn}")

    print(f"\nUpdating all {len(functions)} functions...")
    for fn in functions:
        try:
            lam.update_function_code(FunctionName=fn, ZipFile=zip_bytes)
            print(f"  ✓ {fn}")
        except Exception as e:
            print(f"  ✗ {fn}: {str(e)[:100]}")

    print("\nDone! Lambda code updated.")


if __name__ == "__main__":
    main()
