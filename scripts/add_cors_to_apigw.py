"""Add CORS OPTIONS method to all API Gateway resources."""
import boto3

REGION = "us-east-1"
API_ID = "edb025my3i"

apigw = boto3.client("apigateway", region_name=REGION)

# Get all resources
resources = apigw.get_resources(restApiId=API_ID, limit=100)["items"]

CORS_HEADERS = {
    "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization'",
    "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,PATCH,OPTIONS'",
    "method.response.header.Access-Control-Allow-Origin": "'*'",
}

for r in resources:
    rid = r["id"]
    path = r["path"]
    methods = r.get("resourceMethods") or {}
    
    if "OPTIONS" in methods:
        print(f"  {path}: OPTIONS already exists")
        continue
    if path == "/" or not methods:
        continue

    print(f"Adding OPTIONS to {path} ({rid})...")
    try:
        # Create OPTIONS method
        apigw.put_method(
            restApiId=API_ID, resourceId=rid,
            httpMethod="OPTIONS",
            authorizationType="NONE",
        )
        # MOCK integration
        apigw.put_integration(
            restApiId=API_ID, resourceId=rid,
            httpMethod="OPTIONS",
            type="MOCK",
            requestTemplates={"application/json": '{"statusCode": 200}'},
        )
        # Method response
        apigw.put_method_response(
            restApiId=API_ID, resourceId=rid,
            httpMethod="OPTIONS", statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Headers": False,
                "method.response.header.Access-Control-Allow-Methods": False,
                "method.response.header.Access-Control-Allow-Origin": False,
            },
        )
        # Integration response
        apigw.put_integration_response(
            restApiId=API_ID, resourceId=rid,
            httpMethod="OPTIONS", statusCode="200",
            responseParameters=CORS_HEADERS,
        )
        print(f"  OK")
    except Exception as e:
        print(f"  Error: {e}")

# Deploy
print("\nDeploying API...")
apigw.create_deployment(restApiId=API_ID, stageName="v1")
print("Done!")
