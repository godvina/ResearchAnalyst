"""Add document download route to the deployed API Gateway.

Creates: GET /case-files/{id}/documents/{docId}/download
Routes to the existing CaseFiles Lambda.
"""
import boto3

REGION = "us-east-1"
API_ID = "edb025my3i"

apigw = boto3.client("apigateway", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)

# Find the CaseFiles Lambda ARN
CASE_FILES_LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
fn = lam.get_function(FunctionName=CASE_FILES_LAMBDA)
lambda_arn = fn["Configuration"]["FunctionArn"]
region = REGION
account_id = lambda_arn.split(":")[4]
print(f"Lambda ARN: {lambda_arn}")

# Get all resources to find /case-files/{id}
resources = apigw.get_resources(restApiId=API_ID, limit=200)["items"]
case_file_id_resource = None
for r in resources:
    if r["path"] == "/case-files/{id}":
        case_file_id_resource = r
        break

if not case_file_id_resource:
    print("ERROR: /case-files/{id} resource not found!")
    exit(1)

parent_id = case_file_id_resource["id"]
print(f"Found /case-files/{{id}} resource: {parent_id}")

# Create /case-files/{id}/documents
try:
    docs_resource = apigw.create_resource(
        restApiId=API_ID, parentId=parent_id, pathPart="documents"
    )
    docs_id = docs_resource["id"]
    print(f"Created /documents resource: {docs_id}")
except Exception as e:
    if "ConflictException" in str(type(e).__name__) or "already exists" in str(e).lower():
        # Find existing
        for r in resources:
            if r["path"] == "/case-files/{id}/documents":
                docs_id = r["id"]
                print(f"Found existing /documents resource: {docs_id}")
                break
    else:
        raise

# Create /case-files/{id}/documents/{docId}
try:
    doc_id_resource = apigw.create_resource(
        restApiId=API_ID, parentId=docs_id, pathPart="{docId}"
    )
    doc_id_id = doc_id_resource["id"]
    print(f"Created /{{docId}} resource: {doc_id_id}")
except Exception as e:
    if "already exists" in str(e).lower():
        for r in resources:
            if r["path"] == "/case-files/{id}/documents/{docId}":
                doc_id_id = r["id"]
                print(f"Found existing /{{docId}} resource: {doc_id_id}")
                break
    else:
        raise

# Create /case-files/{id}/documents/{docId}/download
try:
    dl_resource = apigw.create_resource(
        restApiId=API_ID, parentId=doc_id_id, pathPart="download"
    )
    dl_id = dl_resource["id"]
    print(f"Created /download resource: {dl_id}")
except Exception as e:
    if "already exists" in str(e).lower():
        for r in resources:
            if r["path"] == "/case-files/{id}/documents/{docId}/download":
                dl_id = r["id"]
                print(f"Found existing /download resource: {dl_id}")
                break
    else:
        raise

# Add GET method
print(f"\nAdding GET method to /download ({dl_id})...")
try:
    apigw.put_method(
        restApiId=API_ID, resourceId=dl_id,
        httpMethod="GET",
        authorizationType="NONE",
    )
except Exception as e:
    if "already exists" in str(e).lower():
        print("  GET method already exists")
    else:
        raise

# Add Lambda proxy integration
integration_uri = f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{lambda_arn}/invocations"
apigw.put_integration(
    restApiId=API_ID, resourceId=dl_id,
    httpMethod="GET",
    type="AWS_PROXY",
    integrationHttpMethod="POST",
    uri=integration_uri,
)
print("  Integration set")

# Add OPTIONS for CORS
try:
    apigw.put_method(
        restApiId=API_ID, resourceId=dl_id,
        httpMethod="OPTIONS",
        authorizationType="NONE",
    )
except Exception:
    pass

apigw.put_integration(
    restApiId=API_ID, resourceId=dl_id,
    httpMethod="OPTIONS",
    type="MOCK",
    requestTemplates={"application/json": '{"statusCode": 200}'},
)
apigw.put_method_response(
    restApiId=API_ID, resourceId=dl_id,
    httpMethod="OPTIONS", statusCode="200",
    responseParameters={
        "method.response.header.Access-Control-Allow-Headers": False,
        "method.response.header.Access-Control-Allow-Methods": False,
        "method.response.header.Access-Control-Allow-Origin": False,
    },
)
apigw.put_integration_response(
    restApiId=API_ID, resourceId=dl_id,
    httpMethod="OPTIONS", statusCode="200",
    responseParameters={
        "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization'",
        "method.response.header.Access-Control-Allow-Methods": "'GET,OPTIONS'",
        "method.response.header.Access-Control-Allow-Origin": "'*'",
    },
)
print("  CORS OPTIONS set")

# Add Lambda invoke permission for API Gateway
try:
    lam.add_permission(
        FunctionName=CASE_FILES_LAMBDA,
        StatementId=f"apigw-doc-download-{dl_id}",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn=f"arn:aws:execute-api:{region}:{account_id}:{API_ID}/*/GET/case-files/*/documents/*/download",
    )
    print("  Lambda permission added")
except Exception as e:
    if "already exists" in str(e).lower():
        print("  Lambda permission already exists")
    else:
        print(f"  Permission warning: {e}")

# Deploy
print("\nDeploying API...")
apigw.create_deployment(restApiId=API_ID, stageName="v1")
print("Done! Route available at: GET /v1/case-files/{id}/documents/{docId}/download")
