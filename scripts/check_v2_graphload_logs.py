"""Check graph load Lambda logs for the v2 case."""
import boto3
import json

logs = boto3.client("logs", region_name="us-east-1")
log_group = "/aws/lambda/ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg"

# Get recent log streams
streams = logs.describe_log_streams(
    logGroupName=log_group,
    orderBy="LastEventTime",
    descending=True,
    limit=5,
)["logStreams"]

for stream in streams[:3]:
    events = logs.get_log_events(
        logGroupName=log_group,
        logStreamName=stream["logStreamName"],
        limit=30,
    )["events"]
    
    # Look for the v2 case
    for event in events:
        msg = event["message"].strip()
        if "245f5f93" in msg or "Graph load" in msg or "node_count" in msg or "Collected" in msg or "Nodes progress" in msg:
            print(msg[:300])
