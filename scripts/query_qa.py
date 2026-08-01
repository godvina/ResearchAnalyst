"""Query the question-answer endpoint for Epstein clients."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

# Try the drill-down question endpoint
req = urllib.request.Request(
    f"{API}/case-files/{CASE_ID}/drill-down",
    data=json.dumps({
        "question": "Who are Jeffrey Epstein's most likely clients and associates? List all persons found in the evidence.",
        "entity_name": "Jeffrey Epstein",
        "entity_type": "person",
    }).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=29) as resp:
        data = json.loads(resp.read().decode())
        print("=== Drill-Down Response ===")
        if "analysis" in data:
            print(data["analysis"][:2000])
        elif "answer" in data:
            print(data["answer"][:2000])
        else:
            print(json.dumps(data, indent=2)[:2000])
except urllib.request.HTTPError as e:
    body = e.read().decode()[:300]
    print(f"Drill-down HTTP {e.code}: {body}")
except Exception as e:
    print(f"Error: {e}")

# Also try the investigative search
print("\n=== Investigative Search ===")
req2 = urllib.request.Request(
    f"{API}/case-files/{CASE_ID}/investigative-search",
    data=json.dumps({
        "query": "Epstein clients associates visitors flight logs",
        "search_type": "semantic",
        "limit": 15,
    }).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req2, timeout=29) as resp:
        data = json.loads(resp.read().decode())
        results = data.get("results", data.get("documents", []))
        print(f"Found {len(results)} results")
        for r in results[:5]:
            text = r.get("raw_text", r.get("text", r.get("content", "")))[:200]
            fname = r.get("source_filename", r.get("filename", "?"))
            print(f"  - {fname}: {text}")
except urllib.request.HTTPError as e:
    print(f"Search HTTP {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"Error: {e}")
