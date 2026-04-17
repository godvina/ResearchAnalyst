"""Check a few epstein-docs JSON files for text content."""
import urllib.request
import json

files = [
    "results/IMAGES001/DOJ-OGR-00000003.json",
    "results/IMAGES001/DOJ-OGR-00000010.json",
    "results/IMAGES005/HOUSE_OVERSIGHT_020001.json",
]

for path in files:
    url = f"https://raw.githubusercontent.com/epstein-docs/epstein-docs.github.io/main/{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            doc = json.loads(resp.read().decode())
        full_text = doc.get("full_text", "")
        text_blocks = doc.get("text_blocks", [])
        combined = full_text or " ".join(
            b.get("text", "") for b in text_blocks if isinstance(b, dict)
        )
        entities = doc.get("entities", {})
        people = entities.get("people", []) if isinstance(entities, dict) else []
        print(f"{path.split('/')[-1]}:")
        print(f"  full_text: {len(full_text)} chars")
        print(f"  text_blocks: {len(text_blocks)} blocks")
        print(f"  combined text: {len(combined)} chars")
        print(f"  people: {people[:5]}")
        print(f"  text sample: {combined[:150]}")
        print()
    except Exception as e:
        print(f"{path}: {e}")
