#!/bin/bash -xe
exec > >(tee /var/log/entity-combined.log) 2>&1
echo "=== Epstein Combined Entity Backfill ==="
date
yum install -y python3-pip 2>&1 || true
pip3 install boto3 2>&1
aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_entity_combined.py /tmp/backfill.py
cd /tmp
python3 backfill.py 2>&1
aws s3 cp /var/log/entity-combined.log s3://research-analyst-data-lake-974220725866/deploy/ec2-entity-combined-log.txt 2>&1 || true
echo "=== Done ==="
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
