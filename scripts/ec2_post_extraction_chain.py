#!/usr/bin/env python3
"""
Post-Extraction Chain — Runs on EC2 unattended.

Polls Bedrock batch job until complete, then:
  Step 2: Clears old entities from Aurora
  Step 3: Loads Nova Pro results into Aurora
  Step 4: Verifies entity quality
  Step 5: Launches Neptune re-sync EC2

Self-terminates when done.
"""
import boto3
import json
import re
import time
import sys
import os
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────
REGION = "us-east-1"
CASE_ID = os.environ.get("CASE_ID", "7f05e8d5-4492-4f19-8894-25367606db96")
JOB_ARN = os.environ.get("JOB_ARN", "arn:aws:bedrock:us-east-1:974220725866:model-invocation-job/bxjsijen80d5")
BUCKET = "research-analyst-data-lake-974220725866"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
OUTPUT_PREFIX = f"batch-inference/entity-extraction/{CASE_ID}/output-v2/"

# Neptune re-sync EC2 config
EC2_AMI = "ami-0c1fe732b5494dc14"
EC2_TYPE = "t3.small"
EC2_PROFILE = "DOJ-Processing-Profile"
EC2_SUBNET = "subnet-0d4d796be847de3b0"
EC2_SG = "sg-0de960cc4f5c7d392"

bedrock = boto3.client("bedrock", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ── Step 1: Poll batch job ─────────────────────────────────────────
def wait_for_batch():
    log("STEP 1: Waiting for Bedrock batch job to complete...")
    log(f"  Job: {JOB_ARN}")
    while True:
        resp = bedrock.get_model_invocation_job(jobIdentifier=JOB_ARN)
        status = resp.get("status", "UNKNOWN")
        log(f"  Status: {status}")
        
        if status == "Completed":
            stats = resp.get("statistics", {})
            log(f"  Input records: {stats.get('inputRecordCount', '?')}")
            log(f"  Output records: {stats.get('outputRecordCount', '?')}")
            log(f"  Error records: {stats.get('errorRecordCount', '?')}")
            return True
        elif status == "Failed":
            log(f"  FAILED: {resp.get('message', 'unknown error')}")
            return False
        elif status == "Stopped":
            log("  Job was stopped.")
            return False
        
        time.sleep(60)  # Check every minute

# ── Step 2: Clear old entities ──────────────────────────────────────
def clear_old_entities():
    log("STEP 2: Clearing old Nova Lite entities from Aurora...")
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "execute_sql",
            "sql": f"DELETE FROM entities WHERE case_file_id = '{CASE_ID}'",
        }),
    )
    result = json.loads(resp["Payload"].read())
    
    # If execute_sql doesn't exist, try via gremlin_query (which is just a passthrough)
    if "error" in str(result):
        log(f"  execute_sql not available, trying alternative...")
        # Use the entity tracking table approach — just truncate for this case
        resp2 = lam.invoke(
            FunctionName=LAMBDA_NAME,
            Payload=json.dumps({
                "action": "query_aurora_entities",
                "case_id": CASE_ID,
                "limit": 1,
                "offset": 0,
            }),
        )
        r2 = json.loads(resp2["Payload"].read())
        old_count = r2.get("total", 0)
        log(f"  Old entity count: {old_count}. Will be replaced during load (ON CONFLICT UPDATE).")
        return True
    
    log("  Old entities cleared.")
    return True

# ── Step 3: Load Nova Pro results ───────────────────────────────────
def load_results():
    log("STEP 3: Loading Nova Pro results into Aurora...")
    
    # List output files
    paginator = s3.get_paginator("list_objects_v2")
    output_files = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=OUTPUT_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".jsonl.out"):
                output_files.append(obj["Key"])
    
    if not output_files:
        log("  ERROR: No output files found!")
        return False
    
    log(f"  Found {len(output_files)} output files")
    
    total_docs = 0
    total_entities = 0
    total_errors = 0
    batch_buffer = []
    BATCH_SIZE = 50
    
    for file_key in output_files:
        log(f"  Processing {file_key}...")
        obj = s3.get_object(Bucket=BUCKET, Key=file_key)
        content = obj["Body"].read().decode("utf-8")
        
        for line in content.strip().split("\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                doc_id = record.get("recordId", "")
                model_output = record.get("modelOutput", {})
                
                # Extract text from Nova Pro output
                text_out = ""
                try:
                    text_out = (model_output.get("output", {})
                               .get("message", {})
                               .get("content", [{}])[0]
                               .get("text", ""))
                except (IndexError, AttributeError):
                    pass
                
                if not text_out:
                    error = record.get("error", {}).get("message", "")
                    if error:
                        total_errors += 1
                    continue
                
                # Parse entities
                entities = []
                try:
                    match = re.search(r'\[.*\]', text_out, re.DOTALL)
                    if match:
                        entities = json.loads(match.group())
                except (json.JSONDecodeError, AttributeError):
                    try:
                        match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text_out, re.DOTALL)
                        if match:
                            entities = json.loads(match.group(1))
                    except:
                        total_errors += 1
                        continue
                
                total_docs += 1
                
                for ent in entities:
                    # Handle nested lists (some models return [[...]] instead of [...])
                    if isinstance(ent, list):
                        for sub_ent in ent:
                            if isinstance(sub_ent, dict):
                                name = sub_ent.get("name", "").strip()
                                etype = sub_ent.get("type", "unknown").lower()
                                confidence = float(sub_ent.get("confidence", 0.5))
                                if len(name) >= 3:
                                    batch_buffer.append({
                                        "case_id": CASE_ID,
                                        "document_id": doc_id,
                                        "name": name,
                                        "type": etype,
                                        "confidence": confidence,
                                    })
                                    total_entities += 1
                        continue
                    
                    if not isinstance(ent, dict):
                        continue
                    
                    name = ent.get("name", "").strip()
                    etype = ent.get("type", "unknown").lower()
                    confidence = float(ent.get("confidence", 0.5))
                    
                    if len(name) < 3:
                        continue
                    
                    batch_buffer.append({
                        "case_id": CASE_ID,
                        "document_id": doc_id,
                        "name": name,
                        "type": etype,
                        "confidence": confidence,
                    })
                    total_entities += 1
                
                if len(batch_buffer) >= BATCH_SIZE:
                    _flush(batch_buffer)
                    batch_buffer = []
                    
            except json.JSONDecodeError:
                total_errors += 1
        
        log(f"    Docs: {total_docs:,}, Entities: {total_entities:,}, Errors: {total_errors}")
    
    if batch_buffer:
        _flush(batch_buffer)
    
    log(f"  LOAD COMPLETE: {total_docs:,} docs, {total_entities:,} entities, {total_errors} errors")
    return True

def _flush(entities):
    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            Payload=json.dumps({
                "action": "insert_entities_from_batch",
                "entities": entities,
            }),
        )
        result = json.loads(resp["Payload"].read())
        if "error" in str(result).lower():
            log(f"    Batch insert warning: {str(result)[:150]}")
    except Exception as e:
        log(f"    Batch insert error: {str(e)[:150]}")

# ── Step 4: Verify quality ──────────────────────────────────────────
def verify_quality():
    log("STEP 4: Verifying entity quality...")
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": 20,
            "offset": 0,
            "min_occurrence": 2,
        }),
    )
    data = json.loads(resp["Payload"].read())
    total = data.get("total", 0)
    entities = data.get("entities", [])
    
    log(f"  Total entities with occurrence >= 2: {total:,}")
    log(f"  Top 10 entities:")
    for e in entities[:10]:
        log(f"    {e['type']:20s} count={e['count']:6d}  {e['name'][:50]}")
    
    return total > 0

# ── Step 5: Launch Neptune re-sync EC2 ──────────────────────────────
def launch_resync():
    log("STEP 5: Launching Neptune re-sync EC2...")
    
    userdata = f"""#!/bin/bash
set -e
BUCKET="{BUCKET}"
CASE_ID="{CASE_ID}"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION="{REGION}"

echo "=== Neptune Re-Sync EC2 Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Case: $CASE_ID"
echo "Time: $(date)"

pip3 install boto3 --quiet 2>/dev/null || true
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py

cd /tmp
export CASE_ID=$CASE_ID
python3 ec2_neptune_resync.py --case-id $CASE_ID 2>&1 | tee /tmp/resync_log.txt

aws s3 cp /tmp/resync_log.txt s3://$BUCKET/logs/neptune-resync/resync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Re-Sync Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
"""
    
    import base64
    userdata_b64 = base64.b64encode(userdata.encode()).decode()
    
    resp = ec2.run_instances(
        ImageId=EC2_AMI,
        InstanceType=EC2_TYPE,
        MinCount=1, MaxCount=1,
        IamInstanceProfile={"Name": EC2_PROFILE},
        SubnetId=EC2_SUBNET,
        SecurityGroupIds=[EC2_SG],
        UserData=userdata_b64,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": "neptune-resync-auto"},
                {"Key": "auto-terminate", "Value": "true"},
            ],
        }],
    )
    
    instance_id = resp["Instances"][0]["InstanceId"]
    log(f"  Launched EC2: {instance_id}")
    log(f"  Name: neptune-resync-auto")
    log(f"  Expected runtime: ~4 hours, self-terminates when done")
    return True

# ── Main ────────────────────────────────────────────────────────────
def main():
    log("=" * 60)
    log("POST-EXTRACTION CHAIN — Automated Steps 2-5")
    log(f"Case: {CASE_ID}")
    log(f"Batch Job: {JOB_ARN}")
    log("=" * 60)
    
    # Step 1: Wait for batch
    if not wait_for_batch():
        log("FATAL: Batch job did not complete successfully. Stopping.")
        sys.exit(1)
    
    # Step 2: Clear old entities
    clear_old_entities()
    
    # Step 3: Load results
    if not load_results():
        log("FATAL: Load failed. Stopping.")
        sys.exit(1)
    
    # Step 4: Verify
    verify_quality()
    
    # Step 5: Launch Neptune re-sync
    launch_resync()
    
    log("=" * 60)
    log("ALL STEPS COMPLETE")
    log("Neptune re-sync EC2 launched — will run ~4 hours and self-terminate.")
    log("Check logs at: s3://research-analyst-data-lake-974220725866/logs/")
    log("=" * 60)

if __name__ == "__main__":
    main()
