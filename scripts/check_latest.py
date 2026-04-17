"""Check latest execution status."""
import boto3
import json

sfn = boto3.client("stepfunctions", region_name="us-east-1")
arn = "arn:aws:states:us-east-1:974220725866:execution:research-analyst-ingestion:ingest-7f05e8d5-dd4072fa"

r = sfn.describe_execution(executionArn=arn)
print(f"Status: {r['status']}")

if r["status"] != "RUNNING":
    if r.get("output"):
        out = json.loads(r["output"])
        results = out.get("document_results", [])
        for dr in results:
            status = dr.get("status", "unknown")
            doc_id = dr.get("document_id", "?")[:12]
            if status == "failed":
                err = dr.get("error", {})
                cause = err.get("Cause", "")
                try:
                    cause_obj = json.loads(cause)
                    msg = cause_obj.get("errorMessage", "")[:150]
                except Exception:
                    msg = cause[:150]
                print(f"  {doc_id}: FAILED - {msg}")
            else:
                print(f"  {doc_id}: {status}")

history = sfn.get_execution_history(executionArn=arn, maxResults=15, reverseOrder=True)
for event in history["events"][:10]:
    etype = event["type"]
    ts = event["timestamp"].strftime("%H:%M:%S")
    detail = ""
    if "lambdaFunctionSucceededEventDetails" in event:
        output = json.loads(event["lambdaFunctionSucceededEventDetails"].get("output", "{}"))
        backend = output.get("backend", "")
        tier = output.get("search_tier", "")
        dim = output.get("embedding_dimension", "")
        if backend:
            detail = f" backend={backend} tier={tier} dim={dim}"
        else:
            detail = f" {json.dumps(output, default=str)[:150]}"
    elif "lambdaFunctionFailedEventDetails" in event:
        d = event["lambdaFunctionFailedEventDetails"]
        cause = d.get("cause", "")
        try:
            cause_obj = json.loads(cause)
            detail = f" ERROR: {cause_obj.get('errorMessage', '')[:200]}"
        except Exception:
            detail = f" ERROR: {cause[:200]}"
    print(f"  [{ts}] {etype}{detail}")
