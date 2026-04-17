"""Read latest embed Lambda logs for AOSS debug output."""
import boto3

logs = boto3.client("logs", region_name="us-east-1")
log_group = "/aws/lambda/ResearchAnalystStack-IngestionEmbedLambdaE92F3BC0-wYlIRbksk1Jz"

streams = logs.describe_log_streams(
    logGroupName=log_group,
    orderBy="LastEventTime",
    descending=True,
    limit=3,
)["logStreams"]

for stream in streams[:1]:
    events = logs.get_log_events(
        logGroupName=log_group,
        logStreamName=stream["logStreamName"],
        limit=50,
    )["events"]
    print(f"Log stream: {stream['logStreamName']}")
    for event in events:
        msg = event["message"].strip()
        if "AOSS DEBUG" in msg or "OpenSearch" in msg or "ERROR" in msg:
            print(f"  {msg[:300]}")
