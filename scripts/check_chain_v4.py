"""Check chain v4 EC2."""
import boto3
ec2 = boto3.client("ec2", region_name="us-east-1")
INSTANCE_ID = "i-0a7e8e1d0da01c1f9"
inst = ec2.describe_instances(InstanceIds=[INSTANCE_ID])["Reservations"][0]["Instances"][0]
print(f"Instance: {INSTANCE_ID} — {inst['State']['Name']}")
output = ec2.get_console_output(InstanceId=INSTANCE_ID, Latest=True)
text = output.get("Output", "")
if text:
    lines = text.strip().split("\n")
    for l in lines[-25:]:
        if "cloud-init" in l and "]:" in l:
            msg = l.split("]:")[1].strip()[:120]
            print(f"  {msg}")
else:
    print("No console output yet")
