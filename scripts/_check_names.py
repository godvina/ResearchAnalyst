"""Quick check: compare Neptune entity names with S3 photo names."""
import requests, json

url = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'

# Get graph nodes
resp = requests.post(f'{url}/case-files/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/patterns', json={'graph': True})
data = resp.json()
persons = [n for n in data.get('nodes', []) if n.get('type') == 'person']
print('=== Person nodes from Neptune ===')
for p in sorted(persons, key=lambda x: x.get('degree', 0), reverse=True)[:20]:
    print(f'  "{p["name"]}" (degree={p.get("degree",0)})')

# Get entity photos
resp2 = requests.get(f'{url}/case-files/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/entity-photos')
photos = resp2.json()
print('\n=== Entity photo names from S3 ===')
for name in photos.get('entity_photos', {}).keys():
    print(f'  "{name}"')

# Check matches
photo_names = set(photos.get('entity_photos', {}).keys())
neptune_names = set(p['name'] for p in persons)
matches = photo_names & neptune_names
print(f'\n=== Matches: {len(matches)} / {len(photo_names)} photos ===')
for m in matches:
    print(f'  MATCH: "{m}"')
misses = photo_names - neptune_names
if misses:
    print(f'\n=== Photo names NOT in Neptune ({len(misses)}) ===')
    for m in misses:
        print(f'  MISS: "{m}"')
