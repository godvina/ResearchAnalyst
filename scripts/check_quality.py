"""Check quality of entity extraction results from the new DOJ files."""
import boto3
import json

s3 = boto3.client("s3", region_name="us-east-1")
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# Check extraction artifacts from the new EFTA files
paginator = s3.get_paginator("list_objects_v2")
extraction_count = 0
total_entities = 0
entity_types = {}
sample_entities = []

for page in paginator.paginate(Bucket=BUCKET, Prefix=f"cases/{CASE_ID}/extractions/"):
    for obj in page.get("Contents", []):
        if not obj["Key"].endswith("_extraction.json"):
            continue
        extraction_count += 1
        
        # Read a sample of extraction artifacts
        if extraction_count <= 5 or extraction_count % 100 == 0:
            try:
                body = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode()
                data = json.loads(body)
                entities = data.get("entities", [])
                relationships = data.get("relationships", [])
                total_entities += len(entities)
                
                for e in entities:
                    etype = e.get("entity_type", "unknown")
                    entity_types[etype] = entity_types.get(etype, 0) + 1
                
                if extraction_count <= 3:
                    sample_entities.append({
                        "file": obj["Key"].split("/")[-1][:40],
                        "entities": len(entities),
                        "relationships": len(relationships),
                        "names": [e.get("canonical_name", "?")[:30] for e in entities[:5]],
                    })
            except Exception as e:
                pass

print(f"=== Extraction Quality Check ===")
print(f"Total extraction artifacts: {extraction_count}")
print(f"Entities in sampled files: {total_entities}")
print(f"\nEntity type distribution:")
for etype, count in sorted(entity_types.items(), key=lambda x: -x[1]):
    print(f"  {etype}: {count}")

print(f"\nSample extractions:")
for s in sample_entities:
    print(f"  {s['file']}: {s['entities']} entities, {s['relationships']} rels")
    print(f"    Names: {', '.join(s['names'])}")
