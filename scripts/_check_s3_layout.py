"""Check S3 layout to find where the 331K raw files are."""
import boto3
s3 = boto3.client("s3", region_name="us-east-1")

for bucket_name in [
    "research-analyst-data-lake-974220725866",
    "doj-cases-974220725866-us-east-1",
]:
    print(f"\n=== {bucket_name} ===")
    resp = s3.list_objects_v2(Bucket=bucket_name, Delimiter="/", MaxKeys=30)
    for p in resp.get("CommonPrefixes", []):
        prefix = p["Prefix"]
        # Count a sample
        r2 = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, MaxKeys=2)
        has_more = r2.get("IsTruncated", False)
        count_str = f"{r2['KeyCount']}+" if has_more else str(r2["KeyCount"])
        print(f"  {prefix:45} {count_str} files")
