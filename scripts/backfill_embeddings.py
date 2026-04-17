"""Backfill embeddings for documents that have text but no embedding vector.

Queries Aurora for docs with NULL embedding, generates Titan Embed vectors
via the Lambda, and updates the rows.

Usage:
    python scripts/backfill_embeddings.py --dry-run
    python scripts/backfill_embeddings.py
    python scripts/backfill_embeddings.py --batch-size 50 --max-docs 1000
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
    p = argparse.ArgumentParser(description="Backfill embeddings for docs missing vectors")
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=50, help="Docs per Lambda call")
    p.add_argument("--max-docs", type=int, default=0, help="Limit (0=all)")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    lam = boto3.client("lambda", region_name=REGION)

    # Step 1: Get count of docs needing embeddings
    print("  Querying for docs without embeddings...")
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "backfill_embeddings_count",
            "case_id": args.case_id,
        }),
    )
    count_result = json.loads(resp["Payload"].read().decode())
    total_missing = count_result.get("missing_count", 0)
    total_with = count_result.get("has_embedding_count", 0)

    print(f"  Docs with embeddings:    {total_with:,}")
    print(f"  Docs missing embeddings: {total_missing:,}")

    if total_missing == 0:
        print("  All docs have embeddings. Nothing to do.")
        return

    target = min(total_missing, args.max_docs) if args.max_docs else total_missing
    est_cost = target * 0.0001  # ~$0.0001 per Titan Embed call
    est_time = (target / args.batch_size) * 3  # ~3 sec per batch

    print(f"\n  Target: {target:,} docs")
    print(f"  Est. cost: ${est_cost:.2f}")
    print(f"  Est. time: {est_time / 60:.0f} minutes")

    if args.dry_run:
        print("\n  [DRY RUN] No changes made.")
        return

    # Step 2: Process in batches
    total_processed = 0
    total_errors = 0
    start = time.time()
    batch_num = 0

    print(f"\n  Generating embeddings in batches of {args.batch_size}...")

    while total_processed < target:
        batch_num += 1
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "action": "backfill_embeddings_batch",
                "case_id": args.case_id,
                "batch_size": args.batch_size,
            }),
        )
        result = json.loads(resp["Payload"].read().decode())

        if resp.get("FunctionError") or "error" in result:
            total_errors += 1
            logger.error("Batch %d failed: %s", batch_num, str(result)[:300])
            if total_errors > 5:
                print("  Too many errors, stopping.")
                break
            time.sleep(5)
            continue

        processed = result.get("processed", 0)
        remaining = result.get("remaining", 0)
        total_processed += processed

        if batch_num % 10 == 0 or processed == 0:
            elapsed = time.time() - start
            rate = total_processed / max(elapsed, 1) * 60
            print(f"    Batch {batch_num}: +{processed} (total: {total_processed:,}, "
                  f"remaining: {remaining:,}, {rate:.0f} docs/min)")

        if processed == 0:
            print("  No more docs to process.")
            break

        time.sleep(0.5)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  Embedding Backfill Complete")
    print(f"  Processed: {total_processed:,}")
    print(f"  Errors: {total_errors:,}")
    print(f"  Elapsed: {elapsed / 60:.1f} minutes")
    print(f"  Est. cost: ${total_processed * 0.0001:.2f}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
