"""Restore dropped Neptune entities from Aurora.

The entities ARE in Aurora (found at high offsets). Paginate through
ALL 255K Aurora entities, filter for the dropped types, and re-create
them in Neptune.
"""
import boto3
import json
import re
import time
from collections import defaultdict

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + CASE_ID

DROPPED_TYPES = {"object", "other", "identifier", "number", "product",
                 "rule", "classification", "abstract",
                 # Include ALL non-standard types that might have been dropped
                 "abbreviation", "miscellaneous", "measurement", "attribute",
                 "policy", "standard", "term", "thing", "information",
                 "device", "medical", "symptom", "mechanism",
                 }

lam = boto3.client("lambda", region_name=REGION)


def invoke_lambda(payload):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps(payload))
    return json.loads(r["Payload"].read().decode())


def gremlin(q, timeout=60):
    r = invoke_lambda({"action": "gremlin_query", "case_id": CASE_ID,
                       "query": q, "timeout": timeout})
    return r.get("result", r.get("error", ""))


print("=" * 70)
print("RESTORE DROPPED ENTITIES: Aurora → Neptune")
print("=" * 70)

# Phase 1: Scan Aurora for all entities with dropped types
print("\nPhase 1: Scanning Aurora for dropped-type entities...")
page_size = 5000
offset = 0
total_aurora = 255922
dropped_entities = []
type_counts = defaultdict(int)

while offset < total_aurora:
    result = invoke_lambda({
        "action": "query_aurora_entities",
        "case_id": CASE_ID,
        "limit": page_size,
        "offset": offset,
    })
    entities = result.get("entities", [])
    if not entities:
        break

    for ent in entities:
        etype = ent.get("type", "")
        if etype in DROPPED_TYPES:
            dropped_entities.append(ent)
            type_counts[etype] += 1

    offset += page_size
    if offset % 50000 == 0:
        print(f"  Scanned {offset:,}/{total_aurora:,} — "
              f"found {len(dropped_entities)} dropped-type entities so far")

print(f"\n  FOUND {len(dropped_entities)} entities to restore!")
print(f"  By type:")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"    {t}: {c}")

# Phase 2: Re-create in Neptune
print(f"\nPhase 2: Re-creating {len(dropped_entities)} nodes in Neptune...")
created = 0
errors = 0
start = time.time()

for i, ent in enumerate(dropped_entities):
    name = ent.get("name", "")
    etype = ent.get("type", "unknown")
    count = ent.get("count", 1)
    confidence = ent.get("confidence", 0.9)

    if not name or len(name) < 2:
        continue

    # Sanitize for Gremlin
    escaped_name = name.replace("'", "\\'").replace("\\", "\\\\")
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:100]
    vid = f"restored_{etype}_{safe_name}"

    q = (
        f"g.addV('{LABEL}')"
        f".property(id, '{vid}')"
        f".property('canonical_name', '{escaped_name}')"
        f".property('entity_type', '{etype}')"
        f".property('confidence', {confidence})"
        f".property('occurrence_count', {count})"
        f".property('case_file_id', '{CASE_ID}')"
        f".property('source', 'restored_from_aurora')"
    )

    result = gremlin(q)
    if "error" in str(result).lower() and "already exists" not in str(result).lower():
        errors += 1
        if errors <= 5:
            print(f"    Error: {str(result)[:150]}")
    else:
        created += 1

    if (i + 1) % 500 == 0:
        elapsed = time.time() - start
        rate = (i + 1) / elapsed * 60
        print(f"    Progress: {i+1}/{len(dropped_entities)} "
              f"({created} created, {errors} errors, {rate:.0f}/min)")

    time.sleep(0.05)  # Rate limit

elapsed = time.time() - start

# Phase 3: Verify
print(f"\n{'='*70}")
print(f"RESTORATION COMPLETE")
print(f"{'='*70}")
print(f"  Entities restored: {created}")
print(f"  Errors: {errors}")
print(f"  Time: {elapsed/60:.1f} minutes")
print(f"  Source: Aurora entities table")

# Check new count
result = gremlin(f"g.V().hasLabel('{LABEL}').has('source','restored_from_aurora').count()")
match = re.search(r"'@value': (\d+)", str(result))
if match:
    print(f"  Verified in Neptune: {match.group(1)} restored nodes")

# Save what we recovered for the record
with open("scripts/restored_entities_manifest.json", "w") as f:
    json.dump({
        "restored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_restored": created,
        "errors": errors,
        "type_counts": dict(type_counts),
        "sample_entities": [{"name": e["name"], "type": e["type"], "count": e.get("count", 1)}
                           for e in dropped_entities[:100]],
    }, f, indent=2)
print(f"  Manifest saved: scripts/restored_entities_manifest.json")
