"""Recreate the AOSS data access policy to fix the 403 issue."""
import json
import boto3

client = boto3.client("opensearchserverless", region_name="us-east-1")

POLICY_NAME = "research-analyst-search-dap"

# Get current version
resp = client.get_access_policy(name=POLICY_NAME, type="data")
version = resp["accessPolicyDetail"]["policyVersion"]
print(f"Current policy version: {version}")

# Define the correct policy with all needed principals
policy = [
    {
        "Rules": [
            {
                "Resource": ["index/research-analyst-search/*"],
                "Permission": [
                    "aoss:CreateIndex",
                    "aoss:DeleteIndex",
                    "aoss:UpdateIndex",
                    "aoss:DescribeIndex",
                    "aoss:ReadDocument",
                    "aoss:WriteDocument"
                ],
                "ResourceType": "index"
            },
            {
                "Resource": ["collection/research-analyst-search"],
                "Permission": [
                    "aoss:CreateCollectionItems",
                    "aoss:DeleteCollectionItems",
                    "aoss:UpdateCollectionItems",
                    "aoss:DescribeCollectionItems"
                ],
                "ResourceType": "collection"
            }
        ],
        "Principal": [
            "arn:aws:iam::974220725866:root",
            "arn:aws:iam::974220725866:user/eyreaws-local",
            "arn:aws:iam::974220725866:role/ResearchAnalystStack-CaseFilesLambdaServiceRoleC1B8-rCJotA0lmPum",
            "arn:aws:iam::974220725866:role/ResearchAnalystStack-CaseFilesLambdaServiceRole7F1E-0rLmjCQvPaVR"
        ],
        "Description": "Full access for Research Analyst platform"
    }
]

# Update with new policy (force refresh)
resp2 = client.update_access_policy(
    name=POLICY_NAME,
    type="data",
    policyVersion=version,
    policy=json.dumps(policy),
    description="Full access for Research Analyst platform - updated to fix 403"
)
print(f"Updated policy. New version: {resp2['accessPolicyDetail']['policyVersion']}")
print("Wait 60-120 seconds for propagation, then retry.")
