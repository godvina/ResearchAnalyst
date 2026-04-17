"""Check patterns for v2d case (batch size 1)."""
import urllib.request
import json

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "03dfc666-0dc2-40e4-ac47-11c01f48ac09"

url = f"{API_URL}/case-files/{CASE_ID}/patterns"
req = urllib.request.Request(url, data=json.dumps({}).encode(), method="POST",
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode())
        patterns = data.get("patterns", [])
        print(f"Patterns: {len(patterns)}")
        print(f"Graph: {data.get('graph_patterns_count', 0)}")
        print(f"Vector: {data.get('vector_patterns_count', 0)}")
        for p in patterns[:15]:
            e = p.get("entities_involved", [{}])[0]
            print(f"  {e.get('name', '?')} ({e.get('type', '?')}) novelty={p.get('novelty_score', 0)}")
except urllib.error.HTTPError as e:
    body = e.read().decode() if e.fp else ""
    print(f"HTTP {e.code}: {body[:300]}")
