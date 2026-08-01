import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'

sql = """SELECT canonical_name, entity_type, occurrence_count 
         FROM entities 
         WHERE case_file_id='0b24a307-a674-41b6-8d22-581c4a4aa566'::uuid 
         AND entity_type IN ('location','address') 
         AND occurrence_count >= 2 
         ORDER BY occurrence_count DESC LIMIT 40"""

body = json.dumps({'sql': sql}).encode()
req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read().decode())
for r in data.get('rows', []):
    print(f"  {r[0]:30s}  {r[1]:10s}  count={r[2]}")
