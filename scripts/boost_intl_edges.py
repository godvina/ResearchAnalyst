"""Add more international travel edges to Neptune to strengthen pattern detection.
The pattern engine needs multiple persons sharing locations to generate patterns.
"""
import boto3
import json

LAMBDA_NAME = 'ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'
label = f"Entity_{CASE_ID}"

client = boto3.client('lambda', region_name='us-east-1')

def run_gremlin(query):
    event = {'action': 'run_gremlin', 'gremlin': query, 'case_id': CASE_ID}
    resp = client.invoke(FunctionName=LAMBDA_NAME, InvocationType='RequestResponse',
                         Payload=json.dumps(event).encode())
    return json.loads(resp['Payload'].read().decode())

# More persons connected to international locations
# Need 3+ persons per location for pattern detection to fire
additional_edges = [
    # Paris — make it a major convergence (4+ persons)
    ('Victor Nash', 'Paris', 'TRAVELED_TO'),
    ('Sandra Voss', 'Paris', 'TRAVELED_TO'),
    ('Jonathan Mercer', 'Paris', 'TRAVELED_TO'),
    # Morocco/Marrakech — 3+ persons
    ('Victor Nash', 'Marrakech', 'TRAVELED_TO'),
    ('Sandra Voss', 'Morocco', 'TRAVELED_TO'),
    # Tokyo — 3+ persons
    ('Victor Nash', 'Tokyo', 'TRAVELED_TO'),
    ('Sandra Voss', 'Tokyo', 'TRAVELED_TO'),
    # Barcelona — 3+ persons  
    ('Catherine Sterling', 'Barcelona', 'TRAVELED_TO'),
    ('Victor Nash', 'Barcelona', 'TRAVELED_TO'),
    # Moscow — add more
    ('Catherine Sterling', 'Moscow', 'TRAVELED_TO'),
    ('Daniel Whitmore', 'Moscow', 'TRAVELED_TO'),
    # Dubai (new — add vertex first)
    ('Marcus Blackwell', 'Dubai', 'TRAVELED_TO'),
    ('Catherine Sterling', 'Dubai', 'TRAVELED_TO'),
    ('Victor Nash', 'Dubai', 'TRAVELED_TO'),
]

# First add Dubai vertex
print("Adding Dubai vertex...")
q = (f"g.V().has('{label}', 'canonical_name', 'Dubai').fold()"
     f".coalesce(unfold(), addV('{label}')"
     f".property('canonical_name', 'Dubai')"
     f".property('entity_type', 'location')"
     f".property('occurrence_count', 5)"
     f".property('case_id', '{CASE_ID}'))")
result = run_gremlin(q)
print(f"  Dubai: {result.get('status', result.get('error', '?'))}")

# Ensure all persons exist as vertices (they should from the original load)
persons = set(e[0] for e in additional_edges)
for person in persons:
    q = (f"g.V().has('{label}', 'canonical_name', '{person}').fold()"
         f".coalesce(unfold(), addV('{label}')"
         f".property('canonical_name', '{person}')"
         f".property('entity_type', 'person')"
         f".property('occurrence_count', 5)"
         f".property('case_id', '{CASE_ID}'))")
    result = run_gremlin(q)
    print(f"  Person {person}: {result.get('status', result.get('error', '?'))}")

print("\nAdding travel edges...")
for source, target, rel_type in additional_edges:
    q = (f"g.V().has('{label}', 'canonical_name', '{source}')"
         f".as('s')"
         f".V().has('{label}', 'canonical_name', '{target}')"
         f".coalesce("
         f"  __.inE('RELATED_TO').where(outV().as('s')),"
         f"  addE('RELATED_TO').from('s').property('relationship_type', '{rel_type}')"
         f")")
    result = run_gremlin(q)
    status = result.get('status', result.get('error', '?'))
    print(f"  {source} → {target}: {status}")

print("\nDone. Refresh map + Route Intel to see international patterns.")
