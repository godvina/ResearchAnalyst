#!/usr/bin/env python3
"""
Neptune Bulk Sync — Generate CSV from Aurora, load via Neptune Bulk Loader API.

This is the CORRECT way to sync entities to Neptune at scale.
Individual Gremlin upserts = hours. Bulk CSV loader = minutes.

Steps:
  1. Query Aurora for filtered entities (master taxonomy + occurrence >= 2)
  2. Generate Neptune CSV files (vertices + edges)
  3. Upload to S3
  4. Call Neptune Bulk Loader API
  5. Poll until complete

Usage:
    python scripts/neptune_bulk_sync.py --case-id <CASE_ID>

Reference: docs/lessons-learned.md Issue 53
"""
import argparse
import boto3
import json
import csv
import io
import time
import sys
import uuid
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────
REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
NEPTUNE_ENDPOINT = "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
NEPTUNE_PORT = "8182"
NEPTUNE_LOADER_ROLE = "arn:aws:iam::974220725866:role/NeptuneLoadFromS3"

# Master taxonomy types to sync
CORE_TYPES = "person,location,organization,financial_amount,account_number,phone_number,email,address,date,event,flight,legal_case,statute,vehicle,role,financial,time,charge,offense,substance,weapon,property,contact"
MIN_OCCURRENCE = 2

lam = boto3.client("lambda", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def step1_generate_csv(case_id):
    """Query Aurora and generate Neptune-format CSV."""
    label = f"Entity_{case_id}"
    s3_prefix = f"neptune-bulk-load/{case_id}"

    log("STEP 1: Generating CSV from Aurora...")

    # Paginate through filtered entities
    offset = 0
    page_size = 5000
    all_entities = []

    while True:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            Payload=json.dumps({
                "action": "query_aurora_entities",
                "case_id": case_id,
                "limit": page_size,
                "offset": offset,
                "min_occurrence": MIN_OCCURRENCE,
                "type_filter": CORE_TYPES,
            }),
        )
        data = json.loads(resp["Payload"].read())

        if "error" in data:
            log(f"  ERROR: {data['error'][:200]}")
            break

        entities = data.get("entities", [])
        if not entities:
            break

        total = data.get("total", 0)
        all_entities.extend(entities)
        offset += page_size
        log(f"  Fetched {len(all_entities):,} / {total:,} entities")

        if len(entities) < page_size:
            break

    log(f"  Total entities: {len(all_entities):,}")

    # Generate Neptune CSV for vertices
    # Format: ~id, ~label, canonical_name:String, entity_type:String,
    #         occurrence_count:Int, confidence:Double, case_file_id:String
    vertex_buf = io.StringIO()
    writer = csv.writer(vertex_buf)
    writer.writerow([
        "~id", "~label",
        "canonical_name:String", "entity_type:String",
        "occurrence_count:Int", "confidence:Double",
        "case_file_id:String",
    ])

    seen_ids = set()
    for ent in all_entities:
        name = ent.get("name", "").strip()
        etype = ent.get("type", "unknown").lower()
        count = ent.get("count", 1)
        confidence = ent.get("confidence", 0.5)

        # Quality filter
        if len(name) < 3:
            continue

        # Generate deterministic ID from (name, type) to enable upsert behavior
        vid = f"{label}_{etype}_{name}".replace(" ", "_").replace(",", "")[:200]
        if vid in seen_ids:
            continue
        seen_ids.add(vid)

        writer.writerow([vid, label, name, etype, count, confidence, case_id])

    vertex_csv = vertex_buf.getvalue()
    vertex_key = f"{s3_prefix}/vertices.csv"

    s3.put_object(Bucket=BUCKET, Key=vertex_key, Body=vertex_csv.encode("utf-8"))
    log(f"  Uploaded {len(seen_ids):,} vertices to s3://{BUCKET}/{vertex_key}")
    log(f"  CSV size: {len(vertex_csv):,} bytes")

    return vertex_key, len(seen_ids)


def step2_clear_old_nodes(case_id):
    """Clear old Neptune nodes for this case before bulk load."""
    import ssl
    import urllib.request

    label = f"Entity_{case_id}"
    log("STEP 2: Clearing old Neptune nodes...")

    # Count current nodes
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    ctx = ssl.create_default_context()

    def gremlin(query, timeout=120):
        data = json.dumps({"gremlin": query}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e)[:200]}

    result = gremlin(f"g.V().hasLabel('{label}').count()")
    log(f"  Current nodes: {result}")

    # Drop all nodes for this case (batch of 500 at a time)
    dropped = 0
    while True:
        r = gremlin(f"g.V().hasLabel('{label}').limit(500).sideEffect(bothE().drop()).drop()")
        if "error" in str(r):
            log(f"  Drop error (may be empty): {str(r)[:100]}")
            break

        # Check remaining
        count_r = gremlin(f"g.V().hasLabel('{label}').count()")
        remaining = 0
        try:
            remaining = count_r.get("result", {}).get("data", {}).get("@value", [{}])[0].get("@value", 0)
        except:
            pass

        dropped += 500
        if dropped % 5000 == 0:
            log(f"  Dropped ~{dropped:,}, remaining: {remaining:,}")

        if remaining == 0:
            break

        time.sleep(0.1)

    log(f"  Cleared all old nodes")


def step3_bulk_load(case_id, vertex_key):
    """Trigger Neptune Bulk Loader API."""
    import ssl
    import urllib.request

    log("STEP 3: Triggering Neptune Bulk Loader...")

    source = f"s3://{BUCKET}/{vertex_key}"
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/loader"

    payload = {
        "source": source,
        "format": "csv",
        "iamRoleArn": NEPTUNE_LOADER_ROLE,
        "region": REGION,
        "failOnError": "FALSE",
        "parallelism": "HIGH",
        "updateSingleCardinalityProperties": "TRUE",
    }

    ctx = ssl.create_default_context()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            load_id = result.get("payload", {}).get("loadId", "")
            log(f"  Bulk load started: {load_id}")
            log(f"  Source: {source}")
            return load_id
    except urllib.request.HTTPError as he:
        body = he.read().decode("utf-8")[:500]
        log(f"  ERROR: HTTP {he.code}: {body}")

        # If Neptune doesn't have the loader role, fall back to Gremlin
        if "AccessDenied" in body or "role" in body.lower():
            log("  Neptune Bulk Loader not configured (missing IAM role).")
            log("  Falling back to batched Gremlin upserts...")
            return None
        return None
    except Exception as e:
        log(f"  ERROR: {str(e)[:300]}")
        return None


def step3_fallback_gremlin(case_id, vertex_key):
    """Fallback: load via batched Gremlin if bulk loader isn't available."""
    import ssl
    import urllib.request

    log("STEP 3 (FALLBACK): Loading via batched Gremlin upserts...")
    label = f"Entity_{case_id}"

    # Read the CSV back from S3
    obj = s3.get_object(Bucket=BUCKET, Key=vertex_key)
    content = obj["Body"].read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    ctx = ssl.create_default_context()

    def gremlin(query, timeout=30):
        data = json.dumps({"gremlin": query}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                return True
        except:
            return False

    loaded = 0
    errors = 0
    for row in reader:
        vid = row["~id"]
        name = row["canonical_name:String"].replace("'", "\\'")
        etype = row["entity_type:String"]
        count = row["occurrence_count:Int"]
        conf = row["confidence:Double"]

        # Use simple addV with deterministic ID (O(1) per vertex)
        # Neptune will reject duplicates if ID already exists
        q = (
            f"g.addV('{label}')"
            f".property(id, '{vid}')"
            f".property('canonical_name', '{name}')"
            f".property('entity_type', '{etype}')"
            f".property('occurrence_count', {count})"
            f".property('confidence', {conf})"
            f".property('case_file_id', '{case_id}')"
        )

        if gremlin(q):
            loaded += 1
        else:
            errors += 1

        if loaded % 1000 == 0 and loaded > 0:
            log(f"  Progress: {loaded:,} loaded, {errors} errors")
        time.sleep(0.02)

    log(f"  Fallback complete: {loaded:,} loaded, {errors} errors")
    return loaded


def step4_poll_loader(load_id):
    """Poll Neptune Bulk Loader until complete."""
    import ssl
    import urllib.request

    log("STEP 4: Polling bulk loader status...")
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/loader/{load_id}"
    ctx = ssl.create_default_context()

    while True:
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                status = result.get("payload", {}).get("overallStatus", {}).get("status", "UNKNOWN")
                log(f"  Status: {status}")

                if status == "LOAD_COMPLETED":
                    stats = result.get("payload", {}).get("overallStatus", {})
                    log(f"  Total records: {stats.get('totalRecords', '?')}")
                    log(f"  Total errors: {stats.get('totalErrors', '?')}")
                    return True
                elif status in ("LOAD_FAILED", "LOAD_CANCELLED"):
                    log(f"  FAILED: {json.dumps(result)[:500]}")
                    return False
        except Exception as e:
            log(f"  Poll error: {str(e)[:100]}")

        time.sleep(5)


def step5_verify(case_id):
    """Verify Neptune node count after load."""
    import ssl
    import urllib.request

    label = f"Entity_{case_id}"
    log("STEP 5: Verifying Neptune node count...")

    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    ctx = ssl.create_default_context()
    data = json.dumps({"gremlin": f"g.V().hasLabel('{label}').count()"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            log(f"  Neptune node count: {result}")
    except Exception as e:
        log(f"  Verify error: {str(e)[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Neptune Bulk Sync")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--skip-clear", action="store_true", help="Skip clearing old nodes")
    args = parser.parse_args()

    case_id = args.case_id
    log("=" * 60)
    log("Neptune Bulk Sync")
    log(f"Case: {case_id}")
    log("=" * 60)

    # Step 1: Generate CSV
    vertex_key, count = step1_generate_csv(case_id)

    # Step 2: Clear old nodes (optional)
    if not args.skip_clear:
        step2_clear_old_nodes(case_id)

    # Step 3: Bulk load (with Gremlin fallback)
    load_id = step3_bulk_load(case_id, vertex_key)
    if load_id:
        step4_poll_loader(load_id)
    else:
        step3_fallback_gremlin(case_id, vertex_key)

    # Step 5: Verify
    step5_verify(case_id)

    log("=" * 60)
    log("BULK SYNC COMPLETE")
    log("=" * 60)


if __name__ == "__main__":
    main()
