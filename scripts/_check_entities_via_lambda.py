"""Check entities via Lambda's internal DB connection."""
import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')
FUNCTION = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

def invoke(path, params=None):
    event = {
        'httpMethod': 'GET',
        'path': path,
        'pathParameters': {},
        'queryStringParameters': params or {},
        'headers': {'content-type': 'application/json'}
    }
    # Extract path params if needed
    parts = path.split('/')
    if len(parts) >= 3 and parts[1] == 'case-files':
        event['pathParameters'] = {'id': parts[2]}
    
    r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode())
    resp = json.loads(r['Payload'].read())
    return resp.get('statusCode', '?'), json.loads(resp.get('body', '{}'))

# 1. Get case list with entity counts from the matters table
print("=== Cases from API ===")
status, body = invoke('/case-files')
cases = body.get('case_files', body.get('matters', []))
for c in cases:
    name = c.get('matter_name', c.get('topic_name', ''))
    cid = c.get('matter_id', c.get('case_id', ''))
    ents = c.get('total_entities', c.get('entity_count', 0))
    docs = c.get('total_documents', c.get('document_count', 0))
    print(f"  {name[:40]:40s} | {cid[:8]} | {docs:>6} docs | {ents:>6} entities")

# 2. Try to get entities for Epstein case via the search endpoint  
print("\n=== Entity search for Epstein ===")
epstein_id = '7f05e8d5-3b1a-4c2d-9e6f-8a7b5c4d3e2f'
status, body = invoke(f'/case-files/{epstein_id}/entities', {'limit': '3', 'offset': '0'})
print(f"  Status: {status}")
print(f"  Response keys: {list(body.keys())}")
entities = body.get('entities', [])
print(f"  Entities returned: {len(entities)}")
total = body.get('total', body.get('total_count', body.get('count', '?')))
print(f"  Total field: {total}")
if entities:
    print(f"  First entity: {json.dumps(entities[0], indent=2)[:200]}")

# 3. Try the Neptune graph endpoint for Epstein
print("\n=== Neptune graph for Epstein ===")
status, body = invoke(f'/case-files/{epstein_id}/graph', {'limit': '5'})
print(f"  Status: {status}")
print(f"  Response keys: {list(body.keys())[:10]}")
if body.get('nodes'):
    print(f"  Nodes: {len(body['nodes'])}")
elif body.get('error'):
    print(f"  Error: {str(body['error'])[:150]}")

# 4. Try organizations-based entity query
print("\n=== Check org-based queries ===")
status, body = invoke('/organizations')
if body.get('organizations'):
    orgs = body['organizations']
    print(f"  Orgs found: {len(orgs)}")
    for o in orgs[:3]:
        print(f"    {o.get('org_id', '?')[:8]}: {o.get('name', '?')}")
