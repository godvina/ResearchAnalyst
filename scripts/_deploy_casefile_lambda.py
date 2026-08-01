"""Quick deploy of CaseFiles Lambda only."""
import boto3, zipfile, os, io, time

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"):
                continue
            fp = os.path.join(root, f)
            zf.write(fp, os.path.relpath(fp, SRC))
buf.seek(0)
zb = buf.read()
print(f"Zip ready: {len(zb)//1024}KB")

lam = boto3.client("lambda", region_name="us-east-1")
fn = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
print("Uploading to Lambda...")
lam.update_function_code(FunctionName=fn, ZipFile=zb)
print("Upload sent. Waiting for Lambda to be ready...")

for i in range(30):
    time.sleep(5)
    r = lam.get_function_configuration(FunctionName=fn)
    status = r.get("LastUpdateStatus", "Unknown")
    if status == "Successful":
        print(f"Done! State={r['State']} Modified={r['LastModified']}")
        break
    elif status == "Failed":
        print(f"FAILED: {r.get('LastUpdateStatusReason','?')}")
        break
    print(f"  ...waiting ({status})")
else:
    print("Timed out waiting for update.")
