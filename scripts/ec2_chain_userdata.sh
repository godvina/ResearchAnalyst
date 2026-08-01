#!/bin/bash
set -e
BUCKET="research-analyst-data-lake-974220725866"
CASE_ID="7f05e8d5-4492-4f19-8894-25367606db96"
JOB_ARN="arn:aws:bedrock:us-east-1:974220725866:model-invocation-job/bxjsijen80d5"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION="us-east-1"

echo "=== Post-Extraction Chain EC2 Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Case: $CASE_ID"
echo "Job: $JOB_ARN"
echo "Time: $(date)"

pip3 install boto3 --quiet 2>/dev/null || pip3 install boto3 || yum install -y python3-pip && pip3 install boto3

aws s3 cp s3://$BUCKET/deploy/ec2_post_extraction_chain.py /tmp/ec2_post_extraction_chain.py
aws s3 cp s3://$BUCKET/deploy/ec2_neptune_resync.py /tmp/ec2_neptune_resync.py

cd /tmp
export CASE_ID=$CASE_ID
export JOB_ARN=$JOB_ARN
python3 ec2_post_extraction_chain.py 2>&1 | tee /tmp/chain_log.txt

aws s3 cp /tmp/chain_log.txt s3://$BUCKET/logs/post-extraction-chain/chain_$(date +%Y%m%d_%H%M%S).txt

echo "=== Chain Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
