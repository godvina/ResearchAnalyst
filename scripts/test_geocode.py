import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# Try more specific names
locations = ['Barcelona, Spain', 'Antalya, Turkey', 'Casablanca, Morocco', 
             'Morocco', 'Barcelona', 'Antalya']
body = json.dumps({'locations': locations}).encode()
req = urllib.request.Request(API + '/case-files/' + CASE_ID + '/geocode', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read().decode())
geo = data.get('geocoded', {})
for k, v in geo.items():
    print(f"  {k}: lat={v.get('lat')}, lng={v.get('lng')}")
print(f"Resolved: {data.get('resolved', 0)}/{data.get('total', 0)}")
