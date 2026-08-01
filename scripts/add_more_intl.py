"""Add more international travel edges to create distinct co-travel patterns.
Need: Victor Nash circuit, Daniel Whitmore circuit, multi-person convergences.
"""
import boto3, json

LAMBDA = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'
label = f"Entity_{CASE_ID}"
client = boto3.client('lambda', region_name='us-east-1')

def gremlin(q):
    event = {'action': 'run_gremlin', 'gremlin': q, 'case_id': CASE_ID}
    resp = client.invoke(FunctionName=LAMBDA, InvocationType='RequestResponse', Payload=json.dumps(event).encode())
    return json.loads(resp['Payload'].read().decode())

# Add more edges to create 2-3 more international patterns
edges = [
    # Victor Nash international circuit (creates "Victor Nash International Travel" pattern)
    ('Victor Nash', 'Dubai', 'TRAVELED_TO'),  # already exists but ensure
    ('Victor Nash', 'Moscow', 'TRAVELED_TO'),
    # Marcus to more international (fills out his travel network)
    ('Marcus Blackwell', 'Antalya', 'TRAVELED_TO'),
    ('Marcus Blackwell', 'Malaysia', 'TRAVELED_TO'),
    # Patricia Harmon + Marcus co-travel (new pattern)
    ('Patricia Harmon', 'Morocco', 'TRAVELED_TO'),
    ('Patricia Harmon', 'Dubai', 'TRAVELED_TO'),
    ('Patricia Harmon', 'Tokyo', 'TRAVELED_TO'),
    # Daniel Whitmore broader (fills his circuit)
    ('Daniel Whitmore', 'Barcelona', 'TRAVELED_TO'),
    ('Daniel Whitmore', 'Dubai', 'TRAVELED_TO'),
    ('Daniel Whitmore', 'Antalya', 'TRAVELED_TO'),
]

print("Adding edges...")
for source, target, rel_type in edges:
    q = (f"g.V().has('{label}', 'canonical_name', '{source}')"
         f".as('s')"
         f".V().has('{label}', 'canonical_name', '{target}')"
         f".coalesce("
         f"  __.inE('RELATED_TO').where(outV().as('s')),"
         f"  addE('RELATED_TO').from('s').property('relationship_type', '{rel_type}')"
         f")")
    result = gremlin(q)
    print(f"  {source} → {target}: {result.get('status', result.get('error', '?'))}")

print("\nDone.")
