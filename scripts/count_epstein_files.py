"""Count all Epstein Textract files and show breakdown."""
import boto3

REGION = "us-east-1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
DATASETS = ["DataSet1", "DataSet2", "DataSet3", "DataSet4", "DataSet5"]

s3 = boto3.client("s3", region_name=REGION)
total = 0
valid = 0

for ds in DATASETS:
    prefix = f"textract-output/{ds}/"
    count = 0
    small = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                count += 1
                if obj["Size"] > 100:
                    valid += 1
                else:
                    small += 1
    total += count
    print(f"{ds}: {count} files ({small} too small)")

print(f"\nTotal: {total} files, {valid} valid (>100 bytes)")
print(f"Batches of 50: {(valid + 49) // 50}")
print(f"Estimated time: {((valid + 49) // 50) * 3} minutes")
print(f"Estimated cost: ~${valid * 0.005:.2f}")
