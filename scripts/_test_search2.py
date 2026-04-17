"""Test search after embedding dimension fix."""
import json
import urllib.request
import time

time.sleep(25)

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
case_id = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

for q in ["Richard Branson", "richard", "epstein"]:
    url = f"{API_URL}/case-files/{case_id}/search"
    payload = json.dumps({"query": q, "search_mode": "semantic", "top_k": 5}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
        results = body.get("results", [])
        tier = body.get("search_tier", "?")
        print(f"'{q}' -> {len(results)} results (tier={tier})")
        for r in results[:2]:
            fn = r.get("source_filename", r.get("document_id", "?"))
            sc = r.get("score", "?")
            txt = (r.get("text", r.get("content", ""))[:100]).replace("\n", " ")
            print(f"  {fn} score={sc} | {txt}")
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:300] if hasattr(e, "read") else str(e)
        print(f"'{q}' -> HTTP {e.code}: {err}")
    except Exception as e:
        print(f"'{q}' -> Error: {e}")
