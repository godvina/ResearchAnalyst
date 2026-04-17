"""Check VPC endpoint ENI details."""
import boto3

ec2 = boto3.client("ec2", region_name="us-east-1")
enis = ec2.describe_network_interfaces(
    NetworkInterfaceIds=["eni-05a0322466ee5d813", "eni-03bc4255a06404e93", "eni-095af4d814f35eb18"]
)
for eni in enis["NetworkInterfaces"]:
    nid = eni["NetworkInterfaceId"]
    ip = eni["PrivateIpAddress"]
    az = eni["AvailabilityZone"]
    sgs = [g["GroupId"] for g in eni["Groups"]]
    subnet = eni["SubnetId"]
    print(f"{nid}: IP={ip} AZ={az} Subnet={subnet} SGs={sgs}")
