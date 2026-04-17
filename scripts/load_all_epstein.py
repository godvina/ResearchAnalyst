"""Load all 3,800 Epstein Textract files into the enterprise case.

Reads pre-extracted text from the source bucket, batches them into
groups of 50, and triggers a Step Functions execution per batch.
"""
import boto3
import json
import base64
import time
import urllib.request
import uuid

REGION = "us-east-1"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
BATCH_SIZE = 50  # docs per Step Functions execution
DATASETS = ["DataSet1", "DataSet2", "DataSet3", "DataSet4", "DataSet5"]


def list_all_textract_files():
    """List all .json files across all datasets in textract-output/."""
    s3 = boto3.client("s3", region_name=REGION)
    all_files = []
    for ds in DATASETS:
        prefix = f"textract-output/{ds}/"
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".json") and obj["Size"] > 100:
                    all_files.append(obj["Key"])
    return all_files


def read_textract_file(s3_client, key):
    """Read a Textract JSON file and extract the text content."""
    obj = s3_client.get_object(Bucket=SOURCE_BUCKET, Key=key)
    content = json.loads(obj["Body"].read().decode())
    text = content.get("extractedText", "")
    return text


def ingest_batch(batch_files, batch_num, total_batches):
    """Send a batch of files through the ingest API."""
    s3 = boto3.client("s3", region_name=REGION)
    files_payload = []

    for key in batch_files:
        text = read_textract_file(s3, key)
        if not text or len(text) < 10:
            continue
        filename = key.split("/")[-1].replace(".json", ".txt")
        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        files_payload.append({"filename": filename, "content_base64": text_b64})

    if not files_payload:
        print(f"  Batch {batch_num}/{total_batches}: skipped (no valid files)")
        return None

    url = f"{API_URL}/case-files/{CASE_ID}/ingest"
    body = json.dumps({"files": files_payload}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            exec_arn = result.get("execution_arn", "?")
            doc_count = result.get("documents_uploaded", 0)
            print(f"  Batch {batch_num}/{total_batches}: {doc_count} docs -> {exec_arn.split(':')[-1]}")
            return exec_arn
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"  Batch {batch_num}/{total_batches}: HTTP {e.code} - {err[:200]}")
        return None


def main():
    print("=== Epstein Full Load ===")
    print(f"Case: {CASE_ID}")
    print(f"Source: {SOURCE_BUCKET}")
    print(f"Batch size: {BATCH_SIZE}")

    # List all files
    print("\nListing all Textract files...")
    all_files = list_all_textract_files()
    print(f"Found {len(all_files)} files across {len(DATASETS)} datasets")

    # Show breakdown by dataset
    for ds in DATASETS:
        count = len([f for f in all_files if ds in f])
        print(f"  {ds}: {count} files")

    total_batches = (len(all_files) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\nWill create {total_batches} batches of {BATCH_SIZE}")
    print(f"Estimated time: {total_batches * 3} minutes (3 min/batch avg)")

    import sys
    if "--confirm" not in sys.argv:
        print("\nRun with --confirm to proceed.")
        return

    # Process batches
    execution_arns = []
    for i in range(0, len(all_files), BATCH_SIZE):
        batch = all_files[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        arn = ingest_batch(batch, batch_num, total_batches)
        if arn:
            execution_arns.append(arn)
        # Small delay between batches to avoid API throttling
        time.sleep(2)

    print(f"\n=== Load Complete ===")
    print(f"Triggered {len(execution_arns)} executions for {len(all_files)} files")
    print(f"Monitor in Step Functions console.")

    # Save execution ARNs for monitoring
    with open("scripts/epstein_executions.json", "w") as f:
        json.dump({"case_id": CASE_ID, "executions": execution_arns, "total_files": len(all_files)}, f, indent=2)
    print(f"Execution ARNs saved to scripts/epstein_executions.json")


if __name__ == "__main__":
    main()
