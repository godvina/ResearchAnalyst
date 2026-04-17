"""Check person→location edges in Neptune."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")

cases = [
    ("ed0b6c27-3b6b-4255-b9d0-efe8f4383a99", "Epstein Combined"),
]

for cid, name in cases:
    label = "Entity_" + cid
    
    # Count all edges
    q = f"g.V().hasLabel('{label}').outE('RELATED_TO').count()"
    resp = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
                      InvocationType="RequestResponse",
                      Payload=json.dumps({"action": "gremlin_query", "query": q}))
    r = json.loads(resp["Payload"].read().decode())
    print(f"{name} total edges: {r.get('result', '?')}")
    
    # Count person→location edges specifically
    q2 = f"g.V().hasLabel('{label}').has('entity_type','person').outE('RELATED_TO').inV().has('entity_type','location').count()"
    resp2 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
                       InvocationType="RequestResponse",
                       Payload=json.dumps({"action": "gremlin_query", "query": q2}))
    r2 = json.loads(resp2["Payload"].read().decode())
    print(f"{name} person→location edges: {r2.get('result', '?')}")
    
    # Get sample person→location paths
    q3 = f"g.V().hasLabel('{label}').has('entity_type','person').outE('RELATED_TO').inV().has('entity_type','location').path().by('canonical_name').by(label).by('canonical_name').limit(5)"
    resp3 = lam.invoke(FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
                       InvocationType="RequestResponse",
                       Payload=json.dumps({"action": "gremlin_query", "query": q3}))
    r3 = json.loads(resp3["Payload"].read().decode())
    print(f"{name} sample paths: {r3.get('result', '?')[:500]}")
