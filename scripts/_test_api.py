import urllib.request, json
req = urllib.request.Request("https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files")
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
print(f"Cases: {len(data.get('case_files', []))}")
print("API working!")
