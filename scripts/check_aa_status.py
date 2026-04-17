"""Check Ancient Aliens pipeline execution status."""
import boto3
import json

sfn = boto3.client("stepfunctions", region_name="us-east-1")

# Check the successful graph-load-only run
arn = "arn:aws:states:us-east-1:974220725866:execution:research-analyst-ingestion:aa-graphload-only-20260327210000"
r = sfn.describe_execution(executionArn=arn)
print(f"=== Graph Load Only ===")
print(f"Status: {r['status']}")
print(f"Started: {r['startDate']}")
print(f"Stopped: {r.get('stopDate', 'N/A')}")
out = json.loads(r.get("output", "{}"))
gr = out.get("graph_load_result", out.get("status_result", {}))
print(f"Result: {json.dumps(gr, indent=2, default=str)[:500]}")

# Check the failed full 240 v2 run
print(f"\n=== Full 240 v2 ===")
arn2 = "arn:aws:states:us-east-1:974220725866:execution:research-analyst-ingestion:aa-full240v2-20260327193200"
r2 = sfn.describe_execution(executionArn=arn2)
print(f"Status: {r2['status']}")
print(f"Started: {r2['startDate']}")
print(f"Stopped: {r2.get('stopDate', 'N/A')}")
if r2.get("output"):
    out2 = json.loads(r2["output"])
    print(f"Output: {json.dumps(out2, indent=2, default=str)[:500]}")
if r2.get("error"):
    print(f"Error: {r2['error']}")
if r2.get("cause"):
    print(f"Cause: {r2['cause'][:500]}")

# Get last events for the failed run
history = sfn.get_execution_history(executionArn=arn2, maxResults=10, reverseOrder=True)
for event in history["events"][:5]:
    etype = event["type"]
    ts = event["timestamp"].strftime("%H:%M:%S")
    detail = ""
    if "executionFailedEventDetails" in event:
        d = event["executionFailedEventDetails"]
        detail = f" {d.get('error', '')} {d.get('cause', '')[:300]}"
    elif "lambdaFunctionFailedEventDetails" in event:
        d = event["lambdaFunctionFailedEventDetails"]
        detail = f" {d.get('error', '')} {d.get('cause', '')[:300]}"
    elif "taskFailedEventDetails" in event:
        d = event["taskFailedEventDetails"]
        detail = f" {d.get('error', '')} {d.get('cause', '')[:300]}"
    print(f"  [{ts}] {etype}{detail}")
