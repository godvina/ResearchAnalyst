"""Create a fresh Epstein case with the improved entity extraction prompt.

Picks the 50 largest Textract files (most content) for best entity quality.
"""
import boto3
import json
import base64
import urllib.request

REGION = "us-east-1"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
DATASETS = ["DataSet1", "DataSet2", "DataSet4", "DataSet5"]
NUM_DOCS = 50


def api_request(method, path, body=None):
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"  HTTP {e.code}: {err[:300]}")
        return None


def main():
    s3 = boto3.client("s3", region_name=REGION)

    # Find the largest Textract files across all datasets
    print("Finding the most content-rich Textract files...")
    all_files = []
    for ds in DATASETS:
        prefix = f"textract-output/{ds}/"
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".json") and obj["Size"] > 200:
                    all_files.append((obj["Key"], obj["Size"]))

    all_files.sort(key=lambda x: x[1], reverse=True)
    top_files = all_files[:NUM_DOCS]
    print(f"Selected {len(top_files)} files (largest by size)")
    print(f"  Smallest: {top_files[-1][1]} bytes")
    print(f"  Largest: {top_files[0][1]} bytes")

    # Create a new enterprise case
    print("\nCreating fresh Epstein case (v2 - improved extraction)...")
    result = api_request("POST", "/case-files", {
        "topic_name": "Epstein Files v2 (Improved Extraction)",
        "description": "50 highest-content docs with investigation-tuned entity extraction",
        "search_tier": "enterprise",
    })
    if not result:
        print("Failed to create case")
        return

    case_id = result.get("case_id")
    print(f"Case ID: {case_id}")
    print(f"Tier: {result.get('search_tier')}")

    # Read and send files
    print(f"\nReading {NUM_DOCS} Textract files...")
    files_payload = []
    for key, size in top_files:
        obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=key)
        content = json.loads(obj["Body"].read().decode())
        text = content.get("extractedText", "")
        if not text or len(text) < 50:
            continue
        filename = key.split("/")[-1].replace(".json", ".txt")
        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        files_payload.append({"filename": filename, "content_base64": text_b64})

    print(f"Prepared {len(files_payload)} files with content")

    # Ingest
    print(f"\nTriggering ingestion...")
    result = api_request("POST", f"/case-files/{case_id}/ingest", {"files": files_payload})
    if result:
        print(f"Execution: {result.get('execution_arn', '?').split(':')[-1]}")
        print(f"Documents: {result.get('documents_uploaded', 0)}")

    print(f"\n=== Epstein v2 Demo Case ===")
    print(f"Case ID: {case_id}")
    print(f"Docs: {len(files_payload)}")
    print(f"Using improved investigation-tuned entity extraction prompt")
    print(f"New entity types: phone_number, email, address, organization, account_number, vehicle, financial_amount")
    print(f"\nMonitor in Step Functions console.")
    print(f"Once complete, run Pattern Discovery and check Graph Explorer.")


if __name__ == "__main__":
    main()
