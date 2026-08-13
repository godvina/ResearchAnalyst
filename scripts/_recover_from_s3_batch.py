"""Recover dropped entities from S3 batch inference output.

The batch output JSONL has all the raw Nova Lite entity extractions.
We need to parse the modelOutput, find entities with dropped types,
and re-create them in Neptune.
"""
import boto3
import json
import re
import time

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + CASE_ID

DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract"}

s3 = boto3.client("s3", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"


def gremlin(q, timeout=60):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID,
                           "query": q, "timeout": timeout}))
    d = json.loads(r["Payload"].read().decode())
    return d.get("result", d.get("error", ""))


print("=" * 60)
print("RECOVER DROPPED ENTITIES FROM S3 BATCH OUTPUT")
print("=" * 60)

# The batch output has 2 JSONL files (97MB + 49MB)
output_keys = [
    f"batch-inference/entity-extraction/{CASE_ID}/output/17uppsaiaf4c/entities_0000.jsonl.out",
    f"batch-inference/entity-extraction/{CASE_ID}/output/17uppsaiaf4c/entities_0001.jsonl.out",
]

# But the manifest says errorRecordCount: 75069, successRecordCount: 0
# This means the output format might be error records, not success records
# Let's check what format they're in

print("\nChecking batch output format...")
obj = s3.get_object(Bucket=BUCKET, Key=output_keys[0], Range="bytes=0-5000")
sample = obj["Body"].read().decode("utf-8", errors="ignore")
first_line = sample.split("\n")[0]
try:
    record = json.loads(first_line)
    print(f"  Keys: {list(record.keys())}")
    # Check if it has modelOutput or error
    if "modelOutput" in record:
        output = record["modelOutput"]
        if isinstance(output, dict):
            print(f"  modelOutput keys: {list(output.keys())}")
            content = output.get("content", [])
            if content:
                print(f"  content[0]: {str(content[0])[:200]}")
        else:
            print(f"  modelOutput type: {type(output)}")
            print(f"  modelOutput preview: {str(output)[:200]}")
    elif "error" in record:
        print(f"  ERROR field: {record['error']}")
    else:
        print(f"  Record preview: {str(record)[:300]}")
except Exception as e:
    print(f"  Parse error: {e}")
    print(f"  Raw first 300 chars: {first_line[:300]}")
