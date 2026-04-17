"""Test search API for both cases to debug why 'richard branson' returns nothing."""
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

cases = [
    ("Combined (UI)", "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"),
    ("Main Epstein", "7f05e8d5-4492-4f19-8894-25367606db96"),
]

queries = ["Richard Branson", "richard", "epstein"]

for case_name, case_id in cases:
    for q in queries:
        for mode in ["keyword", "semantic"]:
            url = f"{API_URL}/case-files/{case_id}/search"
            payload = json.dumps({"query": q, "search_mode": mode, "top_k": 3}).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = json.loads(resp.read().decode())
                results = body.get("results", [])
                tier = body.get("search_tier", "?")
                print(f"{case_name} | {mode:8s} | '{q}' -> {len(results)} results (tier={tier})")
                if results:
                    for r in results[:2]:
                        fn = r.get("source_filename", r.get("document_id", "?"))
                        sc = r.get("score", "?")
                        txt = (r.get("text", r.get("content", ""))[:80]).replace("\n", " ")
                        print(f"    {fn} score={sc} | {txt}")
            except urllib.error.HTTPError as e:
                err = e.read().decode()[:200] if hasattr(e, "read") else str(e)
                print(f"{case_name} | {mode:8s} | '{q}' -> HTTP {e.code}: {err}")
            except Exception as e:
                print(f"{case_name} | {mode:8s} | '{q}' -> Error: {e}")
