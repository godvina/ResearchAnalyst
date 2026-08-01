#!/usr/bin/env python3
"""Load Bedrock Batch Inference results into Aurora.

Reads output JSONL from S3, parses entity extraction results,
inserts entities into Aurora via Lambda, marks docs as processed.
"""
import json
import time
import boto3

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
OUTPUT_PREFIX = "batch-inference/entity-extraction/7f05e8d5-4492-4f19-8894-25367606db96/output/17uppsaiaf4c/"

lam = boto3.client("lambda", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def invoke_lambda(payload):
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    return json.loads(resp["Payload"].read().decode())


print(f"{'='*60}")
print(f"Loading Bedrock Batch Results into Aurora")
print(f"Case: {CASE_ID}")
print(f"{'='*60}")

# List output files
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=OUTPUT_PREFIX)
output_files = [f for f in resp.get("Contents", []) if f["Key"].endswith(".jsonl.out")]
print(f"Found {len(output_files)} output files")

total_docs = 0
total_entities = 0
total_errors = 0
total_empty = 0
start = time.time()

for f in output_files:
    key = f["Key"]
    size_mb = f["Size"] / 1024 / 1024
    print(f"\nProcessing {key} ({size_mb:.1f} MB)...")

    # Read entire file (up to ~93MB — fits in t3.small 2GB RAM)
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    body = obj["Body"].read().decode("utf-8")

    line_num = 0
    for line in body.strip().split("\n"):
        if not line:
            continue
        line_num += 1
        try:
            record = json.loads(line)
            doc_id = record.get("recordId", "")

            # Check for errors
            if record.get("error"):
                total_errors += 1
                continue

            # Parse the model output — handle both Anthropic and Nova formats
            output = record.get("modelOutput", {})
            text = "[]"
            # Nova format: output.message.content[0].text
            msg = output.get("message", {})
            if msg:
                content = msg.get("content", [{}])
                if isinstance(content, list) and content:
                    text = content[0].get("text", "[]")
            else:
                # Anthropic format: output.content[0].text
                content = output.get("content", [{}])
                if isinstance(content, list) and content:
                    text = content[0].get("text", "[]")
                elif isinstance(content, str):
                    text = content

            if not text or text.strip() == "[]":
                total_empty += 1
                # Still mark as processed
                try:
                    invoke_lambda({
                        "action": "insert_entities_from_batch",
                        "case_id": CASE_ID,
                        "document_id": doc_id,
                        "entity_json": "[]",
                    })
                except Exception:
                    pass
                total_docs += 1
                continue

            # Insert entities via Lambda
            result = invoke_lambda({
                "action": "insert_entities_from_batch",
                "case_id": CASE_ID,
                "document_id": doc_id,
                "entity_json": text,
            })

            if "error" not in result:
                total_docs += 1
                total_entities += result.get("entities_inserted", 0)
            else:
                total_errors += 1

        except Exception as e:
            total_errors += 1

        if line_num % 500 == 0:
            elapsed = time.time() - start
            rate = total_docs / max(elapsed, 1) * 60
            print(f"  Line {line_num:,}: {total_docs:,} docs, {total_entities:,} entities, "
                  f"{total_errors} errors, {total_empty} empty, {rate:.0f} docs/min")

        time.sleep(0.1)  # Don't hammer Lambda

    print(f"  File complete: {line_num:,} lines processed")

elapsed = time.time() - start

# Refresh case stats
print(f"\nRefreshing case stats...")
try:
    stats = invoke_lambda({"action": "refresh_case_stats", "case_id": CASE_ID})
    print(f"Stats: docs={stats.get('document_count', '?')}, entities={stats.get('entity_count', '?')}")
except Exception as e:
    print(f"Stats refresh failed: {e}")

print(f"\n{'='*60}")
print(f"LOAD COMPLETE")
print(f"  Docs processed: {total_docs:,}")
print(f"  Entities inserted: {total_entities:,}")
print(f"  Empty results: {total_empty:,}")
print(f"  Errors: {total_errors}")
print(f"  Elapsed: {elapsed/60:.1f} minutes")
print(f"{'='*60}")
