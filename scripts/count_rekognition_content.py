"""Count Rekognition files with actual content."""
import boto3
import json

s3 = boto3.client("s3", region_name="us-east-1")
BUCKET = "doj-cases-974220725866-us-east-1"

# Count photo-metadata files with actual entities
print("=== photo-metadata ===")
paginator = s3.get_paginator("list_objects_v2")
total = 0
has_persons = 0
has_photos = 0
has_text = 0
sample_persons = []

for page in paginator.paginate(Bucket=BUCKET, Prefix="photo-metadata/"):
    for obj in page.get("Contents", []):
        total += 1
        if obj["Size"] < 100:
            continue
        try:
            body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode()
            data = json.loads(body)
            persons = data.get("personEntities", [])
            if persons:
                has_persons += 1
                if len(sample_persons) < 20:
                    sample_persons.extend(persons[:3])
            if data.get("hasPhotos"):
                has_photos += 1
            if data.get("documentText"):
                has_text += 1
        except Exception:
            pass

print(f"Total files: {total}")
print(f"With person entities: {has_persons}")
print(f"With photos: {has_photos}")
print(f"With document text: {has_text}")
print(f"Sample persons: {sample_persons[:20]}")

# Count rekognition-output files with detections
print("\n=== rekognition-output ===")
total_rek = 0
has_faces = 0
has_labels = 0
has_celebs = 0
has_rek_text = 0

for page in paginator.paginate(Bucket=BUCKET, Prefix="rekognition-output/", PaginationConfig={"MaxItems": 500}):
    for obj in page.get("Contents", []):
        total_rek += 1
        if obj["Size"] < 200:
            continue
        try:
            body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode()
            data = json.loads(body)
            if data.get("faces"):
                has_faces += 1
            if data.get("labels"):
                has_labels += 1
            if data.get("celebrities"):
                has_celebs += 1
            if data.get("text"):
                has_rek_text += 1
        except Exception:
            pass

print(f"Total files: {total_rek}")
print(f"With faces: {has_faces}")
print(f"With labels: {has_labels}")
print(f"With celebrities: {has_celebs}")
print(f"With text: {has_rek_text}")
