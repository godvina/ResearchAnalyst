"""Check status of all running processes."""
import boto3
from datetime import datetime, timezone

ec2 = boto3.client("ec2", region_name="us-east-1")

# All running instances
resp = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["running"]}])
instances = []
for res in resp["Reservations"]:
    for i in res["Instances"]:
        name = ""
        for tag in i.get("Tags", []):
            if tag["Key"] == "Name":
                name = tag["Value"]
        hours = (datetime.now(timezone.utc) - i["LaunchTime"]).total_seconds() / 3600
        instances.append((i["InstanceId"], name, i["InstanceType"], hours))

print(f"Running EC2 instances: {len(instances)}")
for iid, name, itype, hours in sorted(instances, key=lambda x: -x[3]):
    cost = hours * (0.042 if "medium" in itype else 0.021)
    print(f"  {iid}  {name:35s}  {itype:10s}  {hours:6.1f}h  ~${cost:.2f}")

# Check Neptune re-sync EC2 specifically
resync_id = "i-044effa9328442de8"
print(f"\n--- Neptune Re-Sync EC2 ({resync_id}) ---")
try:
    inst = ec2.describe_instances(InstanceIds=[resync_id])["Reservations"][0]["Instances"][0]
    state = inst["State"]["Name"]
    print(f"State: {state}")
    
    if state == "running":
        output = ec2.get_console_output(InstanceId=resync_id, Latest=True)
        text = output.get("Output", "")
        if text:
            lines = text.strip().split("\n")
            script_lines = [l for l in lines if "cloud-init" in l and "]:" in l]
            for l in script_lines[-10:]:
                msg = l.split("]:")[1].strip()[:120]
                print(f"  {msg}")
        else:
            print("  No console output yet")
    elif state == "terminated":
        print("  Self-terminated — check S3 logs")
except Exception as e:
    print(f"  Error: {str(e)[:100]}")

# Total cost estimate
total_cost = sum(h * (0.042 if "medium" in t else 0.021) for _, _, t, h in instances)
print(f"\nTotal running cost: ~${total_cost:.2f}")
