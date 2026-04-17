"""Check S3 prefixes for the Epstein case."""
import boto3

s3 = boto3.client("s3", region_name="us-east-1")
bucket = "research-analyst-data-lake-974220725866"
case = "7f05e8d5-4492-4f19-8894-25367606db96"

# List top-level prefixes under the case
r = s3.list_objects_v2(Bucket=bucket, Prefix=f"cases/{case}/", Delimiter="/", MaxKeys=20)
print("Case prefixes:")
for p in r.get("CommonPrefixes", []):
    prefix = p["Prefix"]
    # Count objects in each prefix
    count = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, PaginationConfig={"MaxItems": 10000}):
        count += page.get("KeyCount", 0)
    print(f"  {prefix}: {count} objects")

# Check epstein_files prefix
r2 = s3.list_objects_v2(Bucket=bucket, Prefix="epstein_files/", MaxKeys=5)
print(f"\nepstein_files/: {r2.get('KeyCount', 0)}+ objects")

# Check top-level prefixes
r3 = s3.list_objects_v2(Bucket=bucket, Prefix="", Delimiter="/", MaxKeys=20)
print("\nTop-level prefixes:")
for p in r3.get("CommonPrefixes", []):
    print(f"  {p['Prefix']}")
