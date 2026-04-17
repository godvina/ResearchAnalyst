"""Check what's been processed through the pipeline across all data sources.

Counts:
1. Raw files in S3 (cases/{case_id}/raw/)
2. Extraction artifacts in S3 (cases/{case_id}/extractions/)
3. Pre-extracted text in S3 (textract-output/DataSet1-5/ and DataSet11/)
4. Neptune node/edge counts via Lambda
"""
import boto3
import json

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

s3 = boto3.client("s3", region_name=REGION)


def count_s3_prefix(bucket, prefix, label=""):
    count = 0
    total_size = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            count += 1
            total_size += obj.get("Size", 0)
        if count % 10000 == 0 and count > 0:
            print(f"  ... {count} so far")
    size_gb = total_size / (1024**3)
    print(f"  {label}: {count:,} files ({size_gb:.2f} GB)")
    return count


print("=" * 60)
print("Processing Status Check")
print("=" * 60)

# 1. Raw files in main bucket
print("\n1. Raw files in S3 (main bucket):")
raw_count = count_s3_prefix(BUCKET, f"cases/{CASE_ID}/raw/", "Raw PDFs/docs")

# 2. Extraction artifacts (= docs that went through Bedrock entity extraction)
print("\n2. Extraction artifacts (processed through pipeline):")
ext_count = count_s3_prefix(BUCKET, f"cases/{CASE_ID}/extractions/", "Extraction JSONs")

# 3. Pre-extracted Textract output (DataSet 1-5)
print("\n3. Pre-extracted Textract output (source bucket):")
for ds in ["DataSet1", "DataSet2", "DataSet3", "DataSet4", "DataSet5"]:
    count_s3_prefix(SOURCE_BUCKET, f"textract-output/{ds}/", f"  {ds}")

# 4. Pre-extracted Textract output (DataSet 11 — new)
print("\n4. DataSet 11 extracted text:")
ds11_count = count_s3_prefix(BUCKET, "textract-output/DataSet11/", "DataSet11 JSONs")

# 5. Neptune bulk load CSVs
print("\n5. Neptune bulk load CSVs:")
csv_count = count_s3_prefix(BUCKET, "neptune-bulk-load/", "Bulk load CSVs")

# Summary
print(f"\n{'=' * 60}")
print("SUMMARY")
print(f"{'=' * 60}")
print(f"  Raw files in S3:           {raw_count:,}")
print(f"  Processed (extractions):   {ext_count:,}")
print(f"  DataSet 11 text extracted: {ds11_count:,}")
print(f"  Neptune CSV batches:       {csv_count:,}")
print(f"  Unprocessed raw files:     ~{raw_count - ext_count:,}")
print(f"{'=' * 60}")
