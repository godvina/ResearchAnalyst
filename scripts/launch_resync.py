"""Launch Neptune re-sync EC2."""
import boto3

ec2 = boto3.client("ec2", region_name="us-east-1")

userdata = """#!/bin/bash
set -e
BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="7f05e8d5-4492-4f19-8894-25367606db96"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION="us-east-1"

echo "=== Neptune Re-Sync EC2 Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Case: $CASE_ID"
echo "Time: $(date)"

pip3 install boto3 || yum install -y python3-pip && pip3 install boto3

aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py

cd /tmp
export CASE_ID=$CASE_ID
python3 ec2_neptune_resync.py --case-id $CASE_ID 2>&1 | tee /tmp/resync_log.txt

aws s3 cp /tmp/resync_log.txt s3://$BUCKET/logs/neptune-resync/resync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Re-Sync Complete ==="
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
            {"Key": "Name", "Value": "neptune-resync-v2"},
            {"Key": "auto-terminate", "Value": "true"},
        ],
    }],
)
iid = resp["Instances"][0]["InstanceId"]
print(f"Launched Neptune re-sync: {iid}")
