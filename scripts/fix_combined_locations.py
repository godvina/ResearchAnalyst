"""Add missing key locations to Neptune for Epstein Combined and create person→location edges.

The patterns endpoint queries Neptune for the graph. Key demo locations like
Marrakesh, Islip/Little St. James, London, Palm Beach were previously added
manually but may have been lost. This script re-adds them.
"""
import boto3
import json
import time

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

def gremlin(query):
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": query}),
    )
    d = json.loads(r["Payload"].read().decode())
    if "error" in d:
        print(f"  ERROR: {d['error'][:300]}")
        return None
    return d.get("result")

# First, figure out the vertex label pattern used in this graph
print("=== Checking graph label pattern ===")
result = gremlin("g.V().limit(3).label()")
print(f"  Sample labels: {result}")

# The label pattern is Entity_{case_id} — we need to find the right case_id
# For Combined, it might use the parent case or its own ID
# Let's check which case_id labels exist
result = gremlin("g.V().label().dedup().limit(20)")
print(f"  Unique labels: {result}")

# Check what property names are used
result = gremlin("g.V().limit(1).properties().key().dedup()")
print(f"  Property keys: {result}")
