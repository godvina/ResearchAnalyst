"""Test the Intelligence Command Brief endpoint."""
import json, boto3, time

client = boto3.client("lambda", region_name="us-east-1")
CASE = "7f05e8d5-4492-4f19-8894-25367606db96"

payload = json.dumps({
    "httpMethod": "GET",
    "path": f"/case-files/{CASE}/intelligence-brief",
    "pathParameters": {"id": CASE},
    "requestContext": {"httpMethod": "GET"},
    "queryStringParameters": {},
    "headers": {},
})

print("Invoking Intelligence Command Brief...")
t0 = time.time()
resp = client.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=payload.encode(),
)
elapsed = time.time() - t0
result = json.loads(resp["Payload"].read())
status = result.get("statusCode", "?")
body = json.loads(result.get("body", "{}"))

print(f"\nStatus: {status} ({elapsed:.1f}s)")
print(f"Prosecution Readiness: {body.get('prosecution_readiness_score', '?')}/100 ({body.get('readiness_label', '?')})")
print(f"\nBLUF: {body.get('bluf', 'N/A')[:200]}")
print(f"\nStrongest Thread: {body.get('strongest_thread', {}).get('typology', 'N/A')}")
print(f"  {body.get('strongest_thread', {}).get('summary', 'N/A')[:200]}")
print(f"  Next: {body.get('strongest_thread', {}).get('next_action', 'N/A')[:150]}")

hubs = body.get("hub_entities", [])
print(f"\nHub Entities: {len(hubs)}")
for h in hubs[:3]:
    print(f"  - {h.get('name','?')}: {h.get('significance','')[:100]}")

vulns = body.get("vulnerabilities", [])
print(f"\nVulnerabilities: {len(vulns)}")
for v in vulns[:3]:
    print(f"  - {v.get('gap','')[:80]}")

print(f"\nTypology Scores: {len(body.get('typology_scores', []))}")
print(f"Generation time: {body.get('generation_time_ms', '?')}ms")
print(f"Cached: {body.get('cached', False)}")

if body.get("cross_typology_insight"):
    print(f"\nCross-Typology: {body['cross_typology_insight'][:200]}")
