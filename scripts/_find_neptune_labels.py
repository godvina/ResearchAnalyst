"""Find what vertex labels exist in Neptune to identify the correct case graph."""
import boto3
import json

lam = boto3.client("lambda", region_name="us-east-1")

def gremlin(query):
    event = {"action": "gremlin_query", "query": query}
    resp = lam.invoke(
        FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
        Payload=json.dumps(event),
    )
    return json.loads(resp["Payload"].read())

# Get all distinct vertex labels
print("Finding all vertex labels in Neptune...")
r = gremlin("g.V().label().dedup().limit(20)")
print(f"Labels: {json.dumps(r)[:1000]}")

# Total vertex count
print("\nTotal vertices in Neptune...")
r = gremlin("g.V().count()")
print(f"Count: {json.dumps(r)[:200]}")

# Total edge count
print("\nTotal edges in Neptune...")
r = gremlin("g.E().count()")
print(f"Count: {json.dumps(r)[:200]}")
