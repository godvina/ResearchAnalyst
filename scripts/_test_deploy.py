"""Quick test of deployed Lambda with debug output."""
import boto3, json

c = boto3.client('lambda', region_name='us-east-1')
FN = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'

# Nightfall case
e = {
    'httpMethod': 'GET',
    'path': '/case-files/0b24a307-a674-41b6-8d22-581c4a4aa566/typology/recruitment_grooming/findings',
    'pathParameters': {'id': '0b24a307-a674-41b6-8d22-581c4a4aa566'},
    'queryStringParameters': {},
    'headers': {'content-type': 'application/json'}
}

r = c.invoke(FunctionName=FN, Payload=json.dumps(e).encode())
resp = json.loads(r['Payload'].read())
print("statusCode:", resp.get('statusCode'))
print("FunctionError:", r.get('FunctionError'))
body_str = resp.get('body', '{}')
body = json.loads(body_str) if body_str else {}
print("body keys:", list(body.keys())[:15])
print("_debug_entity_count:", body.get('_debug_entity_count', 'MISSING'))
print("situations:", len(body.get('situations', [])))
print("error:", body.get('error', 'none'))
print("\nFull body (first 400 chars):")
print(json.dumps(body, indent=2)[:400])
