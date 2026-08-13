"""List all cases — try multiple action names."""
import boto3, json, urllib.request

# Try via API directly
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
req = urllib.request.Request(f"{API_URL}/case-files", method="GET")
req.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        cases = data.get("case_files", data.get("cases", []))
        print(f"Found {len(cases)} cases:")
        for c in cases:
            name = c.get("topic_name", c.get("name", "?"))
            cid = c.get("case_id", "?")
            marker = "***" if "alien" in name.lower() or "ancient" in name.lower() else "   "
            print(f"  {marker} {cid} | {name}")
except Exception as e:
    print(f"API error: {e}")
