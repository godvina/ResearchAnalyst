#!/usr/bin/env python3
"""Quick fix: update entity/relationship counts for main case after Neptune reload."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

sql = "UPDATE case_files SET entity_count = 47859, relationship_count = 21966 WHERE case_id = '7f05e8d5-4492-4f19-8894-25367606db96'"

resp = lam.invoke(FunctionName=LAMBDA, Payload=json.dumps({"action": "run_sql", "sql": sql}))
result = json.loads(resp["Payload"].read())
print(json.dumps(result, indent=2)[:500])
