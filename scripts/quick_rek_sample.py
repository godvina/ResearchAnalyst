"""Quick sample of Rekognition data."""
import boto3
import json

s3 = boto3.client("s3", region_name="us-east-1")
BUCKET = "doj-cases-974220725866-us-east-1"

r1 = s3.list_objects_v2(Bucket=BUCKET, Prefix="photo-metadata/", MaxKeys=1000)
r2 = s3.list_objects_v2(Bucket=BUCKET, Prefix="rekognition-output/", MaxKeys=1000)
print(f"photo-metadata: {r1.get('KeyCount', 0)} files, truncated: {r1.get('IsTruncated')}")
print(f"rekognition-output: {r2.get('KeyCount', 0)} files, truncated: {r2.get('IsTruncated')}")

# Sample photo-metadata files with content
print("\nSample photo-metadata with persons:")
count = 0
for obj in r1.get("Contents", []):
    if obj["Size"] > 400 and count < 10:
        body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode()
        data = json.loads(body)
        persons = data.get("personEntities", [])
        text = (data.get("documentText", "") or "")[:120]
        if persons:
            fname = obj["Key"].split("/")[-1]
            print(f"  {fname}: persons={persons[:5]}, text={text}")
            count += 1
