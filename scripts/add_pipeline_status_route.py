"""Add /case-files/{id}/pipeline-status GET route to API Gateway."""
import boto3

REGION = "us-east-1"
API_ID = "edb025my3i"
STAGE = "v1"

apigw = boto3.client("apigateway", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)

# Find the PipelineConfig Lambda (it dispatches pipeline-status too)
fns = lam.list_functions(MaxItems=50)
config_fn = [f for f in fns["Functions"] if "PipelineConfig" in f["FunctionName"]]
if not config_fn:
    # Fall back to case_files Lambda
    config_fn = [f for f in fns["Functions"] if "CaseFiles" in f["FunctionName"]]

fn_arn = config_fn[0]["FunctionArn"] if config_fn else None
print(f"Lambda ARN: {fn_arn}")

# Find /case-files resource
resources = apigw.get_resources(restApiId=API_ID, limit=500)
case_files_res = None
for r in resources["items"]:
    if r["path"] == "/case-files/{id}":
        case_files_res = r
        break

if not case_files_res:
    print("ERROR: /case-files/{id} resource not found")
    exit(1)

print(f"Parent resource: {case_files_res['id']} ({case_files_res['path']})")

# Check if pipeline-status resource already exists
existing = None
for r in resources["items"]:
    if r["path"] == "/case-files/{id}/pipeline-status":
        existing = r
        break

if existing:
    print(f"Route already exists: {existing['id']}")
    resource_id = existing["id"]
else:
    # Create the resource
    resp = apigw.create_resource(
        restApiId=API_ID,
        parentId=case_files_res["id"],
        pathPart="pipeline-status",
    )
    resource_id = resp["id"]
    print(f"Created resource: {resource_id}")

# Add GET method
try:
    apigw.put_method(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod="GET",
        authorizationType="NONE",
    )
    print("Added GET method")
except apigw.exceptions.ConflictException:
    print("GET method already exists")

# Add Lambda integration
apigw.put_integration(
    restApiId=API_ID,
    resourceId=resource_id,
    httpMethod="GET",
    type="AWS_PROXY",
    integrationHttpMethod="POST",
    uri=f"arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
)
print("Added Lambda integration")

# Add OPTIONS for CORS
try:
    apigw.put_method(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        authorizationType="NONE",
    )
    apigw.put_integration(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        type="AWS_PROXY",
        integrationHttpMethod="POST",
        uri=f"arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/{fn_arn}/invocations",
    )
    print("Added OPTIONS for CORS")
except apigw.exceptions.ConflictException:
    print("OPTIONS already exists")

# Deploy
apigw.create_deployment(restApiId=API_ID, stageName=STAGE)
print(f"\nDeployed to stage '{STAGE}'")
print(f"Endpoint: https://{API_ID}.execute-api.{REGION}.amazonaws.com/{STAGE}/case-files/{{id}}/pipeline-status")
