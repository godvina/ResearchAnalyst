import json, urllib.request
url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/patterns"
req = urllib.request.Request(url, data=json.dumps({"graph": True}).encode(), headers={"Content-Type": "application/json"}, method="POST")
resp = urllib.request.urlopen(req, timeout=28)
d = json.loads(resp.read())
locs = [n for n in d.get("nodes", []) if n.get("type") == "location"]
locs.sort(key=lambda x: x.get("degree", 0), reverse=True)
print(f"Total location nodes: {len(locs)}")
print("Location names on map:")
for n in locs[:30]:
    print(f"  {n['name']} (degree: {n.get('degree', 0)})")

# Check if Teterboro, Islip exist
for search in ["Teterboro", "Islip", "PBI", "Palm Beach", "Larry Visoski"]:
    matches = [n for n in d.get("nodes", []) if search.lower() in n["name"].lower()]
    print(f"\nSearch '{search}': {len(matches)} matches")
    for m in matches[:5]:
        print(f"  {m['name']} (type: {m['type']}, degree: {m.get('degree', 0)})")
