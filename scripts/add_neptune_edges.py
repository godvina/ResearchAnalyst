"""Add international travel edges to Neptune via Lambda invoke.
Uses the neptune_aurora_sync Lambda which has VPC access to Neptune.
"""
import boto3
import json

LAMBDA_NAME = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

client = boto3.client('lambda', region_name='us-east-1')

# International travel edges to add
edges = [
    ('Marcus Blackwell', 'Paris', 'TRAVELED_TO'),
    ('Marcus Blackwell', 'Morocco', 'TRAVELED_TO'),
    ('Marcus Blackwell', 'Tokyo', 'TRAVELED_TO'),
    ('Marcus Blackwell', 'Moscow', 'TRAVELED_TO'),
    ('Marcus Blackwell', 'Barcelona', 'TRAVELED_TO'),
    ('Catherine Sterling', 'Paris', 'TRAVELED_TO'),
    ('Catherine Sterling', 'Morocco', 'TRAVELED_TO'),
    ('Catherine Sterling', 'Philippines', 'TRAVELED_TO'),
    ('Catherine Sterling', 'Antalya', 'TRAVELED_TO'),
    ('Daniel Whitmore', 'Paris', 'TRAVELED_TO'),
    ('Daniel Whitmore', 'Morocco', 'TRAVELED_TO'),
    ('Daniel Whitmore', 'Tokyo', 'TRAVELED_TO'),
    ('Patricia Harmon', 'Paris', 'TRAVELED_TO'),
    ('Patricia Harmon', 'Barcelona', 'TRAVELED_TO'),
]

# First ensure the location vertices exist
label = f"Entity_{CASE_ID}"
locations = ['Paris', 'Morocco', 'Tokyo', 'Moscow', 'Barcelona', 'Antalya', 'Marrakech']

print("=== Adding Neptune Vertices (locations) ===")
for loc in locations:
    # Upsert vertex
    gremlin = (
        f"g.V().has('{label}', 'canonical_name', '{loc}').fold()"
        f".coalesce(unfold(), addV('{label}')"
        f".property('canonical_name', '{loc}')"
        f".property('entity_type', 'location')"
        f".property('occurrence_count', 5)"
        f".property('case_id', '{CASE_ID}'))"
    )
    event = {'action': 'run_gremlin', 'gremlin': gremlin, 'case_id': CASE_ID}
    resp = client.invoke(FunctionName=LAMBDA_NAME, InvocationType='RequestResponse',
                         Payload=json.dumps(event).encode())
    result = json.loads(resp['Payload'].read().decode())
    status = result.get('statusCode', result.get('error', 'ok'))
    print(f"  {loc}: {status}")

print("\n=== Adding Neptune Edges (travel) ===")
for source, target, rel_type in edges:
    # Add edge between person and location
    gremlin = (
        f"g.V().has('{label}', 'canonical_name', '{source}')"
        f".as('s')"
        f".V().has('{label}', 'canonical_name', '{target}')"
        f".coalesce("
        f"  __.inE('RELATED_TO').where(outV().as('s')),"
        f"  addE('RELATED_TO').from('s').property('relationship_type', '{rel_type}')"
        f")"
    )
    event = {'action': 'run_gremlin', 'gremlin': gremlin, 'case_id': CASE_ID}
    resp = client.invoke(FunctionName=LAMBDA_NAME, InvocationType='RequestResponse',
                         Payload=json.dumps(event).encode())
    result = json.loads(resp['Payload'].read().decode())
    status = result.get('statusCode', result.get('error', 'ok'))
    print(f"  {source} → {target}: {status}")

print("\nDone. Refresh map to see international locations.")
