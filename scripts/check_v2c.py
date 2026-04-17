"""Check v2c case status."""
import boto3
import json

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
elif r["status"] == "RUNNING":
    started = r["startDate"].strftime("%H:%M:%S")
    print(f"Started: {started} — still running")
    history = sfn.get_execution_history(executionArn=arn, maxResults=5, reverseOrder=True)
    for event in history["events"][:3]:
        ts = event["timestamp"].strftime("%H:%M:%S")
        print(f"  [{ts}] {event['type']}")
