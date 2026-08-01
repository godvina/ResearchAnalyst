"""Quick test of the run-pipeline endpoint."""
import json
import boto3

LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
lam = boto3.client("lambda", region_name="us-east-1")

# Get first lead
event = {"httpMethod": "GET", "path": "/pre-case/leads", "pathParameters": {},
         "queryStringParameters": {"page": "1", "page_size": "1"},
         "headers": {"Content-Type": "application/json"}, "body": None}
resp = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse", Payload=json.dumps(event))
payload = json.loads(resp["Payload"].read())
body = json.loads(payload.get("body", "{}"))
leads = body.get("leads", [])
if not leads:
    print("No leads found")
    exit()

lead = leads[0]
lead_id = lead["lead_id"]
print(f"Lead: {lead['title']} (status={lead['status']}, id={lead_id})")

# Test run-pipeline
print("\nCalling run-pipeline...")
event2 = {"httpMethod": "POST", "path": f"/pre-case/leads/{lead_id}/run-pipeline",
           "pathParameters": {"lead_id": lead_id},
           "queryStringParameters": {}, "headers": {"Content-Type": "application/json"}, "body": "{}"}
resp2 = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse", Payload=json.dumps(event2))
payload2 = json.loads(resp2["Payload"].read())
print(f"Status code: {payload2.get('statusCode')}")
body2 = payload2.get("body", "")
if isinstance(body2, str):
    body2 = json.loads(body2)
print(f"Response: {json.dumps(body2, indent=2)[:800]}")
