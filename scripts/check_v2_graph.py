"""Check if the v2 demo case has graph data in Neptune."""
import boto3
import json
import urllib.request
import ssl
import os

CASE_ID = "245f5f93-8121-4392-b36b-83ddbd7382f4"
NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")

# Get Neptune endpoint from a Lambda's env vars
if not NEPTUNE_ENDPOINT:
    lam = boto3.client("lambda", region_name="us-east-1")
    fn = lam.get_function_configuration(
        FunctionName="ResearchAnalystStack-PatternsLambda457C2046-toyjGz36d37l"
    )
    NEPTUNE_ENDPOINT = fn["Environment"]["Variables"].get("NEPTUNE_ENDPOINT", "")

print(f"Neptune endpoint: {NEPTUNE_ENDPOINT}")

# The Neptune subgraph label for this case
label = f"Entity_{CASE_ID}"
print(f"Looking for label: {label}")

# Query Neptune directly
def gremlin_query(query):
    url = f"https://{NEPTUNE_ENDPOINT}:8182/gremlin"
    data = json.dumps({"gremlin": query}).encode()
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result.get("result", {}).get("data", {}).get("@value", [])
    except Exception as e:
        print(f"  Query error: {e}")
        return []

# Count nodes
print("\n=== Node Count ===")
count = gremlin_query(f"g.V().hasLabel('{label}').count()")
print(f"Nodes with label '{label}': {count}")

# If no nodes, check what labels exist
if not count or count == [0]:
    print("\nNo nodes found. Checking all labels...")
    all_labels = gremlin_query("g.V().label().dedup().limit(20)")
    print(f"Labels in Neptune: {all_labels}")
    
    # Check if there's a label with the case ID
    matching = [l for l in all_labels if CASE_ID[:8] in str(l)]
    print(f"Labels matching case ID: {matching}")
else:
    # Show sample entities
    print("\n=== Sample Entities ===")
    samples = gremlin_query(
        f"g.V().hasLabel('{label}').limit(10)"
        f".project('name','type','confidence')"
        f".by('canonical_name').by('entity_type').by('confidence')"
    )
    for s in samples:
        if isinstance(s, dict):
            print(f"  {s.get('name', '?')} ({s.get('type', '?')}) conf={s.get('confidence', '?')}")

    # Count edges
    print("\n=== Edge Count ===")
    edge_count = gremlin_query(f"g.V().hasLabel('{label}').outE('RELATED_TO').count()")
    print(f"Edges: {edge_count}")

    # Show entity type breakdown
    print("\n=== Entity Types ===")
    types = gremlin_query(
        f"g.V().hasLabel('{label}').groupCount().by('entity_type')"
    )
    print(f"Types: {types}")
