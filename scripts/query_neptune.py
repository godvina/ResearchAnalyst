"""Quick script to query Neptune graph data via the API Gateway patterns endpoint."""
import json
import sys
import urllib.request

API_BASE = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"


def api_get(path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def main():
    # Get case file details
    print("=== Case File Details ===")
    case = api_get(f"/case-files/{CASE_ID}")
    print(json.dumps(case, indent=2))

    # Trigger pattern discovery to see graph stats
    print("\n=== Triggering Pattern Discovery ===")
    try:
        req = urllib.request.Request(
            f"{API_BASE}/case-files/{CASE_ID}/patterns",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=b"{}",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            patterns = json.loads(resp.read().decode())
            print(json.dumps(patterns, indent=2)[:2000])
    except Exception as e:
        print(f"Pattern discovery: {e}")


if __name__ == "__main__":
    main()
