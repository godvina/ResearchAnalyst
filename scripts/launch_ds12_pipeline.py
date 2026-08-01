#!/usr/bin/env python3
"""
Launch DS12 Ingestion Pipeline on EC2.

Uploads the pipeline scripts to S3, then launches a t3.small EC2 instance
with userdata that downloads and runs the full pipeline unattended.

Prerequisites:
    - Lambda deployed with insert_documents_batch action
    - IAM: DOJ-Processing-Profile has lambda:InvokeFunction, s3:*, bedrock:*
    - Neptune SG: sg-0de960cc4f5c7d392 allows port 8182
    - Run from a machine with ec2:RunInstances, s3:PutObject, iam:PassRole

Usage:
    python scripts/launch_ds12_pipeline.py
"""
import boto3
import json
import os
import sys
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────
REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
AMI_ID = "ami-0c1fe732b5494dc14"  # Amazon Linux 2023
INSTANCE_TYPE = "t3.small"
IAM_PROFILE = "DOJ-Processing-Profile"
SUBNET_ID = "subnet-0d4d796be847de3b0"
SECURITY_GROUP_IDS = ["sg-0de960cc4f5c7d392"]

# Scripts to upload to S3 for the EC2 to download
SCRIPTS_TO_UPLOAD = [
    "scripts/ingest_dataset.py",
    "scripts/entity_extraction_pipeline.py",
    "scripts/neptune_bulk_sync.py",
    "scripts/neptune_edge_sync.py",
]

S3_DEPLOY_PREFIX = "deploy/ds12-pipeline"

# ── Userdata ───────────────────────────────────────────────────────
# Follows the mandatory EC2 userdata template from kiro-builder-playbook.md:
# - pip3 install boto3 (NOT pre-installed on Amazon Linux 2023)
# - Download scripts from S3
# - Run pipeline
# - Upload logs to S3
# - Self-terminate

USERDATA = f"""#!/bin/bash
set -e
BUCKET="{BUCKET}"
REGION="{REGION}"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

echo "=== DS12 Ingestion Pipeline Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Time: $(date)"

# MANDATORY: Install boto3 (NOT pre-installed on Amazon Linux 2023)
pip3 install boto3 || yum install -y python3-pip && pip3 install boto3

# Download pipeline scripts
aws s3 cp s3://$BUCKET/{S3_DEPLOY_PREFIX}/ingest_dataset.py /tmp/ingest_dataset.py
aws s3 cp s3://$BUCKET/{S3_DEPLOY_PREFIX}/entity_extraction_pipeline.py /tmp/entity_extraction_pipeline.py
aws s3 cp s3://$BUCKET/{S3_DEPLOY_PREFIX}/neptune_bulk_sync.py /tmp/neptune_bulk_sync.py
aws s3 cp s3://$BUCKET/{S3_DEPLOY_PREFIX}/neptune_edge_sync.py /tmp/neptune_edge_sync.py

# Run the full pipeline
cd /tmp
python3 ingest_dataset.py 2>&1 | tee /tmp/ds12_pipeline_log.txt

# Upload log to S3
aws s3 cp /tmp/ds12_pipeline_log.txt s3://$BUCKET/logs/ds12-ingest/ec2_log_$(date +%Y%m%d_%H%M%S).txt

# Self-terminate
echo "=== DS12 Pipeline Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
"""


def upload_scripts():
    """Upload pipeline scripts to S3."""
    s3 = boto3.client("s3", region_name=REGION)
    print("Uploading pipeline scripts to S3...")

    for script_path in SCRIPTS_TO_UPLOAD:
        if not os.path.exists(script_path):
            print(f"  ERROR: {script_path} not found!")
            sys.exit(1)

        filename = os.path.basename(script_path)
        s3_key = f"{S3_DEPLOY_PREFIX}/{filename}"

        with open(script_path, "rb") as f:
            s3.put_object(Bucket=BUCKET, Key=s3_key, Body=f.read())
        print(f"  Uploaded: s3://{BUCKET}/{s3_key}")

    print("All scripts uploaded.")


def launch_ec2():
    """Launch EC2 instance with the pipeline userdata."""
    ec2 = boto3.client("ec2", region_name=REGION)

    ts = datetime.now().strftime("%Y%m%d-%H%M")
    instance_name = f"ds12-ingest-{ts}"

    print(f"\nLaunching EC2 instance...")
    print(f"  AMI: {AMI_ID}")
    print(f"  Type: {INSTANCE_TYPE}")
    print(f"  IAM: {IAM_PROFILE}")
    print(f"  Subnet: {SUBNET_ID}")
    print(f"  SG: {SECURITY_GROUP_IDS}")

    resp = ec2.run_instances(
        ImageId=AMI_ID,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        IamInstanceProfile={"Name": IAM_PROFILE},
        SubnetId=SUBNET_ID,
        SecurityGroupIds=SECURITY_GROUP_IDS,
        UserData=USERDATA,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": instance_name},
                {"Key": "auto-terminate", "Value": "true"},
                {"Key": "pipeline", "Value": "ds12-ingest"},
            ],
        }],
    )

    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"\nLaunched: {instance_id}")
    print(f"  Name: {instance_name}")
    print(f"\nMonitor:")
    print(f"  Console output: aws ec2 get-console-output --instance-id {instance_id} --region {REGION}")
    print(f"  Logs: aws s3 ls s3://{BUCKET}/logs/ds12-ingest/")
    print(f"\n5-Minute Rule:")
    print(f"  T+90s:  Check console output")
    print(f"  T+3min: If no output, investigate")
    print(f"  T+5min: Verify documents appearing in Aurora")

    return instance_id


def main():
    print("=" * 60)
    print("DS12 Ingestion Pipeline — EC2 Launcher")
    print("=" * 60)

    # Pre-flight checks
    print("\nPre-flight checks:")
    print(f"  IAM Profile: {IAM_PROFILE} (needs lambda:InvokeFunction, s3:*, bedrock:*, ec2:TerminateInstances)")
    print(f"  Neptune SG: {SECURITY_GROUP_IDS[0]} (port 8182 allowed)")
    print(f"  boto3: installed via userdata (pip3 install boto3)")

    for script in SCRIPTS_TO_UPLOAD:
        exists = os.path.exists(script)
        status = "OK" if exists else "MISSING"
        print(f"  Script {script}: {status}")
        if not exists:
            print(f"  ERROR: {script} not found. Cannot proceed.")
            sys.exit(1)

    # Upload scripts to S3
    upload_scripts()

    # Launch EC2
    instance_id = launch_ec2()

    print(f"\nDone. Instance {instance_id} is running the DS12 pipeline.")


if __name__ == "__main__":
    main()
