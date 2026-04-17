"""Test regenerate case file for Ancient Aliens."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"

# First get theories for this case
url = f"{API}/case-files/{CASE_ID}/theories"
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    theories = data.get("theories", [])
    print(f"Found {len(theories)} theories")
    if theories:
        tid = theories[0]["theory_id"]
        print(f"Testing regenerate on: {theories[0].get('title', '?')[:60]}")
        print(f"Theory ID: {tid}")

        # Try regenerate
        regen_url = f"{API}/case-files/{CASE_ID}/theories/{tid}/case-file/regenerate"
        regen_req = urllib.request.Request(regen_url, data=b"{}", method="POST")
        regen_req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(regen_req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
            print(f"Success! Keys: {list(result.get('case_file', {}).keys())}")
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            print(f"HTTP Error {e.code}: {body[:500]}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("No theories found for Ancient Aliens case")
except Exception as e:
    print(f"Failed to get theories: {e}")
