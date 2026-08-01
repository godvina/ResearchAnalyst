import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# Test exact names from the Neptune response
locations = ['Paris', 'Tokyo', 'Moscow', 'Barcelona', 'Morocco', 'Dubai', 'Antalya',
             'New York', 'Palm Beach', 'Miami, FL', 'CDG', 'Philippines', 'Malaysia']
body = json.dumps({'locations': locations}).encode()
req = urllib.request.Request(API + '/case-files/' + CASE_ID + '/geocode', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read().decode())
geo = data.get('geocoded', {})
unresolved = data.get('unresolved', [])
print(f"Resolved: {data.get('resolved', 0)}/{data.get('total', 0)}")
print("\nGeocoded:")
for k, v in sorted(geo.items()):
    print(f"  {k:25s} → {v.get('lat'):.2f}, {v.get('lng'):.2f}")
print(f"\nUnresolved: {unresolved}")
