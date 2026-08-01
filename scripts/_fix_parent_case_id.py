"""Fix parent_case_id mapping so Neptune queries resolve correctly."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")

# Set parent_case_id for main case
sql = "UPDATE case_files SET parent_case_id = '7f05e8d5-4492-4f19-8894-25367606db96' WHERE case_id = '7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e'"

event = {
    "httpMethod": "POST",
    "path": "/admin/run-migration",
    "body": json.dumps({"sql": sql}),
    "headers": {},
    "pathParameters": {},
    "queryStringParameters": None,
}

print("Setting parent_case_id for main case...")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps(event),
)
result = json.loads(resp["Payload"].read())
print(f"Result: {json.dumps(result)[:300]}")

# Also set for demo case
sql2 = "UPDATE case_files SET parent_case_id = 'ed0b6c27-3b6b-4255-b9d0-efe8f4383a99' WHERE case_id = 'ed0b6c27-4a8e-4f3b-9d1c-5e6f7a8b9c0d'"
event2 = {
    "httpMethod": "POST",
    "path": "/admin/run-migration",
    "body": json.dumps({"sql": sql2}),
    "headers": {},
    "pathParameters": {},
    "queryStringParameters": None,
}
print("\nSetting parent_case_id for demo case...")
resp2 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps(event2),
)
result2 = json.loads(resp2["Payload"].read())
print(f"Result: {json.dumps(result2)[:300]}")

# Verify by checking if the investigator-analysis endpoint now resolves the graph
print("\nVerifying: GET /investigator-analysis should now use graph_case_id...")
verify_event = {
    "httpMethod": "GET",
    "path": "/case-files/7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e/investigator-analysis",
    "pathParameters": {"id": "7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e"},
    "body": None,
    "headers": {},
    "queryStringParameters": None,
}
resp3 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps(verify_event),
)
payload3 = json.loads(resp3["Payload"].read())
body3 = json.loads(payload3.get("body", "{}"))
cc = body3.get("command_center", {})
print(f"  Status: {payload3.get('statusCode')}")
print(f"  Network Density: {cc.get('indicators', [{}])[2] if len(cc.get('indicators', [])) > 2 else 'N/A'}")
print(f"  Viability: {cc.get('viability_score', 'N/A')}")
