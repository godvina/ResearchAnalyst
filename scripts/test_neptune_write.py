"""Test basic Neptune write operations to diagnose 500 errors."""
import boto3
import json
import uuid

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"

def gremlin(query, timeout=120):
    r = lam.invoke(
        FunctionName=LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "gremlin_query",
            "case_id": CASE_ID,
            "query": query,
            "timeout": timeout,
            "max_result_len": 8000,
        }),
    )
    d = json.loads(r["Payload"].read().decode())
    return d

# Test 1: Simple read
print("=== Test 1: Simple read ===")
d = gremlin("g.V().limit(1).id()")
print(f"  Result: {d}")

# Test 2: Simple vertex add
print("\n=== Test 2: Add a test vertex ===")
test_id = str(uuid.uuid4())
d = gremlin(f"g.addV('TestLabel').property(id, '{test_id}').property('name', 'test_location')")
print(f"  Result: {d}")

# Test 3: Simple edge add between two new vertices
print("\n=== Test 3: Add edge between new vertices ===")
v1 = str(uuid.uuid4())
v2 = str(uuid.uuid4())
d = gremlin(f"g.addV('TestLabel').property(id, '{v1}').property('name', 'test_person')")
print(f"  Add v1: {d}")
d = gremlin(f"g.addV('TestLabel').property(id, '{v2}').property('name', 'test_loc')")
print(f"  Add v2: {d}")
e1 = str(uuid.uuid4())
d = gremlin(f"g.V('{v1}').addE('TEST_EDGE').to(g.V('{v2}')).property(id, '{e1}')")
print(f"  Add edge: {d}")

# Test 4: Add edge from existing Epstein vertex to a new test vertex
print("\n=== Test 4: Edge from Epstein to new vertex ===")
epstein_id = "68cec485-03af-17f3-9951-dd1770956dce"
v3 = str(uuid.uuid4())
d = gremlin(f"g.addV('TestLabel').property(id, '{v3}').property('name', 'test_target')")
print(f"  Add target: {d}")
e2 = str(uuid.uuid4())
d = gremlin(f"g.V('{epstein_id}').addE('TEST_EDGE').to(g.V('{v3}')).property(id, '{e2}')")
print(f"  Add edge from Epstein: {d}")

# Test 5: Add edge from Epstein to Marrakesh (the actual operation we need)
print("\n=== Test 5: Edge from Epstein to Marrakesh ===")
marrakesh_id = "a5344fa1-8608-40e1-83ba-19e91266fb40"
e3 = str(uuid.uuid4())
d = gremlin(f"g.V('{epstein_id}').addE('RELATED_TO').to(g.V('{marrakesh_id}')).property(id, '{e3}').property('relationship_type', 'associated_with').property('confidence', 0.9)")
print(f"  Add edge: {d}")

# Cleanup test vertices
print("\n=== Cleanup ===")
for vid in [test_id, v1, v2, v3]:
    d = gremlin(f"g.V('{vid}').drop()")
    print(f"  Drop {vid[:8]}: {d.get('status', d.get('error', '?'))}")
