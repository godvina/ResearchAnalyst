"""Launch EC2 instance to run Neptune-to-Aurora sync.

Uses CDK VPC subnet (has NAT gateway for internet + Neptune access).
IAM: DOJ-Processing-Profile has s3:*, ec2:TerminateInstances, secretsmanager:GetSecretValue.
Userdata includes pip3 install boto3 psycopg2-binary.
Script self-terminates and uploads log to S3.
"""
import boto3
import json

REGION = "us-east-1"
SUBNET_ID = "subnet-0d4d796be847de3b0"  # CDK VPC subnet with NAT
SG_ID = "sg-0de960cc4f5c7d392"  # CDK VPC SG (can reach Neptune + Aurora)
INSTANCE_PROFILE = "DOJ-Processing-Profile"
S3_BUCKET = "research-analyst-data-lake-974220725866"

# Read the sync script
with open("scripts/neptune_to_aurora_sync_ec2.py", "r") as f:
    script_content = f.read()

# Upload script to S3 first (more reliable than embedding in userdata)
s3 = boto3.client("s3", region_name=REGION)
s3.put_object(
    Bucket=S3_BUCKET,
    Key="scripts/neptune_to_aurora_sync_ec2.py",
    Body=script_content.encode()
)
print(f"Uploaded script to s3://{S3_BUCKET}/scripts/neptune_to_aurora_sync_ec2.py")

userdata = f"""#!/bin/bash
set -e
exec > /tmp/sync.log 2>&1
echo "=== EC2 Neptune-Aurora Sync Starting ==="
date

# Install dependencies
pip3 install boto3 psycopg2-binary

# Download script from S3
aws s3 cp s3://{S3_BUCKET}/scripts/neptune_to_aurora_sync_ec2.py /tmp/sync.py --region {REGION}

# Run it
python3 /tmp/sync.py

echo "=== Done ==="
date
"""

ec2 = boto3.client("ec2", region_name=REGION)

resp = ec2.run_instances(
    ImageId="ami-0c02fb55956c7d316",  # Amazon Linux 2023
    InstanceType="t3.medium",
    MinCount=1, MaxCount=1,
    SubnetId=SUBNET_ID,
    SecurityGroupIds=[SG_ID],
    IamInstanceProfile={"Name": INSTANCE_PROFILE},
    UserData=userdata,
    TagSpecifications=[{{
        "ResourceType": "instance",
        "Tags": [
            {{"Key": "Name", "Value": "neptune-aurora-sync"}},
            {{"Key": "Purpose", "Value": "Neptune to Aurora entity/relationship sync"}},
            {{"Key": "AutoTerminate", "Value": "true"}},
        ]
    }}],
    InstanceInitiatedShutdownBehavior="terminate",
)

instance_id = resp["Instances"][0]["InstanceId"]
print(f"\\nEC2 launched: {{instance_id}}")
print(f"  Subnet: {SUBNET_ID}")
print(f"  SG: {SG_ID}")
print(f"  Profile: {INSTANCE_PROFILE}")
print(f"\\nThe instance will:")
print(f"  1. Install boto3 + psycopg2")
print(f"  2. Read entities from Neptune (Entity_7f05e8d5-4492-4f19-8894-25367606db96)")
print(f"  3. Write to Aurora entities + relationships tables (case 7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e)")
print(f"  4. Upload log to s3://{S3_BUCKET}/logs/neptune-aurora-sync/")
print(f"  5. Self-terminate")
print(f"\\nEstimated time: ~10 minutes")
print(f"Check log: aws s3 ls s3://{S3_BUCKET}/logs/neptune-aurora-sync/")
"""
