"""Terminate idle EC2 instances. Protects the active re-sync instance."""
import boto3

ec2 = boto3.client("ec2", region_name="us-east-1")

# PROTECT these — actively doing work
PROTECT = {
    "i-044effa9328442de8",  # neptune-resync-v2 (ACTIVE — syncing entities)
}

resp = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["running"]}])
to_terminate = []
protected = []

for res in resp["Reservations"]:
    for i in res["Instances"]:
        iid = i["InstanceId"]
        name = ""
        for tag in i.get("Tags", []):
            if tag["Key"] == "Name":
                name = tag["Value"]
        
        if iid in PROTECT:
            protected.append((iid, name))
            continue
        
        to_terminate.append((iid, name))

print(f"PROTECTED (will NOT terminate):")
for iid, name in protected:
    print(f"  {iid}  {name}")

print(f"\nWILL TERMINATE ({len(to_terminate)} instances):")
for iid, name in to_terminate:
    print(f"  {iid}  {name}")

print(f"\nTerminating {len(to_terminate)} instances...")
if to_terminate:
    ids = [iid for iid, _ in to_terminate]
    ec2.terminate_instances(InstanceIds=ids)
    print("Done.")
