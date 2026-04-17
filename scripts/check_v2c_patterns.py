"""Check patterns for v2c case."""
import urllib.request
import json

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "18282e5e-6d9e-4498-b198-39dbfd5ddd3e"

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
            entities = p.get("entities_involved", [])
            name = entities[0].get("name", "?") if entities else "?"
            etype = entities[0].get("type", "?") if entities else "?"
            novelty = p.get("novelty_score", 0)
            print(f"  {name} ({etype}) novelty={novelty}")
except urllib.error.HTTPError as e:
    body = e.read().decode() if e.fp else ""
    print(f"HTTP {e.code}: {body[:300]}")
