"""Check AOSS VPC endpoint details."""
import boto3

ec2 = boto3.client("ec2", region_name="us-east-1")
vpces = ec2.describe_vpc_endpoints(
    Filters=[{"Name": "service-name", "Values": ["com.amazonaws.us-east-1.aoss"]}]
)["VpcEndpoints"]

for v in vpces:
    print(f"VPCE: {v['VpcEndpointId']}")
    print(f"  State: {v['State']}")
    print(f"  Private DNS: {v.get('PrivateDnsEnabled')}")
    print(f"  Subnets: {v['SubnetIds']}")
    print(f"  DNS entries:")
    for dns in v.get("DnsEntries", []):
        print(f"    {dns['DnsName']} -> {dns.get('HostedZoneId', 'N/A')}")
    print(f"  Network interfaces: {v.get('NetworkInterfaceIds', [])}")

# Check what subnets the Lambda is in vs the VPC endpoint
lam = boto3.client("lambda", region_name="us-east-1")
fn = lam.get_function_configuration(
    FunctionName="ResearchAnalystStack-IngestionEmbedLambdaE92F3BC0-wYlIRbksk1Jz"
)
lambda_subnets = fn["VpcConfig"]["SubnetIds"]
print(f"\nLambda subnets: {lambda_subnets}")

# Show AZ for each
for sid in lambda_subnets:
    s = ec2.describe_subnets(SubnetIds=[sid])["Subnets"][0]
    in_vpce = sid in vpces[0]["SubnetIds"] if vpces else False
    print(f"  {sid} -> {s['AvailabilityZone']} {'(in VPCE)' if in_vpce else '(NOT in VPCE)'}")
