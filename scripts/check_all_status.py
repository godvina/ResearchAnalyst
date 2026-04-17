"""Check status of all running Epstein pipelines."""
import boto3
import json

sfn = boto3.client("stepfunctions", region_name="us-east-1")

# V2 demo case
print("=== Epstein v2 Demo (50 docs, improved prompt) ===")
v2_arn = "arn:aws:states:us-east-1:974220725866:execution:research-analyst-ingestion:ingest-245f5f93-9fec6a7e"
r = sfn.describe_execution(executionArn=v2_arn)
print(f"Status: {r['status']}")
print(f"Started: {r['startDate'].strftime('%H:%M:%S')}")
if r["status"] != "RUNNING":
    if r.get("stopDate"):
        print(f"Stopped: {r['stopDate'].strftime('%H:%M:%S')}")
    if r.get("output"):
        out = json.loads(r["output"])
        results = out.get("document_results", [])
        success = sum(1 for d in results if d.get("status") == "success")
        failed = sum(1 for d in results if d.get("status") == "failed")
        print(f"Success: {success}, Failed: {failed}")
        # Show first failure reason if any
        for d in results:
            if d.get("status") == "failed":
                err = d.get("error", {})
                cause = err.get("Cause", "")
                try:
                    msg = json.loads(cause).get("errorMessage", "")[:200]
                except Exception:
                    msg = cause[:200]
                print(f"  First failure: {msg}")
                break
        # Show graph load result
        gr = out.get("graph_load_result", {})
        if gr:
            print(f"Graph: {gr.get('node_count', 0)} nodes, {gr.get('edge_count', 0)} edges")
else:
    # Show recent events
    history = sfn.get_execution_history(executionArn=v2_arn, maxResults=5, reverseOrder=True)
    for event in history["events"][:3]:
        etype = event["type"]
        ts = event["timestamp"].strftime("%H:%M:%S")
        detail = ""
        if "lambdaFunctionSucceededEventDetails" in event:
            output = json.loads(event["lambdaFunctionSucceededEventDetails"].get("output", "{}"))
            backend = output.get("backend", "")
            if backend:
                detail = f" backend={backend}"
            else:
                detail = f" {list(output.keys())[:3]}"
        elif "lambdaFunctionFailedEventDetails" in event:
            d = event["lambdaFunctionFailedEventDetails"]
            try:
                detail = f" ERROR: {json.loads(d.get('cause', '{}')).get('errorMessage', '')[:150]}"
            except Exception:
                detail = f" ERROR: {d.get('error', '')}"
        print(f"  [{ts}] {etype}{detail}")

# Full load status - check a sample of executions
print("\n=== Epstein Full Load (3,804 docs, 77 batches) ===")
try:
    with open("scripts/epstein_executions.json") as f:
        exec_data = json.load(f)
    arns = exec_data["executions"]
    running = 0
    succeeded = 0
    failed = 0
    for arn in arns:
        try:
            r = sfn.describe_execution(executionArn=arn)
            if r["status"] == "RUNNING":
                running += 1
            elif r["status"] == "SUCCEEDED":
                succeeded += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    print(f"Total: {len(arns)} executions")
    print(f"Succeeded: {succeeded}, Running: {running}, Failed: {failed}")
except FileNotFoundError:
    print("No execution tracking file found")
