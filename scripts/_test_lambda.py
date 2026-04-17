"""Test case-files Lambda directly."""
import boto3, json
lam = boto3.client("lambda", region_name="us-east-1")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({
        "httpMethod": "GET",
        "resource": "/case-files",
        "path": "/case-files",
        "pathParameters": None,
        "queryStringParameters": None,
        "body": None
    })
)
result = json.loads(resp["Payload"].read().decode())
print("Status:", result.get("statusCode"))
body = json.loads(result.get("body", "{}"))
cases = body.get("case_files", [])
print(f"Cases: {len(cases)}")
for c in cases[:10]:
    cid = c.get("case_id", "?")
    name = c.get("topic_name", "?")
    docs = c.get("document_count", 0)
    ents = c.get("entity_count", 0)
    print(f"  {cid[:12]} docs={docs:>5} ents={ents:>5}  {name}")
if "error" in body:
    print("Error:", json.dumps(body["error"], indent=2)[:500])
