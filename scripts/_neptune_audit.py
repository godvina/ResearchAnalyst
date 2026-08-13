"""Audit Neptune — what's in there and how much is junk?"""
import boto3, json

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

def gremlin(q, timeout=120):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID, "query": q, "timeout": timeout}))
    d = json.loads(r["Payload"].read().decode())
    return d.get("result", d.get("error", ""))

label = "Entity_" + CASE_ID

print("=" * 60)
print("NEPTUNE AUDIT")
print("=" * 60)

# Total counts
print("\nTotal vertices:", gremlin("g.V().count()"))
print("Total edges:", gremlin("g.E().count()"))
q = "g.V().hasLabel('" + label + "').count()"
print("Vertices with our case label:", gremlin(q))

# Breakdown by source
print("\nVertices by source:")
q = "g.V().hasLabel('" + label + "').has('source','rhowardstone_kg').count()"
print("  rhowardstone_kg:", gremlin(q))
q = "g.V().hasLabel('" + label + "').hasNot('source').count()"
print("  (no source/original):", gremlin(q))

# Breakdown by entity_type
print("\nVertices by entity_type:")
q = "g.V().hasLabel('" + label + "').groupCount().by('entity_type')"
result = gremlin(q)
print(" ", result)

# Check for canonical_name presence
print("\nCanonical name check:")
q = "g.V().hasLabel('" + label + "').has('canonical_name').count()"
print("  With canonical_name:", gremlin(q))
q = "g.V().hasLabel('" + label + "').hasNot('canonical_name').count()"
print("  Without canonical_name:", gremlin(q))

# Sample 5 nodes from the old load (no source tag)
print("\nSample old nodes (no source tag, first 5):")
q = "g.V().hasLabel('" + label + "').hasNot('source').limit(5).valueMap('canonical_name','entity_type','occurrence_count')"
result = gremlin(q)
print(" ", result)

# Sample 5 rhowardstone nodes
print("\nSample rhowardstone nodes (first 5):")
q = "g.V().hasLabel('" + label + "').has('source','rhowardstone_kg').limit(5).valueMap('canonical_name','entity_type')"
result = gremlin(q)
print(" ", result)

# All labels in the graph
print("\nAll vertex labels:")
q = "g.V().label().dedup()"
result = gremlin(q)
print(" ", result)
