#!/bin/bash
exec > /var/log/backfill.log 2>&1
echo "Starting $(date)"
pip3 install boto3 -q 2>/dev/null || yum install -y python3-pip -q && pip3 install boto3 -q
aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_entity_backfill.py /tmp/b.py
cd /tmp && python3 b.py
aws s3 cp /var/log/backfill.log s3://research-analyst-data-lake-974220725866/logs/backfill-$(date +%s).txt
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $ID --region us-east-1
