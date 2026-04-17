"""Test Neptune queries directly via the Lambda to debug the entity neighborhood issue."""
import json
import boto3

lambda_client = boto3.client("lambda", region_name="us-east-1")
FUNCTION_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

case_id = "7f05e8d5-4492-4f19-8894-25367606db96"

# Simulate an API Gateway event for entity-neighborhood
event = {
    "httpMethod": "GET",
    "resource": "/case-files/{id}/entity-neighborhood",
    "path": f"/case-files/{case_id}/entity-neighborhood",
    "pathParameters": {"id": case_id},
    "queryStringParameters": {"entity_name": "Jeffrey Epstein", "hops": "1"},
    "headers": {},
    "body": None,
}

print("Invoking Lambda directly for entity-neighborhood...")
resp = lambda_client.invoke(
    FunctionName=FUNCTION_NAME,
    InvocationType="RequestResponse",
    Payload=json.dumps(event),
)
payload = json.loads(resp["Payload"].read().decode())
print(f"Status: {payload.get('statusCode')}")
body = json.loads(payload.get("body", "{}"))
print(f"Nodes: {len(body.get('nodes', []))}")
print(f"Edges: {len(body.get('edges', []))}")
if not body.get("nodes"):
    print("Full body:", json.dumps(body, indent=2)[:500])

# Also check the function error
if resp.get("FunctionError"):
    print(f"Function error: {resp['FunctionError']}")
    print(f"Payload: {json.dumps(payload, indent=2)[:1000]}")
