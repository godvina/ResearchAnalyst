import boto3
ec2 = boto3.client('ec2', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

# Upload sync script
s3.put_object(
    Bucket='research-analyst-data-lake-974220725866',
    Key='deploy/ec2_aurora_neptune_sync.py',
    Body=open('scripts/ec2_aurora_neptune_sync.py', 'rb').read(),
)
print("Uploaded sync script to S3")

userdata = """#!/bin/bash
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
    ImageId='ami-0c02fb55956c7d316',
    InstanceType='t3.small',
    IamInstanceProfile={'Name': 'NikityLoaderEC2Profile'},
    UserData=userdata,
    TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': 'neptune-sync-manual'}]}],
    MinCount=1, MaxCount=1,
)
print(f"Launched: {r['Instances'][0]['InstanceId']}")
