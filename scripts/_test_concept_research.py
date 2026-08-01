"""Quick test of the concept research endpoint."""
import urllib.request
import json

url = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/pattern-library/concept-research/domain/ancient_mysteries"

try:
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read())
    print("SUCCESS! Status 200")
    
    if "briefing" in data:
        b = data["briefing"]
        print(f"Codename: {b.get('codename', '?')}")
        print(f"Field status: {b.get('field_status', '?')}")
        print(f"Summary: {b.get('executive_summary', '')[:200]}")
        targets = b.get("priority_targets", [])
        print(f"Priority targets: {len(targets)}")
        for t in targets[:5]:
            rank = t.get("rank", "?")
            loc = t.get("location", "?")
            rat = t.get("rationale", "")[:80]
            print(f"  #{rank} {loc} — {rat}")
        print(f"\nKey researchers: {len(b.get('key_researchers', []))}")
        for r in b.get("key_researchers", [])[:3]:
            print(f"  {r.get('name', '?')} ({r.get('affiliation', '?')})")
    else:
        print("Response keys:", list(data.keys()))

except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:500]}")
except Exception as e:
    print(f"Error: {e}")
