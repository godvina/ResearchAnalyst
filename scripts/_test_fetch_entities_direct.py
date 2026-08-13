"""Test: Can the Lambda's DB connection actually query entities?
We'll invoke a custom diagnostic endpoint."""
import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')
FUNCTION = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

# Use the typology ANALYSIS endpoint (not findings) which also queries entities
case_id = '7f05e8d5-4492-4f19-8894-25367606db96'

event = {
    'httpMethod': 'GET',
    'path': f'/case-files/{case_id}/typology',
    'pathParameters': {'id': case_id},
    'queryStringParameters': {},
    'headers': {'content-type': 'application/json'}
}

print(f"Testing typology ANALYSIS for case {case_id[:8]}...")
r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode())
resp = json.loads(r['Payload'].read())
status = resp.get('statusCode', '?')
body = json.loads(resp.get('body', '{}'))

print(f"Status: {status}")
print(f"Body keys: {list(body.keys())[:15]}")

if body.get('entity_count') is not None:
    print(f"Entity count from typology: {body['entity_count']}")
if body.get('total_entities') is not None:
    print(f"Total entities: {body['total_entities']}")
if body.get('overall_score') is not None:
    print(f"Overall score: {body['overall_score']}")
if body.get('category_scores'):
    for cs in body['category_scores'][:3]:
        print(f"  {cs.get('category_id', '?')}: {cs.get('score', '?')}%")
if body.get('error'):
    print(f"Error: {body['error']}")

# Full body dump (truncated)
print(f"\nFull response (first 500 chars):")
print(json.dumps(body, indent=2)[:500])
