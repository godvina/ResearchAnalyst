"""Check the Nova Pro batch output format."""
import boto3
import json
import re

s3 = boto3.client("s3", region_name="us-east-1")
bucket = "research-analyst-data-lake-974220725866"
prefix = "batch-inference/entity-extraction/7f05e8d5-4492-4f19-8894-25367606db96/output-v2/"

paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
    for obj in page.get("Contents", []):
        key = obj["Key"]
        if not key.endswith(".jsonl.out"):
            continue
        print(f"File: {key} ({obj['Size']} bytes)")
        
        resp = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-20000")
        content = resp["Body"].read().decode("utf-8")
        lines = content.strip().split("\n")
        
        for i, line in enumerate(lines[:3]):
            record = json.loads(line)
            doc_id = record.get("recordId", "?")[:12]
            mo = record.get("modelOutput", {})
            
            # Check for error
            error = record.get("error", {})
            if error:
                print(f"  Record {i}: {doc_id} ERROR: {error}")
                continue
            
            text_out = ""
            try:
                text_out = mo.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            except (IndexError, AttributeError):
                print(f"  Record {i}: {doc_id} — unexpected output format: {str(mo)[:200]}")
                continue
            
            print(f"  Record {i}: {doc_id} — {len(text_out)} chars output")
            
            # Try to parse entities
            try:
                match = re.search(r'\[.*\]', text_out, re.DOTALL)
                if match:
                    entities = json.loads(match.group())
                    print(f"    Parsed {len(entities)} entities")
                    for e in entities[:5]:
                        if isinstance(e, dict):
                            print(f"      {e.get('type','?'):20s} {e.get('name','?')[:50]}")
                        else:
                            print(f"      NOT A DICT: {type(e).__name__} = {str(e)[:80]}")
                else:
                    print(f"    No JSON array found. Text: {text_out[:200]}")
            except json.JSONDecodeError as je:
                print(f"    JSON parse error: {je}")
                print(f"    Text: {text_out[:200]}")
        
        break  # Only check first file
    break
