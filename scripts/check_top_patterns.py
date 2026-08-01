import json, urllib.request
url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/top-patterns"
resp = urllib.request.urlopen(url, timeout=28)
d = json.loads(resp.read())
patterns = d.get("patterns", [])
print(f"{len(patterns)} patterns")
for p in patterns:
    q = p.get("question", "")[:60]
    raw = p.get("raw_pattern", {})
    entities = raw.get("entities", [])
    print(f"\n  idx={p.get('index')} conf={p.get('confidence')} q={q}")
    print(f"  raw_pattern keys: {list(raw.keys())}")
    print(f"  entities ({len(entities)}): {entities[:5]}")
