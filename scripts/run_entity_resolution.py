"""Run entity resolution for a case via Lambda invocation.

Usage:
    python scripts/run_entity_resolution.py                    # dry run (default)
    python scripts/run_entity_resolution.py --execute          # actually merge
    python scripts/run_entity_resolution.py --no-llm           # skip LLM confirmation
    python scripts/run_entity_resolution.py --case-id <id>     # specific case
"""

import argparse
import boto3
import json
from botocore.config import Config

REGION = "us-east-1"
GRAPH_LOAD_LAMBDA = "ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg"
DEFAULT_CASE = "7f05e8d5-4492-4f19-8894-25367606db96"  # Main Epstein


def main():
    parser = argparse.ArgumentParser(description="Run entity resolution")
    parser.add_argument("--case-id", default=DEFAULT_CASE)
    parser.add_argument("--execute", action="store_true",
                        help="Actually merge (default is dry run)")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM confirmation for ambiguous pairs")
    args = parser.parse_args()

    # We'll invoke the entity resolution Lambda directly
    # For now, use the graph load Lambda name — we'll need to deploy
    # the entity_resolution_handler as a separate Lambda
    # OR we can run it locally if we have VPC access

    # Since we can't reach Neptune from local, invoke via Lambda
    lam = boto3.client("lambda", region_name=REGION, config=Config(
        read_timeout=900,
        connect_timeout=10,
        retries={"max_attempts": 0},
    ))

    event = {
        "case_id": args.case_id,
        "dry_run": not args.execute,
        "use_llm": not args.no_llm,
    }

    print(f"{'='*60}")
    print(f"Entity Resolution — {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"Case: {args.case_id}")
    print(f"LLM confirmation: {'yes' if not args.no_llm else 'no'}")
    print(f"{'='*60}")

    # TODO: Update this to the actual entity resolution Lambda name
    # once deployed. For now, print the event for manual invocation.
    ENTITY_RES_LAMBDA = "ResearchAnalystStack-EntityResolutionLambda"

    try:
        resp = lam.invoke(
            FunctionName=ENTITY_RES_LAMBDA,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )
        result = json.loads(resp["Payload"].read().decode())

        print(f"\nEntities fetched: {result.get('entities_fetched', '?')}")
        print(f"Candidates found: {result.get('candidates_found', '?')}")
        print(f"Merge clusters: {result.get('clusters', '?')}")

        stats = result.get("merge_stats", {})
        print(f"\nMerge stats:")
        print(f"  Merged: {stats.get('merged', 0)}")
        print(f"  Nodes dropped: {stats.get('nodes_dropped', 0)}")
        print(f"  Edges relinked: {stats.get('edges_relinked', 0)}")
        print(f"  Errors: {len(stats.get('errors', []))}")

        print(f"\nOpenSearch updated: {result.get('opensearch_updated', 0)}")

        clusters = result.get("cluster_details", [])
        if clusters:
            print(f"\nCluster details ({len(clusters)} clusters):")
            for c in clusters[:20]:
                print(f"  {c['canonical']} ({c['type']})")
                print(f"    aliases: {c['aliases']}")
                print(f"    total occurrences: {c['total_occurrences']}")

    except Exception as e:
        if "ResourceNotFoundException" in str(e) or "Function not found" in str(e):
            print(f"\nLambda not deployed yet. Deploy entity_resolution_handler first.")
            print(f"Event payload for manual invocation:")
            print(json.dumps(event, indent=2))
        else:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()
