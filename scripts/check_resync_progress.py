"""Check Neptune re-sync EC2 progress."""
import boto3
from datetime import datetime, timezone

ec2 = boto3.client("ec2", region_name="us-east-1")
INSTANCE_ID = "i-044effa9328442de8"

inst = ec2.describe_instances(InstanceIds=[INSTANCE_ID])["Reservations"][0]["Instances"][0]
state = inst["State"]["Name"]
launch = inst["LaunchTime"]
elapsed_h = (datetime.now(timezone.utc) - launch).total_seconds() / 3600
print(f"Instance: {INSTANCE_ID} — {state}")
print(f"Running for: {elapsed_h:.1f} hours")

if state == "terminated":
    print("COMPLETED — check S3 logs at s3://research-analyst-data-lake-974220725866/logs/neptune-resync/")
elif state == "running":
    output = ec2.get_console_output(InstanceId=INSTANCE_ID, Latest=True)
    text = output.get("Output", "")
    if text:
        lines = text.strip().split("\n")
        script_lines = [l for l in lines if "cloud-init" in l and "]:" in l]
        print(f"\nLatest output ({len(script_lines)} script lines):")
        for l in script_lines[-15:]:
            msg = l.split("]:")[1].strip()[:130]
            print(f"  {msg}")
    else:
        print("No console output available")
