"""Check the new v2 case status and graph data."""
import boto3
import json
import urllib.request

API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "9c10071d-65c7-44c2-876f-ff3f10e246ca"

# Check execution
sfn = boto3.client("stepfunctions", region_name="us-east-1")
arn = "arn:aws:states:us-east-1:974220725866:execution:research-analyst-ingestion:ingest-9c10071d-5dcddc81"
r = sfn.describe_execution(executionArn=arn)
print(f"Pipeline: {r['status']}")

if r["status"] == "SUCCEEDED":
    out = json.loads(r.get("output", "{}"))
    results = out.get("document_results", [])
    success = sum(1 for d in results if d.get("status") == "success")
    failed = sum(1 for d in results if d.get("status") == "failed")
    gr = out.get("graph_load_result", {})
    print(f"Docs: {success} success, {failed} failed")
    print(f"Graph: {gr.get('node_count', 0)} nodes, {gr.get('edge_count', 0)} edges")

    # Run pattern discovery
    print("\nRunning pattern discovery...")
    url = f"{API_URL}/case-files/{CASE_ID}/patterns"
    req = urllib.request.Request(url, data=json.dumps({}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
            patterns = data.get("patterns", [])
            print(f"Patterns: {len(patterns)}")
            print(f"Graph patterns: {data.get('graph_patterns_count', 0)}")
            print(f"Vector patterns: {data.get('vector_patterns_count', 0)}")
            for p in patterns[:10]:
                entities = p.get("entities_involved", [])
                names = [(e.get("name", "?"), e.get("type", "?")) for e in entities[:1]]
                degree = p.get("novelty_score", 0)
                print(f"  {names[0][0]} ({names[0][1]}) connections={degree}")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {body[:300]}")
elif r["status"] == "RUNNING":
    print("Still running...")
    history = sfn.get_execution_history(executionArn=arn, maxResults=5, reverseOrder=True)
    for event in history["events"][:3]:
        ts = event["timestamp"].strftime("%H:%M:%S")
        print(f"  [{ts}] {event['type']}")
else:
    print(f"Failed: {r.get('error', 'unknown')}")
