"""Push all git-tracked files to GitHub via the Contents API.

Usage:
    set GITHUB_TOKEN=ghp_xxx
    python scripts/push_to_github.py

This bypasses git SSH/HTTPS which may be blocked by corporate firewalls.
Uses the GitHub Contents API to PUT each file individually.
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

GITHUB_USER = "godvina"
GITHUB_REPO = "ResearchAnalyst"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}"

if not GITHUB_TOKEN:
    print("ERROR: Set GITHUB_TOKEN environment variable first")
    print("  $env:GITHUB_TOKEN = 'ghp_xxx'")
    sys.exit(1)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "ResearchAnalyst-Push",
}

# Skip binary files and large files
SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".ico", ".pdf", ".docx", ".pptx",
                   ".zip", ".gz", ".tar", ".whl", ".pyd", ".so", ".dll", ".exe",
                   ".pyc", ".pyo"}
MAX_FILE_SIZE = 1_000_000  # 1MB limit per file for Contents API


def api_request(method, url, data=None):
    """Make a GitHub API request."""
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:500]
        except Exception:
            pass
        return e.code, {"error": body_text}


def create_repo():
    """Create the GitHub repo if it doesn't exist."""
    status, data = api_request("GET", GITHUB_API)
    if status == 200:
        print(f"Repo {GITHUB_USER}/{GITHUB_REPO} already exists")
        return True

    print(f"Creating repo {GITHUB_USER}/{GITHUB_REPO}...")
    status, data = api_request("POST", "https://api.github.com/user/repos", {
        "name": GITHUB_REPO,
        "description": "Investigative Intelligence Platform — AI-powered investigative analysis",
        "private": False,
        "auto_init": False,
    })
    if status == 201:
        print(f"Created repo: https://github.com/{GITHUB_USER}/{GITHUB_REPO}")
        return True
    else:
        print(f"Failed to create repo: {status} {data}")
        return False


def get_tracked_files():
    """Get list of git-tracked files."""
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd="."
    )
    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    return files


def push_file(filepath):
    """Push a single file to GitHub via Contents API."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in SKIP_EXTENSIONS:
        return "skipped_binary"

    try:
        size = os.path.getsize(filepath)
        if size > MAX_FILE_SIZE:
            return "skipped_large"
        if size == 0:
            return "skipped_empty"
    except OSError:
        return "skipped_missing"

    try:
        with open(filepath, "rb") as f:
            content = f.read()
        encoded = base64.b64encode(content).decode()
    except Exception as e:
        return f"error_read: {e}"

    # Check if file already exists (to get SHA for update)
    url = f"{GITHUB_API}/contents/{filepath}"
    status, existing = api_request("GET", url)
    sha = existing.get("sha") if status == 200 else None

    data = {
        "message": f"Add {filepath}",
        "content": encoded,
        "branch": "main",
    }
    if sha:
        data["sha"] = sha

    status, result = api_request("PUT", url, data)
    if status in (200, 201):
        return "ok"
    elif status == 422 and "sha" in str(result):
        # File exists but SHA mismatch — retry with fresh SHA
        status2, existing2 = api_request("GET", url)
        if status2 == 200:
            data["sha"] = existing2.get("sha")
            status3, result3 = api_request("PUT", url, data)
            if status3 in (200, 201):
                return "ok_retry"
        return f"error_{status}: SHA conflict"
    else:
        return f"error_{status}: {str(result)[:100]}"


def main():
    if not create_repo():
        sys.exit(1)

    # Wait a moment for repo to be ready
    time.sleep(2)

    files = get_tracked_files()
    print(f"\nPushing {len(files)} files to GitHub...")

    ok = 0
    skipped = 0
    errors = 0

    for i, filepath in enumerate(files):
        result = push_file(filepath)
        if result == "ok" or result == "ok_retry":
            ok += 1
        elif result.startswith("skipped"):
            skipped += 1
        else:
            errors += 1
            print(f"  ERROR: {filepath}: {result}")

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(files)} ({ok} ok, {skipped} skipped, {errors} errors)")
            time.sleep(1)  # Rate limit

        time.sleep(0.3)  # GitHub API rate limit: ~5000/hour

    print(f"\nDone: {ok} pushed, {skipped} skipped, {errors} errors")
    print(f"Repo: https://github.com/{GITHUB_USER}/{GITHUB_REPO}")


if __name__ == "__main__":
    main()
