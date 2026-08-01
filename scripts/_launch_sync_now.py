"""Launch EC2 for Neptune-Aurora sync. Self-terminates. Uploads log to S3."""
import boto3

REGION = "us-east-1"
SUBNET_ID = "subnet-0d4d796be847de3b0"
SG_ID = "sg-0de960cc4f5c7d392"
INSTANCE_PROFILE = "DOJ-Processing-Profile"
S3_BUCKET = "research-analyst-data-lake-974220725866"

userdata = (
    "#!/bin/bash\n"
    "set -e\n"
    "exec > /tmp/sync.log 2>&1\n"
    "echo '=== EC2 Neptune-Aurora Sync Starting ==='\n"
    "date\n"
    "pip3 install boto3 psycopg2-binary\n"
    "aws s3 cp s3://research-analyst-data-lake-974220725866/scripts/neptune_to_aurora_sync_ec2.py /tmp/sync.py --region us-east-1\n"
    "python3 /tmp/sync.py\n"
    "echo '=== Done ==='\n"
    "date\n"
)

ec2 = boto3.client("ec2", region_name=REGION)
resp = ec2.run_instances(
    ImageId="ami-0c02fb55956c7d316",
    InstanceType="t3.medium",
    MinCount=1, MaxCount=1,
    SubnetId=SUBNET_ID,
    SecurityGroupIds=[SG_ID],
    IamInstanceProfile={"Name": INSTANCE_PROFILE},
    UserData=userdata,
    TagSpecifications=[{
        "ResourceType": "instance",
        "Tags": [
            {"Key": "Name", "Value": "neptune-aurora-sync"},
            {"Key": "Purpose", "Value": "Neptune to Aurora entity/relationship sync"},
            {"Key": "AutoTerminate", "Value": "true"},
        ]
    }],
    InstanceInitiatedShutdownBehavior="terminate",
)
iid = resp["Instances"][0]["InstanceId"]
print(f"EC2 launched: {iid}")
print(f"Subnet: {SUBNET_ID}")
print(f"SG: {SG_ID}")
print(f"Profile: {INSTANCE_PROFILE}")
print(f"Will self-terminate when done (~10 min)")
print(f"Log: s3://{S3_BUCKET}/logs/neptune-aurora-sync/")
