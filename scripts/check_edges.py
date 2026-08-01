"""Check Neptune edge count for both cases."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")

for case_name, case_id in [("Main", "7f05e8d5-4492-4f19-8894-25367606db96"), ("Combined", "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99")]:
    label = f"Entity_{case_id}"
    
    r1 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        Payload=json.dumps({"action": "gremlin_query", "query": f"g.V().hasLabel('{label}').count()", "timeout": 120}))
    nodes = json.loads(r1["Payload"].read())
    
    r2 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        Payload=json.dumps({"action": "gremlin_query", "query": f"g.V().hasLabel('{label}').outE().count()", "timeout": 120}))
    edges = json.loads(r2["Payload"].read())
    
    print(f"{case_name} ({case_id[:8]}):")
    print(f"  Nodes: {nodes.get('result', '?')}")
    print(f"  Edges: {edges.get('result', '?')}")
