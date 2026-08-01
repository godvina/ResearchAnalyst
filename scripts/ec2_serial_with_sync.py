#!/usr/bin/env python3
"""Serial entity extraction + Neptune sync — proven approach, runs unattended on EC2.

Phase 1: Extract entities (1 worker, batch_size=10 — same as ec2_entity_backfill.py that was working)
Phase 2: Sync Aurora entities to Neptune graph
Phase 3: Refresh case stats
Self-terminates when done.
"""
import json
import time
import uuid
import boto3

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
CASE_NAME = "Epstein Main"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
BATCH_SIZE = 10

lam = boto3.client("lambda", region_name=REGION)


def invoke_lambda(payload):
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    return json.loads(resp["Payload"].read().decode())


# ============================================================
# PHASE 1: Entity Extraction (serial, proven approach)
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 1: Entity Extraction — {CASE_NAME}")
print(f"Case ID: {CASE_ID}")
print(f"Batch size: {BATCH_SIZE}")
print(f"{'='*60}")

result = invoke_lambda({"action": "backfill_entities_count", "case_id": CASE_ID})
missing = result.get("missing_count", 0)
has = result.get("has_entities_count", 0)
print(f"Starting: {has:,} with entities, {missing:,} remaining")

if missing == 0:
    print("All docs have entities. Skipping extraction.")
else:
    total_processed = 0
    total_entities = 0
    total_errors = 0
    start = time.time()
    batch_num = 0

    print(f"Processing {missing:,} docs in batches of {BATCH_SIZE}...")

    while True:
        batch_num += 1
        try:
            result = invoke_lambda({
                "action": "backfill_entities_batch",
                "case_id": CASE_ID,
                "batch_size": BATCH_SIZE,
            })
        except Exception as e:
            total_errors += 1
            print(f"Batch {batch_num} error: {e}")
            if total_errors > 20:
                print("Too many errors, stopping.")
                break
            time.sleep(10)
            continue

        if "error" in result:
            total_errors += 1
            print(f"Batch {batch_num} Lambda error: {str(result)[:200]}")
            if total_errors > 20:
                break
            time.sleep(5)
            continue

        processed = result.get("processed", 0)
        entities = result.get("entities_extracted", 0)
        remaining = result.get("remaining", 0)
        total_processed += processed
        total_entities += entities

        if batch_num % 50 == 0:
            elapsed = time.time() - start
            rate = total_processed / max(elapsed, 1) * 60
            print(f"Batch {batch_num}: {total_processed:,} docs, {total_entities:,} entities, "
                  f"{remaining:,} remaining, {rate:.0f} docs/min, {total_errors} errors")

        if processed == 0:
            print(f"No more docs to process at batch {batch_num}.")
            break

        time.sleep(1)

    elapsed = time.time() - start
    print(f"\nPhase 1 Complete: {total_processed:,} docs, {total_entities:,} entities, "
          f"{total_errors} errors, {elapsed/60:.1f} min")


# ============================================================
# PHASE 2: Aurora → Neptune Sync
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 2: Aurora → Neptune Sync — {CASE_NAME}")
print(f"{'='*60}")

LABEL = f"Entity_{CASE_ID}"
SYNC_BATCH = 5000


def gremlin(query, timeout=120):
    r = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "gremlin_query",
            "case_id": CASE_ID,
            "query": query,
            "timeout": timeout,
            "max_result_len": 2000,
        }),
    )
    d = json.loads(r["Payload"].read().decode())
    if "error" in d:
        return None, d["error"][:300]
    return d.get("result"), None


def query_aurora_entities(limit, offset):
    r = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": CASE_ID,
            "limit": limit,
            "offset": offset,
        }),
    )
    return json.loads(r["Payload"].read().decode())


# Check current Neptune node count
result, err = gremlin(f"g.V().hasLabel('{LABEL}').count()")
print(f"Current Neptune nodes: {result}")

# Get total Aurora entities
data = query_aurora_entities(1, 0)
if "error" in data:
    print(f"ERROR: {data['error']}")
else:
    total = data.get("total", 0)
    print(f"Total distinct entities in Aurora: {total:,}")

    if total == 0:
        print("No entities to sync.")
    else:
        created = 0
        skipped = 0
        errors = 0
        start = time.time()
        offset = 0

        while offset < total:
            data = query_aurora_entities(SYNC_BATCH, offset)
            if "error" in data:
                print(f"ERROR at offset {offset}: {data['error'][:200]}")
                errors += 1
                if errors > 5:
                    break
                time.sleep(5)
                continue

            entities = data.get("entities", [])
            if not entities:
                break

            for ent in entities:
                name = ent.get("name", "")
                etype = ent.get("type", "unknown")
                count = ent.get("count", 1)

                if not name or len(name) < 2:
                    skipped += 1
                    continue

                escaped_name = name.replace("\\", "\\\\").replace("'", "\\'")
                vid = str(uuid.uuid4())
                q = (
                    f"g.addV('{LABEL}')"
                    f".property(id, '{vid}')"
                    f".property('canonical_name', '{escaped_name}')"
                    f".property('entity_type', '{etype}')"
                    f".property('confidence', 0.9)"
                    f".property('occurrence_count', {count})"
                    f".property('case_file_id', '{CASE_ID}')"
                )

                result, err = gremlin(q)
                if err:
                    errors += 1
                    if errors % 100 == 0:
                        print(f"  Error #{errors}: {err[:150]}")
                else:
                    created += 1

                if created % 500 == 0 and created > 0:
                    elapsed = time.time() - start
                    rate = created / max(elapsed, 1) * 60
                    print(f"  Progress: {created:,} created, {skipped:,} skipped, "
                          f"{errors:,} errors, {rate:.0f}/min")

                time.sleep(0.05)

            offset += SYNC_BATCH

        elapsed = time.time() - start
        result, err = gremlin(f"g.V().hasLabel('{LABEL}').count()")
        print(f"\nFinal Neptune nodes: {result}")
        print(f"Phase 2 Complete: {created:,} created, {skipped:,} skipped, "
              f"{errors:,} errors, {elapsed/60:.1f} min")


# ============================================================
# PHASE 3: Refresh Case Stats
# ============================================================
print(f"\n{'='*60}")
print(f"PHASE 3: Refresh Case Stats")
print(f"{'='*60}")

try:
    stats = invoke_lambda({"action": "refresh_case_stats", "case_id": CASE_ID})
    print(f"Stats: docs={stats.get('document_count', '?')}, "
          f"entities={stats.get('entity_count', '?')}, "
          f"relationships={stats.get('relationship_count', '?')}")
except Exception as e:
    print(f"Stats refresh failed: {str(e)[:200]}")

print(f"\n{'='*60}")
print(f"ALL PHASES COMPLETE")
print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
print(f"{'='*60}")
