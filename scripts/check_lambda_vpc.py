"""Check Lambda VPC config and security groups."""
import boto3

lam = boto3.client("lambda", region_name="us-east-1")
ec2 = boto3.client("ec2", region_name="us-east-1")

fn_name = "ResearchAnalystStack-IngestionEmbedLambdaE92F3BC0-wYlIRbksk1Jz"
config = lam.get_function_configuration(FunctionName=fn_name)
vpc_config = config.get("VpcConfig", {})

print(f"Function: {fn_name}")
print(f"Subnets: {vpc_config.get('SubnetIds', [])}")
print(f"Security Groups: {vpc_config.get('SecurityGroupIds', [])}")

# Check SG outbound rules
for sg_id in vpc_config.get("SecurityGroupIds", []):
    sg = ec2.describe_security_groups(GroupIds=[sg_id])["SecurityGroups"][0]
    print(f"\nSG {sg_id} ({sg['GroupName']}):")
    print(f"  Outbound rules:")
    for rule in sg.get("IpPermissionsEgress", []):
        proto = rule.get("IpProtocol", "all")
        from_port = rule.get("FromPort", "all")
        to_port = rule.get("ToPort", "all")
        ranges = [r["CidrIp"] for r in rule.get("IpRanges", [])]
        print(f"    {proto} {from_port}-{to_port} -> {ranges}")

# Check if subnets have internet access
for subnet_id in vpc_config.get("SubnetIds", []):
    subnet = ec2.describe_subnets(SubnetIds=[subnet_id])["Subnets"][0]
    print(f"\nSubnet {subnet_id}: AZ={subnet['AvailabilityZone']}, MapPublicIp={subnet.get('MapPublicIpOnLaunch')}")

# Check route tables for these subnets
for subnet_id in vpc_config.get("SubnetIds", []):
    rts = ec2.describe_route_tables(
        Filters=[{"Name": "association.subnet-id", "Values": [subnet_id]}]
    )["RouteTables"]
    if not rts:
        rts = ec2.describe_route_tables(
            Filters=[{"Name": "association.main", "Values": ["true"]},
                     {"Name": "vpc-id", "Values": [vpc_config.get("VpcId", "")]}]
        )["RouteTables"]
    for rt in rts:
        print(f"\nRoute table for {subnet_id}: {rt['RouteTableId']}")
        for route in rt["Routes"]:
            dest = route.get("DestinationCidrBlock", route.get("DestinationPrefixListId", "?"))
            target = route.get("GatewayId") or route.get("NatGatewayId") or route.get("NetworkInterfaceId") or "?"
            print(f"  {dest} -> {target} ({route.get('State', '?')})")
