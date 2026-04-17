"""Check S3 storage size for the Epstein case and all cases."""
import boto3

s3 = boto3.client("s3", region_name="us-east-1")
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# Check total bucket size
paginator = s3.get_paginator("list_objects_v2")
total_size = 0
total_count = 0
case_size = 0
case_count = 0
raw_size = 0
raw_count = 0
textract_size = 0
textract_count = 0

for page in paginator.paginate(Bucket=BUCKET):
    for obj in page.get("Contents", []):
        key = obj["Key"]
        size = obj["Size"]
        total_size += size
        total_count += 1
        if key.startswith(f"cases/{CASE_ID}/"):
            case_size += size
            case_count += 1
            if "/raw/" in key:
                raw_size += size
                raw_count += 1
        if "textract" in key.lower():
            textract_size += size
            textract_count += 1

def fmt(b):
    if b > 1024**3:
        return f"{b/1024**3:.2f} GB"
    if b > 1024**2:
        return f"{b/1024**2:.2f} MB"
    return f"{b/1024:.2f} KB"

print(f"=== S3 Bucket: {BUCKET} ===")
print(f"Total: {total_count:,} objects, {fmt(total_size)}")
print(f"\n=== Epstein Case ({CASE_ID[:8]}...) ===")
print(f"Total: {case_count:,} objects, {fmt(case_size)}")
print(f"  Raw files: {raw_count:,} objects, {fmt(raw_size)}")
print(f"\n=== Textract Output ===")
print(f"Total: {textract_count:,} objects, {fmt(textract_size)}")

# Also check the DOJ source bucket
DOJ_BUCKET = "doj-cases-974220725866-us-east-1"
try:
    doj_total = 0
    doj_count = 0
    for page in paginator.paginate(Bucket=DOJ_BUCKET):
        for obj in page.get("Contents", []):
            doj_total += obj["Size"]
            doj_count += 1
    print(f"\n=== DOJ Source Bucket ({DOJ_BUCKET}) ===")
    print(f"Total: {doj_count:,} objects, {fmt(doj_total)}")
except Exception as e:
    print(f"\nDOJ bucket not accessible: {e}")
