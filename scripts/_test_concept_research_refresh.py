"""Test concept research with cache bypass."""
import urllib.request
import json

url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/pattern-library/concept-research/domain/ancient_mysteries?refresh=true"

try:
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=35)
    data = json.loads(resp.read())
    print("SUCCESS! Status 200")
    
    if "briefing" in data:
        b = data["briefing"]
        print(f"Codename: {b.get('codename', '?')}")
        print(f"Field status: {b.get('field_status', '?')}")
        summary = b.get('executive_summary', '')
        print(f"Summary: {summary[:200]}")
        targets = b.get("priority_targets", [])
        print(f"Priority targets: {len(targets)}")
        for t in targets[:5]:
            rank = t.get("rank", "?")
            loc = t.get("location", "?")
            print(f"  #{rank} {loc}")
        print(f"Key researchers: {len(b.get('key_researchers', []))}")
        print(f"From cache: {b.get('_from_cache', '?')}")
    else:
        print("Keys:", list(data.keys()))
        print("Raw:", json.dumps(data)[:500])

except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:500]}")
except Exception as e:
    print(f"Error: {e}")
