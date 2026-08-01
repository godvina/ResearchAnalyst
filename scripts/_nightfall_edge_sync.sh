#!/bin/bash
# EC2 Userdata — Neptune Edge Sync for Operation Nightfall
# Loads 4,549 relationship edges between existing vertices
set -e
exec > >(tee /var/log/nightfall-edge-sync.log) 2>&1

BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="0b24a307-a674-41b6-8d22-581c4a4aa566"
REGION="us-east-1"

echo "=== Neptune Edge Sync: Operation Nightfall ==="
echo "Case: $CASE_ID"
echo "Time: $(date)"

# Install deps
yum install -y python3-pip 2>&1 || true
pip3 install boto3 2>&1 || true

# Download the edge sync script
aws s3 cp s3://$BUCKET/deploy/neptune_edge_sync.py /tmp/neptune_edge_sync.py

# Run the edge sync
cd /tmp
export CASE_ID=$CASE_ID
python3 neptune_edge_sync.py --case-id $CASE_ID 2>&1 | tee /tmp/edge_sync_log.txt

# Upload log to S3
aws s3 cp /tmp/edge_sync_log.txt s3://$BUCKET/logs/neptune-resync/nightfall_edge_sync_$(date +%Y%m%d_%H%M%S).txt

echo "=== Edge Sync Complete ==="
echo "NOTE: Manually terminate this instance."
