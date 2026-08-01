"""Check GitHub repo status."""
import urllib.request
import json
import os

token = os.environ.get("GITHUB_TOKEN", "")
req = urllib.request.Request(
    "https://api.github.com/repos/godvina/ResearchAnalyst",
    headers={"Authorization": f"token {token}", "User-Agent": "test"},
)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read().decode())
    print(f"Repo: {d['html_url']}")
    print(f"Size: {d['size']} KB")
    print(f"Default branch: {d['default_branch']}")

# Count files in root
req2 = urllib.request.Request(
    "https://api.github.com/repos/godvina/ResearchAnalyst/git/trees/main?recursive=1",
    headers={"Authorization": f"token {token}", "User-Agent": "test"},
)
try:
    with urllib.request.urlopen(req2) as r2:
        tree = json.loads(r2.read().decode())
        files = [t for t in tree.get("tree", []) if t["type"] == "blob"]
        print(f"Files in repo: {len(files)}")
        print(f"Truncated: {tree.get('truncated', False)}")
except Exception as e:
    print(f"Tree error: {e}")
