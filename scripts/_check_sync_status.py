"""Check Neptune-Aurora sync EC2 status."""
import boto3
import time

print("Waiting 180s for boot+install+first query...")
time.sleep(180)

s3 = boto3.client("s3", region_name="us-east-1")
resp = s3.list_objects_v2(Bucket="research-analyst-data-lake-974220725866", Prefix="logs/neptune-aurora-sync/")
files = [(o["Key"], o["Size"]) for o in resp.get("Contents", [])]

ec2 = boto3.client("ec2", region_name="us-east-1")
r = ec2.describe_instances(InstanceIds=["i-030aacec79363a2a8"])
state = r["Reservations"][0]["Instances"][0]["State"]["Name"]

print(f"EC2: {state}")
print(f"Logs: {files if files else 'None yet'}")

if files:
    # Download and print the log
    key = files[-1][0]
    obj = s3.get_object(Bucket="research-analyst-data-lake-974220725866", Key=key)
    content = obj["Body"].read().decode()
    print(f"\n--- LOG CONTENT ---\n{content[-2000:]}")
