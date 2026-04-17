"""Test Neptune edge creation with detailed error response."""
import boto3
import json
import uuid

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

def gremlin(query):
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "gremlin_query",
            "case_id": CASE_ID,
            "query": query,
            "timeout": 60,
            "max_result_len": 2000,
        }),
    )
    return json.loads(r["Payload"].read().decode())

v1 = str(uuid.uuid4())
v2 = str(uuid.uuid4())
e1 = str(uuid.uuid4())

print("Adding v1...")
d = gremlin(f"g.addV('Test').property(id, '{v1}').property('name', 'p1')")
print(f"  {d.get('status', d.get('error', '?'))}")

print("Adding v2...")
d = gremlin(f"g.addV('Test').property(id, '{v2}').property('name', 'p2')")
print(f"  {d.get('status', d.get('error', '?'))}")

print("Adding edge v1→v2...")
d = gremlin(f"g.V('{v1}').addE('TEST').to(g.V('{v2}')).property(id, '{e1}')")
print(f"  Full response: {json.dumps(d)}")

# Also try without property(id, ...)
print("\nAdding edge v1→v2 (no custom id)...")
d = gremlin(f"g.V('{v1}').addE('TEST2').to(g.V('{v2}'))")
print(f"  Full response: {json.dumps(d)}")

# Cleanup
gremlin(f"g.V('{v1}').drop()")
gremlin(f"g.V('{v2}').drop()")
print("\nCleaned up test vertices")
