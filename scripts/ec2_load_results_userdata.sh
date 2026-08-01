#!/bin/bash
set -e
exec > >(tee /var/log/load-batch-results.log) 2>&1

echo "=== Loading Bedrock Batch Results ==="
date

yum install -y python3-pip 2>/dev/null || dnf install -y python3-pip 2>/dev/null || true
pip3 install boto3

aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_load_batch_results.py /tmp/load_results.py

cd /tmp
python3 load_results.py

echo "Uploading log..."
aws s3 cp /var/log/load-batch-results.log s3://research-analyst-data-lake-974220725866/logs/ec2-load-batch-results-$(date +%Y%m%d-%H%M%S).txt

echo "=== Done ==="
date

TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
