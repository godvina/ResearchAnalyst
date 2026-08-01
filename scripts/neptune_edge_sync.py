#!/usr/bin/env python3
"""
Neptune Edge Sync — Creates RELATED_TO edges between existing vertices.

Queries Aurora relationships via Lambda, looks up source/target vertices
by canonical_name in Neptune, and creates RELATED_TO edges.

Edge query pattern (uses __.V() anonymous traversal for Neptune):
  g.V().hasLabel('{label}').has('canonical_name','{source}')
    .addE('RELATED_TO')
    .to(__.V().hasLabel('{label}').has('canonical_name','{target}'))
    .property('relationship_type','{type}')
    .property('occurrence_count',{count})

Volume: 27,430 edges. Individual Gremlin addE is used because Neptune CSV
Bulk Loader cannot do property-based vertex lookups — our vertices use UUID
IDs and must be resolved by canonical_name. This matches the existing sync
pattern in ec2_neptune_resync.py.
"""
import json
import ssl
import time
import sys
import os
import urllib.request
import boto3
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────
CASE_ID = os.environ.get("CASE_ID", "7f05e8d5-4492-4f19-8894-25367606db96")
CASE_LABEL = f"Entity_{CASE_ID}"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"

NEPTUNE_ENDPOINT = os.environ.get(
    "NEPTUNE_ENDPOINT",
    "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
)
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")

MIN_OCCURRENCE = 1
PAGE_SIZE = 5000

# ── Neptune Client ─────────────────────────────────────────────────
SSL_CTX = ssl.create_default_context()


def neptune_query(query, timeout=30):
    """Execute a Gremlin query via Neptune HTTPS API."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return parse_result(body.get("result", {}).get("data", {}))
    except Exception as e:
        return {"error": str(e)[:300]}


def parse_result(data):
    """Parse Neptune GraphSON response."""
    if isinstance(data, dict):
        gt = data.get("@type", "")
        gv = data.get("@value")
        if gt == "g:List" and isinstance(gv, list):
            return [parse_result(v) for v in gv]
        if gt == "g:Map" and isinstance(gv, list):
            d = {}
            for i in range(0, len(gv) - 1, 2):
                d[parse_result(gv[i])] = parse_result(gv[i + 1])
            return d
        if gt in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
            return gv
        if "@value" in data:
            return parse_result(gv)
        return data
    if isinstance(data, list):
        return [parse_result(v) for v in data]
    return data


def escape_gremlin(s: str) -> str:
    """Escape a string for Gremlin query embedding."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


# ── Lambda Client ──────────────────────────────────────────────────
lam = boto3.client("lambda", region_name=REGION)


def query_relationships(limit, offset):
    """Get paginated relationships from Aurora via Lambda."""
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "query_relationships",
            "case_id": CASE_ID,
            "limit": limit,
            "offset": offset,
            "min_occurrence": MIN_OCCURRENCE,
        }),
    )
    return json.loads(resp["Payload"].read().decode())


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── Main Edge Sync Logic ──────────────────────────────────────────
def main():
    log("=" * 60)
    log("Neptune Edge Sync — RELATED_TO Edges")
    log(f"Case: {CASE_ID}")
    log(f"Label: {CASE_LABEL}")
    log(f"Neptune: {NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}")
    log(f"Min occurrence: {MIN_OCCURRENCE}")
    log("=" * 60)

    # Step 1: Verify Neptune connectivity
    test = neptune_query("g.V().limit(1).count()", timeout=10)
    if isinstance(test, dict) and "error" in test:
        log(f"FATAL: Cannot connect to Neptune: {test['error']}")
        sys.exit(1)
    log("Neptune connection verified ✓")

    # Step 2: Check current vertex and edge counts
    v_count = neptune_query(f"g.V().hasLabel('{CASE_LABEL}').count()", timeout=60)
    if isinstance(v_count, list) and v_count:
        v_count = v_count[0]
    log(f"Current Neptune vertices: {v_count}")

    e_count = neptune_query("g.E().hasLabel('RELATED_TO').count()", timeout=60)
    if isinstance(e_count, list) and e_count:
        e_count = e_count[0]
    log(f"Current Neptune RELATED_TO edges: {e_count}")

    # Step 3: Get first page to determine total
    data = query_relationships(1, 0)
    if "error" in data:
        log(f"FATAL: Aurora query failed: {data['error']}")
        sys.exit(1)
    total = data.get("total", 0)
    log(f"Total relationships in Aurora (occurrence >= {MIN_OCCURRENCE}): {total:,}")

    if total == 0:
        log("No relationships to sync. Exiting.")
        return

    # Step 4: Process relationships in pages
    offset = 0
    created = 0
    skipped_missing = 0
    skipped_empty = 0
    errors = 0
    start = time.time()

    while offset < total:
        data = query_relationships(PAGE_SIZE, offset)
        if "error" in data:
            log(f"ERROR at offset {offset}: {data['error'][:200]}")
            errors += 1
            if errors > 10:
                log("Too many consecutive errors, stopping.")
                break
            time.sleep(5)
            continue

        relationships = data.get("relationships", [])
        if not relationships:
            log(f"No relationships returned at offset {offset}, done.")
            break

        for rel in relationships:
            # Aurora relationship fields: source, target, type, count, confidence
            source_name = rel.get("source", "")
            target_name = rel.get("target", "")
            rel_type = rel.get("type", "co-occurrence")
            occurrence = rel.get("count", 1)

            if not source_name or not target_name:
                skipped_empty += 1
                continue

            # Escape for Gremlin
            esc_source = escape_gremlin(source_name)
            esc_target = escape_gremlin(target_name)
            esc_rel_type = escape_gremlin(rel_type)

            # Build edge creation query — look up vertices by canonical_name
            # Uses __.V() for anonymous traversal (Neptune requirement)
            query = (
                f"g.V().hasLabel('{CASE_LABEL}').has('canonical_name', '{esc_source}')"
                f".addE('RELATED_TO')"
                f".to(__.V().hasLabel('{CASE_LABEL}').has('canonical_name', '{esc_target}'))"
                f".property('relationship_type', '{esc_rel_type}')"
                f".property('occurrence_count', {occurrence})"
                f".property('case_file_id', '{CASE_ID}')"
            )

            result = neptune_query(query, timeout=30)

            if isinstance(result, dict) and "error" in result:
                err_msg = result["error"]
                errors += 1
                if errors % 100 == 0:
                    log(f"  Error #{errors}: {err_msg[:150]}")
            elif isinstance(result, list) and len(result) == 0:
                # Empty result means one or both vertices not found
                skipped_missing += 1
            else:
                created += 1

            # Progress logging every 1000 edges
            total_processed = created + skipped_missing + skipped_empty + errors
            if total_processed > 0 and total_processed % 1000 == 0:
                elapsed = time.time() - start
                rate = created / max(elapsed, 1) * 60
                log(f"  Progress: {created:,} created, {skipped_missing:,} skipped (missing vertex), "
                    f"{skipped_empty:,} skipped (empty), {errors:,} errors, {rate:.0f}/min")

            # Light rate limiting
            if (created + skipped_missing) % 20 == 0:
                time.sleep(0.02)

        offset += PAGE_SIZE
        elapsed = time.time() - start
        rate = created / max(elapsed, 1) * 60
        log(f"  Page {offset // PAGE_SIZE}: created={created:,}, "
            f"skipped_missing={skipped_missing:,}, skipped_empty={skipped_empty:,}, "
            f"errors={errors}, rate={rate:.0f}/min")

    elapsed = time.time() - start

    # Step 5: Final edge count
    final_e_count = neptune_query("g.E().hasLabel('RELATED_TO').count()", timeout=60)
    if isinstance(final_e_count, list) and final_e_count:
        final_e_count = final_e_count[0]

    log("=" * 60)
    log("EDGE SYNC COMPLETE")
    log(f"  Aurora relationships:  {total:,}")
    log(f"  Edges created:         {created:,}")
    log(f"  Skipped (no vertex):   {skipped_missing:,}")
    log(f"  Skipped (empty name):  {skipped_empty:,}")
    log(f"  Errors:                {errors}")
    log(f"  Neptune edges before:  {e_count}")
    log(f"  Neptune edges after:   {final_e_count}")
    log(f"  Elapsed:               {elapsed/60:.1f} minutes")
    log("=" * 60)


if __name__ == "__main__":
    for i, arg in enumerate(sys.argv):
        if arg == "--case-id" and i + 1 < len(sys.argv):
            CASE_ID = sys.argv[i + 1]
            CASE_LABEL = f"Entity_{CASE_ID}"
    main()
