"""Sample extractions in S3 to find files with dropped entity types.
Check 100 random files for non-standard types."""
import boto3
import json
import random

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract"}

s3 = boto3.client("s3", region_name=REGION)

# List a chunk of extraction files
prefix = f"cases/{CASE_ID}/extractions/"
paginator = s3.get_paginator("list_objects_v2")
all_keys = []
for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
    for obj in page.get("Contents", []):
        all_keys.append(obj["Key"])
    if len(all_keys) > 1000:
        break

print(f"Got {len(all_keys)} extraction file keys")

# Sample 50 random files
sample = random.sample(all_keys, min(50, len(all_keys)))
all_types_seen = {}
dropped_examples = []

print(f"Sampling {len(sample)} files...")
for key in sample:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        data = json.loads(obj["Body"].read().decode())
        entities = data.get("entities", [])
        for e in entities:
            t = e.get("type", e.get("entity_type", "unknown"))
            all_types_seen[t] = all_types_seen.get(t, 0) + 1
            if t.lower() in DROPPED_TYPES:
                dropped_examples.append({
                    "file": key.split("/")[-1],
                    "type": t,
                    "name": e.get("name", e.get("canonical_name", "?")),
                    "confidence": e.get("confidence", "?"),
                })
    except Exception as ex:
        pass

print(f"\nAll entity types across {len(sample)} files:")
for t, c in sorted(all_types_seen.items(), key=lambda x: -x[1]):
    marker = " *** DROPPED ***" if t.lower() in DROPPED_TYPES else ""
    print(f"  {t}: {c}{marker}")

print(f"\nDropped-type entities found: {len(dropped_examples)}")
if dropped_examples:
    print("\nSamples:")
    for e in dropped_examples[:30]:
        print(f"  [{e['type']}] {e['name']} (conf={e['confidence']}) from {e['file'][:30]}")
else:
    print("\nNONE found in S3 extractions — those types came from elsewhere")
    print("(Likely from the Neptune entity extraction pipeline or cross-case agent)")
