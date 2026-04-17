"""Quick health check of all key Combined case endpoints."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

tests = [
    ("GET", f"/case-files/{CASE_ID}", None, "Case details"),
    ("POST", f"/case-files/{CASE_ID}/patterns", {"graph": True}, "Knowledge graph"),
    ("POST", f"/case-files/{CASE_ID}/patterns", {"travel_intelligence": True}, "Route Intel"),
    ("POST", f"/case-files/{CASE_ID}/geocode", {"locations": ["New York", "Paris"]}, "Geocode"),
    ("GET", f"/case-files/{CASE_ID}/investigator-analysis", None, "AI Briefing"),
]

for method, path, body, label in tests:
    try:
        url = API + path
        if body:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"}, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            # Quick summary
            if "nodes" in data:
                print(f"  ✅ {label}: {len(data['nodes'])} nodes, {len(data.get('edges', []))} edges")
            elif "insights" in data:
                print(f"  ✅ {label}: {len(data['insights'])} insights, {data.get('stats', {}).get('total_connections', '?')} connections")
            elif "geocoded" in data:
                print(f"  ✅ {label}: {data.get('resolved', 0)}/{data.get('total', 0)} resolved")
            elif "case_name" in data:
                print(f"  ✅ {label}: {data.get('case_name', '?')} ({data.get('document_count', '?')} docs)")
            else:
                keys = list(data.keys())[:5]
                print(f"  ✅ {label}: keys={keys}")
    except urllib.request.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:100]
        except:
            pass
        print(f"  ❌ {label}: HTTP {e.code} {body_text}")
    except Exception as e:
        print(f"  ❌ {label}: {str(e)[:100]}")
