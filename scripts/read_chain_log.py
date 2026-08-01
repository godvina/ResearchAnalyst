"""Read the latest chain log to check entity load results."""
import boto3
s3 = boto3.client("s3", region_name="us-east-1")
key = "logs/post-extraction-chain/chain_20260421_111620.txt"
obj = s3.get_object(Bucket="research-analyst-data-lake-974220725866", Key=key)
text = obj["Body"].read().decode("utf-8")
lines = text.strip().split("\n")
# Show STEP lines and summary lines
for l in lines:
    if any(k in l for k in ["STEP", "COMPLETE", "Total", "Docs:", "entities", "Error", "Verify", "quality", "occurrence"]):
        print(l[:150])
