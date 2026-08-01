"""Test that investigator-analysis correctly routes to Intelligence Command Brief for large cases."""
import json, boto3, time

client = boto3.client("lambda", region_name="us-east-1")
CASE = "7f05e8d5-4492-4f19-8894-25367606db96"

payload = json.dumps({
    "httpMethod": "GET",
    "path": f"/case-files/{CASE}/investigator-analysis",
    "pathParameters": {"id": CASE},
    "requestContext": {"httpMethod": "GET"},
    "queryStringParameters": {},
    "headers": {},
})

print("Testing investigator-analysis route for large case...")
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
print(f"large_case: {body.get('large_case')}")
print(f"Has intelligence_brief: {'intelligence_brief' in body}")

if body.get("intelligence_brief"):
    ib = body["intelligence_brief"]
    print(f"Score: {ib.get('prosecution_readiness_score')}/100 ({ib.get('readiness_label')})")
    print(f"Cached: {ib.get('cached')}")
    print(f"BLUF: {ib.get('bluf', '')[:150]}")
else:
    print(f"Response keys: {list(body.keys())[:10]}")
    if body.get("error"):
        print(f"Error: {body['error']}")
