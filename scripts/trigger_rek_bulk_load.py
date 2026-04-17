"""Trigger Neptune bulk load for Rekognition CSV files.

Invokes the graph load Lambda with a minimal event that will
trigger the bulk CSV loader for the pre-generated files.
"""
import boto3
import json

REGION = "us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
DATA_BUCKET = "research-analyst-data-lake-974220725866"

s3 = boto3.client("s3", region_name=REGION)

# Find the Rekognition CSV files
r = s3.list_objects_v2(Bucket=DATA_BUCKET, Prefix=f"neptune-bulk-load/{CASE_ID}/rek_", MaxKeys=10)
csv_files = sorted([obj["Key"] for obj in r.get("Contents", [])])
nodes_key = [f for f in csv_files if "nodes" in f][0] if csv_files else None
edges_key = [f for f in csv_files if "edges" in f][0] if csv_files else None

print(f"Nodes CSV: {nodes_key}")
print(f"Edges CSV: {edges_key}")

if not nodes_key:
    print("No CSV files found!")
    exit(1)

# Read the nodes CSV to create a fake extraction result that the graph loader can process
# Actually, let's just invoke a simple Lambda that triggers the Neptune loader
# We'll use the existing graph load Lambda but pass the entities inline

# Read the nodes CSV and convert to entity format
import csv, io
nodes_body = s3.get_object(Bucket=DATA_BUCKET, Key=nodes_key)["Body"].read().decode()
reader = csv.DictReader(io.StringIO(nodes_body))
entities = []
for row in reader:
    entities.append({
        "canonical_name": row["canonical_name:String"],
        "entity_type": row["entity_type:String"],
        "confidence": float(row["confidence:Double"]),
        "occurrence_count": int(row["occurrence_count:Int"]),
    })

print(f"\nLoaded {len(entities)} entities from CSV")
print(f"Sample: {[e['canonical_name'] for e in entities[:5]]}")

# Read edges CSV
edges_body = s3.get_object(Bucket=DATA_BUCKET, Key=edges_key)["Body"].read().decode()
reader = csv.DictReader(io.StringIO(edges_body))
# We can't easily pass edges through the Lambda — the bulk loader handles them
# Let's just invoke the Lambda with the entities and let it generate new CSVs + bulk load

# Build extraction results format
extraction_results = [{
    "status": "success",
    "entities": entities,
    "relationships": [],  # Edges are in the CSV, will be loaded separately
}]

print(f"\nInvoking graph load Lambda...")
lam = boto3.client("lambda", region_name=REGION)
event = {
    "case_id": CASE_ID,
    "load_strategy": "bulk",
    "extraction_results": extraction_results,
}

resp = lam.invoke(
    FunctionName="ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg",
    InvocationType="RequestResponse",
    Payload=json.dumps(event),
)
result = json.loads(resp["Payload"].read().decode())
print(f"Result: {json.dumps(result, indent=2)}")

# Now load the edges CSV separately
print(f"\nNow loading edges CSV via a second invocation...")
# Read edges and convert to relationship format
edges_body2 = s3.get_object(Bucket=DATA_BUCKET, Key=edges_key)["Body"].read().decode()
reader2 = csv.DictReader(io.StringIO(edges_body2))

# Build entity name lookup from the node IDs
entity_lookup = {}
for e in entities:
    node_id = f"{CASE_ID}_{e['entity_type']}_{e['canonical_name']}"
    entity_lookup[node_id] = e["canonical_name"]

relationships = []
for row in reader2:
    src_name = entity_lookup.get(row["~from"], "")
    tgt_name = entity_lookup.get(row["~to"], "")
    if src_name and tgt_name:
        relationships.append({
            "source_entity": src_name,
            "target_entity": tgt_name,
            "relationship_type": row.get("relationship_type:String", "co-occurrence"),
            "confidence": float(row.get("confidence:Double", 0.6)),
        })

print(f"Loaded {len(relationships)} relationships from edges CSV")

# Invoke again with relationships
event2 = {
    "case_id": CASE_ID,
    "load_strategy": "bulk",
    "extraction_results": [{
        "status": "success",
        "entities": entities,
        "relationships": relationships,
    }],
}

resp2 = lam.invoke(
    FunctionName="ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg",
    InvocationType="RequestResponse",
    Payload=json.dumps(event2),
    # Lambda payload limit is 6MB — check if we're under
)
result2 = json.loads(resp2["Payload"].read().decode())
print(f"Result: {json.dumps(result2, indent=2)}")
