"""Test the travel intelligence API endpoint."""
import urllib.request
import json

API = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

print("=== Testing Route Intelligence API ===")
req = urllib.request.Request(
    f"{API}/case-files/{CASE_ID}/patterns",
    data=json.dumps({"travel_intelligence": True}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
        print(f"Status: {resp.status}")
        
        stats = body.get("stats", {})
        print(f"\nStats: {json.dumps(stats, indent=2)}")
        
        insights = body.get("insights", [])
        print(f"\nAI Insights ({len(insights)}):")
        for ins in insights:
            print(f"  {ins.get('icon', '?')} [{ins.get('priority', '?')}] {ins.get('title', '?')}")
            print(f"    {ins.get('narrative', '')[:150]}")
            if ins.get("locations"):
                print(f"    Locations: {', '.join(ins['locations'][:5])}")
        
        corridors = body.get("corridors", [])
        print(f"\nCorridors ({len(corridors)}):")
        for c in corridors[:5]:
            locs = ", ".join(f"{l['name']} ({l['frequency']}x)" for l in c.get("top_locations", [])[:3])
            print(f"  {c['person']}: {c['total_connections']} connections → {locs}")
        
        hubs = body.get("hubs", [])
        print(f"\nHubs ({len(hubs)}):")
        for h in hubs[:5]:
            print(f"  {h['location']}: {', '.join(h['persons'][:3])} ({h['person_count']} persons)")
        
        outliers = body.get("outliers", [])
        print(f"\nOutliers ({len(outliers)}):")
        for o in outliers[:5]:
            print(f"  {o['person']} → {o['location']}: {o['reason'][:100]}")

except urllib.request.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print(e.read().decode()[:500])
except Exception as e:
    print(f"Error: {e}")
