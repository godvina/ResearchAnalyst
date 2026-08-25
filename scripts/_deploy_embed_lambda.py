"""Deploy the fixed opensearch_serverless_backend (_index_exists Issue 51 fix)
to the IngestionEmbed Lambda via S3. Mirrors _deploy_via_s3.py packaging
(EXCLUDES src/data so the zip stays ~47MB, well under the 250MB limit).
"""
import boto3
import zipfile
import os
import io
import time

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
S3_KEY = "deploy/lambda-code-latest.zip"
# The embed Lambda that routes enterprise-tier docs to OpenSearch
FN_NAME = "ResearchAnalystStack-IngestionEmbedLambdaE92F3BC0-wYlIRbksk1Jz"

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
EXCLUDE_DIRS = {"__pycache__", "data"}
EXCLUDE_EXT = (".pyc", ".csv", ".parquet", ".zip")

print("Creating zip (excluding src/data)...")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith(EXCLUDE_EXT):
                continue
            fp = os.path.join(root, f)
            zf.write(fp, os.path.relpath(fp, SRC))
buf.seek(0)
zb = buf.read()
print(f"Zip size: {len(zb)//1024}KB")

s3 = boto3.client("s3", region_name=REGION)
s3.put_object(Bucket=BUCKET, Key=S3_KEY, Body=zb)
print("S3 upload done")

lam = boto3.client("lambda", region_name=REGION)
lam.update_function_code(FunctionName=FN_NAME, S3Bucket=BUCKET, S3Key=S3_KEY)
print(f"update_function_code triggered on {FN_NAME}")

for i in range(40):
    time.sleep(5)
    r = lam.get_function_configuration(FunctionName=FN_NAME)
    st = r.get("LastUpdateStatus", "?")
    if st == "Successful":
        print(f"DONE! Modified={r['LastModified']}")
        break
    if st == "Failed":
        print(f"FAILED: {r.get('LastUpdateStatusReason','?')}")
        break
    print(f"  ...{st}")
else:
    print("timed out")
