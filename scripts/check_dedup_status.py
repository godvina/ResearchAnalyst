"""Check Neptune dedup EC2 status."""
import boto3
import base64

ec2 = boto3.client('ec2', region_name='us-east-1')
INSTANCE_ID = 'i-02c7504fe4396d404'

# Check instance state
resp = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
inst = resp['Reservations'][0]['Instances'][0]
state = inst['State']['Name']
print(f"Instance {INSTANCE_ID}: {state}")

if state == 'terminated':
    print("EC2 self-terminated — dedup likely completed. Check S3 logs.")
    print("Log: s3://research-analyst-data-lake-974220725866/logs/neptune-dedup/")
elif state == 'running':
    # Get console output
    output = ec2.get_console_output(InstanceId=INSTANCE_ID, Latest=True)
    text = output.get('Output', '')
    if text:
        lines = text.strip().split('\n')
        # Find script output lines
        script_lines = [l for l in lines if 'cloud-init[1653]' in l]
        print(f"\nLast 15 script output lines:")
        for line in script_lines[-15:]:
            # Extract just the message part
            if ']:' in line:
                msg = line.split(']:')[1].strip()
                print(f"  {msg}")
    else:
        print("No console output available yet")

# Also check all running instances
print("\n--- All Running EC2 Instances ---")
all_resp = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
for res in all_resp['Reservations']:
    for i in res['Instances']:
        name = ''
        for tag in i.get('Tags', []):
            if tag['Key'] == 'Name':
                name = tag['Value']
        launch = i['LaunchTime'].strftime('%Y-%m-%d')
        itype = i['InstanceType']
        print(f"  {i['InstanceId']}  {name:35s}  {itype:12s}  launched {launch}")
