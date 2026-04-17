#!/bin/bash
set -e
exec > >(tee /var/log/entity-backfill.log) 2>&1

echo "=== Starting Entity Backfill ==="
date
whoami

# Amazon Linux 2023 has python3 but no pip by default
echo "Installing pip3..."
yum install -y python3-pip 2>/dev/null || dnf install -y python3-pip 2>/dev/null || true

echo "Installing boto3..."
pip3 install boto3

echo "Downloading backfill script..."
aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_entity_backfill.py /tmp/backfill.py

echo "Running backfill..."
cd /tmp
python3 backfill.py

echo "Uploading log..."
aws s3 cp /var/log/entity-backfill.log s3://research-analyst-data-lake-974220725866/logs/ec2-entity-backfill-$(date +%Y%m%d-%H%M%S).txt

echo "=== Done ==="
date

# Self-terminate
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
