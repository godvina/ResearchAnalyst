"""Fix AOSS VPC endpoint security group to allow Lambda access."""
import boto3

ec2 = boto3.client("ec2", region_name="us-east-1")

# Get the AOSS VPC endpoint
vpces = ec2.describe_vpc_endpoints(
    Filters=[{"Name": "service-name", "Values": ["com.amazonaws.us-east-1.aoss"]}]
)["VpcEndpoints"]

for vpce in vpces:
    vpce_id = vpce["VpcEndpointId"]
    sgs = [g["GroupId"] for g in vpce["Groups"]]
    print(f"VPCE: {vpce_id}, SGs: {sgs}, State: {vpce['State']}")

    # Check the SG inbound rules
    for sg_id in sgs:
        sg = ec2.describe_security_groups(GroupIds=[sg_id])["SecurityGroups"][0]
        print(f"  SG {sg_id} inbound rules:")
        for rule in sg["IpPermissions"]:
            ranges = [r["CidrIp"] for r in rule.get("IpRanges", [])]
            sg_refs = [r["GroupId"] for r in rule.get("UserIdGroupPairs", [])]
            print(f"    {rule.get('IpProtocol')} {rule.get('FromPort')}-{rule.get('ToPort')} CIDRs={ranges} SGs={sg_refs}")

# Get the Lambda embed function's SG
lam = boto3.client("lambda", region_name="us-east-1")
fn = lam.get_function_configuration(
    FunctionName="ResearchAnalystStack-IngestionEmbedLambdaE92F3BC0-wYlIRbksk1Jz"
)
lambda_sgs = fn["VpcConfig"]["SecurityGroupIds"]
print(f"\nLambda SGs: {lambda_sgs}")

# Add Lambda SG to AOSS VPC endpoint SG inbound
aoss_sg_id = sgs[0]
for lsg in lambda_sgs:
    try:
        ec2.authorize_security_group_ingress(
            GroupId=aoss_sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": 443,
                "ToPort": 443,
                "UserIdGroupPairs": [{"GroupId": lsg}],
            }],
        )
        print(f"Added Lambda SG {lsg} to AOSS VPC endpoint SG {aoss_sg_id}")
    except Exception as e:
        if "Duplicate" in str(e) or "already exists" in str(e):
            print(f"Lambda SG {lsg} already in AOSS VPC endpoint SG")
        else:
            print(f"Error: {e}")

# Also add all other Lambda SGs
fns = lam.list_functions(MaxItems=50)
all_lambda_sgs = set()
for f in fns["Functions"]:
    if "ResearchAnalystStack" in f["FunctionName"]:
        vpc_config = f.get("VpcConfig", {})
        for sg in vpc_config.get("SecurityGroupIds", []):
            all_lambda_sgs.add(sg)

print(f"\nAll Lambda SGs: {all_lambda_sgs}")
for lsg in all_lambda_sgs:
    try:
        ec2.authorize_security_group_ingress(
            GroupId=aoss_sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": 443,
                "ToPort": 443,
                "UserIdGroupPairs": [{"GroupId": lsg}],
            }],
        )
        print(f"  Added {lsg}")
    except Exception as e:
        if "Duplicate" in str(e) or "already exists" in str(e):
            print(f"  {lsg} already exists")
        else:
            print(f"  Error adding {lsg}: {e}")

print("\nDone!")
