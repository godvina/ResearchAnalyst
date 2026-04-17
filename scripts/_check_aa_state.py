"""Check Ancient Aliens case state — documents, entities, Neptune."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"

url = f"{API}/case-files/{CASE_ID}"
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode())
print(f"document_count:     {data.get('document_count')}")
print(f"entity_count:       {data.get('entity_count')}")
print(f"relationship_count: {data.get('relationship_count')}")
print(f"status:             {data.get('status')}")
