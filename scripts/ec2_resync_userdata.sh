#!/bin/bash
# EC2 Userdata — Neptune Re-Sync (run after dedup completes)
# Instance type: t3.small ($0.02/hr)
# Expected runtime: 1-3 hours depending on entity count after filtering
set -e

BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="7f05e8d5-4492-4f19-8894-25367606db96"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION="us-east-1"

echo "=== Neptune Re-Sync EC2 Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Case: $CASE_ID"
echo "Time: $(date)"

# Install boto3 (needed for Lambda invoke)
pip3 install boto3 --quiet 2>/dev/null || true

# Download the re-sync script
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py

# Run the re-sync
cd /tmp
export CASE_ID=$CASE_ID
python3 ec2_neptune_resync.py --case-id $CASE_ID 2>&1 | tee /tmp/resync_log.txt

# Upload log to S3
aws s3 cp /tmp/resync_log.txt s3://$BUCKET/logs/neptune-resync/resync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Re-Sync Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
