"""Deploy updated code to all Lambda functions."""
import boto3
import zipfile
import io
import os

REGION = "us-east-1"
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
SRC_DIR = os.path.abspath(SRC_DIR)
DEPS_DIR = os.path.join(os.path.dirname(__file__), "..", "lambda-deps")
DEPS_DIR = os.path.abspath(DEPS_DIR)

# Build zip
print("Building deployment zip...")
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    # Add src/ code
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__" and d != "frontend"]
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                arc_name = os.path.relpath(full_path, SRC_DIR)
                zf.write(full_path, arc_name)
    # Add lambda-deps (psycopg2, etc.) — include ALL files for binary compat
    if os.path.exists(DEPS_DIR):
        for root, dirs, files in os.walk(DEPS_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                full_path = os.path.join(root, f)
                arc_name = os.path.relpath(full_path, DEPS_DIR)
                zf.write(full_path, arc_name)
zip_bytes = zip_buffer.getvalue()
print(f"Zip size: {len(zip_bytes) / 1024:.1f} KB")

lam = boto3.client("lambda", region_name=REGION)
fns = lam.list_functions(MaxItems=50)
research_fns = [f["FunctionName"] for f in fns["Functions"]
                if "ResearchAnalyst" in f["FunctionName"]]

print(f"\nUpdating {len(research_fns)} Lambda functions...")
for fn_name in sorted(research_fns):
    try:
        lam.update_function_code(FunctionName=fn_name, ZipFile=zip_bytes)
        print(f"  OK {fn_name}")
    except Exception as e:
        print(f"  FAIL {fn_name}: {str(e)[:100]}")

print("\nDone.")
