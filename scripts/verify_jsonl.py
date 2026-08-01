"""Verify the JSONL prompt quality for the Nova Pro batch job."""
import boto3
import json

s3 = boto3.client("s3", region_name="us-east-1")
bucket = "research-analyst-data-lake-974220725866"
key = "batch-inference/entity-extraction/7f05e8d5-4492-4f19-8894-25367606db96/input-v2/batch_0000.jsonl"

# Read first 50KB to get at least one complete record
obj = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-50000")
content = obj["Body"].read().decode("utf-8")
first_line = content.split("\n")[0]

record = json.loads(first_line)
print(f"recordId: {record['recordId'][:12]}...")
print(f"Model format: Nova (messages/content/text)")

prompt = record["modelInput"]["messages"][0]["content"][0]["text"]
print(f"Prompt length: {len(prompt)} chars")
print(f"Max tokens: {record['modelInput']['inferenceConfig']['maxTokens']}")

# Show the taxonomy section of the prompt (not the document text)
lines = prompt.split("\n")
print(f"\n--- PROMPT STRUCTURE ({len(lines)} lines) ---")
for i, line in enumerate(lines):
    if "Document text:" in line:
        print(f"  [Lines 1-{i}: Taxonomy instructions]")
        print(f"  [Lines {i+1}-{len(lines)}: Document text ({len(lines)-i-1} lines)]")
        break

# Show the taxonomy types listed
print("\n--- ENTITY TYPES IN PROMPT ---")
for line in lines:
    if line.strip().startswith("- ") and ":" in line:
        print(f"  {line.strip()}")

# Show first 200 chars of document text
doc_start = prompt.find("---\n") + 4
doc_text = prompt[doc_start:doc_start+200]
print(f"\n--- DOCUMENT TEXT PREVIEW ---")
print(doc_text)
