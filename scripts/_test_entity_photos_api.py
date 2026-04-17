"""Test entity photos API response size and content."""
import requests, json

url = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
case_id = 'ed0b6c27-3b6b-4255-b9d0-efe8f4383a99'

resp = requests.get(f'{url}/case-files/{case_id}/entity-photos')
print(f'Status: {resp.status_code}')
print(f'Response size: {len(resp.text)} bytes ({len(resp.text)/1024:.1f} KB)')

data = resp.json()
print(f'Keys: {list(data.keys())}')
print(f'photo_count: {data.get("photo_count")}')

for name, val in data.get('entity_photos', {}).items():
    prefix = val[:50] if val else 'None'
    print(f'  {name}: {len(val)} chars, starts with: {prefix}')
