"""Quick inventory of what's loaded across S3 buckets and Aurora."""
import boto3
import json
import urllib.request

REGION = "us-east-1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
DATA_BUCKET = "research-analyst-data-lake-974220725866"
API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

s3 = boto3.client("s3", region_name=REGION)

print("=" * 60)
print("INVENTORY REPORT")
print("=" * 60)

# 1. Source bucket prefixes
print("\n--- SOURCE BUCKET (doj-cases) ---")
prefixes = ["pdfs/", "bw-documents/", "documents/", "photo-metadata/", "rekognition-output/", "textract-output/"]
for p in prefixes:
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    size = 0
    for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=p):
        for obj in page.get("Contents", []):
            count += 1
            size += obj["Size"]
    print(f"  {p:25s} {count:>8,} files  {size/1024/1024:>10,.1f} MB")

# 2. DataSet zips
print("\n--- DATASET ZIPS ---")
for ds in range(1, 13):
    prefix = f"DataSet{ds}/"
    count = 0
    size = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            count += 1
            size += obj["Size"]
    if count > 0:
        print(f"  DataSet{ds:>2d}:  {count:>5} files  {size/1024/1024:>10,.1f} MB")

# 3. Data lake - case raw files
print("\n--- DATA LAKE (processed cases) ---")
cases = {
    "Epstein Combined": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
    "Epstein Main": "7f05e8d5-4492-4f19-8894-25367606db96",
    "Ancient Aliens": "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7",
}
for name, cid in cases.items():
    raw_count = 0
    raw_size = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=DATA_BUCKET, Prefix=f"cases/{cid}/raw/"):
        for obj in page.get("Contents", []):
            raw_count += 1
            raw_size += obj["Size"]
    # Get Aurora counts via API
    try:
        req = urllib.request.Request(f"{API}/case-files/{cid}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        doc_count = data.get("document_count", 0)
        entity_count = data.get("entity_count", 0)
    except Exception:
        doc_count = "?"
        entity_count = "?"
    print(f"  {name:20s}  S3 raw: {raw_count:>8,}  Aurora docs: {doc_count:>8}  Entities: {entity_count:>8}")

# 4. DOJ datasets available (from DOJ website)
print("\n--- DOJ DATASETS (12 total) ---")
print("  DS1-5:   Loaded (Phase 1 — ~3,800 docs)")
print("  DS6-7:   NOT loaded (need download)")
print("  DS8-12:  Placeholder only (robots.txt)")
print("  DS11:    Loaded (Phase 2 — ~3,466 docs)")
print("\n  MISSING: DS6, DS7, DS8, DS9, DS10, DS12")
print("  These contain the bulk of the 106K+ documents")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("  Currently loaded:  ~8,974 docs (Epstein Combined)")
print("  Available from DOJ: ~106,000+ docs (DS1-12)")
print("  Gap:               ~97,000 docs (DS6-10, DS12)")
print("  Estimated size:    ~150-180 GB (raw PDFs + images)")
print("  Processed text:    ~20-30 GB (text only, no images)")
