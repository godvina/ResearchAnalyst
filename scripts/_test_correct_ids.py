"""Test typology findings with the CORRECT case_file_ids from Aurora."""
import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')
FUNCTION = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

# CORRECT IDs from case_files table
cases = [
    ('7f05e8d5-4492-4f19-8894-25367606db96', 'Epstein Main (248K entities)'),
    ('ed0b6c27-3b6b-4255-b9d0-efe8f4383a99', 'Epstein Combined (15K entities)'),
    ('0b24a307-a674-41b6-8d22-581c4a4aa566', 'Operation Nightfall (6.6K entities)'),
    ('1354d90a-9c26-4c51-9370-f618570335a3', 'Trucking CDL (222 entities)'),
]

categories = ['recruitment_grooming', 'financial_control']

for case_id, name in cases:
    print(f"\n{'='*50}")
    print(f"{name}")
    print(f"  ID: {case_id}")
    
    for cat in categories:
        event = {
            'httpMethod': 'GET',
            'path': f'/case-files/{case_id}/typology/{cat}/findings',
            'pathParameters': {'id': case_id},
            'queryStringParameters': {},
            'headers': {'content-type': 'application/json'}
        }
        r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode())
        resp = json.loads(r['Payload'].read())
        body = json.loads(resp.get('body', '{}'))
        sits = body.get('situations', [])
        
        if sits:
            print(f"  {cat}: {len(sits)} situations ✓")
            for s in sits[:2]:
                print(f"    - {s.get('title', '?')[:50]} ({s.get('confidence', '?')})")
        else:
            print(f"  {cat}: 0 situations")
