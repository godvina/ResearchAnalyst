"""Trigger the full command center analysis to restore all scores."""
import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# The command center engine is triggered via POST /case-files/{id}/command-center
# with bypass_cache to force fresh computation
print("Triggering command center computation...")
body = json.dumps({'bypass_cache': True}).encode()
req = urllib.request.Request(API + '/case-files/' + CASE_ID + '/command-center', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
try:
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read().decode())
    print(f"Status: {data.get('status', '?')}")
    print(f"Keys: {list(data.keys())[:15]}")
    if 'indicators' in data:
        for ind in data['indicators']:
            print(f"  {ind.get('key','?'):25s} = {ind.get('score',0)}")
    if 'prosecution_readiness' in data:
        print(f"Prosecution: {data['prosecution_readiness']}")
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        err = e.read().decode()[:500]
        print(err)
    # Try GET instead
    print("\nTrying GET /command-center...")
    req2 = urllib.request.Request(API + '/case-files/' + CASE_ID + '/command-center')
    try:
        resp2 = urllib.request.urlopen(req2, timeout=120)
        data2 = json.loads(resp2.read().decode())
        print(f"Keys: {list(data2.keys())[:15]}")
    except Exception as e2:
        print(f"GET also failed: {e2}")
        if hasattr(e2, 'read'):
            print(e2.read().decode()[:300])
