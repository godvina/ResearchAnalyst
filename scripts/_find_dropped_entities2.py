"""Check the extractions/ folder in S3 for entity data with dropped types."""
import boto3
import json

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract"}

s3 = boto3.client("s3", region_name=REGION)

# Check extractions folder
prefix = f"cases/{CASE_ID}/extractions/"
print(f"Checking: s3://{BUCKET}/{prefix}")
paginator = s3.get_paginator("list_objects_v2")
count = 0
sample_keys = []
for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix, MaxKeys=100):
    for obj in page.get("Contents", []):
        count += 1
        if count <= 5:
            sample_keys.append(obj["Key"])

print(f"  Total extraction files: {count}")
if sample_keys:
    print(f"  Samples: {sample_keys[:3]}")

    # Read one to see format
    key = sample_keys[0]
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    content = json.loads(obj["Body"].read().decode())
    print(f"\n  Keys in extraction file: {list(content.keys())[:10]}")
    
    # Look for entities
    entities = content.get("entities", content.get("extracted_entities", []))
    print(f"  Entities in this file: {len(entities)}")
    if entities:
        types_found = set()
        dropped_found = []
        for e in entities:
            t = e.get("type", e.get("entity_type", ""))
            types_found.add(t)
            if t.lower() in DROPPED_TYPES:
                dropped_found.append(e)
        print(f"  Types found: {types_found}")
        if dropped_found:
            print(f"\n  DROPPED TYPE ENTITIES IN THIS FILE:")
            for e in dropped_found[:10]:
                print(f"    [{e.get('type', '?')}] {e.get('name', e.get('canonical_name', '?'))}")

# Also check the non-empty batch output files
print(f"\n\nChecking batch output files...")
resp = s3.list_objects_v2(Bucket=BUCKET, 
    Prefix=f"batch-inference/entity-extraction/{CASE_ID}/output/")
for obj in resp.get("Contents", []):
    if obj["Size"] > 0:
        print(f"  Non-empty: {obj['Key']} ({obj['Size']} bytes)")
        data = s3.get_object(Bucket=BUCKET, Key=obj["Key"])
        content = data["Body"].read().decode("utf-8", errors="ignore")
        lines = content.strip().split("\n")
        print(f"    Lines: {len(lines)}")
        if lines and lines[0]:
            print(f"    First line preview: {lines[0][:300]}")

# Check if there are other output prefixes
print(f"\n\nChecking all batch-inference prefixes...")
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="batch-inference/", Delimiter="/")
for p in resp.get("CommonPrefixes", []):
    print(f"  {p['Prefix']}")
