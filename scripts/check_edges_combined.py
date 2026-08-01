"""Check Neptune edges for combined case only."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
label = "Entity_ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

r1 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({"action": "gremlin_query", "query": f"g.V().hasLabel('{label}').count()", "timeout": 60}))
print("Combined nodes:", json.loads(r1["Payload"].read()).get("result", "?"))

r2 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({"action": "gremlin_query", "query": "g.E().count()", "timeout": 60}))
print("Total edges (all cases):", json.loads(r2["Payload"].read()).get("result", "?"))

r3 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
    Payload=json.dumps({"action": "gremlin_query", "query": "g.V().count()", "timeout": 60}))
print("Total nodes (all cases):", json.loads(r3["Payload"].read()).get("result", "?"))
