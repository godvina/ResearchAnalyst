"""Check patterns Lambda logs for v2c case."""
import boto3

logs = boto3.client("logs", region_name="us-east-1")
log_group = "/aws/lambda/ResearchAnalystStack-PatternsLambda457C2046-toyjGz36d37l"

streams = logs.describe_log_streams(
    logGroupName=log_group,
    orderBy="LastEventTime",
    descending=True,
    limit=2,
)["logStreams"]

for stream in streams[:1]:
    events = logs.get_log_events(
        logGroupName=log_group,
        logStreamName=stream["logStreamName"],
        limit=20,
    )["events"]
    for event in events:
        msg = event["message"].strip()
        if msg and not msg.startswith("INIT_START") and not msg.startswith("END") and not msg.startswith("REPORT"):
            print(msg[:300])
