"""Check current Neptune node count via Lambda."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({
        "action": "gremlin_query",
        "query": "g.V().hasLabel('Entity_7f05e8d5-4492-4f19-8894-25367606db96').count()",
        "timeout": 120,
    }),
)
result = json.loads(resp["Payload"].read())
print(f"Neptune node count: {result.get('result', result)}")
