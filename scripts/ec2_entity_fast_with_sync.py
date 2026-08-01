#!/usr/bin/env python3
"""Fast entity extraction + Neptune sync — runs unattended on EC2, self-terminates when done.

Phase 1: Extract entities for all docs missing them (10 parallel workers)
Phase 2: Sync Aurora entities to Neptune graph
Phase 3: Refresh case stats
"""
import json
import time
import uuid
import boto3
from multiprocessing import Process, Value

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
CASE_NAME = "Epstein Main"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
BATCH_SIZE = 10
NUM_WORKERS = 3

lam = boto3.client("lambda", region_name=REGION)

total_processed = Value('i', 0)
total_errors = Value('i', 0)


def worker(worker_id):
    """Each worker gets its own boto3 client and processes batches."""
    client = boto3.client("lambda", region_name=REGION)
    consecutive_empty = 0
    local_processed = 0
    local_errors = 0

    while True:
        try:
            resp = client.invoke(
                FunctionName=LAMBDA_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "action": "backfill_entities_batch",
                    "case_id": CASE_ID,
                    "batch_size": BATCH_SIZE,
                }),
            )
            result = json.loads(resp["Payload"].read().decode())

            if "error" in result or resp.get("FunctionError"):
                local_errors += 1
                with total_errors.get_lock():
                    total_errors.value += 1
                if local_errors > 30:
                    print(f"  Worker {worker_id}: too many errors ({local_errors}), stopping")
                    return
                time.sleep(3)
                continue

            processed = result.get("processed", 0)
            if processed == 0:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    print(f"  Worker {worker_id}: no more docs, stopping after {local_processed} processed")
                    return
                time.sleep(2)
                continue

            consecutive_empty = 0
            local_processed += processed
            with total_processed.get_lock():
                total_processed.value += processed

            time.sleep(2)  # Longer pause to avoid Lambda/Bedrock throttling
        except Exception as e:
            local_errors += 1
            with total_errors.get_lock():
                total_errors.value += 1
            print(f"  Worker {worker_id}: exception: {str(e)[:100]}")
            time.sleep(5)


def run_entity_extraction():
    """Phase 1: Run parallel entity extraction."""
    print(f"\n{'='*60}")
    print(f"PHASE 1: Entity Extraction — {CASE_NAME}")
    print(f"Case ID: {CASE_ID}")
    print(f"Workers: {NUM_WORKERS}, Batch size: {BATCH_SIZE}")
    print(f"{'='*60}")

    # Check initial count
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
    )
    result = json.loads(resp["Payload"].read().decode())
    has = result.get("has_entities_count", 0)
    missing = result.get("missing_count", 0)
    print(f"Starting: {has:,} with entities, {missing:,} remaining")

    if missing == 0:
        print("All docs have entities. Skipping extraction.")
        return

    print(f"Launching {NUM_WORKERS} workers...")
    start = time.time()
    workers = []
    for i in range(NUM_WORKERS):
        p = Process(target=worker, args=(i,))
        p.start()
        workers.append(p)
        time.sleep(0.5)

    # Monitor progress
    while any(p.is_alive() for p in workers):
        time.sleep(60)
        elapsed = time.time() - start
        rate = total_processed.value / max(elapsed, 1) * 60
        try:
            resp = lam.invoke(
                FunctionName=LAMBDA_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
            )
            r = json.loads(resp["Payload"].read().decode())
            actual_has = r.get("has_entities_count", 0)
            actual_missing = r.get("missing_count", 0)
            print(f"  PROGRESS: {actual_has:,} done, {actual_missing:,} remaining, "
                  f"{rate:.0f} docs/min, {total_errors.value} errors, {elapsed/60:.0f} min elapsed")
        except Exception:
            print(f"  PROGRESS: ~{total_processed.value} processed locally, {elapsed/60:.0f} min elapsed")

    for p in workers:
        p.join()

    elapsed = time.time() - start

    # Final count
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"action": "backfill_entities_count", "case_id": CASE_ID}),
    )
    result = json.loads(resp["Payload"].read().decode())
    print(f"\nPhase 1 Complete: {result.get('has_entities_count', '?'):,} with entities, "
          f"{result.get('missing_count', '?'):,} remaining, "
          f"{total_errors.value} errors, {elapsed/60:.1f} min")


def run_neptune_sync():
    """Phase 2: Sync Aurora entities to Neptune graph."""
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
        return
    total = data.get("total", 0)
    print(f"Total distinct entities in Aurora: {total:,}")

    if total == 0:
        print("No entities to sync.")
        return

    # Paginate through Aurora entities and create Neptune nodes
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

            # Escape single quotes for Gremlin
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
                print(f"  Progress: {created:,} created, {skipped:,} skipped, {errors:,} errors, "
                      f"{rate:.0f}/min (offset: {offset})")

            time.sleep(0.05)  # Rate limit

        offset += SYNC_BATCH

    elapsed = time.time() - start

    # Verify
    result, err = gremlin(f"g.V().hasLabel('{LABEL}').count()")
    print(f"\nFinal Neptune nodes: {result}")
    print(f"\nPhase 2 Complete: {created:,} created, {skipped:,} skipped, "
          f"{errors:,} errors, {elapsed/60:.1f} min")


def run_refresh_stats():
    """Phase 3: Refresh case stats."""
    print(f"\n{'='*60}")
    print(f"PHASE 3: Refresh Case Stats — {CASE_NAME}")
    print(f"{'='*60}")

    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "refresh_case_stats", "case_id": CASE_ID}),
        )
        stats = json.loads(resp["Payload"].read().decode())
        print(f"Stats: docs={stats.get('document_count', '?')}, "
              f"entities={stats.get('entity_count', '?')}, "
              f"relationships={stats.get('relationship_count', '?')}")
    except Exception as e:
        print(f"Stats refresh failed: {str(e)[:200]}")


if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"ENTITY EXTRACTION + NEPTUNE SYNC")
    print(f"Case: {CASE_NAME} ({CASE_ID})")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"{'='*60}")

    overall_start = time.time()

    # Phase 1: Entity extraction
    run_entity_extraction()

    # Phase 2: Neptune sync
    run_neptune_sync()

    # Phase 3: Refresh stats
    run_refresh_stats()

    overall_elapsed = time.time() - overall_start
    print(f"\n{'='*60}")
    print(f"ALL PHASES COMPLETE — {overall_elapsed/60:.1f} minutes total")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"{'='*60}")
