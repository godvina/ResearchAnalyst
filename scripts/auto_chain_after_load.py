"""Auto-chain: Poll Aurora load progress, then launch Neptune sync when done.

Runs as a background process. When the entity_extraction_done count stops
increasing (load EC2 finished), it launches the Neptune sync EC2.
"""
import boto3
import json
import time

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
LOAD_EC2 = "i-0aa1a66b083a0c35d"

lam = boto3.client("lambda", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def invoke_lambda(payload):
    resp = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
                      Payload=json.dumps(payload))
    return json.loads(resp["Payload"].read().decode())


def get_count():
    try:
        r = invoke_lambda({"action": "backfill_entities_count", "case_id": CASE_ID})
        return r.get("has_entities_count", 0), r.get("missing_count", 0)
    except Exception:
        return -1, -1


def is_ec2_running(instance_id):
    try:
        r = ec2.describe_instances(InstanceIds=[instance_id])
        state = r["Reservations"][0]["Instances"][0]["State"]["Name"]
        return state == "running"
    except Exception:
        return False


print("=== Auto-Chain: Waiting for Aurora load to complete ===")
print(f"Monitoring load EC2: {LOAD_EC2}")

prev_count = 0
stable_checks = 0

while True:
    done, remaining = get_count()
    running = is_ec2_running(LOAD_EC2)
    print(f"  {time.strftime('%H:%M:%S')} Done: {done:,} | Remaining: {remaining:,} | EC2: {'running' if running else 'stopped'}")

    if not running and done > 1000:
        print("Load EC2 terminated — load is complete!")
        break

    if done == prev_count and done > 1000:
        stable_checks += 1
        if stable_checks >= 3:
            print("Count stable for 3 checks — load appears complete.")
            break
    else:
        stable_checks = 0

    prev_count = done
    time.sleep(120)  # Check every 2 minutes

# === STEP 1: Refresh case stats ===
print("\n=== Step 1: Refreshing case stats ===")
try:
    stats = invoke_lambda({"action": "refresh_case_stats", "case_id": CASE_ID})
    print(f"Stats: docs={stats.get('document_count', '?')}, entities={stats.get('entity_count', '?')}")
except Exception as e:
    print(f"Stats refresh failed: {e}")

# === STEP 2: Noise cleanup ===
print("\n=== Step 2: Cleaning noise entities ===")
try:
    cleanup = invoke_lambda({"action": "cleanup_noise_entities", "case_id": CASE_ID})
    print(f"Deleted {cleanup.get('deleted', 0)} noise entities")
except Exception as e:
    print(f"Cleanup failed: {e}")

# === STEP 3: Launch Neptune sync EC2 ===
print("\n=== Step 3: Launching Neptune sync EC2 ===")
try:
    # Upload the sync script
    s3.put_object(
        Bucket=BUCKET,
        Key="deploy/ec2_aurora_neptune_sync.py",
        Body=open("scripts/ec2_aurora_neptune_sync.py", "rb").read(),
    )
except Exception:
    print("Could not upload sync script — it should already be in S3")

sync_userdata = """#!/bin/bash
set -e
exec > >(tee /var/log/neptune-sync.log) 2>&1
echo "=== Neptune Sync ==="
date
yum install -y python3-pip 2>/dev/null || dnf install -y python3-pip 2>/dev/null || true
pip3 install boto3
aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_aurora_neptune_sync.py /tmp/sync.py
cd /tmp
python3 sync.py
echo "Uploading log..."
aws s3 cp /var/log/neptune-sync.log s3://research-analyst-data-lake-974220725866/logs/ec2-neptune-sync-$(date +%Y%m%d-%H%M%S).txt
echo "=== Done ==="
date
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
"""

r = ec2.run_instances(
    ImageId="ami-0c02fb55956c7d316",
    InstanceType="t3.small",
    IamInstanceProfile={"Name": "NikityLoaderEC2Profile"},
    UserData=sync_userdata,
    TagSpecifications=[{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "neptune-sync-auto"}]}],
    MinCount=1, MaxCount=1,
)
sync_id = r["Instances"][0]["InstanceId"]
print(f"Neptune sync EC2 launched: {sync_id}")
print("It will sync Aurora entities to Neptune, then self-terminate.")

# === STEP 4: Final stats refresh ===
print("\n=== All steps queued. Neptune sync running in background. ===")
print(f"Load EC2: {LOAD_EC2} (terminated)")
print(f"Sync EC2: {sync_id} (running)")
print("When sync completes, Epstein Main knowledge graph will have all new entities.")
