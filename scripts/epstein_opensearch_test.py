"""Epstein OpenSearch Test — Steps 4-5.

Case already created: 7f05e8d5-4492-4f19-8894-25367606db96 (enterprise tier)
Sends 5 Textract files through the ingest API with base64 content.
"""
import boto3
import json
import base64
import urllib.request

REGION = "us-east-1"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# Top 5 largest Textract files
TEST_FILES = [
    "textract-output/DataSet1/VOL00001/IMAGES/0001/EFTA00000476.json",
    "textract-output/DataSet1/VOL00001/IMAGES/0001/EFTA00000473.json",
    "textract-output/DataSet1/VOL00001/IMAGES/0001/EFTA00000019.json",
    "textract-output/DataSet4/VOL00004/IMAGES/0001/EFTA00007685.json",
    "textract-output/DataSet4/VOL00004/IMAGES/0001/EFTA00007703.json",
]


def main():
    s3 = boto3.client("s3", region_name=REGION)

    # Read Textract files and extract text
    print("=== Reading 5 Textract files from source bucket ===")
    files_payload = []
    for src_key in TEST_FILES:
        obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=src_key)
        content = json.loads(obj["Body"].read().decode())
        text = content.get("extractedText", "")
        filename = src_key.split("/")[-1].replace(".json", ".txt")
        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        files_payload.append({
            "filename": filename,
            "content_base64": text_b64,
        })
        print(f"  {filename}: {len(text)} chars")

    # Send through ingest API
    print(f"\n=== Triggering ingestion via API ===")
    print(f"Case ID: {CASE_ID}")

    url = f"{API_URL}/case-files/{CASE_ID}/ingest"
    body = json.dumps({"files": files_payload}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            print(f"Response: {json.dumps(result, indent=2)}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {err_body[:500]}")
        return

    print(f"\n=== Pipeline triggered! ===")
    print(f"Case: {CASE_ID} (enterprise tier)")
    print(f"Files: {len(TEST_FILES)}")
    print(f"The embed handler will route to OpenSearch Serverless.")
    print(f"\nMonitor Step Functions in the AWS console.")
    print(f"Once complete, test search:")
    print(f"  POST {API_URL}/case-files/{CASE_ID}/search")
    print(f'  Body: {{"query": "Epstein", "search_mode": "keyword"}}')


if __name__ == "__main__":
    main()
