"""Check Epstein Main case state."""
import urllib.request, json
API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
MAIN_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
req = urllib.request.Request(f"{API}/case-files/{MAIN_ID}")
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode())
print(f"document_count: {data.get('document_count')}")
print(f"entity_count:   {data.get('entity_count')}")
print(f"status:         {data.get('status')}")
