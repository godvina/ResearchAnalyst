"""Quick count of files in the epstein S3 prefix."""
import boto3

s3 = boto3.client("s3", region_name="us-east-1")
bucket = "research-analyst-data-lake-974220725866"
prefix = "cases/7f05e8d5-4492-4f19-8894-25367606db96/raw/"

count = 0
token = None
while True:
    kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
    if token:
        kwargs["ContinuationToken"] = token
    resp = s3.list_objects_v2(**kwargs)
    count += resp.get("KeyCount", 0)
    if count % 10000 == 0 and count > 0:
        print(f"  counted {count} so far...")
    if not resp.get("IsTruncated"):
        break
    token = resp["NextContinuationToken"]

print(f"\nTotal files in S3: {count}")
