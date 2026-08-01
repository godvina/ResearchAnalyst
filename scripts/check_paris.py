import boto3, json

LAMBDA_NAME = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'
label = f"Entity_{CASE_ID}"

client = boto3.client('lambda', region_name='us-east-1')

# Check what Paris looks like in Neptune
q = f"g.V().has('{label}', 'canonical_name', 'Paris').valueMap(true)"
event = {'action': 'run_gremlin', 'gremlin': q, 'case_id': CASE_ID}
resp = client.invoke(FunctionName=LAMBDA_NAME, InvocationType='RequestResponse',
                     Payload=json.dumps(event).encode())
result = json.loads(resp['Payload'].read().decode())
print("Paris vertex:", json.dumps(result, indent=2, default=str)[:500])

# Check degree
q2 = f"g.V().has('{label}', 'canonical_name', 'Paris').bothE().count()"
event2 = {'action': 'run_gremlin', 'gremlin': q2, 'case_id': CASE_ID}
resp2 = client.invoke(FunctionName=LAMBDA_NAME, InvocationType='RequestResponse',
                      Payload=json.dumps(event2).encode())
result2 = json.loads(resp2['Payload'].read().decode())
print("Paris edge count:", result2)

# Check total location count
q3 = f"g.V().hasLabel('{label}').has('entity_type', 'location').count()"
event3 = {'action': 'run_gremlin', 'gremlin': q3, 'case_id': CASE_ID}
resp3 = client.invoke(FunctionName=LAMBDA_NAME, InvocationType='RequestResponse',
                      Payload=json.dumps(event3).encode())
result3 = json.loads(resp3['Payload'].read().decode())
print("Total location vertices:", result3)
