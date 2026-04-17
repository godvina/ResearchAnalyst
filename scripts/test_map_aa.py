"""Test map locations for Ancient Aliens and Epstein Combined."""
import urllib.request
import json

cases = {
    "Ancient Aliens": "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7",
    "Epstein Combined": "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
    "Epstein Main": "7f05e8d5-4492-4f19-8894-25367606db96",
}

for name, cid in cases.items():
    url = f"https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/{cid}/patterns"
    data = json.dumps({"graph": True}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode())
        nodes = d.get("nodes", [])
        locations = [n for n in nodes if n.get("type") == "location"]
        print(f"{name}: {len(nodes)} nodes, {len(locations)} locations")
        for loc in locations[:5]:
            print(f"  {loc['name']} (degree: {loc.get('degree', 0)})")
    except Exception as e:
        print(f"{name}: ERROR - {e}")
    print()
