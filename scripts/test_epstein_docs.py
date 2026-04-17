"""Test epstein-docs.github.io JSON data source."""
import urllib.request
import json

# Try the results JSON files
for i in range(3):
    url = f"https://raw.githubusercontent.com/epstein-docs/epstein-docs.github.io/main/results/results_{i}.json"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list):
            print(f"results_{i}.json: {len(data)} items")
            if data:
                print(f"  Keys: {list(data[0].keys())}")
                text = data[0].get("text", "") or data[0].get("content", "") or data[0].get("ocr_text", "")
                print(f"  Text sample ({len(text)} chars): {text[:200]}")
        elif isinstance(data, dict):
            print(f"results_{i}.json: dict with keys {list(data.keys())[:10]}")
    except Exception as e:
        print(f"results_{i}.json: {e}")
