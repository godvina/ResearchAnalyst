"""Test the typology findings API endpoint for HSI cases."""
import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')
FUNCTION = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

# Test cases
test_cases = [
    ('11111111-aaaa-bbbb-cccc-111111111111', 'supply_chain_sourcing', 'Sinaloa - Supply Chain'),
    ('11111111-aaaa-bbbb-cccc-111111111111', 'financial_control', 'Sinaloa - Financial Control'),
    ('1354d90a-9c26-4c51-9370-f618570335a3', 'recruitment_grooming', 'Trucking CDL - Recruitment'),
    ('22222222-aaaa-bbbb-cccc-222222222222', 'financial_control', 'Feeding Our Future - Financial'),
]

for case_id, category, label in test_cases:
    event = {
        'httpMethod': 'GET',
        'path': f'/case-files/{case_id}/typology/{category}/findings',
        'pathParameters': {'id': case_id},
        'queryStringParameters': {},
        'headers': {'content-type': 'application/json'}
    }
    
    print(f"\n--- {label} ---")
    print(f"  Case: {case_id[:8]}... Category: {category}")
    
    try:
        r = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode())
        resp = json.loads(r['Payload'].read())
        status = resp.get('statusCode', '?')
        print(f"  Status: {status}")
        
        if status == 200:
            body = json.loads(resp.get('body', '{}'))
            situations = body.get('situations', [])
            print(f"  Situations found: {len(situations)}")
            for s in situations[:2]:
                title = s.get('title', 'untitled')
                conf = s.get('confidence', '?')
                docs = s.get('document_count', 0)
                print(f"    - {title} ({conf}, {docs} docs)")
        else:
            body = json.loads(resp.get('body', '{}'))
            error = body.get('error', body.get('message', 'Unknown'))
            print(f"  ERROR: {str(error)[:150]}")
    except Exception as e:
        print(f"  EXCEPTION: {str(e)[:150]}")
