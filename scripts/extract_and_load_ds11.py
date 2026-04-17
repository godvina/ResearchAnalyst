"""DataSet 11 — Extract text from raw PDFs in S3, save as JSON, then load into pipeline.

Two phases:
  Phase 1: Text extraction (PyPDF2 local first, Textract for scanned PDFs)
    - Downloads each PDF from S3
    - Tries PyPDF2 text extraction locally (free)
    - If < 50 chars extracted, flags as scanned → calls Textract (paid)
    - Saves result as JSON to s3://bucket/textract-output/DataSet11/{filename}.json
    - Skips files that already have a JSON output (resumable)

  Phase 2: Pipeline ingestion (same pattern as load_all_epstein.py)
    - Reads the saved JSON text files
    - Skips blank/empty docs (< 10 chars)
    - Batches into groups of 50
    - Triggers Step Functions executions

Usage:
    # Phase 1 only — extract text from first 10000 PDFs
    python scripts/extract_and_load_ds11.py --phase extract --max-files 10000

    # Phase 2 only — load extracted text into pipeline (first 10000)
    python scripts/extract_and_load_ds11.py --phase load --max-files 10000

    # Both phases
    python scripts/extract_and_load_ds11.py --phase both --max-files 10000

    # Dry run — just count files and estimate cost
    python scripts/extract_and_load_ds11.py --phase extract --max-files 10000 --dry-run
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import uuid

import boto3
from botocore.config import Config

REGION = "us-east-1"
BUCKET = "research-analyst-data-lake-974220725866"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
RAW_PREFIX = f"cases/{CASE_ID}/raw/"
OUTPUT_PREFIX = "textract-output/DataSet11/"
API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
STATE_MACHINE_ARN = "arn:aws:states:us-east-1:974220725866:stateMachine:research-analyst-ingestion"

SCANNED_THRESHOLD = 50  # chars per page — below this = scanned PDF
BLANK_THRESHOLD = 10    # total chars — below this = skip for pipeline

s3 = boto3.client("s3", region_name=REGION)
textract = boto3.client("textract", region_name=REGION)
sfn = boto3.client("stepfunctions", region_name=REGION, config=Config(
    retries={"max_attempts": 3, "mode": "adaptive"}
))


# ============================================================================
# Phase 1: Text Extraction
# ============================================================================

def list_raw_pdfs(max_files=0):
    """List PDF files in the raw/ prefix."""
    pdfs = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=RAW_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            if filename.lower().endswith(".pdf"):
                pdfs.append(filename)
            if max_files and len(pdfs) >= max_files:
                return sorted(pdfs)
    return sorted(pdfs)


def list_already_extracted():
    """List filenames that already have JSON output in textract-output/DataSet11/."""
    extracted = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=OUTPUT_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            if filename.endswith(".json"):
                # JSON filename = original PDF name + .json
                extracted.add(filename.replace(".json", ""))
    return extracted


def extract_text_pypdf2(pdf_bytes):
    """Try to extract text from PDF using PyPDF2 locally (free)."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        blank_pages = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            text = text.strip()
            if len(text) < 5:
                blank_pages += 1
            pages.append(text)
        full_text = "\n\n".join(p for p in pages if p)
        return full_text, len(reader.pages), blank_pages
    except Exception as e:
        return "", 0, 0


def extract_text_textract(pdf_bytes):
    """Extract text using AWS Textract (paid — $1.50/1000 pages)."""
    try:
        resp = textract.detect_document_text(
            Document={"Bytes": pdf_bytes}
        )
        lines = []
        for block in resp.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block.get("Text", ""))
        return "\n".join(lines)
    except Exception as e:
        # Textract has a 5MB limit for synchronous — large PDFs need async
        return f"[TEXTRACT_ERROR: {str(e)[:200]}]"


def save_extraction_json(filename, text, page_count, blank_pages, method):
    """Save extracted text as JSON to S3."""
    result = {
        "sourceFile": filename,
        "extractedText": text,
        "pageCount": page_count,
        "blankPages": blank_pages,
        "extractionMethod": method,  # "pypdf2" or "textract"
        "charCount": len(text),
        "extractedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    key = f"{OUTPUT_PREFIX}{filename}.json"
    s3.put_object(
        Bucket=BUCKET, Key=key,
        Body=json.dumps(result, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    return key


def run_extraction(max_files, dry_run=False):
    """Phase 1: Extract text from raw PDFs."""
    print("=" * 60)
    print("Phase 1: Text Extraction from Raw PDFs")
    print(f"Source: s3://{BUCKET}/{RAW_PREFIX}")
    print(f"Output: s3://{BUCKET}/{OUTPUT_PREFIX}")
    print(f"Max files: {max_files or 'all'}")
    print("=" * 60)

    print("\nListing raw PDFs...")
    pdfs = list_raw_pdfs(max_files)
    print(f"Found {len(pdfs)} PDFs")

    print("Checking already extracted...")
    already = list_already_extracted()
    print(f"Already extracted: {len(already)}")

    to_extract = [f for f in pdfs if f.replace(".pdf", "") not in already
                  and f not in already]
    print(f"Need to extract: {len(to_extract)}")

    if dry_run:
        print(f"\n[DRY RUN] Would extract {len(to_extract)} PDFs")
        print(f"Estimated Textract cost (worst case, all scanned): ${len(to_extract) * 1.50 / 1000:.2f}")
        print(f"Estimated Textract cost (50% scanned): ${len(to_extract) * 0.5 * 1.50 / 1000:.2f}")
        return

    stats = {"pypdf2": 0, "textract": 0, "blank": 0, "errors": 0, "total_chars": 0}
    start = time.time()

    for i, filename in enumerate(to_extract, 1):
        try:
            # Download PDF from S3
            key = f"{RAW_PREFIX}{filename}"
            obj = s3.get_object(Bucket=BUCKET, Key=key)
            pdf_bytes = obj["Body"].read()

            # Try PyPDF2 first (free)
            text, page_count, blank_pages = extract_text_pypdf2(pdf_bytes)

            # Check if we got enough text
            chars_per_page = len(text) / max(page_count, 1)
            if chars_per_page < SCANNED_THRESHOLD and len(pdf_bytes) < 5 * 1024 * 1024:
                # Scanned PDF — use Textract (only for files < 5MB sync limit)
                textract_text = extract_text_textract(pdf_bytes)
                if not textract_text.startswith("[TEXTRACT_ERROR"):
                    text = textract_text
                    method = "textract"
                    stats["textract"] += 1
                else:
                    method = "pypdf2_fallback"
                    stats["pypdf2"] += 1
            else:
                method = "pypdf2"
                stats["pypdf2"] += 1

            if len(text.strip()) < BLANK_THRESHOLD:
                stats["blank"] += 1

            stats["total_chars"] += len(text)

            # Save JSON to S3
            save_extraction_json(filename, text, page_count, blank_pages, method)

            if i % 100 == 0:
                elapsed = time.time() - start
                rate = i / max(elapsed / 60, 0.01)
                print(f"  [{i}/{len(to_extract)}] {rate:.0f} files/min | "
                      f"pypdf2={stats['pypdf2']} textract={stats['textract']} "
                      f"blank={stats['blank']} errors={stats['errors']}")

        except Exception as e:
            stats["errors"] += 1
            if stats["errors"] <= 10:
                print(f"  ERROR [{filename}]: {str(e)[:200]}")

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Phase 1 Complete — {elapsed / 60:.1f} minutes")
    print(f"  PyPDF2 extracted: {stats['pypdf2']}")
    print(f"  Textract extracted: {stats['textract']}")
    print(f"  Blank/empty: {stats['blank']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Total chars: {stats['total_chars']:,}")
    print(f"  Textract cost: ~${stats['textract'] * 1.50 / 1000:.2f}")
    print(f"{'=' * 60}")


# ============================================================================
# Phase 2: Pipeline Ingestion
# ============================================================================

def list_extracted_jsons(max_files=0):
    """List JSON files in textract-output/DataSet11/."""
    jsons = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=OUTPUT_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json") and obj["Size"] > 50:
                jsons.append(key)
            if max_files and len(jsons) >= max_files:
                return jsons
    return jsons


def read_extracted_text(s3_key):
    """Read extracted text from a JSON file in S3."""
    obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
    data = json.loads(obj["Body"].read().decode())
    return data.get("extractedText", ""), data.get("sourceFile", "")


def ingest_batch_via_api(batch_texts, batch_num, total_batches):
    """Send a batch of extracted texts through the ingest API."""
    import urllib.request

    files_payload = []
    for text, source_filename in batch_texts:
        if not text or len(text.strip()) < BLANK_THRESHOLD:
            continue
        filename = source_filename.replace(".pdf", ".txt") if source_filename else f"doc_{uuid.uuid4().hex[:8]}.txt"
        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        files_payload.append({"filename": filename, "content_base64": text_b64})

    if not files_payload:
        print(f"  Batch {batch_num}/{total_batches}: skipped (no valid files)")
        return None

    url = f"{API_URL}/case-files/{CASE_ID}/ingest"
    body = json.dumps({"files": files_payload}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            exec_arn = result.get("execution_arn", "?")
            doc_count = result.get("documents_uploaded", 0)
            print(f"  Batch {batch_num}/{total_batches}: {doc_count} docs -> {exec_arn.split(':')[-1] if ':' in str(exec_arn) else exec_arn}")
            return exec_arn
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"  Batch {batch_num}/{total_batches}: HTTP {e.code} - {err[:200]}")
        return None
    except Exception as e:
        print(f"  Batch {batch_num}/{total_batches}: ERROR - {str(e)[:200]}")
        return None


def run_load(max_files, batch_size=50):
    """Phase 2: Load extracted text into the pipeline."""
    print("=" * 60)
    print("Phase 2: Load Extracted Text into Pipeline")
    print(f"Source: s3://{BUCKET}/{OUTPUT_PREFIX}")
    print(f"Target case: {CASE_ID}")
    print(f"Max files: {max_files or 'all'}")
    print(f"Batch size: {batch_size}")
    print("=" * 60)

    print("\nListing extracted JSONs...")
    json_keys = list_extracted_jsons(max_files)
    print(f"Found {len(json_keys)} extracted text files")

    if not json_keys:
        print("No extracted files found. Run --phase extract first.")
        return

    # Read all texts and filter blanks
    print("Reading extracted texts and filtering blanks...")
    valid_texts = []
    blank_count = 0
    for i, key in enumerate(json_keys):
        text, source = read_extracted_text(key)
        if text and len(text.strip()) >= BLANK_THRESHOLD:
            valid_texts.append((text, source))
        else:
            blank_count += 1
        if (i + 1) % 1000 == 0:
            print(f"  Read {i + 1}/{len(json_keys)}...")

    print(f"Valid docs (>= {BLANK_THRESHOLD} chars): {len(valid_texts)}")
    print(f"Blank/empty skipped: {blank_count}")

    # Batch and send
    total_batches = (len(valid_texts) + batch_size - 1) // batch_size
    print(f"\nSending {len(valid_texts)} docs in {total_batches} batches of {batch_size}")

    executions = []
    for i in range(0, len(valid_texts), batch_size):
        batch = valid_texts[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        arn = ingest_batch_via_api(batch, batch_num, total_batches)
        if arn:
            executions.append(arn)
        time.sleep(2)  # Small delay between batches

    print(f"\n{'=' * 60}")
    print(f"Phase 2 Complete")
    print(f"  Triggered {len(executions)} Step Functions executions")
    print(f"  Total docs sent: {len(valid_texts)}")
    print(f"  Blanks skipped: {blank_count}")
    print(f"  Monitor: AWS Console → Step Functions → research-analyst-ingestion")
    print(f"{'=' * 60}")

    # Save execution log
    log = {
        "case_id": CASE_ID,
        "executions": executions,
        "total_docs": len(valid_texts),
        "blanks_skipped": blank_count,
        "batch_size": batch_size,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    log_path = "scripts/ds11_load_executions.json"
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)
    print(f"  Execution log saved to {log_path}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Extract and load DataSet 11 PDFs")
    parser.add_argument("--phase", choices=["extract", "load", "both"], default="both",
                        help="Which phase to run")
    parser.add_argument("--max-files", type=int, default=5000,
                        help="Max files to process (default 5000)")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Docs per pipeline batch (default 50)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Just count files and estimate cost")
    args = parser.parse_args()

    if args.phase in ("extract", "both"):
        run_extraction(args.max_files, args.dry_run)

    if args.phase in ("load", "both") and not args.dry_run:
        run_load(args.max_files, args.batch_size)


if __name__ == "__main__":
    main()