"""Audit what data is actually loaded in Aurora — check source tags, filenames, counts."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
MAIN = "7f05e8d5-4492-4f19-8894-25367606db96"
COMBINED = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

print("=== AUDITING LOADED DATA ===\n")

# Get sample filenames from main case at different offsets
resp = lam.invoke(
    FunctionName=LAMBDA,
    Payload=json.dumps({
        "action": "get_documents_for_extraction",
        "case_id": MAIN,
        "limit": 10,
        "offset": 0,
        "max_text_length": 50,
    }),
)
data = json.loads(resp["Payload"].read())
total = data.get("total", 0)
print(f"Main case documents with text: {total}")
print(f"\nSample filenames:")
for d in data.get("docs", []):
    print(f"  {d.get('filename', '?')[:80]}")

# Check different offsets
for offset in [10000, 30000, 50000, 70000]:
    resp2 = lam.invoke(
        FunctionName=LAMBDA,
        Payload=json.dumps({
            "action": "get_documents_for_extraction",
            "case_id": MAIN,
            "limit": 3,
            "offset": offset,
            "max_text_length": 50,
        }),
    )
    data2 = json.loads(resp2["Payload"].read())
    docs2 = data2.get("docs", [])
    if docs2:
        print(f"\nAt offset {offset}:")
        for d in docs2:
            print(f"  {d.get('filename', '?')[:80]}")

# Check S3 source bucket
print(f"\n=== S3 SOURCE BUCKET ===")
s3 = boto3.client("s3", region_name="us-east-1")
try:
    for prefix in ["pdfs/", "bw-documents/", "DataSet", "huggingface/", "preprocessed/", "json/", "text/"]:
        resp_s3 = s3.list_objects_v2(Bucket="doj-cases-974220725866-us-east-1", Prefix=prefix, MaxKeys=3)
        count = resp_s3.get("KeyCount", 0)
        if count > 0:
            print(f"  {prefix}: {count}+ files")
            for obj in resp_s3.get("Contents", [])[:2]:
                print(f"    {obj['Key'][:80]}  ({obj['Size']} bytes)")
except Exception as e:
    print(f"  Source bucket error: {str(e)[:100]}")

# Check data lake bucket for case prefixes
print(f"\n=== DATA LAKE BUCKET - CASE PREFIXES ===")
bucket = "research-analyst-data-lake-974220725866"
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket, Prefix="cases/", Delimiter="/"):
    for p in page.get("CommonPrefixes", []):
        # Count files in each case prefix
        count_resp = s3.list_objects_v2(Bucket=bucket, Prefix=p["Prefix"] + "raw/", MaxKeys=1)
        has_raw = count_resp.get("KeyCount", 0) > 0
        print(f"  {p['Prefix']}  raw_files={'yes' if has_raw else 'no'}")
