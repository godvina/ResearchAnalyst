"""Debug the ingest API 400 error — prints the full response body."""
import json
import urllib.request
import urllib.error

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
BUCKET = "research-analyst-data-lake-974220725866"

url = f"{API_URL}/case-files/{CASE_ID}/ingest"
body = json.dumps({
    "source_bucket": BUCKET,
    "s3_keys": [f"cases/{CASE_ID}/raw/EFTA-00000001.pdf"],
    "skip_duplicates": True,
}).encode()

req = urllib.request.Request(url, data=body, method="POST",
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"SUCCESS {resp.status}: {resp.read().decode()}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
    print(f"Body: {e.read().decode()}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
