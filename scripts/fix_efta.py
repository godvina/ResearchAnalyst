import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# Delete trawler alerts that mention EFTA or Western Digital
sql = "DELETE FROM trawler_alerts WHERE case_id='" + CASE_ID + "'::uuid AND (entity_names::text LIKE '%EFTA%' OR title LIKE '%EFTA%' OR entity_names::text LIKE '%Western Digital%' OR title LIKE '%Western Digital%')"
body = json.dumps({'sql': sql}).encode()
req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
try:
    resp = urllib.request.urlopen(req, timeout=30)
    print('Deleted:', json.loads(resp.read().decode()))
except Exception as e:
    print('Error:', e)
    if hasattr(e, 'read'):
        print(e.read().decode()[:400])
