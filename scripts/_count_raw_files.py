"""Count raw files across all DataSets and prefixes."""
import boto3
s3 = boto3.client("s3", region_name="us-east-1")

# DS11 in main bucket
bucket = "research-analyst-data-lake-974220725866"
count = 0
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket, Prefix="textract-output/DataSet11/"):
    count += len(page.get("Contents", []))
print(f"DS11 extracted (main bucket): {count}")

# Raw PDFs in source bucket
source = "doj-cases-974220725866-us-east-1"
for ds in range(1, 13):
    prefix = f"DataSet{ds}/"
    r = s3.list_objects_v2(Bucket=source, Prefix=prefix, MaxKeys=5)
    c = r.get("KeyCount", 0)
    trunc = "+" if r.get("IsTruncated") else ""
    if c > 0:
        print(f"  DataSet{ds}/: {c}{trunc} raw files")

for prefix in ["pdfs/", "bw-documents/"]:
    r = s3.list_objects_v2(Bucket=source, Prefix=prefix, MaxKeys=5)
    c = r.get("KeyCount", 0)
    trunc = "+" if r.get("IsTruncated") else ""
    if c > 0:
        print(f"  {prefix}: {c}{trunc} files")
