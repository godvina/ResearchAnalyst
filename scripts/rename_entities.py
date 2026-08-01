"""
Rename real company names in Aurora via the case-files API admin endpoint.
Uses the live Lambda which has VPC database access.
"""
import urllib.request
import json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# Map of real company names → fictional replacements
COMPANY_RENAMES = {
    '3M': 'Trimark Industries',
    'JPM': 'Pinnacle Capital',
    'JP Morgan': 'Pinnacle Capital',
    'JPMorgan': 'Pinnacle Capital',
    'JPMorgan Chase': 'Pinnacle Capital',
    'Goldman Sachs': 'Meridian Partners',
    'Goldman': 'Meridian Partners',
    'Deutsche Bank': 'Vereinsbank AG',
    'Citibank': 'Atlantic National Bank',
    'Citigroup': 'Atlantic National Group',
    'Bear Stearns': 'Northern Trust Securities',
    'Wexner': 'Harrington',
    'Les Wexner': 'Douglas Harrington',
    'Leslie Wexner': 'Douglas Harrington',
    "Victoria's Secret": 'Luxe Apparel',
    'The Limited': 'Prestige Brands',
    'L Brands': 'Harrington Brands',
    'Microsoft': 'Vertex Software',
    'Google': 'Nexus Digital',
    'Apple': 'Orion Devices',
    'Amazon': 'Titan Commerce',
    'Tesla': 'Volt Motors',
    'Boeing': 'Skyward Aerospace',
    'Lockheed': 'Centurion Defense',
}


def api_call(method, path, body=None):
    url = API + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {'error': str(e)}


def main():
    print("=== Entity Rename via API ===")
    print(f"Case: {CASE_ID}")
    print(f"Renames: {len(COMPANY_RENAMES)}")
    print()

    # Use the admin/rename-entity endpoint
    payload = {
        'case_id': CASE_ID,
        'renames': COMPANY_RENAMES,
    }

    resp = api_call('POST', '/admin/rename-entities', payload)
    if 'error' in resp:
        print(f"API endpoint not available: {resp['error']}")
        print("\nFalling back to direct SQL via Lambda invoke...")
        rename_via_lambda()
    else:
        print(f"Result: {json.dumps(resp, indent=2)}")


def rename_via_lambda():
    """Invoke Lambda directly with a rename SQL payload."""
    import boto3

    client = boto3.client('lambda', region_name='us-east-1')
    LAMBDA_NAME = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

    # Build the rename event — the case_files dispatcher handles /admin/rename-entities
    event = {
        'httpMethod': 'POST',
        'path': '/admin/rename-entities',
        'pathParameters': {'proxy': 'admin/rename-entities'},
        'body': json.dumps({
            'case_id': CASE_ID,
            'renames': COMPANY_RENAMES,
        }),
        'headers': {'Content-Type': 'application/json'},
    }

    print("Invoking Lambda...")
    resp = client.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType='RequestResponse',
        Payload=json.dumps(event).encode(),
    )
    result = json.loads(resp['Payload'].read().decode())
    status = result.get('statusCode', 0)
    body = json.loads(result.get('body', '{}'))
    print(f"Status: {status}")
    print(f"Result: {json.dumps(body, indent=2)[:500]}")


if __name__ == '__main__':
    main()
