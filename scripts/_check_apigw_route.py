"""Check API Gateway route for pipeline-status."""
import boto3

apigw = boto3.client("apigateway", region_name="us-east-1")
lam = boto3.client("lambda", region_name="us-east-1")

resources = apigw.get_resources(restApiId="edb025my3i", limit=500)
for r in resources["items"]:
    if "pipeline-status" in r.get("path", ""):
        print(f"Resource: {r['id']} {r['path']}")
        methods = r.get("resourceMethods", {})
        print(f"Methods: {list(methods.keys())}")
        for method in methods:
            try:
                integ = apigw.get_integration(
                    restApiId="edb025my3i",
                    resourceId=r["id"],
                    httpMethod=method,
                )
                uri = integ.get("uri", "")
                print(f"  {method} → {uri[:120]}")
            except Exception as e:
                print(f"  {method} → error: {e}")

# Check Lambda permission
fn_name = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
try:
    policy = lam.get_policy(FunctionName=fn_name)
    print(f"\nLambda policy exists: {len(policy['Policy'])} chars")
except lam.exceptions.ResourceNotFoundException:
    print("\nNo resource policy on Lambda — API Gateway can't invoke it!")
    print("Need to add permission.")
