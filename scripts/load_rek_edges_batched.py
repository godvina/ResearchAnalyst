"""Load Rekognition edges into Neptune via Lambda in smaller batches.

The full edges CSV has 4,585 edges which exceeds Lambda's 6MB payload limit
when sent as a single invocation. This script:
1. Reads the edges CSV from S3
2. Reads the nodes CSV to build entity lookup
3. Splits relationships into batches of 200
4. Invokes the graph load Lambda for each batch
5. Reports progress and totals
"""
import boto3
import csv
import io
import json
import time

REGION = "us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
DATA_BUCKET = "research-analyst-data-lake-974220725866"
LAMBDA_NAME = "ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg"
BATCH_SIZE = 200  # relationships per Lambda invocation

from botocore.config import Config

s3 = boto3.client("s3", region_name=REGION)
# Graph load Lambda can take up to 900s (bulk CSV upload + Neptune loader + polling)
# Default boto3 read_timeout is 60s which causes ReadTimeoutError
lam = boto3.client("lambda", region_name=REGION, config=Config(
    read_timeout=900,
    connect_timeout=10,
    retries={"max_attempts": 0},  # we handle retries ourselves
))


def find_csv_files():
    """Find the Rekognition CSV files in S3."""
    r = s3.list_objects_v2(Bucket=DATA_BUCKET, Prefix=f"neptune-bulk-load/{CASE_ID}/rek_", MaxKeys=20)
    files = sorted([obj["Key"] for obj in r.get("Contents", [])])
    nodes_key = next((f for f in files if "nodes" in f), None)
    edges_key = next((f for f in files if "edges" in f), None)
    return nodes_key, edges_key


def load_entities_from_csv(nodes_key):
    """Read nodes CSV and return entity list + node ID lookup."""
    body = s3.get_object(Bucket=DATA_BUCKET, Key=nodes_key)["Body"].read().decode()
    reader = csv.DictReader(io.StringIO(body))
    entities = []
    node_id_to_name = {}
    for row in reader:
        name = row["canonical_name:String"]
        etype = row["entity_type:String"]
        node_id = row["~id"]
        entities.append({
            "canonical_name": name,
            "entity_type": etype,
            "confidence": float(row.get("confidence:Double", 0.6)),
            "occurrence_count": int(row.get("occurrence_count:Int", 1)),
        })
        node_id_to_name[node_id] = name
    return entities, node_id_to_name


def load_relationships_from_csv(edges_key, node_id_to_name):
    """Read edges CSV and return relationship list."""
    body = s3.get_object(Bucket=DATA_BUCKET, Key=edges_key)["Body"].read().decode()
    reader = csv.DictReader(io.StringIO(body))
    relationships = []
    for row in reader:
        src_name = node_id_to_name.get(row["~from"], "")
        tgt_name = node_id_to_name.get(row["~to"], "")
        if src_name and tgt_name:
            relationships.append({
                "source_entity": src_name,
                "target_entity": tgt_name,
                "relationship_type": row.get("relationship_type:String", "co-occurrence"),
                "confidence": float(row.get("confidence:Double", 0.6)),
            })
    return relationships


def invoke_batch(batch_num, entities, relationships_batch):
    """Invoke the graph load Lambda with a batch of relationships."""
    event = {
        "case_id": CASE_ID,
        "load_strategy": "bulk",
        "extraction_results": [{
            "status": "success",
            "entities": entities,
            "relationships": relationships_batch,
        }],
    }
    payload = json.dumps(event)
    payload_mb = len(payload.encode()) / (1024 * 1024)

    print(f"  Batch {batch_num}: {len(relationships_batch)} edges, payload {payload_mb:.2f} MB")

    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=payload,
    )
    result = json.loads(resp["Payload"].read().decode())
    status = result.get("status", "unknown")
    nodes = result.get("node_count", 0)
    edges = result.get("edge_count", 0)
    strategy = result.get("load_strategy", "unknown")
    print(f"  Result: status={status}, strategy={strategy}, nodes={nodes}, edges={edges}")
    return result


def main():
    print("=" * 60)
    print("Rekognition Edges Batch Loader")
    print(f"Case: {CASE_ID}")
    print(f"Batch size: {BATCH_SIZE} edges per invocation")
    print("=" * 60)

    # Find CSV files
    nodes_key, edges_key = find_csv_files()
    print(f"\nNodes CSV: {nodes_key}")
    print(f"Edges CSV: {edges_key}")
    if not nodes_key or not edges_key:
        print("ERROR: CSV files not found!")
        return

    # Load entities
    entities, node_id_to_name = load_entities_from_csv(nodes_key)
    print(f"Loaded {len(entities)} entities from nodes CSV")

    # Load relationships
    relationships = load_relationships_from_csv(edges_key, node_id_to_name)
    print(f"Loaded {len(relationships)} relationships from edges CSV")

    # Split into batches
    batches = []
    for i in range(0, len(relationships), BATCH_SIZE):
        batches.append(relationships[i:i + BATCH_SIZE])
    print(f"\nSplit into {len(batches)} batches of up to {BATCH_SIZE} edges each")

    # Process batches
    total_edges = 0
    failed_batches = 0
    start_time = time.time()

    for i, batch in enumerate(batches, 1):
        print(f"\n--- Batch {i}/{len(batches)} ---")
        try:
            result = invoke_batch(i, entities, batch)
            total_edges += result.get("edge_count", 0)
            # Wait between batches to avoid throttling Neptune
            if i < len(batches):
                print("  Waiting 5s before next batch...")
                time.sleep(5)
        except Exception as e:
            print(f"  FAILED: {str(e)[:200]}")
            failed_batches += 1
            time.sleep(10)  # longer wait after failure

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("COMPLETE")
    print(f"Total edges loaded: {total_edges}")
    print(f"Failed batches: {failed_batches}/{len(batches)}")
    print(f"Elapsed: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
