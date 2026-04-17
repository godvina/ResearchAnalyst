#!/bin/bash
set -e
exec > /var/log/nikity-loader.log 2>&1

echo "=== Nikity Loader Starting ==="
date

# Install dependencies
yum install -y python3.12 python3.12-pip
pip3.12 install datasets boto3

# Download loader script from S3
aws s3 cp s3://research-analyst-data-lake-974220725866/deploy/ec2_nikity_loader.py /home/ec2-user/loader.py

# Run it — DS9-12 only, text insert
cd /home/ec2-user
python3.12 loader.py --datasets 9,10,11,12 2>&1 | tee /home/ec2-user/loader-output.log

# Upload log to S3
aws s3 cp /home/ec2-user/loader-output.log s3://research-analyst-data-lake-974220725866/deploy/ec2-nikity-loader-output.log
aws s3 cp /var/log/nikity-loader.log s3://research-analyst-data-lake-974220725866/deploy/ec2-nikity-loader-system.log

echo "=== Nikity Loader Complete ==="
date

# Self-terminate
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region us-east-1
