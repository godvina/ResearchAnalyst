"""Update AOSS network policy with the AOSS-managed VPC endpoint."""
import boto3
import json
import time

REGION = "us-east-1"
aoss = boto3.client("opensearchserverless", region_name=REGION)

# Wait for AOSS VPC endpoint to be active
print("Waiting for AOSS VPC endpoint to become active...")
for i in range(60):
    vpces = aoss.list_vpc_endpoints()["vpcEndpointSummaries"]
    for v in vpces:
        print(f"  [{i}] {v['id']}: {v['status']}")
        if v["status"] == "ACTIVE":
            vpce_id = v["id"]
            print(f"\nVPC endpoint active: {vpce_id}")

            # Update network policy
            # First get current version
            policy = aoss.get_security_policy(type="network", name="research-analyst-search-net")
            version = policy["securityPolicyDetail"]["policyVersion"]

            aoss.update_security_policy(
                type="network",
                name="research-analyst-search-net",
                policyVersion=version,
                policy=json.dumps([{
                    "Rules": [
                        {"ResourceType": "collection", "Resource": ["collection/research-analyst-search"]},
                        {"ResourceType": "dashboard", "Resource": ["collection/research-analyst-search"]},
                    ],
                    "AllowFromPublic": False,
                    "SourceVPCEs": [vpce_id],
                }]),
            )
            print(f"Updated network policy with AOSS VPC endpoint {vpce_id}")
            exit(0)
    time.sleep(10)

print("Timed out waiting for VPC endpoint")
