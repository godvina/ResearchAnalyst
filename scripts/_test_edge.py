"""Test Neptune edge creation with __.V() pattern."""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

def gremlin(q):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q, "timeout": 30}))
    return json.loads(r["Payload"].read().decode())

label = f"Entity_{CASE_ID}"

# Add two test nodes
r1 = gremlin(f"g.addV('{label}').property(id,'test_node_A').property('canonical_name','TestA')")
r2 = gremlin(f"g.addV('{label}').property(id,'test_node_B').property('canonical_name','TestB')")
print("Node A:", r1.get("result", r1.get("error", "")))
print("Node B:", r2.get("result", r2.get("error", "")))

# Try edge with __.V()
r3 = gremlin("g.V('test_node_A').addE('related_to').to(__.V('test_node_B')).property('type','test')")
print("Edge __.V():", r3.get("result", r3.get("error", "")))

# If that fails, try without __
if "error" in r3:
    r4 = gremlin("g.V('test_node_A').addE('related_to').to(g.V('test_node_B')).property('type','test')")
    print("Edge g.V():", r4.get("result", r4.get("error", "")))

# Cleanup
gremlin("g.V('test_node_A').drop()")
gremlin("g.V('test_node_B').drop()")
print("Cleaned up test nodes")
