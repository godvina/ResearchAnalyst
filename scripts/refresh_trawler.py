"""Clear old trawler alerts and trigger a fresh trawl for better Did You Know cards."""
import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# 1. Clear all existing trawler alerts for this case
sql = "DELETE FROM trawler_alerts WHERE case_id='" + CASE_ID + "'::uuid"
body = json.dumps({'sql': sql}).encode()
req = urllib.request.Request(API + '/admin/run-migration', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
try:
    resp = urllib.request.urlopen(req, timeout=30)
    print('Cleared old alerts:', json.loads(resp.read().decode()))
except Exception as e:
    print('Clear error:', e)

# 2. Trigger a fresh trawl
body2 = json.dumps({}).encode()
req2 = urllib.request.Request(API + '/case-files/' + CASE_ID + '/trawl', data=body2, method='POST')
req2.add_header('Content-Type', 'application/json')
try:
    resp2 = urllib.request.urlopen(req2, timeout=60)
    print('Trawl result:', json.loads(resp2.read().decode()))
except Exception as e:
    print('Trawl error:', e)
    if hasattr(e, 'read'):
        print(e.read().decode()[:300])
