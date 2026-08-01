"""Test all anomaly detection endpoints."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

types = ["structuring", "temporal_convergence", "ghost_entity", "absence_pattern", "decay_pattern", "proxy_network", "anomaly_destination"]

for t in types:
    url = f"{API}/case-files/{CASE_ID}/anomaly/{t}"
    req = urllib.request.Request(url, data=json.dumps({}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=25)
        body = json.loads(resp.read().decode())
        print(f"  {t:25s}: {body.get('count', '?')} patterns — {body.get('message', '')[:60]}")
    except urllib.request.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"  {t:25s}: HTTP {e.code} — {body}")
    except Exception as e:
        print(f"  {t:25s}: ERROR — {str(e)[:100]}")
