"""Grant all Lambda roles aoss:APIAccessAll permission."""
import boto3
import json

REGION = "us-east-1"
COLLECTION_ARN = "arn:aws:aoss:us-east-1:974220725866:collection/u260nrrtc0q87ji8iu0k"

lam = boto3.client("lambda", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)

# Get all Lambda roles
fns = lam.list_functions(MaxItems=50)
roles = set()
for fn in fns["Functions"]:
    if "ResearchAnalystStack" in fn["FunctionName"]:
        role_name = fn["Role"].split("/")[-1]
        roles.add(role_name)

print(f"Found {len(roles)} Lambda roles")

# Create inline policy for AOSS access
policy_doc = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": ["aoss:APIAccessAll", "aoss:DashboardsAccessAll"],
        "Resource": [COLLECTION_ARN],
    }],
})

for role_name in sorted(roles):
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="AOSSAccess",
            PolicyDocument=policy_doc,
        )
        print(f"  Added AOSSAccess to {role_name}")
    except Exception as e:
        print(f"  Error for {role_name}: {e}")

print("\nDone!")
