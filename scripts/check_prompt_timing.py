"""Check whether the full load used the old or new extraction prompt.

Compare the Lambda deploy time vs when the extract steps ran.
"""
import boto3
import json

sfn = boto3.client("stepfunctions", region_name="us-east-1")
lam = boto3.client("lambda", region_name="us-east-1")

# When was the extract Lambda last updated?
fn = lam.get_function_configuration(
    FunctionName="ResearchAnalystStack-IngestionExtractLambdaEACDEFC-mIfdS2zUJ89i"
)
last_modified = fn["LastModified"]
print(f"Extract Lambda last modified: {last_modified}")

# Check a few full-load executions to see when their extract steps ran
with open("scripts/epstein_executions.json") as f:
    exec_data = json.load(f)

# Check first, middle, and last batch
sample_indices = [0, 38, 76]
for idx in sample_indices:
    arn = exec_data["executions"][idx]
    name = arn.split(":")[-1]
    
    history = sfn.get_execution_history(executionArn=arn, maxResults=100, reverseOrder=False)
    
    # Find the first ExtractEntities Lambda invocation
    for event in history["events"]:
        if event["type"] == "LambdaFunctionScheduled":
            details = event.get("lambdaFunctionScheduledEventDetails", {})
            resource = details.get("resource", "")
            if "Extract" in resource:
                ts = event["timestamp"]
                print(f"Batch {idx+1}/77 ({name}): Extract started at {ts.strftime('%H:%M:%S')}")
                break
    else:
        # Check if it even got to extract
        r = sfn.describe_execution(executionArn=arn)
        print(f"Batch {idx+1}/77 ({name}): Status={r['status']}, Started={r['startDate'].strftime('%H:%M:%S')}")
