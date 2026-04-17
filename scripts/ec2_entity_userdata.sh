#!/bin/bash
set -e
exec > /var/log/entity-backfill.log 2>&1

echo "=== Entity Backfill Starting ==="
date

# Python 3.11 is pre-installed on Amazon Linux 2023
python3 --version
pip3 install boto3

# Download the backfill script from S3
aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_entity_backfill.py /home/ec2-user/backfill.py

# Run it
cd /home/ec2-user
python3 backfill.py 2>&1 | tee /home/ec2-user/backfill-output.log

# Upload logs
aws s3 cp /home/ec2-user/backfill-output.log s3://research-analyst-data-lake-974220725866/deploy/ec2-entity-backfill-output.log
aws s3 cp /var/log/entity-backfill.log s3://research-analyst-data-lake-974220725866/deploy/ec2-entity-backfill-system.log

echo "=== Entity Backfill Complete ==="
date

# Self-terminate
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
