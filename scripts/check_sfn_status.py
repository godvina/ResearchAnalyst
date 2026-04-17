"""Quick check: Step Functions execution status for recent ingestion runs."""
import boto3
from datetime import datetime, timezone, timedelta

sfn = boto3.client("stepfunctions", region_name="us-east-1")
sm_arn = None

paginator = sfn.get_paginator("list_state_machines")
for page in paginator.paginate():
    for sm in page["stateMachines"]:
        if "ingestion" in sm["name"].lower() or "research" in sm["name"].lower():
            sm_arn = sm["stateMachineArn"]
            print(f"State machine: {sm['name']}")
            break
    if sm_arn:
        break

if not sm_arn:
    print("No ingestion state machine found")
else:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    for status in ["RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]:
        try:
            resp = sfn.list_executions(stateMachineArn=sm_arn, statusFilter=status, maxResults=100)
            recent = [e for e in resp.get("executions", []) if e["startDate"] > cutoff]
            if recent:
                print(f"  {status}: {len(recent)}")
        except Exception as e:
            print(f"  {status}: error - {e}")
