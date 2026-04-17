#!/bin/bash
set -e
exec > >(tee /var/log/neptune-sync.log) 2>&1

echo "=== Starting Aurora → Neptune Sync ==="
date

yum install -y python3-pip 2>/dev/null || dnf install -y python3-pip 2>/dev/null || true
pip3 install boto3

aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_aurora_neptune_sync.py /tmp/sync.py

cd /tmp
python3 sync.py

aws s3 cp /var/log/neptune-sync.log s3://research-analyst-data-lake-974220725866/logs/neptune-sync-$(date +%Y%m%d-%H%M%S).txt

echo "=== Done ==="
date

TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
