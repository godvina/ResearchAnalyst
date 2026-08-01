"""Launch Neptune Bulk Sync EC2."""
import boto3

ec2 = boto3.client("ec2", region_name="us-east-1")

userdata = """#!/bin/bash
set -e
BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="7f05e8d5-4492-4f19-8894-25367606db96"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION="us-east-1"

echo "=== Neptune Bulk Sync EC2 Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Time: $(date)"

pip3 install boto3 || yum install -y python3-pip && pip3 install boto3

aws s3 cp s3://$BUCKET/deploy/neptune_bulk_sync.py /tmp/neptune_bulk_sync.py

cd /tmp
python3 neptune_bulk_sync.py --case-id $CASE_ID --skip-clear 2>&1 | tee /tmp/bulk_sync_log.txt

aws s3 cp /tmp/bulk_sync_log.txt s3://$BUCKET/logs/neptune-bulk-sync/sync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Bulk Sync Complete ==="
"""

resp = ec2.run_instances(
    ImageId="ami-0c1fe732b5494dc14",
    InstanceType="t3.small",
    MinCount=1, MaxCount=1,
    IamInstanceProfile={"Name": "DOJ-Processing-Profile"},
    SubnetId="subnet-0d4d796be847de3b0",
    SecurityGroupIds=["sg-0de960cc4f5c7d392"],
    UserData=userdata,
    TagSpecifications=[{
        "ResourceType": "instance",
        "Tags": [
            {"Key": "Name", "Value": "neptune-bulk-sync"},
            {"Key": "auto-terminate", "Value": "true"},
        ],
    }],
)
iid = resp["Instances"][0]["InstanceId"]
print(f"Launched: {iid}")
print("Using --skip-clear to avoid deleting 943K old nodes (upserts will overwrite)")
print("Verify within 2 minutes per protocol!")
