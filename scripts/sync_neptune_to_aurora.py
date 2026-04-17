"""Sync Neptune graph entities to Aurora entities table.

Invokes the CaseFiles Lambda with a custom action to read all entities
from Neptune for a given case and upsert them into Aurora. This bridges
the gap where Neptune has graph data but Aurora entities table is empty.

Requires: Lambda deployed with the neptune_aurora_sync handler.

Usage:
    python scripts/sync_neptune_to_aurora.py                    # Epstein Combined
    python scripts/sync_neptune_to_aurora.py --case-id <uuid>   # any case
    python scripts/sync_neptune_to_aurora.py --dry-run           # check without syncing
"""
import argparse
import boto3
import json

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
EPSTEIN_COMBINED = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"


def sync(case_id: str, dry_run: bool = False):
    lam = boto3.client("lambda", region_name=REGION)

    if dry_run:
        print(f"DRY RUN — would sync Neptune entities to Aurora for case {case_id}")
        print(f"Lambda: {LAMBDA_NAME}")
        print(f"Action: sync_neptune_to_aurora")
        print()
        print("To run for real, remove --dry-run flag.")
        return

    print(f"Syncing Neptune → Aurora for case {case_id}")
    print(f"Lambda: {LAMBDA_NAME}")
    print()

    payload = {
        "action": "sync_neptune_to_aurora",
        "case_id": case_id,
    }

    print("Invoking Lambda (synchronous)...")
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )

    status = resp["StatusCode"]
    body = json.loads(resp["Payload"].read().decode())

    print(f"Status: {status}")
    print(f"Result: {json.dumps(body, indent=2)}")

    if "error" in body:
        print(f"\nError: {body['error']}")
        return

    print(f"\nNeptune entities found: {body.get('neptune_entities', '?')}")
    print(f"Aurora rows upserted:   {body.get('aurora_upserted', '?')}")
    print(f"Errors:                 {body.get('errors', '?')}")

    if body.get("aurora_upserted", 0) > 0:
        print("\nEntity count updated on case_files table.")
        print("Theory generation should now work for this case.")

    # --- Refresh case stats after sync completes ---
    print(f"\nRefreshing case stats for case {case_id}...")
    refresh_payload = {
        "action": "refresh_case_stats",
        "case_id": case_id,
    }

    try:
        refresh_resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(refresh_payload),
        )

        refresh_status = refresh_resp["StatusCode"]
        refresh_body = json.loads(refresh_resp["Payload"].read().decode())

        if "error" in refresh_body:
            print(f"Warning: refresh_case_stats returned error: {refresh_body['error']}")
        else:
            doc_count = refresh_body.get("document_count", "?")
            entity_count = refresh_body.get("entity_count", "?")
            rel_count = refresh_body.get("relationship_count", "?")
            print(f"Refreshed case stats (HTTP {refresh_status}):")
            print(f"  document_count:     {doc_count}")
            print(f"  entity_count:       {entity_count}")
            print(f"  relationship_count: {rel_count}")
            print("\nSidebar will now display correct counts.")
    except Exception as e:
        print(f"Warning: Failed to refresh case stats: {e}")
        print("Sync completed but stats may be stale. Run refresh manually if needed.")


def main():
    parser = argparse.ArgumentParser(description="Sync Neptune entities to Aurora")
    parser.add_argument("--case-id", default=EPSTEIN_COMBINED,
                        help=f"Case ID (default: Epstein Combined {EPSTEIN_COMBINED})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without executing")
    args = parser.parse_args()

    sync(args.case_id, args.dry_run)


if __name__ == "__main__":
    main()
