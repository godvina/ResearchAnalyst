"""Load Nikity/Epstein-Files DS9-12 text via HuggingFace REST API.

Uses the dataset viewer API to page through rows without downloading
the massive Parquet files. No memory issues.

Usage:
    python scripts/load_nikity_api.py --dry-run
    python scripts/load_nikity_api.py
    python scripts/load_nikity_api.py --max-docs 1000
"""

import argparse
import json
import logging
import time
import urllib.request
import uuid

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
API_BASE = "https://datasets-server.huggingface.co/rows"
DATASET = "Nikity/Epstein-Files"
PAGE_SIZE = 100  # max rows per API call
TARGET_DATASETS = {9, 10, 11, 12}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--max-docs", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--all-datasets", action="store_true", help="Include all datasets, not just 9-12")
    return p.parse_args()


def fetch_rows(offset, length=100):
    """Fetch rows from HuggingFace dataset viewer API."""
    url = f"{API_BASE}?dataset={DATASET}&config=default&split=train&offset={offset}&length={length}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("API fetch failed at offset %d: %s", offset, str(e)[:200])
        return None


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
    target_ds = None if args.all_datasets else TARGET_DATASETS

    print("=" * 60)
    print("  Nikity Epstein-Files API Loader")
    print(f"  Case: {args.case_id}")
    print(f"  Target datasets: {target_ds or 'ALL'}")
    print(f"  Page size: {PAGE_SIZE}")
    print("=" * 60)

    # Phase 1: Scan through API pages, collect text docs
    docs = []
    seen_doc_ids = set()
    offset = 0
    total_scanned = 0
    skipped_image = 0
    skipped_ds = 0
    skipped_empty = 0
    skipped_dup = 0
    consecutive_empty = 0
    max_consecutive_empty = 20  # stop after 20 empty pages

    print("\n  Scanning via API...")

    while True:
        data = fetch_rows(offset, PAGE_SIZE)
        if data is None:
            consecutive_empty += 1
            if consecutive_empty > 5:
                logger.warning("Too many API failures, stopping scan")
                break
            time.sleep(2)
            offset += PAGE_SIZE
            continue

        rows = data.get("rows", [])
        if not rows:
            consecutive_empty += 1
            if consecutive_empty > max_consecutive_empty:
                break
            offset += PAGE_SIZE
            continue

        consecutive_empty = 0

        for r in rows:
            row = r.get("row", {})
            total_scanned += 1

            ft = (row.get("file_type") or "").lower()
            if ft in ("image", "audio", "video"):
                skipped_image += 1
                continue

            ds_id = row.get("dataset_id")
            if target_ds and ds_id is not None and int(ds_id) not in target_ds:
                skipped_ds += 1
                continue

            text = row.get("text_content") or ""
            if not text.strip() or len(text.strip()) < 30:
                skipped_empty += 1
                continue

            doc_id = row.get("doc_id", "")
            if doc_id in seen_doc_ids:
                skipped_dup += 1
                continue
            seen_doc_ids.add(doc_id)

            filename = row.get("file_name") or doc_id
            docs.append({
                "source_filename": filename,
                "raw_text": text,
                "source_metadata": {
                    "source": "nikity_api",
                    "dataset_id": ds_id,
                    "doc_id": doc_id,
                    "online_url": row.get("online_url", ""),
                },
            })

        if total_scanned % 5000 == 0:
            print(f"    Scanned {total_scanned:,}, DS9-12 text: {len(docs):,}")

        if args.max_docs and len(docs) >= args.max_docs:
            print(f"    Reached --max-docs limit ({args.max_docs})")
            break

        offset += PAGE_SIZE
        time.sleep(0.3)  # rate limit

    print(f"\n  Scan complete:")
    print(f"    Total scanned:     {total_scanned:,}")
    print(f"    Image/audio/video: {skipped_image:,}")
    print(f"    Wrong dataset:     {skipped_ds:,}")
    print(f"    Empty/short:       {skipped_empty:,}")
    print(f"    Duplicates:        {skipped_dup:,}")
    print(f"    Docs to insert:    {len(docs):,}")

    if args.dry_run:
        total_chars = sum(len(d["raw_text"]) for d in docs)
        print(f"\n  [DRY RUN] {len(docs):,} docs, {total_chars:,} chars ({total_chars / 1_000_000:.1f} MB)")
        return

    # Phase 2: Insert
    lam = boto3.client("lambda", region_name=REGION)
    batch_size = args.batch_size
    total_inserted = 0
    total_errors = 0
    start = time.time()

    print(f"\n  Inserting {len(docs):,} docs in batches of {batch_size}...")

    for batch_start in range(0, len(docs), batch_size):
        batch = docs[batch_start:batch_start + batch_size]
        batch_num = (batch_start // batch_size) + 1
        total_batches = (len(docs) + batch_size - 1) // batch_size

        result = insert_batch(lam, args.case_id, batch)
        if "error" in result:
            total_errors += len(batch)
        else:
            total_inserted += result.get("documents_inserted", 0)

        if batch_num % 10 == 0 or batch_num == total_batches:
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
        print(f"\n  Stats: docs={stats.get('document_count','?')}, entities={stats.get('entity_count','?')}")
    except Exception:
        pass

    print(f"\n{'=' * 60}")
    print(f"  Done: {total_inserted:,} inserted, {total_errors:,} errors, {elapsed / 60:.1f} min")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
