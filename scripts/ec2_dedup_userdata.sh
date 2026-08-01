#!/bin/bash
# EC2 Userdata — Neptune Dedup (run overnight)
# Instance type: t3.small ($0.02/hr)
# Expected runtime: 4-8 hours for 1.3M nodes
set -e

BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="7f05e8d5-4492-4f19-8894-25367606db96"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION="us-east-1"

echo "=== Neptune Dedup EC2 Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Time: $(date)"

# Download the dedup script
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_dedup.py /tmp/ec2_neptune_dedup.py

# Run the dedup
cd /tmp
python3 ec2_neptune_dedup.py 2>&1 | tee /tmp/dedup_log.txt

# Upload log to S3
aws s3 cp /tmp/dedup_log.txt s3://$BUCKET/logs/neptune-dedup/dedup_$(date +%Y%m%d_%H%M%S).txt

echo "=== Dedup Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
