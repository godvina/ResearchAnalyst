"""Test typology findings for Epstein and Nightfall cases."""
import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')
FUNCTION = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

cases = [
    ('7f05e8d5-3b1a-4c2d-9e6f-8a7b5c4d3e2f', 'Epstein (main)'),
    ('ed0b6c27-1a2b-3c4d-5e6f-7a8b9c0d1e2f', 'Nightfall (demo)'),
]

categories = ['recruitment_grooming', 'financial_control', 'venue_logistics']

for case_id, name in cases:
    print(f"\n{'='*50}")
    print(f"CASE: {name} ({case_id[:8]})")
    print(f"{'='*50}")
    
    # Check entity count
    event = {
        'httpMethod': 'GET',
        'path': f'/case-files/{case_id}/entities',
        'pathParameters': {'id': case_id},
        'queryStringParameters': {'limit': '3'},
        'headers': {'content-type': 'application/json'}
    }
    r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode())
    resp = json.loads(r['Payload'].read())
    body = json.loads(resp.get('body', '{}'))
    total = body.get('total', body.get('count', len(body.get('entities', []))))
    print(f"  Entities: {total}")
    
    # Test typology for each category
    for cat in categories:
        event2 = {
            'httpMethod': 'GET',
            'path': f'/case-files/{case_id}/typology/{cat}/findings',
            'pathParameters': {'id': case_id},
            'queryStringParameters': {},
            'headers': {'content-type': 'application/json'}
        }
        r2 = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event2).encode())
        resp2 = json.loads(r2['Payload'].read())
        status2 = resp2.get('statusCode', '?')
        body2 = json.loads(resp2.get('body', '{}'))
        sits = body2.get('situations', [])
        err = body2.get('error', '')
        
        if sits:
            print(f"  {cat}: {len(sits)} situations ✓")
            print(f"    First: {sits[0].get('title', '?')[:60]}")
        elif err:
            print(f"  {cat}: ERROR - {str(err)[:100]}")
        else:
            print(f"  {cat}: 0 situations (status {status2})")
