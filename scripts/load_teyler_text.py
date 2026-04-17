"""Load House Oversight Epstein docs from teyler/epstein-files-20k.

This dataset has 2.1M page-level rows in CSV format (filename + text).
We group pages by document, filter empties, dedup against Aurora, and insert.

Usage:
    python scripts/load_teyler_text.py --dry-run
    python scripts/load_teyler_text.py
"""

import argparse
import json
import logging
import os
import time
import uuid
from collections import defaultdict

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
HF_DATASET = "teyler/epstein-files-20k"


def parse_args():
    p = argparse.ArgumentParser(description="Load teyler Epstein text into Aurora")
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-docs", type=int, default=0)
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

    from datasets import load_dataset
    import csv
    import io

    logger.info("Loading teyler/epstein-files-20k dataset...")
    ds = load_dataset(HF_DATASET, split="train")

    print("=" * 60)
    print("  Teyler Epstein-Files-20K Text Loader")
    print(f"  Case: {args.case_id}")
    print(f"  Total rows: {len(ds):,}")
    print("=" * 60)

    # The dataset is a single 'text' column with CSV-formatted data
    # Row 0 is the header: "filename,text"
    # Remaining rows are: "FILENAME.txt","actual document text"
    print("\n  Parsing rows and grouping by document...")

    doc_texts = defaultdict(list)
    skipped_empty = 0
    skipped_header = 0
    total_parsed = 0

    for i, row in enumerate(ds):
        raw = row.get("text", "")
        if not raw or not raw.strip():
            skipped_empty += 1
            continue

        # Skip the CSV header row
        if raw.strip().startswith("filename,text"):
            skipped_header += 1
            continue

        # Parse CSV-formatted row: filename,"text content"
        try:
            reader = csv.reader(io.StringIO(raw))
            parts = next(reader)
            if len(parts) >= 2:
                filename = parts[0].strip()
                text = parts[1].strip()
            else:
                filename = f"teyler_row_{i}"
                text = raw.strip()
        except Exception:
            filename = f"teyler_row_{i}"
            text = raw.strip()

        if not text or len(text) < 20:
            skipped_empty += 1
            continue

        # Group by base document name (strip .txt extension and page suffixes)
        doc_texts[filename].append(text)
        total_parsed += 1

        if i % 500000 == 0 and i > 0:
            print(f"    Parsed {i:,}/{len(ds):,} rows, {len(doc_texts):,} unique docs...")

    print(f"\n  Parse complete:")
    print(f"    Total rows:       {len(ds):,}")
    print(f"    Parsed:           {total_parsed:,}")
    print(f"    Empty/short:      {skipped_empty:,}")
    print(f"    Header rows:      {skipped_header:,}")
    print(f"    Unique documents: {len(doc_texts):,}")

    # Build document records (merge pages per doc)
    documents = []
    for filename, texts in doc_texts.items():
        merged_text = "\n\n---\n\n".join(texts) if len(texts) > 1 else texts[0]
        documents.append({
            "source_filename": filename,
            "raw_text": merged_text,
            "source_metadata": {
                "source": "teyler_hf",
                "dataset": HF_DATASET,
                "page_count": len(texts),
            },
        })

    if args.max_docs and len(documents) > args.max_docs:
        documents = documents[:args.max_docs]
        print(f"    Limited to {args.max_docs} docs")

    print(f"    Documents to insert: {len(documents):,}")

    if args.dry_run:
        total_chars = sum(len(d["raw_text"]) for d in documents)
        print(f"\n  [DRY RUN] Would insert {len(documents):,} documents")
        print(f"  Total text: {total_chars:,} chars ({total_chars / 1_000_000:.1f} MB)")
        return

    # Insert
    lam = boto3.client("lambda", region_name=REGION)
    batch_size = args.batch_size
    total_inserted = 0
    total_errors = 0
    start_time = time.time()

    print(f"\n  Inserting {len(documents):,} documents in batches of {batch_size}...")

    for batch_start in range(0, len(documents), batch_size):
        batch = documents[batch_start:batch_start + batch_size]
        batch_num = (batch_start // batch_size) + 1
        total_batches = (len(documents) + batch_size - 1) // batch_size

        result = insert_batch(lam, args.case_id, batch)

        if "error" in result:
            total_errors += len(batch)
            logger.error("Batch %d failed: %s", batch_num, str(result)[:300])
        else:
            inserted = result.get("documents_inserted", 0)
            total_inserted += inserted
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"    Batch {batch_num}/{total_batches}: inserted {inserted} (total: {total_inserted:,})")

        if batch_start + batch_size < len(documents):
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
        print(f"    Docs: {stats.get('document_count', '?')}, Entities: {stats.get('entity_count', '?')}")
    except Exception as e:
        logger.warning("Stats refresh failed: %s", e)

    print(f"\n{'=' * 60}")
    print("  Ingestion Complete")
    print(f"{'=' * 60}")
    print(f"  Documents inserted:  {total_inserted:,}")
    print(f"  Duplicates skipped:  {len(documents) - total_inserted:,}")
    print(f"  Errors:              {total_errors:,}")
    print(f"  Elapsed:             {elapsed / 60:.1f} minutes")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
