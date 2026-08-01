import json, urllib.request
url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/geocode"
req = urllib.request.Request(url, data=json.dumps({"locations": ["Teterboro", "Islip", "PBI", "Palm Beach", "KTEB"]}).encode(), headers={"Content-Type": "application/json"}, method="POST")
resp = urllib.request.urlopen(req, timeout=28)
d = json.loads(resp.read())
print("Geocoded:", json.dumps(d.get("geocoded", {}), indent=2))
print("Resolved:", d.get("resolved", 0), "/", d.get("total", 0))
