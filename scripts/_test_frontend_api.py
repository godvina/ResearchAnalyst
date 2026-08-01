"""Test the precomputed typology API endpoint via Lambda invoke."""
import json, boto3

client = boto3.client("lambda", region_name="us-east-1")
CASE = "7f05e8d5-4492-4f19-8894-25367606db96"

payload = json.dumps({
    "httpMethod": "GET",
    "path": f"/case-files/{CASE}/typology-precomputed",
    "pathParameters": {"id": CASE},
    "requestContext": {"httpMethod": "GET"},
    "headers": {},
})

resp = client.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=payload.encode(),
)
result = json.loads(resp["Payload"].read())
status = result.get("statusCode", "?")
body = json.loads(result.get("body", "{}"))

print(f"Status: {status}")
print(f"precomputed: {body.get('precomputed')}")
print(f"any_stale: {body.get('any_stale')}")
print(f"typologies: {len(body.get('typologies', []))}")
if body.get("typologies"):
    print(f"\nTop 3 typologies:")
    for t in body["typologies"][:3]:
        print(f"  {t['typology_module_id']:25s} score={t['overall_score']:.4f} ({t['match_strength']}) subs={len(t.get('sub_categories', []))}")
print(f"\nsummary_graph: {'present' if body.get('summary_graph') else 'none'}")
print(f"pipeline_status: {body.get('pipeline_status', {}).get('status', 'none')}")
