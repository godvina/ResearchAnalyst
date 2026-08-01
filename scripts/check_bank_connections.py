import boto3, json

LAMBDA = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'
label = f"Entity_{CASE_ID}"
client = boto3.client('lambda', region_name='us-east-1')

# Check what Helvetia Private Bank connects to
q = f"g.V().has('{label}', 'canonical_name', 'Helvetia Private Bank Acct CHE-4419').both('RELATED_TO').values('canonical_name')"
event = {'action': 'run_gremlin', 'gremlin': q, 'case_id': CASE_ID}
resp = client.invoke(FunctionName=LAMBDA, InvocationType='RequestResponse', Payload=json.dumps(event).encode())
result = json.loads(resp['Payload'].read().decode())
print("Helvetia Bank connections:", result)

# Check what entities are in the Financial Control findings
import urllib.request
API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
req = urllib.request.Request(API + '/case-files/' + CASE_ID + '/typology/financial_control/findings')
resp2 = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp2.read().decode())
situations = data.get('situations', [])
print(f"\nFinancial Control: {len(situations)} incidents")
for i, s in enumerate(situations):
    entities = [e['name'] for e in s.get('entities', [])]
    has_location = any(e.get('type') == 'location' for e in s.get('entities', []))
    print(f"  Inc {i+1}: {s['title'][:50]} | Entities: {entities} | Has location: {has_location}")
