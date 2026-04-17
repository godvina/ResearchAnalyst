"""Test the timeline API for Combined case."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

print("=== Testing Timeline API ===")
req = urllib.request.Request(
    f"{API}/case-files/{CASE_ID}/timeline",
    data=json.dumps({"clustering_window_hours": 48, "gap_threshold_days": 30}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
        events = body.get("events", [])
        clusters = body.get("clusters", [])
        gaps = body.get("gaps", [])
        phases = body.get("phases", [])
        narrative = body.get("narrative_header", "")
        
        print(f"Status: {resp.status}")
        print(f"Events: {len(events)}")
        print(f"Clusters: {len(clusters)}")
        print(f"Gaps: {len(gaps)}")
        print(f"Phases: {len(phases)}")
        print(f"Narrative: {narrative[:200]}")
        
        if events:
            print(f"\nSample events (first 10):")
            for e in events[:10]:
                ts = e.get("timestamp", "?")
                etype = e.get("event_type", "?")
                ents = [ent.get("name", "?") for ent in e.get("entities", [])[:3]]
                print(f"  {ts} [{etype}] entities: {', '.join(ents)}")
        else:
            print("\nNO EVENTS — timeline is empty")
            # Check raw response for clues
            print(f"Full response keys: {list(body.keys())}")
            print(f"Response preview: {json.dumps(body)[:500]}")

except urllib.request.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(e.read().decode()[:500])
except Exception as e:
    print(f"Error: {e}")
