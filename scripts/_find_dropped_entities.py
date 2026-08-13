"""Find what the dropped Neptune entities actually WERE.

Check S3 batch inference output for entity extraction results that had
the dropped types: object, other, identifier, number, product, rule, 
classification, abstract.

These types were in Neptune but NOT in Aurora — meaning they came from
a pipeline that wrote directly to Neptune (Step Functions entity extraction
or the batch inference load).
"""
import boto3
import json
import re

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract"}

s3 = boto3.client("s3", region_name=REGION)

print("=" * 60)
print("FINDING WHAT THE DROPPED ENTITIES WERE")
print("=" * 60)

# Check batch inference output in S3
output_prefix = f"batch-inference/entity-extraction/{CASE_ID}/output/"
print(f"\nChecking S3: s3://{BUCKET}/{output_prefix}")

resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=output_prefix, MaxKeys=10)
output_files = resp.get("Contents", [])
print(f"  Found {len(output_files)} output files")

if output_files:
    # Read the first output file to see what entity types it produces
    key = output_files[0]["Key"]
    print(f"  Sampling: {key} ({output_files[0]['Size']} bytes)")
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    content = obj["Body"].read().decode("utf-8", errors="ignore")
    
    # JSONL format — each line is a result
    dropped_entities = []
    total_entities = 0
    for line in content.strip().split("\n")[:100]:
        try:
            record = json.loads(line)
            # The output format varies — check for entity extraction results
            output = record.get("modelOutput", record.get("output", {}))
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except:
                    pass
            
            # Look for entities in various response formats
            entities = []
            if isinstance(output, dict):
                entities = output.get("entities", [])
                if not entities and "content" in output:
                    # Claude format
                    content_text = output["content"]
                    if isinstance(content_text, list):
                        content_text = content_text[0].get("text", "")
                    try:
                        parsed = json.loads(content_text)
                        entities = parsed if isinstance(parsed, list) else parsed.get("entities", [])
                    except:
                        pass
            
            for ent in entities:
                total_entities += 1
                etype = ent.get("type", "").lower()
                if etype in DROPPED_TYPES:
                    dropped_entities.append(ent)
        except Exception:
            continue
    
    print(f"  Total entities in sample: {total_entities}")
    print(f"  Entities with dropped types: {len(dropped_entities)}")
    if dropped_entities:
        print(f"\n  SAMPLES OF DROPPED ENTITIES:")
        for e in dropped_entities[:20]:
            print(f"    [{e.get('type', '?')}] {e.get('name', '?')} (conf: {e.get('confidence', '?')})")

# Also check the cases/ path for any stored entity results
cases_prefix = f"cases/{CASE_ID}/"
print(f"\n\nChecking S3: s3://{BUCKET}/{cases_prefix}")
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=cases_prefix, MaxKeys=20, Delimiter="/")
prefixes = resp.get("CommonPrefixes", [])
files = resp.get("Contents", [])
print(f"  Subfolders: {[p['Prefix'].split('/')[-2] for p in prefixes]}")
print(f"  Files: {len(files)}")

# Check if there's an entities/ subfolder
entities_prefix = f"cases/{CASE_ID}/entities/"
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=entities_prefix, MaxKeys=5)
ent_files = resp.get("Contents", [])
print(f"\n  Entities in S3: {len(ent_files)} files")
if ent_files:
    print(f"  First: {ent_files[0]['Key']}")
