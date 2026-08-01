import boto3, json

client = boto3.client('lambda', region_name='us-east-1')
LAMBDA = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'
label = f"Entity_{CASE_ID}"

# Rename EFTA to Eastern Pacific Trust Ltd in Neptune
q = f"g.V().has('{label}', 'canonical_name', 'EFTA').property('canonical_name', 'Eastern Pacific Trust Ltd')"
event = {'action': 'run_gremlin', 'gremlin': q, 'case_id': CASE_ID}
resp = client.invoke(FunctionName=LAMBDA, InvocationType='RequestResponse', Payload=json.dumps(event).encode())
print('EFTA rename:', json.loads(resp['Payload'].read().decode()))
