"""Batch Rekognition face detection on extracted images, with face crop metadata output.

Processes images in batches to avoid Lambda timeout. Saves face_crop_metadata
artifact to S3 for the graph loader to pick up.
"""
import boto3
import json
import hashlib
import time
import sys

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

s3 = boto3.client("s3", region_name=REGION)
rek = boto3.client("rekognition", region_name=REGION)

prefix = f"cases/{CASE_ID}/extracted-images/"
MIN_CONFIDENCE = 90.0  # Rekognition uses 0-100 scale

# List all extracted images
print("Listing extracted images...")
images = []
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
    for obj in page.get("Contents", []):
        key = obj["Key"]
        if key.lower().endswith((".jpg", ".jpeg", ".png")):
            images.append(key)

print(f"Found {len(images)} images to process")

# Process each image
face_crop_metadata = []
processed = 0
errors = 0
faces_found = 0

for i, s3_key in enumerate(images):
    filename = s3_key[len(prefix):]
    # Parse source document ID
    source_doc_id = filename.split("_page")[0] if "_page" in filename else "unknown"

    try:
        resp = rek.detect_faces(
            Image={"S3Object": {"Bucket": BUCKET, "Name": s3_key}},
            Attributes=["ALL"],
        )
        for j, face in enumerate(resp.get("FaceDetails", [])):
            confidence = face.get("Confidence", 0)
            if confidence < MIN_CONFIDENCE:
                continue

            bb = face.get("BoundingBox", {})
            left = bb.get("Left", 0.0)
            top = bb.get("Top", 0.0)
            width = bb.get("Width", 0.0)
            height = bb.get("Height", 0.0)

            raw = f"{s3_key}:{left}:{top}:{width}:{height}"
            crop_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]
            crop_key = f"cases/{CASE_ID}/face-crops/unidentified/{crop_hash}.jpg"

            gender = face.get("Gender", {}).get("Value", "Unknown")
            age_low = face.get("AgeRange", {}).get("Low", 0)
            age_high = face.get("AgeRange", {}).get("High", 0)

            face_crop_metadata.append({
                "crop_s3_key": crop_key,
                "source_s3_key": s3_key,
                "source_document_id": source_doc_id,
                "bounding_box": {"Left": left, "Top": top, "Width": width, "Height": height},
                "confidence": round(confidence / 100, 4),
                "entity_name": "unidentified",
                "gender": gender,
                "age_range": f"{age_low}-{age_high}",
            })
            faces_found += 1

        processed += 1
    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  Error on {filename}: {str(e)[:80]}")

    if (i + 1) % 100 == 0:
        print(f"  Processed {i+1}/{len(images)} — {faces_found} faces found, {errors} errors")

print(f"\nDone! Processed {processed}/{len(images)} images")
print(f"Faces found: {faces_found}")
print(f"Errors: {errors}")

# Save face_crop_metadata to S3
artifact_key = f"cases/{CASE_ID}/rekognition-artifacts/face_crop_metadata.json"
s3.put_object(
    Bucket=BUCKET,
    Key=artifact_key,
    Body=json.dumps(face_crop_metadata, default=str).encode(),
    ContentType="application/json",
)
print(f"\nSaved face_crop_metadata artifact: {artifact_key}")
print(f"  {len(face_crop_metadata)} entries")
