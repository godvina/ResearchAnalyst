"""Check bulk sync EC2 — T+2min verification."""
import boto3
ec2 = boto3.client("ec2", region_name="us-east-1")
INSTANCE_ID = "i-0685d47ead1410fc5"
inst = ec2.describe_instances(InstanceIds=[INSTANCE_ID])["Reservations"][0]["Instances"][0]
print(f"Instance: {INSTANCE_ID} — {inst['State']['Name']}")
output = ec2.get_console_output(InstanceId=INSTANCE_ID, Latest=True)
text = output.get("Output", "")
if text:
    lines = text.strip().split("\n")
    for l in lines[-20:]:
        if "cloud-init" in l and "]:" in l:
            msg = l.split("]:")[1].strip()[:130]
            print(f"  {msg}")
else:
    print("  No console output yet — check again in 30s")
