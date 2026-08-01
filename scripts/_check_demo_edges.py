"""Check if demo case ed0b6c27 has edges in Neptune by querying a high-degree entity."""
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
case_id = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

# Test 1: Query neighbors of Teterboro (highest degree entity)
print("=== Test 1: Neighbor query for Teterboro ===")
payload = json.dumps({"entity_name": "Teterboro"}).encode()
req = urllib.request.Request(
    f"{API_URL}/case-files/{case_id}/patterns",
    data=payload, method="POST",
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
        print(f"  Level 1 count: {body.get('level1_count', 0)}")
        print(f"  Level 2 count: {body.get('level2_count', 0)}")
        nodes = body.get("nodes", [])
        print(f"  Total nodes returned: {len(nodes)}")
        for n in nodes[:10]:
            print(f"    {n.get('name', '?')} ({n.get('type', '?')}) level={n.get('level', '?')}")
        edges = body.get("edges", [])
        print(f"  Edges returned: {len(edges)}")
        for e in edges[:5]:
            print(f"    {e.get('from', '?')} -> {e.get('to', '?')}")
except Exception as e:
    print(f"  Error: {e}")

# Test 2: Graph mode (what the frontend uses)
print("\n=== Test 2: Graph mode (frontend view) ===")
payload2 = json.dumps({"graph": True}).encode()
req2 = urllib.request.Request(
    f"{API_URL}/case-files/{case_id}/patterns",
    data=payload2, method="POST",
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req2, timeout=30) as resp:
        body2 = json.loads(resp.read().decode())
        print(f"  Total nodes: {body2.get('total_nodes', 0)}")
        print(f"  Total edges sampled: {body2.get('total_edges_sampled', 0)}")
        nodes2 = body2.get("nodes", [])
        edges2 = body2.get("edges", [])
        print(f"  Nodes returned: {len(nodes2)}")
        print(f"  Edges returned: {len(edges2)}")
        # Show first few nodes with degree
        for n in nodes2[:5]:
            print(f"    {n.get('name', '?')} ({n.get('type', '?')}) degree={n.get('degree', 0)}")
        for e in edges2[:5]:
            print(f"    Edge: {e.get('from', '?')} -> {e.get('to', '?')} ({e.get('type', '?')})")
except Exception as e:
    print(f"  Error: {e}")

# Test 3: Check Epstein Main for comparison
print("\n=== Test 3: Epstein Main neighbor query for Paris ===")
epstein_id = "7f05e8d5-4492-4f19-8894-25367606db96"
payload3 = json.dumps({"entity_name": "Paris"}).encode()
req3 = urllib.request.Request(
    f"{API_URL}/case-files/{epstein_id}/patterns",
    data=payload3, method="POST",
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req3, timeout=30) as resp:
        body3 = json.loads(resp.read().decode())
        print(f"  Paris Level 1 count: {body3.get('level1_count', 0)}")
        print(f"  Paris Level 2 count: {body3.get('level2_count', 0)}")
        edges3 = body3.get("edges", [])
        print(f"  Edges: {len(edges3)}")
        for e in edges3[:5]:
            print(f"    {e.get('from', '?')} -> {e.get('to', '?')}")
except Exception as e:
    print(f"  Error: {e}")
