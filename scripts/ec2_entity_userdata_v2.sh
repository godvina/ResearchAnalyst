#!/bin/bash -xe
exec > >(tee /var/log/entity-backfill.log) 2>&1

echo "=== Starting Entity Backfill ==="
date
whoami
which python3
python3 --version

pip3 install boto3 2>&1 || yum install -y python3-pip && pip3 install boto3

aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_entity_backfill.py /tmp/backfill.py

cd /tmp
python3 backfill.py 2>&1

aws s3 cp /var/log/entity-backfill.log s3://research-analyst-data-lake-974220725866/deploy/ec2-entity-backfill-log.txt

echo "=== Done ==="
date

TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
