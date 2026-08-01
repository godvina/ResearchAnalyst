"""Add international travel relationships to create compelling patterns on the map."""
import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# Add relationships: person → location (travel connections)
relationships = [
    # Marcus Blackwell international circuit
    ('Marcus Blackwell', 'Paris', 'traveled_to'),
    ('Marcus Blackwell', 'Morocco', 'traveled_to'),
    ('Marcus Blackwell', 'Tokyo', 'traveled_to'),
    ('Marcus Blackwell', 'Moscow', 'traveled_to'),
    ('Marcus Blackwell', 'Barcelona', 'traveled_to'),
    # Catherine Sterling international circuit
    ('Catherine Sterling', 'Paris', 'traveled_to'),
    ('Catherine Sterling', 'Morocco', 'traveled_to'),
    ('Catherine Sterling', 'Philippines', 'traveled_to'),
    ('Catherine Sterling', 'Antalya', 'traveled_to'),
    # Other associates
    ('Daniel Whitmore', 'Paris', 'traveled_to'),
    ('Daniel Whitmore', 'Morocco', 'traveled_to'),
    ('Daniel Whitmore', 'Tokyo', 'traveled_to'),
    ('Patricia Harmon', 'Paris', 'traveled_to'),
    ('Patricia Harmon', 'Barcelona', 'traveled_to'),
]

# Also ensure Morocco and Tokyo exist as entities
new_entities = [
    ('Morocco', 'location'),
    ('Tokyo', 'location'),
    ('Marrakech', 'location'),
]

# Insert entities first
for name, etype in new_entities:
    sql = f"INSERT INTO entities (case_file_id, canonical_name, entity_type, occurrence_count) VALUES ('{CASE_ID}'::uuid, '{name}', '{etype}', 5) ON CONFLICT DO NOTHING"
    body = json.dumps({'sql': sql}).encode()
    req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        print(f'Entity {name}: {json.loads(resp.read().decode()).get("rowcount", 0)}')
    except Exception as e:
        print(f'Entity {name} error: {e}')

# Insert relationships
for source, target, rel_type in relationships:
    sql = f"INSERT INTO relationships (case_file_id, source_entity, target_entity, relationship_type, occurrence_count) VALUES ('{CASE_ID}'::uuid, '{source}', '{target}', '{rel_type}', 3) ON CONFLICT DO NOTHING"
    body = json.dumps({'sql': sql}).encode()
    req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        rc = result.get('rowcount', 0)
        if rc != 0:
            print(f'  {source} → {target}: added')
    except Exception as e:
        print(f'  {source} → {target}: error {e}')

# Clear pattern caches so new patterns are generated
sql = f"DELETE FROM top_pattern_cache WHERE case_file_id='{CASE_ID}'::uuid"
body = json.dumps({'sql': sql}).encode()
req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print(f'\nCleared pattern cache: {json.loads(resp.read().decode())}')
except:
    pass

print('\nDone. Refresh the map and click Route Intel to see international patterns.')
