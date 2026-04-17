"""Check v2d case (batch size 1)."""
import boto3, json, urllib.request

sfn = boto3.client("stepfunctions", region_name="us-east-1")
arn = "arn:aws:states:us-east-1:974220725866:execution:research-analyst-ingestion:ingest-03dfc666-0f845a0f"
r = sfn.describe_execution(executionArn=arn)
print(f"Status: {r['status']}")
if r["status"] == "SUCCEEDED":
    out = json.loads(r.get("output", "{}"))
    results = out.get("document_results", [])
    success = sum(1 for d in results if d.get("status") == "success")
    failed = sum(1 for d in results if d.get("status") == "failed")
    gr = out.get("graph_load_result", {})
    print(f"Docs: {success} success, {failed} failed")
    print(f"Graph: {gr.get('node_count', 0)} nodes, {gr.get('edge_count', 0)} edges")

    # Test pattern discovery
    API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
    CASE_ID = "03dfc666-0dc2-40e4-ac47-11c01f48ac09"
    url = f"{API_URL}/case-files/{CASE_ID}/patterns"
    req = urllib.request.Request(url, data=json.dumps({}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode())
        patterns = data.get("patterns", [])
        print(f"\nPatterns: {len(patterns)}")
        print(f"Graph: {data.get('graph_patterns_count', 0)}, Vector: {data.get('vector_patterns_count', 0)}")
        for p in patterns[:10]:
            e = p.get("entities_involved", [{}])[0]
            print(f"  {e.get('name', '?')} ({e.get('type', '?')})")
elif r["status"] == "RUNNING":
    print(f"Started: {r['startDate'].strftime('%H:%M:%S')} — still running")
