"""Push changed files to GitHub via the Contents API (incremental).

Usage:
    $env:GITHUB_TOKEN = "ghp_xxx"
    python scripts/push_to_github.py

This bypasses git SSH/HTTPS which may be blocked by corporate firewalls.
Uses the GitHub Contents API to PUT only files that have changed since
the last successful push. Tracks the last-pushed commit in .git/github-push-sha.

For a full re-push of all files: python scripts/push_to_github.py --full
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
PUSH_SHA_FILE = os.path.join(".git", "github-push-sha")

# Load from .env file if token not in environment
if not GITHUB_TOKEN and os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GITHUB_TOKEN="):
                GITHUB_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not GITHUB_TOKEN:
    print("ERROR: Set GITHUB_TOKEN environment variable or add to .env file")
    print("  Option 1: $env:GITHUB_TOKEN = 'ghp_xxx'")
    print("  Option 2: Add GITHUB_TOKEN=ghp_xxx to .env file (already gitignored)")
    sys.exit(1)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "ResearchAnalyst-Push",
}

# Skip binary files and large files
SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".ico", ".pdf", ".docx", ".pptx",
                   ".zip", ".gz", ".tar", ".whl", ".pyd", ".so", ".dll", ".exe",
                   ".pyc", ".pyo", ".mp3", ".wav", ".mp4"}
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


def get_current_sha():
    """Get current HEAD commit SHA."""
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip()


def get_last_pushed_sha():
    """Get SHA of last successfully pushed commit."""
    if os.path.exists(PUSH_SHA_FILE):
        with open(PUSH_SHA_FILE, "r") as f:
            return f.read().strip()
    return None


def save_pushed_sha(sha):
    """Record SHA of successful push."""
    with open(PUSH_SHA_FILE, "w") as f:
        f.write(sha)


def get_changed_files(since_sha=None):
    """Get files changed since last push. If no prior push, return all tracked files."""
    if since_sha:
        # Check if the SHA still exists in history
        check = subprocess.run(["git", "cat-file", "-t", since_sha],
                               capture_output=True, text=True)
        if check.returncode == 0:
            result = subprocess.run(
                ["git", "diff", "--name-only", since_sha, "HEAD"],
                capture_output=True, text=True
            )
            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            # Also include any untracked-but-staged files
            return files

    # Fallback: all tracked files
    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def get_deleted_files(since_sha):
    """Get files deleted since last push (need to delete from GitHub too)."""
    if not since_sha:
        return []
    check = subprocess.run(["git", "cat-file", "-t", since_sha],
                           capture_output=True, text=True)
    if check.returncode != 0:
        return []
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=D", since_sha, "HEAD"],
        capture_output=True, text=True
    )
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def push_file(filepath):
    """Push a single file to GitHub via Contents API."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in SKIP_EXTENSIONS:
        return "skipped_binary"

    if not os.path.exists(filepath):
        return "skipped_missing"

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

    # If SHA matches (content identical), skip
    if sha:
        import hashlib
        # GitHub blob SHA = sha1("blob {size}\0{content}")
        blob_header = f"blob {len(content)}\0".encode()
        local_sha = hashlib.sha1(blob_header + content).hexdigest()
        if local_sha == sha:
            return "skipped_unchanged"

    data = {
        "message": f"Update {filepath}",
        "content": encoded,
        "branch": "main",
    }
    if sha:
        data["sha"] = sha

    status, result = api_request("PUT", url, data)
    if status in (200, 201):
        return "ok"
    elif status == 422 and "sha" in str(result):
        # SHA mismatch — retry with fresh SHA
        status2, existing2 = api_request("GET", url)
        if status2 == 200:
            data["sha"] = existing2.get("sha")
            status3, result3 = api_request("PUT", url, data)
            if status3 in (200, 201):
                return "ok_retry"
        return f"error_{status}: SHA conflict"
    else:
        return f"error_{status}: {str(result)[:100]}"


def delete_file(filepath):
    """Delete a file from GitHub."""
    url = f"{GITHUB_API}/contents/{filepath}"
    status, existing = api_request("GET", url)
    if status != 200:
        return "skipped_not_on_github"

    sha = existing.get("sha")
    data = {"message": f"Delete {filepath}", "sha": sha, "branch": "main"}
    status, result = api_request("DELETE", url, data)
    if status == 200:
        return "deleted"
    return f"error_delete_{status}"


def main():
    full_mode = "--full" in sys.argv

    if not create_repo():
        sys.exit(1)

    time.sleep(1)

    current_sha = get_current_sha()
    last_sha = None if full_mode else get_last_pushed_sha()

    if last_sha and not full_mode:
        print(f"Last push: {last_sha[:8]}")
        print(f"Current:   {current_sha[:8]}")
        files = get_changed_files(last_sha)
        deleted = get_deleted_files(last_sha)
    else:
        if full_mode:
            print("Full push mode (all tracked files)")
        else:
            print("First push (no prior SHA recorded)")
        files = get_changed_files(None)
        deleted = []

    # Filter out files that no longer exist (deleted)
    files = [f for f in files if os.path.exists(f)]

    total = len(files) + len(deleted)
    if total == 0:
        print("Nothing to push — already up to date.")
        save_pushed_sha(current_sha)
        return

    print(f"\nPushing {len(files)} changed files" +
          (f" + deleting {len(deleted)} files" if deleted else "") +
          " to GitHub...")

    ok = 0
    skipped = 0
    errors = 0

    for i, filepath in enumerate(files):
        result = push_file(filepath)
        if result in ("ok", "ok_retry"):
            ok += 1
            print(f"  ✓ {filepath}")
        elif result.startswith("skipped"):
            skipped += 1
        else:
            errors += 1
            print(f"  ✗ {filepath}: {result}")

        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(files)}")

        time.sleep(0.3)  # Rate limit

    for filepath in deleted:
        result = delete_file(filepath)
        if result == "deleted":
            print(f"  🗑 {filepath}")
        time.sleep(0.3)

    print(f"\nDone: {ok} pushed, {skipped} skipped, {errors} errors")
    print(f"Repo: https://github.com/{GITHUB_USER}/{GITHUB_REPO}")

    if errors == 0:
        save_pushed_sha(current_sha)
        print(f"Saved push marker: {current_sha[:8]}")
    else:
        print("⚠ Errors occurred — push marker NOT updated (will retry next time)")


if __name__ == "__main__":
    main()
