"""Check Ancient Aliens case and test graph loading."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

# List cases
r = urllib.request.urlopen(API + "/case-files")
cases = json.loads(r.read().decode()).get("case_files", [])

aa_cases = [c for c in cases if "ancient" in c.get("topic_name", "").lower() or "alien" in c.get("topic_name", "").lower()]
print(f"Found {len(aa_cases)} Ancient Aliens cases:")
for c in aa_cases:
    cid = c["case_id"]
    print(f"  {cid[:12]}  {c['topic_name']}  status={c['status']}  docs={c.get('document_count',0)}  tier={c.get('search_tier','?')}")

    # Try loading graph
    try:
        req = urllib.request.Request(
            f"{API}/case-files/{cid}/patterns",
            data=json.dumps({"graph": True}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            print(f"    Graph: {len(nodes)} nodes, {len(edges)} edges")
            if nodes:
                print(f"    Sample: {nodes[0].get('name','?')} ({nodes[0].get('type','?')})")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"    Graph error: HTTP {e.code} - {body[:200]}")
    except Exception as e:
        print(f"    Graph error: {e}")
