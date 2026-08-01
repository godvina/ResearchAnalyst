"""Check what the patterns API returns for both cases."""
import urllib.request, json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

for name, cid in [("Combined", "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"), ("Main", "7f05e8d5-4492-4f19-8894-25367606db96")]:
    url = f"{API}/case-files/{cid}/patterns"
    req = urllib.request.Request(url, data=json.dumps({"graph": True}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=25)
        data = json.loads(resp.read())
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        total = data.get("total_nodes", "?")
        print(f"{name}: {len(nodes)} nodes returned, {len(edges)} edges, total_nodes={total}")
        
        types = {}
        for n in nodes:
            t = n.get("type", "?")
            types[t] = types.get(t, 0) + 1
        for t, c in sorted(types.items(), key=lambda x: -x[1])[:5]:
            print(f"  {t}: {c}")
        
        locs = [n for n in nodes if n.get("type") == "location"]
        print(f"  Locations: {len(locs)}")
        for l in locs[:5]:
            print(f"    {l.get('name', '?')}")
    except Exception as e:
        print(f"{name}: ERROR - {str(e)[:200]}")
