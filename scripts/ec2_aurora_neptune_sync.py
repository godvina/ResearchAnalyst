#!/usr/bin/env python3
"""EC2 Aurora→Neptune entity sync — runs unattended, self-terminates when done.

Pulls distinct entities from Aurora and creates Neptune graph nodes.
Uses __.V() for edge creation (Neptune requires anonymous traversals).
"""
import json
import time
import uuid
import boto3

LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
CASE_NAME = "Epstein Main"
LABEL = f"Entity_{CASE_ID}"
BATCH_SIZE = 5000

lam = boto3.client("lambda", region_name=REGION)

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

print(f"{'='*60}")
print(f"Aurora → Neptune Sync: {CASE_NAME}")
print(f"Case ID: {CASE_ID}")
print(f"{'='*60}")

# Step 1: Check current Neptune node count
result, err = gremlin(f"g.V().hasLabel('{LABEL}').count()")
print(f"Current Neptune nodes: {result}")

# Step 2: Get total Aurora entities
data = query_aurora_entities(1, 0)
if "error" in data:
    print(f"ERROR: {data['error']}")
    exit(1)
total = data.get("total", 0)
print(f"Total distinct entities in Aurora: {total:,}")

# Step 3: Paginate through Aurora entities and create Neptune nodes
created = 0
skipped = 0
errors = 0
start = time.time()
offset = 0

while offset < total:
    data = query_aurora_entities(BATCH_SIZE, offset)
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
        escaped_name = name.replace("'", "\\'").replace("\\", "\\\\")

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
                  f"{rate:.0f}/min (offset: {offset + entities.index(ent)})")

        time.sleep(0.05)  # Rate limit to avoid Neptune throttling

    offset += BATCH_SIZE

elapsed = time.time() - start

# Step 4: Verify
result, err = gremlin(f"g.V().hasLabel('{LABEL}').count()")
print(f"\nFinal Neptune nodes: {result}")

print(f"\n{'='*60}")
print(f"Aurora → Neptune Sync Complete")
print(f"  Created: {created:,}")
print(f"  Skipped: {skipped:,}")
print(f"  Errors:  {errors:,}")
print(f"  Elapsed: {elapsed/60:.1f} minutes")
print(f"{'='*60}")
