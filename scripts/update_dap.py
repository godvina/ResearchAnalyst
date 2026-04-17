"""Update AOSS data access policy with explicit Lambda role ARNs."""
import boto3
import json

REGION = "us-east-1"
COLLECTION_NAME = "research-analyst-search"

lam = boto3.client("lambda", region_name=REGION)
aoss = boto3.client("opensearchserverless", region_name=REGION)

# Collect all Lambda role ARNs
roles = set()
fns = lam.list_functions(MaxItems=50)
for fn in fns["Functions"]:
    if "ResearchAnalystStack" in fn["FunctionName"]:
        roles.add(fn["Role"])

print(f"Found {len(roles)} Lambda roles:")
for r in sorted(roles):
    print(f"  {r}")

# Also add account root as fallback
account_id = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
principals = list(roles) + [f"arn:aws:iam::{account_id}:root"]

# Update the data access policy
aoss.update_access_policy(
    type="data",
    name=f"{COLLECTION_NAME}-dap",
    policyVersion="MTc3NDY2MTI1MjE2Nl8x",
    policy=json.dumps([{
        "Rules": [
            {
                "ResourceType": "index",
                "Resource": [f"index/{COLLECTION_NAME}/*"],
                "Permission": [
                    "aoss:CreateIndex", "aoss:UpdateIndex", "aoss:DescribeIndex",
                    "aoss:ReadDocument", "aoss:WriteDocument",
                ],
            },
            {
                "ResourceType": "collection",
                "Resource": [f"collection/{COLLECTION_NAME}"],
                "Permission": [
                    "aoss:CreateCollectionItems", "aoss:UpdateCollectionItems",
                    "aoss:DescribeCollectionItems",
                ],
            },
        ],
        "Principal": principals,
        "Description": "Lambda access to OpenSearch Serverless collection",
    }]),
)
print(f"\nUpdated data access policy with {len(principals)} principals")
