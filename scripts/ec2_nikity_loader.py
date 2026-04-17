#!/usr/bin/env python3
"""EC2 script: Load Nikity/Epstein-Files text into Aurora via Lambda.

Designed to run on an r6i.large (16GB RAM) EC2 in us-east-1.
Downloads the Nikity Parquet dataset, extracts text-only rows,
filters to DS9-12 (or all), deduplicates, and inserts via Lambda.

Usage on EC2:
    pip install datasets boto3
    python ec2_nikity_loader.py
    python ec2_nikity_loader.py --datasets 9,10,11,12
    python ec2_nikity_loader.py --all-datasets
"""

import argparse
import json
import logging
import time
import uuid

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
HF_DATASET = "Nikity/Epstein-Files"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--datasets", type=str, default="9,10,11,12",
                   help="Comma-separated dataset IDs to include")
    p.add_argument("--all-datasets", action="store_true",
                   help="Include all datasets (not just 9-12)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-docs", type=int, default=0)
    return p.parse_args()


def insert_batch(lam, case_id, docs):
    payload = {
        "action": "batch_insert_documents",
        "case_id": case_id,
        "documents": [
            {
                "document_id": str(uuid.uuid4()),
                "source_filename": d["source_filename"],
                "raw_text": d["raw_text"][:50_000],
                "source_metadata": d["source_metadata"],
            }
            for d in docs if d.get("raw_text", "").strip()
        ],
        "skip_embeddings": True,
        "skip_entity_extraction": True,
    }
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    body = json.loads(resp["Payload"].read().decode())
    if resp.get("FunctionError"):
        return {"error": body}
    return body


def main():
    args = parse_args()
    include_ds = None
    if not args.all_datasets:
        include_ds = {int(x.strip()) for x in args.datasets.split(",") if x.strip()}

    from datasets import load_dataset

    logger.info("Loading Nikity/Epstein-Files (full download, text columns only)...")
    logger.info("This requires ~16GB RAM for the Parquet files...")

    # Load the full dataset — on EC2 with 16GB RAM this works
    ds = load_dataset(HF_DATASET, split="train")
    logger.info("Dataset loaded: %d total rows", len(ds))

    print("=" * 60)
    print("  Nikity Epstein-Files Loader (EC2)")
    print(f"  Case: {args.case_id}")
    print(f"  Total rows: {len(ds):,}")
    print(f"  Target datasets: {include_ds or 'ALL'}")
    print("=" * 60)

    # Extract text-only docs
    docs = []
    seen = set()
    skipped_image = 0
    skipped_ds = 0
    skipped_empty = 0
    skipped_dup = 0

    print("\n  Filtering to text docs...")
    for i in range(len(ds)):
        row = ds[i]

        # Skip non-text
        ft = (row.get("file_type") or "").lower()
        if ft in ("image", "audio", "video"):
            skipped_image += 1
            continue

        # Filter by dataset
        ds_id = row.get("dataset_id")
        if include_ds and ds_id is not None and int(ds_id) not in include_ds:
            skipped_ds += 1
            continue

        # Get text
        text = row.get("text_content") or ""
        if not text.strip() or len(text.strip()) < 30:
            skipped_empty += 1
            continue

        # Dedup by doc_id
        doc_id = row.get("doc_id", "")
        if doc_id in seen:
            skipped_dup += 1
            continue
        seen.add(doc_id)

        filename = row.get("file_name") or doc_id
        meta_raw = row.get("metadata") or "{}"
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else (meta_raw or {})

        docs.append({
            "source_filename": filename,
            "raw_text": text,
            "source_metadata": {
                "source": "nikity_hf",
                "dataset_id": ds_id,
                "doc_id": doc_id,
                "online_url": row.get("online_url", ""),
                **meta,
            },
        })

        if (i + 1) % 10000 == 0:
            print(f"    Scanned {i + 1:,}/{len(ds):,}, kept {len(docs):,}...")

        if args.max_docs and len(docs) >= args.max_docs:
            break

    print(f"\n  Filter complete:")
    print(f"    Image/audio/video: {skipped_image:,}")
    print(f"    Wrong dataset:     {skipped_ds:,}")
    print(f"    Empty/short:       {skipped_empty:,}")
    print(f"    Duplicates:        {skipped_dup:,}")
    print(f"    Docs to insert:    {len(docs):,}")

    if args.dry_run:
        total_chars = sum(len(d["raw_text"]) for d in docs)
        print(f"\n  [DRY RUN] {len(docs):,} docs, {total_chars:,} chars ({total_chars/1_000_000:.1f} MB)")
        return

    # Insert
    lam = boto3.client("lambda", region_name=REGION)
    total_inserted = 0
    total_errors = 0
    start = time.time()
    batch_size = args.batch_size
    total_batches = (len(docs) + batch_size - 1) // batch_size

    print(f"\n  Inserting {len(docs):,} docs in {total_batches} batches...")

    for batch_start in range(0, len(docs), batch_size):
        batch = docs[batch_start:batch_start + batch_size]
        batch_num = (batch_start // batch_size) + 1

        result = insert_batch(lam, args.case_id, batch)
        if "error" in result:
            total_errors += len(batch)
            logger.error("Batch %d failed: %s", batch_num, str(result)[:300])
        else:
            total_inserted += result.get("documents_inserted", 0)

        if batch_num % 20 == 0 or batch_num == total_batches:
            print(f"    Batch {batch_num}/{total_batches}: total inserted {total_inserted:,}")

        time.sleep(0.5)

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
    except Exception as e:
        logger.warning("Stats refresh failed: %s", e)

    print(f"\n{'=' * 60}")
    print(f"  Done: {total_inserted:,} inserted, {total_errors:,} errors, {elapsed/60:.1f} min")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
