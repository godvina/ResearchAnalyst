"""Check Step Functions execution status."""
import boto3
import json

sfn = boto3.client("stepfunctions", region_name="us-east-1")
arn = "arn:aws:states:us-east-1:974220725866:execution:research-analyst-ingestion:ingest-7f05e8d5-537fca4f"

r = sfn.describe_execution(executionArn=arn)
print(f"Status: {r['status']}")
print(f"Started: {r['startDate']}")
if r["status"] != "RUNNING":
    if "output" in r:
        out = json.loads(r["output"])
        print(f"Output: {json.dumps(out, indent=2, default=str)[:2000]}")
    if "error" in r:
        print(f"Error: {r['error']}")
    if "cause" in r:
        print(f"Cause: {r['cause'][:500]}")

# Get execution history for recent events
history = sfn.get_execution_history(executionArn=arn, maxResults=20, reverseOrder=True)
for event in history["events"][:10]:
    etype = event["type"]
    ts = event["timestamp"].strftime("%H:%M:%S")
    detail = ""
    if "lambdaFunctionSucceededEventDetails" in event:
        output = json.loads(event["lambdaFunctionSucceededEventDetails"].get("output", "{}"))
        detail = f" -> {json.dumps(output, default=str)[:200]}"
    elif "lambdaFunctionFailedEventDetails" in event:
        d = event["lambdaFunctionFailedEventDetails"]
        detail = f" -> ERROR: {d.get('error', '')} {d.get('cause', '')[:200]}"
    elif "taskFailedEventDetails" in event:
        d = event["taskFailedEventDetails"]
        detail = f" -> TASK FAILED: {d.get('error', '')} {d.get('cause', '')[:200]}"
    print(f"  [{ts}] {etype}{detail}")
