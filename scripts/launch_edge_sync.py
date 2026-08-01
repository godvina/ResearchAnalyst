#!/usr/bin/env python3
"""
Launch EC2 instance to run Neptune edge sync.

Uploads the edge sync script to S3, launches an EC2 with userdata that:
  1. Installs boto3
  2. Downloads and runs the edge sync script
  3. Uploads log to S3
  4. Attempts self-termination (DOJ-Processing-Role may not have ec2:TerminateInstances)

EC2 config:
  - AMI: ami-0c1fe732b5494dc14
  - Profile: DOJ-Processing-Profile
  - Subnet: subnet-0d4d796be847de3b0
  - SG: sg-0de960cc4f5c7d392
"""
import boto3

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
S3_KEY = "deploy/neptune_edge_sync.py"

ec2 = boto3.client("ec2", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)

# Step 1: Upload edge sync script to S3
print("Uploading neptune_edge_sync.py to S3...")
s3.put_object(
    Bucket=BUCKET,
    Key=S3_KEY,
    Body=open("scripts/neptune_edge_sync.py", "rb").read(),
)
print(f"  Uploaded to s3://{BUCKET}/{S3_KEY}")

# Step 2: Launch EC2
userdata = """#!/bin/bash
set -e
exec > >(tee /var/log/neptune-edge-sync.log) 2>&1

BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="7f05e8d5-4492-4f19-8894-25367606db96"
REGION="us-east-1"

echo "=== Neptune Edge Sync EC2 Starting ==="
echo "Time: $(date)"

# Install dependencies
pip3 install boto3 || yum install -y python3-pip && pip3 install boto3

# Download and run edge sync script
aws s3 cp s3://$BUCKET/deploy/neptune_edge_sync.py /tmp/neptune_edge_sync.py

cd /tmp
export CASE_ID=$CASE_ID
python3 neptune_edge_sync.py --case-id $CASE_ID 2>&1 | tee /tmp/edge_sync_output.txt

# Upload log to S3
echo "Uploading log to S3..."
aws s3 cp /var/log/neptune-edge-sync.log s3://$BUCKET/logs/neptune-edge-sync/edge_sync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Edge Sync Complete ==="
echo "Time: $(date)"

# Self-terminate (may fail if role lacks ec2:TerminateInstances — that's OK)
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION || echo "Self-terminate failed (expected if role lacks permission)"
"""

print("Launching EC2 instance...")
resp = ec2.run_instances(
    ImageId="ami-0c1fe732b5494dc14",
    InstanceType="t3.small",
    MinCount=1,
    MaxCount=1,
    IamInstanceProfile={"Name": "DOJ-Processing-Profile"},
    SubnetId="subnet-0d4d796be847de3b0",
    SecurityGroupIds=["sg-0de960cc4f5c7d392"],
    UserData=userdata,
    TagSpecifications=[{
        "ResourceType": "instance",
        "Tags": [
            {"Key": "Name", "Value": "neptune-edge-sync"},
            {"Key": "auto-terminate", "Value": "true"},
            {"Key": "Purpose", "Value": "Neptune RELATED_TO edge creation"},
        ],
    }],
)

instance_id = resp["Instances"][0]["InstanceId"]
print(f"Launched: {instance_id}")
print(f"  Name: neptune-edge-sync")
print(f"  Type: t3.small")
print(f"  Profile: DOJ-Processing-Profile")
print(f"  Expected runtime: ~14 minutes")
print(f"\nMonitor: aws ec2 get-console-output --instance-id {instance_id} --region {REGION}")
