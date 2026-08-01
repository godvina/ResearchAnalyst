"""Check Aurora relationships table for the main case."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# Check if there's a relationship query action
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({
        "action": "query_relationships",
        "case_id": CASE_ID,
        "limit": 5,
    }),
)
data = json.loads(resp["Payload"].read())
print(f"Relationships query: {json.dumps(data)[:500]}")
