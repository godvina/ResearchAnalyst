"""Load pre-OCR'd text from HuggingFace DS6-8 into Aurora for Epstein Main.

Bypasses Step Functions entirely — inserts text + embeddings directly via
the CaseFiles Lambda. Entity extraction runs via Bedrock Haiku.

Usage:
    python scripts/load_huggingface_text.py
    python scripts/load_huggingface_text.py --dry-run
    python scripts/load_huggingface_text.py --skip-entity-extraction
    python scripts/load_huggingface_text.py --reset
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"
PROGRESS_FILE = "scripts/hf_ingestion_progress.json"
HF_DATASET = "ishumilin/epstein-files-ocr-datasets-1-8-early-release"

# DS1-5 are already loaded — only ingest DS6-8
SKIP_DATASETS = {1, 2, 3, 4, 5}


def parse_args():
    p = argparse.ArgumentParser(description="Load HuggingFace DS6-8 text into Aurora")
    p.add_argument("--case-id", default=CASE_ID)
    p.add_argument("--batch-size", type=int, default=200, help="Docs per Lambda batch")
    p.add_argument("--dry-run", action="store_true", help="Count pages without inserting")
    p.add_argument("--reset", action="store_true", help="Delete progress file and start over")
    p.add_argument("--skip-entity-extraction", action="store_true")
    p.add_argument("--skip-embeddings", action="store_true")
    p.add_argument("--max-docs", type=int, default=0, help="Limit total docs (0=unlimited)")
    return p.parse_args()


def load_dataset_streaming():
    """Clone the HuggingFace repo via git, then return local page file paths."""
    import glob
    import subprocess

    local_dir = os.path.join("data", "hf_epstein_ocr")

    if os.path.exists(os.path.join(local_dir, "pages")):
        logger.info("Dataset already downloaded at: %s", local_dir)
    else:
        logger.info("Cloning HuggingFace dataset via git (172MB)...")
        repo_url = f"https://huggingface.co/datasets/{HF_DATASET}"
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, local_dir],
            check=True,
        )
        logger.info("Clone complete: %s", local_dir)

    # Find all .md files under pages/
    pattern = os.path.join(local_dir, "pages", "**", "*.md")
    files = sorted(glob.glob(pattern, recursive=True))
    logger.info("Found %d local .md page files", len(files))
    return files, local_dir


def download_page_text(file_path: str) -> str:
    """Read a local page file and return its text content."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def get_dataset_tag(example: dict) -> int | None:
    """Extract dataset number (1-8) from the example metadata or filename."""
    # Try metadata fields first
    for key in ("dataset", "dataset_id", "ds", "subset"):
        val = example.get(key)
        if val is not None:
            try:
                return int(str(val).strip())
            except ValueError:
                pass

    # Try extracting from filename/path
    for key in ("file_name", "filename", "path", "id"):
        val = example.get(key, "")
        if not val:
            continue
        val = str(val).lower()
        # Patterns: "ds6/page_001.md", "dataset_6/...", "6/page_001.md"
        for prefix in ("ds", "dataset_", "dataset"):
            idx = val.find(prefix)
            if idx >= 0:
                num_str = val[idx + len(prefix):]
                num_str = num_str.lstrip("_").split("/")[0].split("_")[0].split(".")[0]
                try:
                    return int(num_str)
                except ValueError:
                    pass
    return None


def group_pages_into_documents(pages: list[dict]) -> list[dict]:
    """Group consecutive pages by document prefix into document-level records.

    Each page dict has: text, filename, dataset_tag
    Returns list of: {source_filename, raw_text, source_metadata}
    """
    if not pages:
        return []

    # Sort by filename for grouping
    pages.sort(key=lambda p: p.get("filename", ""))

    documents = []
    current_prefix = None
    current_pages = []

    for page in pages:
        fname = page.get("filename", "")
        # Extract prefix: everything before the last page number
        # e.g., "EFTA02255838_page_1.md" → "EFTA02255838"
        parts = fname.rsplit("_page_", 1)
        prefix = parts[0] if len(parts) > 1 else fname.rsplit(".", 1)[0]

        if prefix != current_prefix and current_pages:
            # Flush current group
            documents.append(_merge_pages(current_prefix, current_pages))
            current_pages = []

        current_prefix = prefix
        current_pages.append(page)

    # Flush last group
    if current_pages:
        documents.append(_merge_pages(current_prefix, current_pages))

    return documents


def _merge_pages(prefix: str, pages: list[dict]) -> dict:
    """Merge a group of pages into a single document record."""
    text = "\n\n---\n\n".join(p["text"] for p in pages if p.get("text"))
    filenames = [p.get("filename", "") for p in pages]
    ds_tag = pages[0].get("dataset_tag")

    return {
        "source_filename": prefix or filenames[0],
        "raw_text": text,
        "source_metadata": {
            "source": "huggingface",
            "dataset": HF_DATASET,
            "dataset_tag": ds_tag,
            "pages": filenames,
            "page_count": len(pages),
        },
    }


def insert_documents_via_lambda(lam_client, case_id: str, docs: list[dict],
                                skip_embeddings: bool = False,
                                skip_extraction: bool = False) -> dict:
    """Insert a batch of documents into Aurora via the CaseFiles Lambda.

    Uses the 'batch_insert_documents' action which inserts directly into
    the documents table, optionally generating embeddings and extracting entities.
    """
    payload = {
        "action": "batch_insert_documents",
        "case_id": case_id,
        "documents": [
            {
                "document_id": str(uuid.uuid4()),
                "source_filename": d["source_filename"],
                "raw_text": d["raw_text"][:50_000],  # cap text size for Lambda payload
                "source_metadata": d["source_metadata"],
            }
            for d in docs
            if d.get("raw_text", "").strip()  # skip empty docs
        ],
        "skip_embeddings": skip_embeddings,
        "skip_entity_extraction": skip_extraction,
    }

    resp = lam_client.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    body = json.loads(resp["Payload"].read().decode())

    if resp.get("FunctionError"):
        logger.error("Lambda error: %s", json.dumps(body)[:500])
        return {"error": body}

    return body


def save_progress(data: dict):
    """Save progress to JSON file."""
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_progress() -> dict | None:
    """Load progress from JSON file if it exists."""
    if not os.path.exists(PROGRESS_FILE):
        return None
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def main():
    args = parse_args()

    if args.reset and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        logger.info("Progress file deleted. Starting fresh.")

    # Check for resume
    progress = load_progress()
    resume_from = 0
    if progress and progress.get("status") == "in_progress":
        resume_from = progress.get("pages_processed", 0)
        logger.info("Resuming from page %d", resume_from)

    # Download full dataset locally first (172MB, much faster than file-by-file)
    file_paths, local_dir = load_dataset_streaming()

    # First pass: collect and filter pages
    print("=" * 60)
    print("  HuggingFace DS6-8 Text Loader")
    print(f"  Case: {args.case_id}")
    print(f"  Dataset: {HF_DATASET}")
    print(f"  Local dir: {local_dir}")
    print(f"  Total files found: {len(file_paths)}")
    print("=" * 60)

    print("\n  Scanning files and filtering DS1-5...")
    pages = []
    skipped_ds15 = 0
    skipped_empty = 0
    skipped_unknown = 0
    total_scanned = 0

    for i, fpath in enumerate(file_paths):
        total_scanned += 1

        # Resume support
        if i < resume_from:
            continue

        # Extract page number from filename: page_17000.md → 17000
        fname = os.path.basename(fpath)
        import re as _re
        m = _re.search(r"page[_-]?(\d+)", fname)
        if not m:
            skipped_unknown += 1
            continue

        page_num = int(m.group(1))
        # Pages 0-16999 are DS1-5, pages 17000+ are DS6-8
        if page_num < 17000:
            skipped_ds15 += 1
            continue

        ds_tag = 6 if page_num < 25000 else (7 if page_num < 35000 else 8)

        # Read text from local file (fast — no HTTP)
        text = download_page_text(fpath)

        if not text.strip() or len(text.strip()) < 20:
            skipped_empty += 1
            continue

        pages.append({
            "text": text,
            "filename": fname,
            "dataset_tag": ds_tag,
        })

        if total_scanned % 5000 == 0:
            print(f"    Scanned {total_scanned:,} files, kept {len(pages):,}...")

        if args.max_docs and len(pages) >= args.max_docs:
            print(f"    Reached --max-docs limit ({args.max_docs})")
            break

    print(f"\n  Scan complete:")
    print(f"    Total scanned:    {total_scanned:,}")
    print(f"    DS1-5 skipped:    {skipped_ds15:,}")
    print(f"    Empty skipped:    {skipped_empty:,}")
    print(f"    Unknown DS skip:  {skipped_unknown:,}")
    print(f"    DS6-8 pages kept: {len(pages):,}")

    # Group pages into documents
    print("\n  Grouping pages into documents...")
    documents = group_pages_into_documents(pages)
    avg_pages = len(pages) / max(len(documents), 1)
    print(f"    Documents created: {len(documents):,}")
    print(f"    Avg pages/doc:     {avg_pages:.1f}")

    if args.dry_run:
        total_chars = sum(len(d["raw_text"]) for d in documents)
        est_cost = (total_chars / 1000) * 0.00025  # Haiku pricing rough estimate
        print(f"\n  [DRY RUN] Would insert {len(documents):,} documents")
        print(f"  Total text: {total_chars:,} chars ({total_chars / 1_000_000:.1f} MB)")
        print(f"  Est. Bedrock cost: ${est_cost:.2f}")
        return

    # Insert into Aurora via Lambda
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

        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} docs)...")

        result = insert_documents_via_lambda(
            lam, args.case_id, batch,
            skip_embeddings=args.skip_embeddings,
            skip_extraction=args.skip_entity_extraction,
        )

        if "error" in result:
            total_errors += len(batch)
            logger.error("Batch %d failed: %s", batch_num, str(result)[:300])
        else:
            inserted = result.get("documents_inserted", len(batch))
            total_inserted += inserted
            entities = result.get("entities_extracted", 0)
            print(f"    Inserted: {inserted}, Entities: {entities}")

        # Save progress
        save_progress({
            "status": "in_progress",
            "pages_processed": batch_start + len(batch) + resume_from,
            "documents_inserted": total_inserted,
            "errors": total_errors,
            "batch_number": batch_num,
        })

        # Brief pause between batches to avoid Lambda throttling
        if batch_start + batch_size < len(documents):
            time.sleep(1)

    elapsed = time.time() - start_time

    # Refresh case stats
    print("\n  Refreshing case stats...")
    try:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "refresh_case_stats", "case_id": args.case_id}),
        )
        stats = json.loads(resp["Payload"].read().decode())
        print(f"    Docs: {stats.get('document_count', '?')}, "
              f"Entities: {stats.get('entity_count', '?')}, "
              f"Rels: {stats.get('relationship_count', '?')}")
    except Exception as e:
        logger.warning("Stats refresh failed: %s", e)

    # Save final progress
    save_progress({
        "status": "completed",
        "pages_processed": total_scanned,
        "documents_inserted": total_inserted,
        "errors": total_errors,
        "elapsed_seconds": elapsed,
    })

    # Summary
    print(f"\n{'=' * 60}")
    print("  Ingestion Complete")
    print(f"{'=' * 60}")
    print(f"  Documents inserted:  {total_inserted:,}")
    print(f"  Errors:              {total_errors:,}")
    print(f"  Elapsed:             {elapsed / 60:.1f} minutes")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
