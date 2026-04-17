"""Test geocode endpoint directly."""
import urllib.request
import json

cid = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
url = f"https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/{cid}/geocode"
body = json.dumps({"locations": ["New York", "Paris", "Washington", "London"]}).encode()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as resp:
    d = json.loads(resp.read().decode())
print(json.dumps(d, indent=2))
