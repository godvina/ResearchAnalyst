"""Create OpenSearch Serverless collection for enterprise tier search."""
import json
import subprocess
import time

COLLECTION_NAME = "research-analyst-search"
REGION = "us-east-1"
ACCOUNT_ID = "974220725866"


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr[:500]}")
        return None
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    # 1. Encryption policy
    print("Creating encryption policy...")
    enc_policy = json.dumps({
        "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]}],
        "AWSOwnedKey": True,
    })
    run(["aws", "opensearchserverless", "create-security-policy",
         "--name", f"{COLLECTION_NAME}-enc", "--type", "encryption",
         "--policy", enc_policy, "--region", REGION])
    print("  Done")

    # 2. Network policy (public access for now — VPC endpoint can be added later)
    print("Creating network policy...")
    net_policy = json.dumps([{
        "Rules": [
            {"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]},
            {"ResourceType": "dashboard", "Resource": [f"collection/{COLLECTION_NAME}"]},
        ],
        "AllowFromPublic": True,
    }])
    run(["aws", "opensearchserverless", "create-security-policy",
         "--name", f"{COLLECTION_NAME}-net", "--type", "network",
         "--policy", net_policy, "--region", REGION])
    print("  Done")

    # 3. Data access policy
    print("Creating data access policy...")
    dap = json.dumps([{
        "Rules": [
            {
                "ResourceType": "index",
                "Resource": [f"index/{COLLECTION_NAME}/*"],
                "Permission": ["aoss:CreateIndex", "aoss:UpdateIndex", "aoss:DescribeIndex",
                               "aoss:ReadDocument", "aoss:WriteDocument"],
            },
            {
                "ResourceType": "collection",
                "Resource": [f"collection/{COLLECTION_NAME}"],
                "Permission": ["aoss:CreateCollectionItems", "aoss:UpdateCollectionItems",
                               "aoss:DescribeCollectionItems"],
            },
        ],
        "Principal": [f"arn:aws:iam::{ACCOUNT_ID}:root"],
        "Description": "Full access for account",
    }])
    run(["aws", "opensearchserverless", "create-access-policy",
         "--name", f"{COLLECTION_NAME}-dap", "--type", "data",
         "--policy", dap, "--region", REGION])
    print("  Done")

    # 4. Create collection
    print("Creating VECTORSEARCH collection...")
    result = run(["aws", "opensearchserverless", "create-collection",
                  "--name", COLLECTION_NAME, "--type", "VECTORSEARCH",
                  "--description", "Enterprise tier vector search for Research Analyst",
                  "--region", REGION])
    if result:
        collection_id = result.get("createCollectionDetail", {}).get("id", "")
        print(f"  Collection ID: {collection_id}")
        print(f"  Status: {result.get('createCollectionDetail', {}).get('status', '')}")

    # 5. Wait for collection to be active
    print("Waiting for collection to become ACTIVE...")
    for i in range(30):
        time.sleep(10)
        status_result = run(["aws", "opensearchserverless", "batch-get-collection",
                            "--names", COLLECTION_NAME, "--region", REGION])
        if status_result:
            details = status_result.get("collectionDetails", [])
            if details:
                status = details[0].get("status", "")
                endpoint = details[0].get("collectionEndpoint", "")
                print(f"  [{i*10}s] Status: {status}")
                if status == "ACTIVE":
                    print(f"\nCollection is ACTIVE!")
                    print(f"Endpoint: {endpoint}")
                    print(f"Collection ID: {details[0].get('id', '')}")
                    return
    print("Timed out waiting for collection")


if __name__ == "__main__":
    main()
