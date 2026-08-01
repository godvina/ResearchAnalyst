"""Check recent Bedrock batch jobs."""
import boto3
bedrock = boto3.client("bedrock", region_name="us-east-1")
jobs = bedrock.list_model_invocation_jobs(maxResults=5, sortBy="CreationTime", sortOrder="Descending")
for j in jobs.get("invocationJobSummaries", []):
    status = j.get("status", "?")
    name = j.get("jobName", "?")
    submitted = str(j.get("submitTime", ""))[:19]
    arn = j.get("jobArn", "")
    print(f"  {status:12s}  {name:50s}  {submitted}  {arn[-20:]}")
