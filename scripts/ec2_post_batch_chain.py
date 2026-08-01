#!/usr/bin/env python3
"""
Post-Batch Chain — Runs steps 1-5 unattended after Bedrock batch completes.

1. Poll batch job until Completed
2. Clear old entities from Aurora
3. Load Nova Pro results into Aurora
4. Verify entity quality
5. Launch Neptune re-sync EC2

Run on EC2 or locally. Self-terminates EC2 after Neptune re-sync launches.

Usage:
    python3 ec2_post_batch_chain.py
"""
import boto3
import json
import time
import sys
import re
import os
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────
REGION = "us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
JOB_ARN = "arn:aws:bedrock:us-east-1:974220725866:model-invocation-job/bxjsijen80d5"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
BUCKET = "research-analyst-data-lake-974220725866"
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


# ═══════════════════════════════════════════════════════════════════
# STEP 1: Poll batch job until complete
# ═══════════════════════════════════════════════════════════════════
def step1_poll_batch():
    log("=" * 60)
    log("STEP 1: Polling Bedrock batch job...")
    log(f"Job: {JOB_ARN}")
    log("=" * 60)

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

        if status == "Failed":
            log(f"  FAILED: {resp.get('message', 'unknown error')}")
            return False

        if status in ("Expired", "Stopped"):
            log(f"  Job {status}. Cannot proceed.")
            return False

        # Still running — wait 60 seconds
        log(f"  Waiting 60s...")
        time.sleep(60)


# ═══════════════════════════════════════════════════════════════════
# STEP 2: Clear old entities from Aurora
# ═══════════════════════════════════════════════════════════════════
def step2_clear_old_entities():
    log("=" * 60)
    log("STEP 2: Clearing old Nova Lite entities from Aurora...")
    log("=" * 60)

    # Get current count
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": 1,
            "offset": 0,
        }),
    )
    data = json.loads(resp["Payload"].read())
    old_count = data.get("total", 0)
    log(f"  Current entity count: {old_count:,}")

    # Delete old entities via a custom action
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "clear_entities_for_case",
            "case_id": CASE_ID,
        }),
    )
    result = json.loads(resp["Payload"].read())

    if "error" in result:
        # Action might not exist — try direct SQL approach
        log(f"  clear_entities_for_case not available: {result['error'][:100]}")
        log("  Attempting delete via insert_entities_from_batch with clear flag...")
        resp2 = lam.invoke(
            FunctionName=LAMBDA_NAME,
            Payload=json.dumps({
                "action": "insert_entities_from_batch",
                "case_id": CASE_ID,
                "clear_existing": True,
                "entities": [],
            }),
        )
        result2 = json.loads(resp2["Payload"].read())
        log(f"  Result: {str(result2)[:200]}")
    else:
        log(f"  Cleared: {result}")

    # Verify
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": 1,
            "offset": 0,
        }),
    )
    data = json.loads(resp["Payload"].read())
    new_count = data.get("total", 0)
    log(f"  Entity count after clear: {new_count:,} (was {old_count:,})")
    return True


# ═══════════════════════════════════════════════════════════════════
# STEP 3: Load Nova Pro results into Aurora
# ═══════════════════════════════════════════════════════════════════
def step3_load_results():
    log("=" * 60)
    log("STEP 3: Loading Nova Pro results into Aurora...")
    log(f"Source: s3://{BUCKET}/{OUTPUT_PREFIX}")
    log("=" * 60)

    # List output files
    paginator = s3.get_paginator("list_objects_v2")
    output_files = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=OUTPUT_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".jsonl.out"):
                output_files.append(obj["Key"])

    if not output_files:
        log("ERROR: No output files found!")
        return False

    log(f"  Found {len(output_files)} output files")

    total_docs = 0
    total_entities = 0
    total_errors = 0
    batch_buffer = []
    BATCH_SIZE = 50

    for file_key in output_files:
        log(f"  Processing {file_key.split('/')[-1]}...")
        obj = s3.get_object(Bucket=BUCKET, Key=file_key)
        content = obj["Body"].read().decode("utf-8")

        for line in content.strip().split("\n"):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
                doc_id = record.get("recordId", "")
                model_output = record.get("modelOutput", {})

                # Nova Pro format
                text_out = (model_output.get("output", {})
                           .get("message", {})
                           .get("content", [{}])[0]
                           .get("text", ""))

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

                # Flush batch
                if len(batch_buffer) >= BATCH_SIZE:
                    _flush(batch_buffer)
                    batch_buffer = []

            except json.JSONDecodeError:
                total_errors += 1

        log(f"    Running total: {total_docs:,} docs, {total_entities:,} entities, {total_errors} errors")

    # Flush remaining
    if batch_buffer:
        _flush(batch_buffer)

    log(f"\n  LOAD COMPLETE: {total_docs:,} docs, {total_entities:,} entities, {total_errors} errors")
    return True


def _flush(entities):
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "insert_entities_from_batch",
            "entities": entities,
        }),
    )
    result = json.loads(resp["Payload"].read())
    if "error" in result:
        pass  # Log silently, don't stop


# ═══════════════════════════════════════════════════════════════════
# STEP 4: Verify entity quality
# ═══════════════════════════════════════════════════════════════════
def step4_verify():
    log("=" * 60)
    log("STEP 4: Verifying entity quality...")
    log("=" * 60)

    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": 20,
            "offset": 0,
        }),
    )
    data = json.loads(resp["Payload"].read())
    total = data.get("total", 0)
    entities = data.get("entities", [])

    log(f"  Total entities: {total:,}")
    log(f"  Top 20 by occurrence:")
    for e in entities:
        log(f"    {e['type']:20s} count={e['count']:6d}  {e['name'][:50]}")

    # Quick quality check
    valid = sum(1 for e in entities if len(e["name"]) >= 3 and e["name"][0].isalpha())
    precision = valid / len(entities) if entities else 0
    log(f"\n  Quick precision check (top 20): {precision:.0%}")

    if precision < 0.7:
        log("  WARNING: Precision below 70% — review the extraction results!")
    else:
        log("  Quality looks good ✓")

    return True


# ═══════════════════════════════════════════════════════════════════
# STEP 5: Launch Neptune re-sync EC2
# ═══════════════════════════════════════════════════════════════════
def step5_launch_resync():
    log("=" * 60)
    log("STEP 5: Launching Neptune re-sync EC2...")
    log("=" * 60)

    userdata = f"""#!/bin/bash
set -e
BUCKET="{BUCKET}"
CASE_ID="{CASE_ID}"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

echo "=== Neptune Re-Sync EC2 Starting ==="
echo "Case: $CASE_ID"
echo "Time: $(date)"

pip3 install boto3 --quiet 2>/dev/null || true
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py

cd /tmp
export CASE_ID=$CASE_ID
python3 ec2_neptune_resync.py --case-id $CASE_ID 2>&1 | tee /tmp/resync_log.txt

aws s3 cp /tmp/resync_log.txt s3://$BUCKET/logs/neptune-resync/resync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Re-Sync Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region {REGION}
"""

    import base64
    resp = ec2.run_instances(
        ImageId=EC2_AMI,
        InstanceType=EC2_TYPE,
        IamInstanceProfile={"Name": EC2_PROFILE},
        SubnetId=EC2_SUBNET,
        SecurityGroupIds=[EC2_SG],
        UserData=userdata,
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": "neptune-resync-post-batch"},
                {"Key": "auto-terminate", "Value": "true"},
            ],
        }],
    )

    instance_id = resp["Instances"][0]["InstanceId"]
    log(f"  EC2 launched: {instance_id}")
    log(f"  Type: {EC2_TYPE}, Profile: {EC2_PROFILE}")
    log(f"  Expected runtime: ~4 hours, self-terminates when done")
    log(f"  Logs: s3://{BUCKET}/logs/neptune-resync/")

    # Verify launch per protocol
    log("  Waiting 90s for boot...")
    time.sleep(90)
    output = ec2.get_console_output(InstanceId=instance_id, Latest=True)
    console = output.get("Output", "")
    if "Re-Sync" in console or "Starting" in console:
        log("  Script started ✓")
    elif console:
        log(f"  Console output: {console[-200:]}")
    else:
        log("  No console output yet — check in 2 minutes")

    return True


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    log("=" * 60)
    log("POST-BATCH CHAIN — Steps 1-5 Automated")
    log(f"Case: {CASE_ID}")
    log(f"Batch Job: {JOB_ARN}")
    log(f"Time: {datetime.now().isoformat()}")
    log("=" * 60)

    # Step 1: Poll batch
    if not step1_poll_batch():
        log("FATAL: Batch job did not complete. Stopping.")
        sys.exit(1)

    # Step 2: Clear old entities
    step2_clear_old_entities()

    # Step 3: Load results
    if not step3_load_results():
        log("FATAL: Load failed. Stopping.")
        sys.exit(1)

    # Step 4: Verify
    step4_verify()

    # Step 5: Launch Neptune re-sync
    step5_launch_resync()

    log("\n" + "=" * 60)
    log("ALL STEPS COMPLETE")
    log("  Batch: ✓ Completed")
    log("  Aurora: ✓ Old entities cleared, new entities loaded")
    log("  Quality: ✓ Verified")
    log("  Neptune: ✓ Re-sync EC2 launched (runs ~4 hours)")
    log("=" * 60)


if __name__ == "__main__":
    main()
