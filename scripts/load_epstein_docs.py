"""Load epstein-docs.github.io pre-extracted text + entities into Aurora.

29,439 JSON files with OCR text, entities (people, orgs, locations, dates),
and document metadata. Entities are pre-extracted — no Bedrock needed.

Usage:
    python scripts/load_epstein_docs.py --dry-run
    python scripts/load_epstein_docs.py
    python scripts/load_epstein_docs.py --max-docs 1000
"""

import argparse
import glob
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
DATA_DIR = "data/epstein-docs/results"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=200)
    p.add_argument("--max-docs", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
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

    files = sorted(glob.glob(os.path.join(DATA_DIR, "**", "*.json"), recursive=True))
    print("=" * 60)
    print("  Epstein-Docs Pre-Extracted Text + Entity Loader")
    print(f"  Case: {args.case_id}")
    print(f"  JSON files found: {len(files):,}")
    print("=" * 60)

    # Parse all JSON files
    docs = []
    skipped_empty = 0
    total_entities = 0

    print("\n  Reading JSON files...")
    for i, fpath in enumerate(files):
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except Exception:
            continue

        # Extract text
        full_text = data.get("full_text", "")
        if not full_text:
            text_blocks = data.get("text_blocks", [])
            full_text = " ".join(
                b.get("text", "") for b in text_blocks if isinstance(b, dict)
            )

        if not full_text.strip() or len(full_text.strip()) < 30:
            skipped_empty += 1
            continue

        # Extract entities
        entities_raw = data.get("entities", {})
        entity_list = []
        if isinstance(entities_raw, dict):
            for etype, names in entities_raw.items():
                if isinstance(names, list):
                    for name in names:
                        if isinstance(name, str) and name.strip():
                            entity_list.append({"name": name.strip(), "type": etype})
                            total_entities += 1

        filename = os.path.basename(fpath).replace(".json", "")
        subfolder = os.path.basename(os.path.dirname(fpath))

        docs.append({
            "source_filename": filename,
            "raw_text": full_text,
            "source_metadata": {
                "source": "epstein_docs_github",
                "subfolder": subfolder,
                "entities": entity_list[:50],  # cap to keep payload small
                "metadata": data.get("document_metadata", {}),
            },
        })

        if (i + 1) % 5000 == 0:
            print(f"    Read {i + 1:,}/{len(files):,}, kept {len(docs):,}")

        if args.max_docs and len(docs) >= args.max_docs:
            break

    print(f"\n  Parse complete:")
    print(f"    Files read:     {len(files):,}")
    print(f"    Empty skipped:  {skipped_empty:,}")
    print(f"    Docs to insert: {len(docs):,}")
    print(f"    Pre-extracted entities: {total_entities:,}")

    if args.dry_run:
        total_chars = sum(len(d["raw_text"]) for d in docs)
        print(f"\n  [DRY RUN] {len(docs):,} docs, {total_chars:,} chars ({total_chars / 1_000_000:.1f} MB)")
        return

    # Insert
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
