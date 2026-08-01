#!/bin/bash
# EC2 Userdata — Neptune Re-Sync for Operation Nightfall
# Instance type: t3.small
# Expected runtime: 5-15 minutes for ~6,700 entities
set -e
exec > >(tee /var/log/nightfall-resync.log) 2>&1

BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="0b24a307-a674-41b6-8d22-581c4a4aa566"
REGION="us-east-1"

echo "=== Neptune Re-Sync: Operation Nightfall ==="
echo "Case: $CASE_ID"
echo "Time: $(date)"

# Install deps FIRST
yum install -y python3-pip 2>&1 || true
pip3 install boto3 2>&1 || true

# Download the re-sync script
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py

# Run the re-sync
cd /tmp
export CASE_ID=$CASE_ID
python3 ec2_neptune_resync.py --case-id $CASE_ID 2>&1 | tee /tmp/resync_log.txt

# Upload log to S3
aws s3 cp /tmp/resync_log.txt s3://$BUCKET/logs/neptune-resync/nightfall_resync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Re-Sync Complete ==="
echo "NOTE: Manually terminate this instance when verified."
