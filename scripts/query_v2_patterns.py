"""Query patterns API for the v2 demo case."""
import urllib.request
import json

CASE_ID = "245f5f93-8121-4392-b36b-83ddbd7382f4"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

# Run pattern discovery
url = f"{API_URL}/case-files/{CASE_ID}/patterns"
req = urllib.request.Request(url, data=json.dumps({}).encode(), method="POST",
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode())
        patterns = data.get("patterns", [])
        print(f"Patterns found: {len(patterns)}")
        print(f"Graph patterns: {data.get('graph_patterns_count', 0)}")
        print(f"Vector patterns: {data.get('vector_patterns_count', 0)}")
        for p in patterns[:10]:
            entities = p.get("entities_involved", [])
            names = [(e.get("name", "?"), e.get("type", "?")) for e in entities[:3]]
            print(f"  {p.get('connection_type', '?')}: {names}")
except urllib.error.HTTPError as e:
    body = e.read().decode() if e.fp else ""
    print(f"HTTP {e.code}: {body[:500]}")
except Exception as e:
    print(f"Error: {e}")
