"""Update OpenSearch Serverless data access policy to include the pipeline Lambda role."""
import json
import boto3

client = boto3.client("opensearchserverless", region_name="us-east-1")

# The Lambda role that needs access
LAMBDA_ROLE = "arn:aws:iam::974220725866:role/ResearchAnalystStack-CaseFilesLambdaServiceRoleC1B8-rCJotA0lmPum"

# Get current policy
resp = client.get_access_policy(name="research-analyst-search-dap", type="data")
current_policy = resp["accessPolicyDetail"]["policy"]
if isinstance(current_policy, str):
    current_policy = json.loads(current_policy)
print(f"Current policy: {json.dumps(current_policy, indent=2)[:500]}")

# The policy is a list of rules. Add the Lambda role to existing principals.
# Find the rule and add our role
for rule in current_policy:
    principals = rule.get("Principal", [])
    if LAMBDA_ROLE not in principals:
        principals.append(LAMBDA_ROLE)
        rule["Principal"] = principals

print(f"\nUpdated policy: {json.dumps(current_policy, indent=2)[:800]}")

# Update
client.update_access_policy(
    name="research-analyst-search-dap",
    type="data",
    policyVersion=resp["accessPolicyDetail"]["policyVersion"],
    policy=json.dumps(current_policy),
)
print("\n✓ Data access policy updated — Lambda role now has OpenSearch access")
