"""Launch chain v4 EC2."""
import boto3
import base64

ec2 = boto3.client("ec2", region_name="us-east-1")

with open("scripts/ec2_chain_userdata.sh") as f:
    userdata = f.read()

resp = ec2.run_instances(
    ImageId="ami-0c1fe732b5494dc14",
    InstanceType="t3.small",
    MinCount=1, MaxCount=1,
    IamInstanceProfile={"Name": "DOJ-Processing-Profile"},
    SubnetId="subnet-0d4d796be847de3b0",
    SecurityGroupIds=["sg-0de960cc4f5c7d392"],
    UserData=userdata,
    TagSpecifications=[{
        "ResourceType": "instance",
        "Tags": [
            {"Key": "Name", "Value": "chain-v4"},
            {"Key": "auto-terminate", "Value": "true"},
        ],
    }],
)
iid = resp["Instances"][0]["InstanceId"]
print(f"Launched: {iid}")
