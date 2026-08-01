"""Neptune to Aurora sync: reads entities+edges from Neptune, writes to Aurora.

Runs on EC2 in CDK VPC. Self-terminates when done.
Uses batch INSERT (execute_values) for speed.

Key IDs:
- Neptune graph label: Entity_7f05e8d5-4492-4f19-8894-25367606db96
- Aurora target case_file_id: 7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e
"""
import boto3
import json
import ssl
import time
import urllib.request
import os
import sys
from datetime import datetime

# Config
NEPTUNE_ENDPOINT = "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
NEPTUNE_PORT = "8182"
NEPTUNE_CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"  # Neptune graph label
AURORA_CASE_ID = "7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e"  # Aurora case_file_id
S3_BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"
LOG_KEY = f"logs/neptune-aurora-sync/sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

log_lines = []

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    log_lines.append(line)

def gremlin(query, timeout=120):
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    result = body.get("result", {}).get("data", {})
    if isinstance(result, dict) and "@value" in result:
        return result["@value"]
    return result

def unwrap(val):
    if isinstance(val, dict):
        if val.get("@type") == "g:Map" and "@value" in val:
            items = val["@value"]
            return {unwrap(items[i]): unwrap(items[i+1]) for i in range(0, len(items), 2)}
        if "@value" in val:
            return unwrap(val["@value"])
        return {k: unwrap(v) for k, v in val.items()}
    if isinstance(val, list):
        return [unwrap(v) for v in val]
    return val

def upload_log():
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(Bucket=S3_BUCKET, Key=LOG_KEY, Body="\n".join(log_lines))
    log(f"Log uploaded to s3://{S3_BUCKET}/{LOG_KEY}")

def self_terminate():
    try:
        ec2 = boto3.client("ec2", region_name=REGION)
        token_req = urllib.request.Request("http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"}, method="PUT")
        token = urllib.request.urlopen(token_req, timeout=2).read().decode()
        iid_req = urllib.request.Request("http://169.254.169.254/latest/meta-data/instance-id",
            headers={"X-aws-ec2-metadata-token": token})
        instance_id = urllib.request.urlopen(iid_req, timeout=2).read().decode()
        log(f"Self-terminating instance {instance_id}")
        ec2.terminate_instances(InstanceIds=[instance_id])
    except Exception as e:
        log(f"Self-terminate failed (may be running locally): {e}")

def main():
    log("=== Neptune to Aurora Sync ===")
    log(f"Neptune label: Entity_{NEPTUNE_CASE_ID}")
    log(f"Aurora target: {AURORA_CASE_ID}")

    # Import psycopg2 and get DB connection
    import psycopg2
    from psycopg2.extras import execute_values

    # Get DB credentials from Secrets Manager
    sm = boto3.client("secretsmanager", region_name=REGION)
    secret = json.loads(sm.get_secret_value(SecretId="AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ")["SecretString"])
    conn = psycopg2.connect(
        host=secret["host"], port=secret["port"],
        dbname=secret["dbname"], user=secret["username"], password=secret["password"]
    )
    conn.autocommit = False
    cur = conn.cursor()
    log("Connected to Aurora")

    # Step 1: Query filtered entities from Neptune (person, org, location, event with occurrence > 1)
    label = f"Entity_{NEPTUNE_CASE_ID}"
    log("Step 1: Querying entities from Neptune (filtered: person/org/location/event, occurrence > 1)...")
    t0 = time.time()
    
    entity_types = ['person', 'organization', 'location', 'event']
    all_entities = []
    
    for etype in entity_types:
        query = (
            f"g.V().hasLabel('{label}')"
            f".has('entity_type', '{etype}')"
            f".has('occurrence_count', gt(1))"
            f".project('name','type','confidence','count')"
            f".by('canonical_name')"
            f".by('entity_type')"
            f".by(coalesce(values('confidence'), constant(0.5)))"
            f".by(coalesce(values('occurrence_count'), constant(1)))"
            f".limit(15000)"
        )
        try:
            raw = gremlin(query, timeout=180)
            entities = [unwrap(r) for r in raw]
            all_entities.extend(entities)
            log(f"  {etype}: {len(entities)} entities")
        except Exception as e:
            log(f"  {etype}: FAILED - {str(e)[:200]}")
    
    log(f"  Total entities: {len(all_entities)} in {time.time()-t0:.1f}s")

    # Step 2: Batch insert entities into Aurora
    log("Step 2: Inserting entities into Aurora (batch)...")
    t0 = time.time()
    
    # Clear existing entities for this case first
    cur.execute("DELETE FROM entities WHERE case_file_id = %s", (AURORA_CASE_ID,))
    log(f"  Cleared existing entities")
    
    rows = []
    for e in all_entities:
        name = e.get("name", "")
        etype = e.get("type", "unknown")
        conf = float(e.get("confidence", 0.5))
        occ = int(e.get("count", 1))
        if name and len(name) >= 2:
            rows.append((AURORA_CASE_ID, name, etype, conf, occ))
    
    if rows:
        execute_values(cur,
            "INSERT INTO entities (case_file_id, canonical_name, entity_type, confidence, occurrence_count) "
            "VALUES %s ON CONFLICT (case_file_id, canonical_name, entity_type) DO UPDATE SET "
            "occurrence_count = GREATEST(entities.occurrence_count, EXCLUDED.occurrence_count), "
            "confidence = GREATEST(entities.confidence, EXCLUDED.confidence)",
            rows, page_size=1000
        )
    conn.commit()
    log(f"  Inserted {len(rows)} entities in {time.time()-t0:.1f}s")

    # Step 3: Query edges from Neptune (top 50K by weight)
    log("Step 3: Querying edges from Neptune...")
    t0 = time.time()
    
    query = (
        f"g.V().hasLabel('{label}')"
        f".has('entity_type', within('person','organization','location','event'))"
        f".has('occurrence_count', gt(1))"
        f".outE().limit(50000)"
        f".project('src','tgt','type','weight')"
        f".by(outV().values('canonical_name'))"
        f".by(inV().values('canonical_name'))"
        f".by(coalesce(values('relationship_type'), constant('related_to')))"
        f".by(coalesce(values('weight'), constant(1)))"
    )
    try:
        raw = gremlin(query, timeout=300)
        edges = [unwrap(r) for r in raw]
        log(f"  Got {len(edges)} edges in {time.time()-t0:.1f}s")
    except Exception as e:
        log(f"  Edge query failed: {str(e)[:300]}")
        edges = []

    # Step 4: Batch insert relationships into Aurora
    log("Step 4: Inserting relationships into Aurora (batch)...")
    t0 = time.time()
    
    # Clear existing relationships
    cur.execute("DELETE FROM relationships WHERE case_file_id = %s", (AURORA_CASE_ID,))
    log(f"  Cleared existing relationships")
    
    rel_rows = []
    for e in edges:
        src = e.get("src", "")
        tgt = e.get("tgt", "")
        rtype = e.get("type", "related_to")
        weight = int(e.get("weight", 1))
        if src and tgt and src != tgt:
            rel_rows.append((AURORA_CASE_ID, src, tgt, rtype, weight))
    
    if rel_rows:
        execute_values(cur,
            "INSERT INTO relationships (case_file_id, source_entity, target_entity, relationship_type, weight) "
            "VALUES %s ON CONFLICT DO NOTHING",
            rel_rows, page_size=1000
        )
    conn.commit()
    log(f"  Inserted {len(rel_rows)} relationships in {time.time()-t0:.1f}s")

    # Step 5: Update counts
    log("Step 5: Updating case counts...")
    cur.execute(
        "UPDATE case_files SET entity_count = %s, relationship_count = %s, last_activity = now() WHERE case_id = %s",
        (len(rows), len(rel_rows), AURORA_CASE_ID)
    )
    # Also update matters table
    try:
        cur.execute(
            "UPDATE matters SET total_entities = %s, total_relationships = %s WHERE matter_id = %s",
            (len(rows), len(rel_rows), AURORA_CASE_ID)
        )
    except Exception:
        pass
    conn.commit()
    
    log(f"\n=== SYNC COMPLETE ===")
    log(f"Entities synced: {len(rows)}")
    log(f"Relationships synced: {len(rel_rows)}")
    log(f"Aurora case_id: {AURORA_CASE_ID}")
    
    cur.close()
    conn.close()
    
    upload_log()
    self_terminate()

if __name__ == "__main__":
    main()
