"""Quick check: how many files are in S3 for the Epstein case."""
import boto3

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
PREFIX = f"cases/{CASE_ID}/raw/"

s3 = boto3.client("s3", region_name=REGION)
paginator = s3.get_paginator("list_objects_v2")

count = 0
total_size = 0
for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
    for obj in page.get("Contents", []):
        count += 1
        total_size += obj["Size"]

print(f"Files in S3: {count:,}")
print(f"Total size: {total_size / (1024*1024*1024):.2f} GB")
print(f"Bucket: {BUCKET}")
print(f"Prefix: {PREFIX}")
