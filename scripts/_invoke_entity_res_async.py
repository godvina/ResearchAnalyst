"""Fire-and-forget async invocation of entity resolution Lambda."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-EntityResolutionLambda",
    InvocationType="Event",  # async — returns immediately
    Payload=json.dumps({
        "case_id": "7f05e8d5-4492-4f19-8894-25367606db96",
        "dry_run": False,
        "use_llm": False,
        "max_degree": 500,
    }),
)
print(f"Async invoke status: {resp['StatusCode']}")
print("Entity resolution running in background (check CloudWatch logs for results)")
