"""Test the case-files list endpoint."""
import json, boto3, time
client = boto3.client("lambda", region_name="us-east-1")
payload = json.dumps({
    "httpMethod": "GET",
    "path": "/case-files",
    "pathParameters": {},
    "requestContext": {"httpMethod": "GET"},
    "queryStringParameters": {},
    "headers": {},
})
t0 = time.time()
resp = client.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=payload.encode(),
)
elapsed = time.time() - t0
result = json.loads(resp["Payload"].read())
status = result.get("statusCode", "?")
body = json.loads(result.get("body", "{}"))
print(f"Status: {status} ({elapsed:.1f}s)")
if isinstance(body, list):
    print(f"Cases returned: {len(body)}")
elif isinstance(body, dict):
    cases = body.get("cases", body.get("items", []))
    print(f"Cases returned: {len(cases)}")
    if not cases:
        print(f"Keys: {list(body.keys())[:10]}")
        print(f"Body preview: {str(body)[:300]}")
