import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

req = urllib.request.Request(API + '/case-files/' + CASE_ID + '/typology/transportation_movement/findings')
resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read().decode())
situations = data.get('situations', [])
print(f"Transportation & Movement: {len(situations)} incidents")
for i, s in enumerate(situations):
    entities = s.get('entities', [])
    entity_names = [e['name'] for e in entities]
    locations = [e['name'] for e in entities if e.get('type') == 'location']
    flags = s.get('flags_triggered', [])
    print(f"\n  Inc {i+1}: {s['title']}")
    print(f"    Entities: {entity_names}")
    print(f"    Locations: {locations}")
    print(f"    Flags: {flags}")
    print(f"    Docs: {s.get('document_count', 0)}, Rels: {s.get('relationship_count', 0)}, Confidence: {s.get('confidence', '?')}")
