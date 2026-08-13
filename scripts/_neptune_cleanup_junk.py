"""Neptune Cleanup — Drop garbage entity types, keep legitimate ones.

SAFETY: Only drops nodes from OUR case label with hasNot('source').
Other cases, other labels, and rhowardstone nodes are untouched.
Edges connecting to dropped nodes will be auto-removed by Neptune.
"""
import boto3
import json
import re
import time

lam = boto3.client("lambda", region_name="us-east-1")
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LABEL = "Entity_" + CASE_ID

# Entity types to KEEP (legitimate investigation entities)
KEEP_TYPES = {
    "person", "organization", "location", "date", "event",
    "financial_amount", "financial", "phone_number", "email", "address",
    "account_number", "vehicle", "artifact", "civilization", "theme",
    "document", "legal_case", "legal", "statute", "legislation", "flight",
    "role", "court_location", "case", "law",
}


def gremlin_raw(q, timeout=300):
    """Execute Gremlin, return raw result string."""
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps({"action": "gremlin_query", "case_id": CASE_ID,
                           "query": q, "timeout": timeout, "max_result_len": 50000}))
    d = json.loads(r["Payload"].read().decode())
    return d.get("result", d.get("error", ""))


def get_count(q):
    """Execute count query and extract integer."""
    result = gremlin_raw(q)
    if isinstance(result, str):
        match = re.search(r"'@value': (\d+)", result)
        if match:
            return int(match.group(1))
    return 0


def get_list(q):
    """Execute query returning a list of strings."""
    result = gremlin_raw(q)
    if isinstance(result, str):
        # Extract all string values from the g:List response
        matches = re.findall(r"'([^']+)'", result)
        # Filter out Neptune type annotations
        filtered = [m for m in matches if not m.startswith("g:") and not m.startswith("@")]
        return filtered
    return []


print("=" * 60)
print("NEPTUNE CLEANUP — Remove Garbage Entity Types")
print("=" * 60)
print(f"  Case: {CASE_ID}")
print(f"  ONLY touching nodes with label={LABEL} and hasNot('source')")
print(f"  Other cases/labels are SAFE")

# Step 1: Get all entity types for old (untagged) nodes
print("\nStep 1: Getting entity types for untagged nodes...")
all_types = get_list(
    "g.V().hasLabel('" + LABEL + "').hasNot('source')"
    ".values('entity_type').dedup()"
)
print(f"  Found {len(all_types)} distinct entity types")

# Step 2: Count key types to understand impact
print("\nStep 2: Counting major types...")
keep_types = {}
drop_types = {}

# Only count the high-volume types we know about
priority_types = [
    "person", "email", "address", "organization", "location", "date",
    "financial_amount", "financial", "phone_number", "event",
    "document", "legal", "vehicle", "object", "other", "abstract",
    "identifier", "number", "product", "rule", "classification",
]

for etype in priority_types:
    if etype in all_types:
        count = get_count(
            "g.V().hasLabel('" + LABEL + "').hasNot('source')"
            ".has('entity_type','" + etype + "').count()"
        )
        if etype in KEEP_TYPES:
            keep_types[etype] = count
        else:
            drop_types[etype] = count
        print(f"    {etype}: {count:,} {'[KEEP]' if etype in KEEP_TYPES else '[DROP]'}")

# Count all remaining types (smaller ones) as DROP
remaining_types = [t for t in all_types if t not in priority_types and t not in KEEP_TYPES]
print(f"\n  Additional garbage types to drop: {len(remaining_types)}")

keep_total = sum(keep_types.values())
drop_total = sum(drop_types.values())

print(f"\n  SUMMARY (major types only):")
print(f"    Keeping: {keep_total:,} nodes")
print(f"    Dropping: {drop_total:,} nodes (just from major types)")
print(f"    + {len(remaining_types)} minor garbage types")

# Step 3: Drop the garbage
print(f"\nStep 3: Dropping garbage nodes...")
print("  (Neptune drops nodes + all attached edges)")

total_dropped = 0

# Drop the major garbage types first
all_to_drop = list(drop_types.keys()) + remaining_types

for etype in all_to_drop:
    safe_type = etype.replace("'", "\\\\'").replace(" ", " ")
    # Drop in batches of 10000
    passes = 0
    while passes < 100:  # safety limit
        q = (
            "g.V().hasLabel('" + LABEL + "')"
            ".has('entity_type','" + safe_type + "')"
            ".hasNot('source')"
            ".limit(10000).drop()"
        )
        gremlin_raw(q, timeout=300)
        passes += 1

        # Check if any remain
        remaining = get_count(
            "g.V().hasLabel('" + LABEL + "')"
            ".has('entity_type','" + safe_type + "')"
            ".hasNot('source').count()"
        )
        if remaining == 0:
            break

    count = drop_types.get(etype, 0)
    total_dropped += count
    if count >= 100:
        print(f"    Dropped {etype}: {count:,}")

print(f"\n  Nodes dropped: ~{total_dropped:,}")

# Step 4: Verify
print("\nStep 4: Final verification...")
time.sleep(3)
remaining_nodes = get_count("g.V().hasLabel('" + LABEL + "').count()")
rh_nodes = get_count("g.V().hasLabel('" + LABEL + "').has('source','rhowardstone_kg').count()")
total_edges = get_count("g.E().count()")
total_vertices = get_count("g.V().count()")

print(f"  Total graph vertices: {total_vertices:,}")
print(f"  Our case nodes: {remaining_nodes:,}")
print(f"    - rhowardstone (curated): {rh_nodes}")
print(f"    - old (kept types): {remaining_nodes - rh_nodes:,}")
print(f"  Total edges: {total_edges:,}")

print("\n" + "=" * 60)
print("CLEANUP COMPLETE")
print("=" * 60)
