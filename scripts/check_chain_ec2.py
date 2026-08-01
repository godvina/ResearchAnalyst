"""Check the post-extraction chain EC2 status."""
import boto3
ec2 = boto3.client("ec2", region_name="us-east-1")
INSTANCE_ID = "i-09f7a6a43e4d95e7d"

inst = ec2.describe_instances(InstanceIds=[INSTANCE_ID])["Reservations"][0]["Instances"][0]
print(f"Instance: {INSTANCE_ID} — {inst['State']['Name']}")

output = ec2.get_console_output(InstanceId=INSTANCE_ID, Latest=True)
text = output.get("Output", "")
if text:
    lines = text.strip().split("\n")
    script_lines = [l for l in lines if "cloud-init" in l and ("===" in l or "STEP" in l or "Status" in l or "chain" in l.lower() or "Post-Extraction" in l)]
    if script_lines:
        print("Script output:")
        for l in script_lines[-10:]:
            if "]:" in l:
                print(f"  {l.split(']:')[1].strip()}")
    else:
        # Show last 10 lines
        print("Last 10 console lines:")
        for l in lines[-10:]:
            print(f"  {l.strip()[:100]}")
else:
    print("No console output yet")
