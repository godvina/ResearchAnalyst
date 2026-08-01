"""Test AI Investigator via HTTP API (same path the frontend uses)."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

print("=== Test get_suspects via HTTP ===")
try:
    req = urllib.request.Request(
        f"{API}/case-files/{CASE_ID}/ai-investigator",
        data=json.dumps({"investigator_action": "get_suspects"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=29) as resp:
        data = json.loads(resp.read().decode())
        suspects = data.get("suspects", [])
        questions = data.get("questions", [])
        print(f"Status: {resp.status}")
        print(f"Suspects: {len(suspects)}")
        print(f"Questions: {len(questions)}")
        for q in questions[:3]:
            print(f"  {q.get('icon','')} {q.get('question','')[:60]}")
        for s in suspects[:5]:
            print(f"  {s['name']}: {s['connections']}")
except urllib.request.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Test analyze_suspect via HTTP ===")
try:
    req = urllib.request.Request(
        f"{API}/case-files/{CASE_ID}/ai-investigator",
        data=json.dumps({"investigator_action": "analyze_suspect", "suspect_name": "Leon Black"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=29) as resp:
        data = json.loads(resp.read().decode())
        print(f"Status: {resp.status}")
        print(f"Connections: {len(data.get('connections', []))}")
        print(f"Analysis: {data.get('analysis', '')[:300]}")
        print(f"Follow-ups: {data.get('follow_up_questions', [])}")
except urllib.request.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"Error: {e}")
