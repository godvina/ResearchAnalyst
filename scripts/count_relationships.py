"""Count relationships in Aurora for the main case."""
import boto3, json
lam = boto3.client("lambda", region_name="us-east-1")
resp = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({
        "action": "query_relationships",
        "case_id": "7f05e8d5-4492-4f19-8894-25367606db96",
        "limit": 1,
        "offset": 0,
    }),
)
data = json.loads(resp["Payload"].read())
total = data.get("total", "?")
print(f"Total relationships in Aurora: {total}")

resp2 = lam.invoke(
    FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({
        "action": "query_relationships",
        "case_id": "7f05e8d5-4492-4f19-8894-25367606db96",
        "limit": 1,
        "offset": 0,
        "min_occurrence": 2,
    }),
)
data2 = json.loads(resp2["Payload"].read())
total2 = data2.get("total", "?")
print(f"Relationships with occurrence >= 2: {total2}")
