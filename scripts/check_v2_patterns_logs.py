"""Check patterns Lambda logs for the v2 case."""
import boto3

logs = boto3.client("logs", region_name="us-east-1")
log_group = "/aws/lambda/ResearchAnalystStack-PatternsLambda457C2046-toyjGz36d37l"

streams = logs.describe_log_streams(
    logGroupName=log_group,
    orderBy="LastEventTime",
    descending=True,
    limit=3,
)["logStreams"]

for stream in streams[:2]:
    events = logs.get_log_events(
        logGroupName=log_group,
        logStreamName=stream["logStreamName"],
        limit=30,
    )["events"]
    
    for event in events:
        msg = event["message"].strip()
        if "245f5f93" in msg or "node count" in msg or "Centrality" in msg or "ERROR" in msg or "Neptune" in msg:
            print(msg[:300])
