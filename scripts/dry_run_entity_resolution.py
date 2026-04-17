"""Local dry run of entity resolution — fetches entities via Patterns Lambda,
runs fuzzy matching locally, shows what WOULD be merged without touching Neptune.

Usage: python scripts/dry_run_entity_resolution.py
"""
import boto3
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.entity_resolution_service import (
    EntityResolutionService,
    compute_similarity,
    LLM_REVIEW_THRESHOLD,
    AUTO_MERGE_THRESHOLD,
)

REGION = "us-east-1"
PATTERNS_LAMBDA = "ResearchAnalystStack-PatternsLambda457C2046-toyjGz36d37l"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

lam = boto3.client("lambda", region_name=REGION)


def fetch_entities_via_lambda():
    """Get entity list from Neptune via the already-deployed Patterns Lambda."""
    resp = lam.invoke(
        FunctionName=PATTERNS_LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "httpMethod": "POST",
            "path": f"/cases/{CASE_ID}/patterns",
            "pathParameters": {"id": CASE_ID},
            "queryStringParameters": {},
            "body": json.dumps({"graph": True}),
            "headers": {"Content-Type": "application/json"},
        }),
    )
    result = json.loads(resp["Payload"].read().decode())
    body = json.loads(result.get("body", "{}"))
    nodes = body.get("nodes", [])
    # Convert to entity format
    entities = []
    for n in nodes:
        entities.append({
            "name": n.get("name", ""),
            "type": n.get("type", ""),
            "occurrence_count": n.get("degree", 1),
            "confidence": n.get("confidence", 0.5),
        })
    return entities


def main():
    print("=" * 60)
    print("Entity Resolution DRY RUN (local)")
    print(f"Case: {CASE_ID[:8]}...")
    print("=" * 60)

    print("\nFetching entities via Patterns Lambda...")
    entities = fetch_entities_via_lambda()
    print(f"Got {len(entities)} entities from Neptune (top 200 by degree)")

    # Run fuzzy matching locally
    svc = EntityResolutionService(neptune_endpoint="dry-run", neptune_port="8182")
    candidates = svc.find_candidates(entities)

    print(f"\nFound {len(candidates)} merge candidates:")
    print(f"  Auto-merge (sim >= {AUTO_MERGE_THRESHOLD}): "
          f"{sum(1 for c in candidates if c.method == 'auto')}")
    print(f"  Needs LLM review ({LLM_REVIEW_THRESHOLD} <= sim < {AUTO_MERGE_THRESHOLD}): "
          f"{sum(1 for c in candidates if c.method == 'needs_llm')}")

    # Show all candidates
    if candidates:
        print(f"\n{'─'*60}")
        print("MERGE CANDIDATES (sorted by similarity):")
        print(f"{'─'*60}")
        for c in candidates:
            marker = "✓ AUTO" if c.method == "auto" else "? LLM"
            print(f"  [{marker}] {c.similarity:.3f}  "
                  f'"{c.name_a}" ↔ "{c.name_b}" ({c.entity_type})')

    # Build clusters (without LLM, treat needs_llm as auto for preview)
    for c in candidates:
        if c.method == "needs_llm":
            c.method = "auto"  # preview mode: assume all merge
    clusters = svc.build_clusters(candidates, entities)

    if clusters:
        print(f"\n{'─'*60}")
        print(f"MERGE CLUSTERS ({len(clusters)} clusters):")
        print(f"{'─'*60}")
        for cl in clusters:
            print(f"\n  Canonical: {cl.canonical_name} ({cl.entity_type})")
            print(f"  Aliases:   {cl.aliases}")
            print(f"  Total occ: {cl.total_occurrences}")
    else:
        print("\nNo merge clusters found in the top 200 entities.")
        print("(Full resolution with all entities may find more candidates)")

    print(f"\n{'='*60}")
    print("DRY RUN COMPLETE — no changes made to Neptune or OpenSearch")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
