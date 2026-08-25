"""Deploy Lambda via S3 (faster for large packages — avoids direct upload timeout)."""
import boto3
import zipfile
import os
import io
import time

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
S3_KEY = "deploy/lambda-code-latest.zip"
FN_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")

# Directories under src/ that are runtime DATA, not Lambda code. Excluded from the
# deploy zip — they belong in S3, not the code bundle. Without this, src/data alone
# is ~3.3GB and blows past Lambda's 250MB unzipped limit. The deployed package is ~43MB.
EXCLUDE_DIRS = {"__pycache__", "data"}
EXCLUDE_EXT = (".pyc", ".csv", ".parquet", ".zip")

print("Creating zip...")
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
print(f"Zip size: {len(zb) // 1024}KB")

# Upload to S3 (multipart, handles large files)
print(f"Uploading to s3://{BUCKET}/{S3_KEY}...")
s3 = boto3.client("s3", region_name=REGION)
s3.put_object(Bucket=BUCKET, Key=S3_KEY, Body=zb)
print("S3 upload done!")

# Update Lambda from S3
print(f"Updating Lambda {FN_NAME} from S3...")
lam = boto3.client("lambda", region_name=REGION)
lam.update_function_code(
    FunctionName=FN_NAME,
    S3Bucket=BUCKET,
    S3Key=S3_KEY,
)
print("Lambda update triggered!")

# Wait for ready
for i in range(30):
    time.sleep(5)
    r = lam.get_function_configuration(FunctionName=FN_NAME)
    status = r.get("LastUpdateStatus", "Unknown")
    if status == "Successful":
        print(f"DONE! Modified={r['LastModified']}")
        break
    elif status == "Failed":
        print(f"FAILED: {r.get('LastUpdateStatusReason', '?')}")
        break
    print(f"  ...waiting ({status})")
else:
    print("Timed out.")
