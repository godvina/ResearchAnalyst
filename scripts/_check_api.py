"""Quick check: test API endpoints for case loading."""
import json, urllib.request

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

# Try organizations endpoint
try:
    req = urllib.request.Request(f"{API}/organizations", method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        orgs = data.get("organizations", [])
        print(f"Organizations: {len(orgs)}")
        for org in orgs[:3]:
            oid = org.get("org_id", "?")
            print(f"  {oid[:12]} - {org.get('org_name', '?')}")
            # Try matters for this org
            try:
                req2 = urllib.request.Request(f"{API}/organizations/{oid}/matters", method="GET")
                with urllib.request.urlopen(req2, timeout=15) as resp2:
                    mdata = json.loads(resp2.read().decode())
                    matters = mdata.get("matters", [])
                    print(f"    Matters: {len(matters)}")
            except Exception as e2:
                print(f"    Matters error: {e2}")
except Exception as e:
    print(f"Orgs error: {e}")

# Try legacy case-files
try:
    req = urllib.request.Request(f"{API}/case-files", method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        cases = data.get("case_files", [])
        print(f"\nLegacy case-files: {len(cases)}")
        for c in cases[:5]:
            print(f"  {c.get('case_id','?')[:12]} - {c.get('topic_name','?')}")
except Exception as e:
    print(f"Case-files error: {e}")
