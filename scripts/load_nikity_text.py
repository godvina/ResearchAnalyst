"""Load pre-extracted text from Nikity/Epstein-Files HuggingFace dataset.

Streams the dataset (no full download needed), filters to text-only rows,
deduplicates against existing Aurora docs, and inserts via Lambda.

Usage:
    python scripts/load_nikity_text.py --dry-run
    python scripts/load_nikity_text.py
    python scripts/load_nikity_text.py --max-docs 1000
"""

import argparse
import json
import logging
import os
import time
import uuid

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
HF_DATASET = "Nikity/Epstein-Files"
PROGRESS_FILE = "scripts/nikity_ingestion_progress.json"


def parse_args():
    p = argparse.ArgumentParser(description="Load Nikity Epstein text into Aurora")
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-docs", type=int, default=0)
    p.add_argument("--skip-datasets", type=str, default="",
                   help="Comma-separated dataset IDs to skip (e.g., '1,2,3,4,5')")
    return p.parse_args()


def insert_batch(lam_client, case_id, docs):
    """Insert a batch of documents via Lambda."""
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
    resp = lam_client.invoke(
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
    skip_ds = set()
    if args.skip_datasets:
        skip_ds = {int(x.strip()) for x in args.skip_datasets.split(",") if x.strip()}

    from datasets import load_dataset

    logger.info("Streaming Nikity/Epstein-Files dataset (text rows only)...")
    ds = load_dataset(HF_DATASET, split="train", streaming=True)

    print("=" * 60)
    print("  Nikity Epstein-Files Text Loader")
    print(f"  Case: {args.case_id}")
    print(f"  Skip datasets: {skip_ds or 'none'}")
    print("=" * 60)

    docs = []
    total_scanned = 0
    skipped_no_text = 0
    skipped_ds = 0
    skipped_short = 0
    skipped_image = 0
    seen_doc_ids = set()

    print("\n  Streaming and filtering...")

    for row in ds:
        total_scanned += 1

        # Skip non-text rows (images, audio, video)
        file_type = (row.get("file_type") or "").lower()
        if file_type in ("image", "audio", "video"):
            skipped_image += 1
            continue

        # Skip specified datasets
        ds_id = row.get("dataset_id")
        if ds_id is not None and int(ds_id) in skip_ds:
            skipped_ds += 1
            continue

        # Get text content
        text = row.get("text_content") or ""
        if not text.strip() or len(text.strip()) < 30:
            skipped_no_text += 1
            continue

        # Deduplicate by doc_id (dataset has multiple rows per doc — text + images)
        doc_id = row.get("doc_id", "")
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)

        filename = row.get("file_name") or doc_id or f"nikity_{total_scanned}"
        ds_id_val = row.get("dataset_id", "unknown")
        metadata_raw = row.get("metadata") or "{}"
        if isinstance(metadata_raw, str):
            try:
                meta = json.loads(metadata_raw)
            except Exception:
                meta = {}
        else:
            meta = metadata_raw if isinstance(metadata_raw, dict) else {}

        docs.append({
            "source_filename": filename,
            "raw_text": text,
            "source_metadata": {
                "source": "nikity_hf",
                "dataset_id": ds_id_val,
                "doc_id": doc_id,
                "online_url": row.get("online_url", ""),
                **meta,
            },
        })

        if total_scanned % 5000 == 0:
            print(f"    Scanned {total_scanned:,}, kept {len(docs):,}...")

        if args.max_docs and len(docs) >= args.max_docs:
            print(f"    Reached --max-docs limit ({args.max_docs})")
            break

    print(f"\n  Scan complete:")
    print(f"    Total rows scanned: {total_scanned:,}")
    print(f"    Image/audio/video:  {skipped_image:,}")
    print(f"    Skipped datasets:   {skipped_ds:,}")
    print(f"    No/short text:      {skipped_no_text:,}")
    print(f"    Docs to insert:     {len(docs):,}")

    if args.dry_run:
        total_chars = sum(len(d["raw_text"]) for d in docs)
        print(f"\n  [DRY RUN] Would insert {len(docs):,} documents")
        print(f"  Total text: {total_chars:,} chars ({total_chars / 1_000_000:.1f} MB)")
        return

    # Insert
    lam = boto3.client("lambda", region_name=REGION)
    batch_size = args.batch_size
    total_inserted = 0
    total_errors = 0
    start_time = time.time()

    print(f"\n  Inserting {len(docs):,} documents in batches of {batch_size}...")

    for batch_start in range(0, len(docs), batch_size):
        batch = docs[batch_start:batch_start + batch_size]
        batch_num = (batch_start // batch_size) + 1
        total_batches = (len(docs) + batch_size - 1) // batch_size

        result = insert_batch(lam, args.case_id, batch)

        if "error" in result:
            total_errors += len(batch)
            logger.error("Batch %d failed: %s", batch_num, str(result)[:300])
        else:
            inserted = result.get("documents_inserted", 0)
            total_inserted += inserted
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"    Batch {batch_num}/{total_batches}: inserted {inserted}")

        if batch_start + batch_size < len(docs):
            time.sleep(0.5)

    elapsed = time.time() - start_time

    # Refresh stats
    print("\n  Refreshing case stats...")
    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "refresh_case_stats", "case_id": args.case_id}),
        )
        stats = json.loads(resp["Payload"].read().decode())
        print(f"    Docs: {stats.get('document_count', '?')}, "
              f"Entities: {stats.get('entity_count', '?')}")
    except Exception as e:
        logger.warning("Stats refresh failed: %s", e)

    print(f"\n{'=' * 60}")
    print("  Ingestion Complete")
    print(f"{'=' * 60}")
    print(f"  Documents inserted:  {total_inserted:,}")
    print(f"  Duplicates skipped:  {len(docs) - total_inserted:,}")
    print(f"  Errors:              {total_errors:,}")
    print(f"  Elapsed:             {elapsed / 60:.1f} minutes")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
