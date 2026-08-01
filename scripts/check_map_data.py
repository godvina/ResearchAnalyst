import urllib.request, json

API = 'https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1'
CASE_ID = '0b24a307-a674-41b6-8d22-581c4a4aa566'

# Call the same endpoint the map uses
body = json.dumps({'graph': True}).encode()
req = urllib.request.Request(API + '/case-files/' + CASE_ID + '/patterns', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
resp = urllib.request.urlopen(req, timeout=60)
data = json.loads(resp.read().decode())

nodes = data.get('nodes', [])
locations = [n for n in nodes if n.get('type') == 'location']
print(f"Total nodes: {len(nodes)}, Locations: {len(locations)}")
print("\nTop 30 locations by degree:")
locations.sort(key=lambda x: x.get('degree', 0), reverse=True)
for loc in locations[:30]:
    print(f"  {loc['name']:30s} degree={loc.get('degree',0)}")

# Check if Paris is in the list
intl = ['Paris', 'Tokyo', 'Moscow', 'Barcelona', 'Marrakech', 'Morocco', 'Dubai', 'Antalya']
print("\n\nInternational locations in response:")
for name in intl:
    found = [n for n in locations if n['name'] == name]
    if found:
        print(f"  {name}: YES (degree={found[0].get('degree',0)})")
    else:
        print(f"  {name}: NOT IN RESPONSE")
