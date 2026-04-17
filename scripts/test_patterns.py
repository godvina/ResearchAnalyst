"""Test the patterns API endpoint."""
import json
import urllib.request

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"

print("Triggering pattern discovery...")
req = urllib.request.Request(
    f"{API}/case-files/{CASE_ID}/patterns",
    method="POST",
    headers={"Content-Type": "application/json"},
    data=b"{}",
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
        print(f"Graph patterns: {data.get('graph_patterns_count', 0)}")
        print(f"Vector patterns: {data.get('vector_patterns_count', 0)}")
        print(f"Total: {data.get('combined_count', 0)}")
        for p in data.get("patterns", [])[:5]:
            names = [e.get("name", "") for e in p.get("entities_involved", [])][:5]
            print(f"  {p.get('connection_type')}: {names} (conf={p.get('confidence_score')})")
except urllib.error.HTTPError as e:
    body = e.read().decode() if e.fp else ""
    print(f"HTTP {e.code}: {body[:500]}")
except Exception as e:
    print(f"Error: {e}")
