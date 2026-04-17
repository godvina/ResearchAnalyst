"""Create AOSS VPC endpoint in supported AZs."""
import boto3
import json
import time

REGION = "us-east-1"
ec2 = boto3.client("ec2", region_name=REGION)

# Get default VPC
vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
vpc_id = vpcs[0]["VpcId"]
print(f"VPC: {vpc_id}")

# Get subnets — only use AZs a, b, c (AOSS doesn't support all AZs)
subnets = ec2.describe_subnets(
    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
)["Subnets"]

supported_azs = ["us-east-1a", "us-east-1b", "us-east-1c"]
selected_subnets = [s["SubnetId"] for s in subnets if s["AvailabilityZone"] in supported_azs]
print(f"Selected subnets ({supported_azs}): {selected_subnets}")

# Create a security group for the VPC endpoint
sg = ec2.create_security_group(
    GroupName="aoss-vpce-sg",
    Description="Security group for AOSS VPC endpoint",
    VpcId=vpc_id,
)
sg_id = sg["GroupId"]
print(f"Created SG: {sg_id}")

# Allow HTTPS from VPC CIDR
vpc_cidr = vpcs[0]["CidrBlock"]
ec2.authorize_security_group_ingress(
    GroupId=sg_id,
    IpPermissions=[{
        "IpProtocol": "tcp",
        "FromPort": 443,
        "ToPort": 443,
        "IpRanges": [{"CidrIp": vpc_cidr, "Description": "HTTPS from VPC"}],
    }],
)
print(f"Added inbound rule: HTTPS from {vpc_cidr}")

# Create the VPC endpoint
print("Creating AOSS VPC endpoint...")
vpce = ec2.create_vpc_endpoint(
    VpcId=vpc_id,
    ServiceName=f"com.amazonaws.{REGION}.aoss",
    VpcEndpointType="Interface",
    SubnetIds=selected_subnets,
    SecurityGroupIds=[sg_id],
    PrivateDnsEnabled=True,
)
vpce_id = vpce["VpcEndpoint"]["VpcEndpointId"]
print(f"VPC Endpoint: {vpce_id}")
print(f"State: {vpce['VpcEndpoint']['State']}")

# Update the network policy to use VPC endpoint
print("\nUpdating AOSS network policy to use VPC endpoint...")
aoss = boto3.client("opensearchserverless", region_name=REGION)

# Delete old public network policy
try:
    aoss.delete_security_policy(type="network", name="research-analyst-search-net")
    print("Deleted old network policy")
except Exception as e:
    print(f"Delete old policy: {e}")

# Create new VPC-based network policy
aoss.create_security_policy(
    type="network",
    name="research-analyst-search-net",
    policy=json.dumps([{
        "Rules": [
            {"ResourceType": "collection", "Resource": ["collection/research-analyst-search"]},
            {"ResourceType": "dashboard", "Resource": ["collection/research-analyst-search"]},
        ],
        "AllowFromPublic": False,
        "SourceVPCEs": [vpce_id],
    }]),
)
print(f"Created network policy with VPC endpoint {vpce_id}")

# Wait for endpoint to become available
print("\nWaiting for VPC endpoint to become available...")
for i in range(30):
    r = ec2.describe_vpc_endpoints(VpcEndpointIds=[vpce_id])
    state = r["VpcEndpoints"][0]["State"]
    if state == "available":
        print(f"VPC endpoint is available!")
        break
    print(f"  [{i+1}] State: {state}")
    time.sleep(10)

print("\nDone! Lambda functions can now reach AOSS through the VPC endpoint.")
