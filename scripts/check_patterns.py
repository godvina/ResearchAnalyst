import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

body = json.dumps({'travel_intelligence': True}).encode()
req = urllib.request.Request(API + '/case-files/' + CASE_ID + '/patterns', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
resp = urllib.request.urlopen(req, timeout=60)
data = json.loads(resp.read().decode())

insights = data.get('insights', [])
print(f"Total patterns: {len(insights)}")
print()
for i, ins in enumerate(insights):
    locs = ins.get('locations', [])
    persons = ins.get('persons', [])
    intl = [l for l in locs if l in ['Paris','Tokyo','Moscow','Barcelona','Morocco','Dubai','Antalya','Marrakech']]
    marker = ' *** INTERNATIONAL ***' if intl else ''
    print(f"  {i+1}. [{ins.get('type','?')}] {ins.get('title','?')[:60]}{marker}")
    print(f"     Locations: {locs[:6]}")
    print(f"     Persons: {persons[:4]}")
    print()
