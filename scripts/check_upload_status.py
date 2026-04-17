"""Quick check: how many files are in S3 for the Epstein case."""
import boto3

s3 = boto3.client("s3", region_name="us-east-1")
BUCKET = "research-analyst-data-lake-974220725866"
PREFIX = "cases/7f05e8d5-4492-4f19-8894-25367606db96/raw/"

paginator = s3.get_paginator("list_objects_v2")
count = 0
total_size = 0
recent = []

for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
    for obj in page.get("Contents", []):
        count += 1
        total_size += obj["Size"]
        recent.append((obj["Key"].split("/")[-1], obj["Size"], obj["LastModified"]))

recent.sort(key=lambda x: x[2], reverse=True)

print(f"Total files in raw/: {count}")
print(f"Total size: {total_size / (1024*1024):.1f} MB")
print(f"\nMost recent 10 files:")
for name, size, modified in recent[:10]:
    print(f"  {name} ({size/1024:.1f} KB) — {modified}")
