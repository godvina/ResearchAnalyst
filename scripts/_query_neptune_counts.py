"""Query Neptune edge/node counts via the API Gateway (no direct Lambda invoke needed)."""
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"

CASES = [
    ("Epstein Main", "7f05e8d5-4492-4f19-8894-25367606db96"),
    ("Epstein v2", "0c5c28f7-ab20-41c5-b452-16f8c58e78ec"),
    ("Ancient Aliens", "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7"),
    ("DOJ Batch", "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"),
]

for case_name, case_id in CASES:
    print(f"\n{'='*50}")
    print(f"{case_name} ({case_id[:8]})")

    try:
        url = f"{API_URL}/case-files/{case_id}/patterns"
        payload = json.dumps({"graph": True}).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())

        nodes = body.get("nodes", [])
        edges = body.get("edges", [])
        total_nodes = body.get("total_nodes", len(nodes))
        total_edges = body.get("total_edges_sampled", len(edges))
        print(f"  Total nodes in Neptune: {total_nodes}")
        print(f"  Edges (sampled): {total_edges}")
        if nodes:
            print(f"  Top 10 entities by degree:")
            for n in nodes[:10]:
                print(f"    {n.get('name', '?')} ({n.get('type', '?')}) — degree: {n.get('degree', 0)}")
        else:
            print("  No nodes returned (graph may be empty for this case)")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300] if hasattr(e, 'read') else str(e)
        print(f"  HTTP {e.code}: {err_body}")
    except Exception as e:
        print(f"  Error: {str(e)[:300]}")
