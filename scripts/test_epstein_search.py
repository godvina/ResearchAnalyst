"""Test search against the 5 Epstein docs indexed in OpenSearch."""
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"


def search(query, mode="keyword", top_k=5):
    url = f"{API_URL}/case-files/{CASE_ID}/search"
    body = json.dumps({"query": query, "search_mode": mode, "top_k": top_k}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {err[:500]}")
        return None


print("=== Keyword Search: 'Epstein' ===")
r = search("Epstein", mode="keyword")
if r:
    print(f"Tier: {r.get('search_tier')}")
    print(f"Modes: {r.get('available_modes')}")
    print(f"Results: {len(r.get('results', []))}")
    for hit in r.get("results", [])[:3]:
        score = hit.get("score", "N/A")
        text = hit.get("text", "")[:100]
        print(f"  Score: {score}  Text: {text}...")

print("\n=== Keyword Search: 'water treatment' ===")
r = search("water treatment", mode="keyword")
if r:
    print(f"Results: {len(r.get('results', []))}")
    for hit in r.get("results", [])[:3]:
        score = hit.get("score", "N/A")
        text = hit.get("text", "")[:100]
        print(f"  Score: {score}  Text: {text}...")

print("\n=== Semantic Search: 'maintenance records' ===")
r = search("maintenance records", mode="semantic")
if r:
    print(f"Results: {len(r.get('results', []))}")
    for hit in r.get("results", [])[:3]:
        score = hit.get("score", "N/A")
        text = hit.get("text", "")[:100]
        print(f"  Score: {score}  Text: {text}...")

print("\n=== Case Info ===")
url = f"{API_URL}/case-files/{CASE_ID}"
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=15) as resp:
    case = json.loads(resp.read().decode())
    print(f"Topic: {case.get('topic_name')}")
    print(f"Tier: {case.get('search_tier')}")
    print(f"Status: {case.get('status')}")
    print(f"Docs: {case.get('document_count')}")
