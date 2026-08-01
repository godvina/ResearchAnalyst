#!/bin/bash
set -e
exec > >(tee /var/log/batch-inference.log) 2>&1

echo "=== Starting Bedrock Batch Entity Extraction ==="
date
whoami

echo "Installing pip3 and boto3..."
yum install -y python3-pip 2>/dev/null || dnf install -y python3-pip 2>/dev/null || true
pip3 install boto3

echo "Downloading script..."
aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_batch_generate_submit.py /tmp/batch_job.py

echo "Running batch generation + submission..."
cd /tmp
python3 batch_job.py

echo "Uploading log..."
aws s3 cp /var/log/batch-inference.log s3://research-analyst-data-lake-974220725866/logs/ec2-batch-inference-$(date +%Y%m%d-%H%M%S).txt

echo "=== Done ==="
date

# Self-terminate
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
