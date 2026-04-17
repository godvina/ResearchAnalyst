"""Check what Rekognition data exists in the Epstein source bucket."""
import boto3
import json

s3 = boto3.client("s3", region_name="us-east-1")
BUCKET = "doj-cases-974220725866-us-east-1"

for prefix in ["rekognition-output/", "rekognition-results/", "photo-metadata/"]:
    r = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=10)
    contents = r.get("Contents", [])
    print(f"\n{prefix}: {len(contents)} files")
    for obj in contents[:5]:
        key = obj["Key"]
        size = obj["Size"]
        print(f"  {key} ({size} bytes)")
        # Read first file to see format
        if size > 0 and size < 50000 and contents.index(obj) == 0:
            try:
                body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()
                data = json.loads(body)
                print(f"    Keys: {list(data.keys())[:10]}")
                # Show sample content
                sample = json.dumps(data, indent=2)[:500]
                print(f"    Sample: {sample}")
            except Exception as e:
                print(f"    Read error: {e}")
