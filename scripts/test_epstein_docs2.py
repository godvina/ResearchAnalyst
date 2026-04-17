"""Check epstein-docs repo structure via GitHub API."""
import urllib.request
import json

url = "https://api.github.com/repos/epstein-docs/epstein-docs.github.io/git/trees/main?recursive=1"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode())

tree = data.get("tree", [])
results = [t for t in tree if t["path"].startswith("results/") and t["path"].endswith(".json")]
print(f"Total JSON result files: {len(results)}")
for r in results[:5]:
    print(f"  {r['path']} ({r.get('size', '?')} bytes)")

# Count by subfolder
folders = set()
for r in results:
    parts = r["path"].split("/")
    if len(parts) >= 2:
        folders.add(parts[1])
print(f"Subfolders: {len(folders)}")
print(f"Sample: {sorted(list(folders))[:10]}")

# Try fetching one result file
if results:
    sample = results[0]
    raw_url = f"https://raw.githubusercontent.com/epstein-docs/epstein-docs.github.io/main/{sample['path']}"
    req2 = urllib.request.Request(raw_url)
    with urllib.request.urlopen(req2, timeout=30) as resp2:
        doc = json.loads(resp2.read().decode())
    print(f"\nSample doc keys: {list(doc.keys())}")
    text = doc.get("text", "") or doc.get("content", "") or doc.get("ocr_text", "")
    print(f"Text length: {len(text)}")
    print(f"Text sample: {text[:200]}")
    entities = doc.get("entities", {})
    print(f"Entities: {list(entities.keys()) if isinstance(entities, dict) else len(entities)}")
