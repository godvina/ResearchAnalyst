"""Backfill entity extraction for documents that have text but no entities.

Queries Aurora for docs without entities, runs Bedrock Haiku extraction
via the Lambda, and inserts entities into Aurora.

Usage:
    python scripts/backfill_entities.py --dry-run
    python scripts/backfill_entities.py
    python scripts/backfill_entities.py --batch-size 20 --max-docs 500
"""

import argparse
import json
import logging
import time

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"


def parse_args():
    p = argparse.ArgumentParser(description="Backfill entity extraction for docs missing entities")
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=20, help="Docs per Lambda call")
    p.add_argument("--max-docs", type=int, default=0, help="Limit (0=all)")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    lam = boto3.client("lambda", region_name=REGION)

    # Count docs needing entities
    print("  Querying for docs without entities...")
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "backfill_entities_count",
            "case_id": args.case_id,
        }),
    )
    result = json.loads(resp["Payload"].read().decode())
    missing = result.get("missing_count", 0)
    has = result.get("has_entities_count", 0)

    print(f"  Docs with entities:    {has:,}")
    print(f"  Docs missing entities: {missing:,}")

    if missing == 0:
        print("  All docs have entities. Nothing to do.")
        return

    target = min(missing, args.max_docs) if args.max_docs else missing
    est_cost = target * 0.00025
    est_time = (target / args.batch_size) * 8  # ~8 sec per batch (Bedrock calls)

    print(f"\n  Target: {target:,} docs")
    print(f"  Est. cost: ${est_cost:.2f}")
    print(f"  Est. time: {est_time / 60:.0f} minutes")

    if args.dry_run:
        print("\n  [DRY RUN] No changes made.")
        return

    # Process
    total_processed = 0
    total_entities = 0
    total_errors = 0
    start = time.time()
    batch_num = 0

    print(f"\n  Extracting entities in batches of {args.batch_size}...")

    while total_processed < target:
        batch_num += 1
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "action": "backfill_entities_batch",
                "case_id": args.case_id,
                "batch_size": args.batch_size,
            }),
        )
        result = json.loads(resp["Payload"].read().decode())

        if resp.get("FunctionError") or "error" in result:
            total_errors += 1
            logger.error("Batch %d failed: %s", batch_num, str(result)[:300])
            if total_errors > 10:
                print("  Too many errors, stopping.")
                break
            time.sleep(5)
            continue

        processed = result.get("processed", 0)
        entities = result.get("entities_extracted", 0)
        remaining = result.get("remaining", 0)
        total_processed += processed
        total_entities += entities

        if batch_num % 10 == 0 or processed == 0:
            elapsed = time.time() - start
            rate = total_processed / max(elapsed, 1) * 60
            print(f"    Batch {batch_num}: +{processed} docs, +{entities} entities "
                  f"(total: {total_processed:,}, remaining: {remaining:,}, {rate:.0f} docs/min)")

        if processed == 0:
            print("  No more docs to process.")
            break

        time.sleep(1)

    elapsed = time.time() - start

    # Refresh stats
    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "refresh_case_stats", "case_id": args.case_id}),
        )
        stats = json.loads(resp["Payload"].read().decode())
        print(f"\n  Case stats: docs={stats.get('document_count','?')}, entities={stats.get('entity_count','?')}")
    except Exception:
        pass

    print(f"\n{'=' * 60}")
    print(f"  Entity Extraction Complete")
    print(f"  Docs processed:  {total_processed:,}")
    print(f"  Entities found:  {total_entities:,}")
    print(f"  Errors:          {total_errors:,}")
    print(f"  Elapsed:         {elapsed / 60:.1f} minutes")
    print(f"  Est. cost:       ${total_processed * 0.00025:.2f}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
