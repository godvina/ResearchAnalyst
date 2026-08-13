"""Check what case_file_id values actually exist in the entities table."""
import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')
FUNCTION = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

# Use the case_files handler with a debug SQL query
# We'll invoke the search endpoint which can hit entities table
# Or better — use the admin/custom-query if it exists

# Try a direct entity search for the Epstein main case (248K entities)
case_id = '7f05e8d5-3b1a-4c2d-9e6f-8a7b5c4d3e2f'

# Test: search for "Epstein" entity in this case
event = {
    'httpMethod': 'GET',
    'path': f'/case-files/{case_id}/search',
    'pathParameters': {'id': case_id},
    'queryStringParameters': {'q': 'epstein', 'limit': '3'},
    'headers': {'content-type': 'application/json'}
}

r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode())
resp = json.loads(r['Payload'].read())
status = resp.get('statusCode', '?')
body = json.loads(resp.get('body', '{}'))
print(f"Search 'epstein' in case {case_id[:8]}: status={status}")
print(f"  Keys: {list(body.keys())[:10]}")
if body.get('results'):
    print(f"  Results: {len(body['results'])}")
    for r2 in body['results'][:2]:
        print(f"    {r2.get('entity_name', r2.get('canonical_name', r2.get('name', '?')))}: {r2.get('entity_type', '?')}")
elif body.get('entities'):
    print(f"  Entities: {len(body['entities'])}")
elif body.get('error'):
    print(f"  Error: {body['error']}")

# Try the org-based entity query
print("\n--- Org-based entity query ---")
event2 = {
    'httpMethod': 'GET',
    'path': f'/organizations/95bd7590-bbbb-cccc-dddd-eeeeeeeeeeee/matters/{case_id}/entities',
    'pathParameters': {'org_id': '95bd7590-bbbb-cccc-dddd-eeeeeeeeeeee', 'matter_id': case_id},
    'queryStringParameters': {'limit': '5'},
    'headers': {'content-type': 'application/json'}
}
r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event2).encode())
resp = json.loads(r['Payload'].read())
status = resp.get('statusCode', '?')
body = json.loads(resp.get('body', '{}'))
print(f"  Status: {status}")
print(f"  Keys: {list(body.keys())[:10]}")
if body.get('entities'):
    print(f"  Found {len(body['entities'])} entities!")
    for e in body['entities'][:3]:
        print(f"    {e.get('canonical_name', '?')}: {e.get('entity_type', '?')}")
elif body.get('error'):
    print(f"  Error: {body['error']}")

# Also try the typology analysis (non-findings) which should show scores
print("\n--- Typology analysis (scores only) ---")
event3 = {
    'httpMethod': 'GET',
    'path': f'/case-files/{case_id}/typology',
    'pathParameters': {'id': case_id},
    'queryStringParameters': {},
    'headers': {'content-type': 'application/json'}
}
r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event3).encode())
resp = json.loads(r['Payload'].read())
status = resp.get('statusCode', '?')
body = json.loads(resp.get('body', '{}'))
print(f"  Status: {status}")
scores = body.get('category_scores', body.get('scores', []))
if scores:
    print(f"  Category scores: {len(scores)}")
    for s in scores[:3]:
        print(f"    {s.get('category_id', s.get('id', '?'))}: {s.get('score', s.get('match_percentage', '?'))}")
elif body.get('overall_score') is not None:
    print(f"  Overall: {body.get('overall_score')}")
    print(f"  Body keys: {list(body.keys())[:10]}")
elif body.get('error'):
    print(f"  Error: {body['error']}")
else:
    print(f"  Body: {json.dumps(body)[:300]}")
