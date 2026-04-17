"""Recreate AOSS policies that were deleted."""
import boto3
import json

REGION = "us-east-1"
COLLECTION_NAME = "research-analyst-search"

client = boto3.client("opensearchserverless", region_name=REGION)

# Encryption policy
try:
    client.create_security_policy(
        type="encryption",
        name=f"{COLLECTION_NAME}-enc",
        policy=json.dumps({
            "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]}],
            "AWSOwnedKey": True,
        }),
    )
    print("Created encryption policy")
except Exception as e:
    print(f"Encryption policy: {e}")

# Network policy — allow public access (simpler than VPC endpoint for now)
try:
    client.create_security_policy(
        type="network",
        name=f"{COLLECTION_NAME}-net",
        policy=json.dumps([{
            "Rules": [
                {"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]},
                {"ResourceType": "dashboard", "Resource": [f"collection/{COLLECTION_NAME}"]},
            ],
            "AllowFromPublic": True,
        }]),
    )
    print("Created network policy (public access)")
except Exception as e:
    print(f"Network policy: {e}")

# Data access policy — account root
sts = boto3.client("sts", region_name=REGION)
account_id = sts.get_caller_identity()["Account"]

try:
    client.create_access_policy(
        type="data",
        name=f"{COLLECTION_NAME}-dap",
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
            "Principal": [f"arn:aws:iam::{account_id}:root"],
            "Description": "Lambda access to OpenSearch Serverless collection",
        }]),
    )
    print("Created data access policy")
except Exception as e:
    print(f"Data access policy: {e}")

print("Done.")
