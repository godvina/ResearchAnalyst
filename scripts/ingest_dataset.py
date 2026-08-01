#!/usr/bin/env python3
"""
DS12 Dataset Ingestion Pipeline — End-to-End Unattended EC2 Script

Downloads a ZIP from standardworks.ai, extracts text files, inserts into
Aurora via Lambda (batch of 500), tags with source_metadata, runs entity
extraction via the EXISTING entity_extraction_pipeline.py, and syncs to
Neptune via the EXISTING neptune_bulk_sync.py and neptune_edge_sync.py.

Designed to run unattended on EC2 with self-terminate at end.

Usage (on EC2):
    python3 /tmp/ingest_dataset.py

Reference:
    - scripts/entity_extraction_pipeline.py — entity extraction pipeline
    - scripts/neptune_bulk_sync.py — Neptune vertex sync
    - scripts/neptune_edge_sync.py — Neptune edge sync
    - .kiro/steering/kiro-builder-playbook.md — EC2 rules
"""
import boto3
import json
import os
import sys
import time
import uuid
import zipfile
import io
import subprocess
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

CONFIG = {
    # Dataset
    "dataset_name": "DS12",
    "download_url": "https://standard-works-public-archives.s3-accelerate.amazonaws.com/epstein-files/DataSet12.zip.zip",
    "expected_doc_count": 153,
    "case_id": "7f05e8d5-4492-4f19-8894-25367606db96",

    # Source metadata tagged on every document
    "source_metadata": {
        "dataset": "DS12",
        "source": "standardworks_ai",
    },

    # AWS
    "region": "us-east-1",
    "bucket": "research-analyst-data-lake-974220725866",
    "lambda_name": "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",

    # Batch sizes — uses batch of 500 per Lambda call (multi-row INSERT)
    "aurora_batch_size": 500,

    # Paths
    "work_dir": "/tmp/ds12_ingest",
    "scripts_dir": "/tmp",
}


# ═══════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════

LOG_LINES = []


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)


def log_gate(gate_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    log(f"  TEST GATE [{gate_name}]: {status} -- {detail}")
    if not passed:
        log(f"  FATAL: Gate [{gate_name}] failed. Aborting pipeline.")
        upload_logs()
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# AWS CLIENTS
# ═══════════════════════════════════════════════════════════════════

lam = boto3.client("lambda", region_name=CONFIG["region"])
s3 = boto3.client("s3", region_name=CONFIG["region"])
bedrock = boto3.client("bedrock", region_name=CONFIG["region"])


def invoke_lambda(payload):
    """Invoke the case files Lambda and return parsed response."""
    resp = lam.invoke(
        FunctionName=CONFIG["lambda_name"],
        Payload=json.dumps(payload),
    )
    return json.loads(resp["Payload"].read())


# ═══════════════════════════════════════════════════════════════════
# STEP 1: DOWNLOAD ZIP
# ═══════════════════════════════════════════════════════════════════

def step1_download():
    log("=" * 60)
    log("STEP 1: Download ZIP")
    log(f"  URL: {CONFIG['download_url']}")
    log("=" * 60)

    work_dir = CONFIG["work_dir"]
    os.makedirs(work_dir, exist_ok=True)
    zip_path = os.path.join(work_dir, "dataset.zip")

    try:
        req = Request(CONFIG["download_url"], headers={"User-Agent": "DS12-Ingest/1.0"})
        with urlopen(req, timeout=300) as resp:
            data = resp.read()
            with open(zip_path, "wb") as f:
                f.write(data)
        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        log(f"  Downloaded: {size_mb:.1f} MB")
    except (URLError, Exception) as e:
        log(f"  Download error: {str(e)[:300]}")
        log_gate("download", False, f"Download failed: {str(e)[:200]}")

    log_gate("download", os.path.exists(zip_path) and os.path.getsize(zip_path) > 0,
             f"File exists, {os.path.getsize(zip_path):,} bytes")

    return zip_path


# ═══════════════════════════════════════════════════════════════════
# STEP 2: EXTRACT TEXT FILES
# ═══════════════════════════════════════════════════════════════════

def step2_extract(zip_path):
    log("=" * 60)
    log("STEP 2: Extract text files from ZIP")
    log("=" * 60)

    work_dir = CONFIG["work_dir"]
    extract_dir = os.path.join(work_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    text_files = []

    def extract_from_zip(zpath, target_dir):
        """Extract text files, handling nested ZIPs."""
        nonlocal text_files
        with zipfile.ZipFile(zpath, "r") as zf:
            for name in zf.namelist():
                # Skip directories and macOS resource forks
                if name.endswith("/") or "/__MACOSX" in name or "/." in name:
                    continue

                lower = name.lower()

                # Nested ZIP — extract and recurse
                if lower.endswith(".zip"):
                    nested_path = os.path.join(target_dir, os.path.basename(name))
                    with zf.open(name) as src, open(nested_path, "wb") as dst:
                        dst.write(src.read())
                    try:
                        extract_from_zip(nested_path, target_dir)
                    except zipfile.BadZipFile:
                        log(f"  Warning: Bad nested ZIP: {name}")
                    continue

                # Text files (.txt, .text, .csv, .md, .log, etc.)
                if lower.endswith((".txt", ".text", ".csv", ".md", ".log", ".tsv")):
                    out_path = os.path.join(target_dir, os.path.basename(name))
                    # Handle duplicate filenames
                    if os.path.exists(out_path):
                        base, ext = os.path.splitext(out_path)
                        out_path = f"{base}_{uuid.uuid4().hex[:6]}{ext}"
                    with zf.open(name) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
                    text_files.append(out_path)

    extract_from_zip(zip_path, extract_dir)
    log(f"  Extracted {len(text_files)} text files")

    expected = CONFIG["expected_doc_count"]
    log_gate("extract", len(text_files) >= expected * 0.9,
             f"Got {len(text_files)} files (expected ~{expected})")

    return text_files


# ═══════════════════════════════════════════════════════════════════
# STEP 3: INSERT INTO AURORA VIA LAMBDA (batch of 500)
# Uses insert_documents_batch action — multi-row INSERT, NOT one at a time
# ═══════════════════════════════════════════════════════════════════

def step3_aurora_insert(text_files):
    log("=" * 60)
    log("STEP 3: Insert documents into Aurora (batch of 500)")
    log(f"  Case ID: {CONFIG['case_id']}")
    log(f"  Batch size: {CONFIG['aurora_batch_size']}")
    log(f"  Source metadata: {json.dumps(CONFIG['source_metadata'])}")
    log("=" * 60)

    case_id = CONFIG["case_id"]
    batch_size = CONFIG["aurora_batch_size"]
    total_inserted = 0
    total_skipped = 0
    batch = []

    for i, fpath in enumerate(text_files):
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
        except Exception as e:
            log(f"  Warning: Could not read {fpath}: {e}")
            total_skipped += 1
            continue

        if not raw_text.strip() or len(raw_text.strip()) < 50:
            total_skipped += 1
            continue

        doc = {
            "document_id": str(uuid.uuid4()),
            "source_filename": os.path.basename(fpath),
            "raw_text": raw_text,
            "source_metadata": CONFIG["source_metadata"],
        }
        batch.append(doc)

        # Flush batch at batch_size (500 docs per Lambda call)
        if len(batch) >= batch_size:
            result = invoke_lambda({
                "action": "insert_documents_batch",
                "case_id": case_id,
                "documents": batch,
            })
            ins = result.get("documents_inserted", 0)
            total_inserted += ins
            log(f"  Batch {i // batch_size + 1}: inserted {ins}, total {total_inserted}")
            if "error" in result:
                log(f"  Warning: {result['error'][:200]}")
            batch = []

    # Flush remaining
    if batch:
        result = invoke_lambda({
            "action": "insert_documents_batch",
            "case_id": case_id,
            "documents": batch,
        })
        ins = result.get("documents_inserted", 0)
        total_inserted += ins
        log(f"  Final batch: inserted {ins}, total {total_inserted}")
        if "error" in result:
            log(f"  Warning: {result['error'][:200]}")

    log(f"  Total inserted: {total_inserted}")
    log(f"  Total skipped: {total_skipped}")

    # Verify: query Aurora for document count
    verify_result = invoke_lambda({
        "action": "get_documents_for_extraction",
        "case_id": case_id,
        "limit": 1,
        "offset": 0,
    })
    aurora_count = verify_result.get("total", 0)
    log(f"  Aurora document count (with text): {aurora_count}")

    log_gate("aurora_insert", total_inserted > 0,
             f"Inserted {total_inserted} documents, Aurora total: {aurora_count}")

    # Update case stats
    invoke_lambda({
        "action": "refresh_case_stats",
        "case_id": case_id,
    })
    log("  Case stats refreshed")

    return total_inserted


# ═══════════════════════════════════════════════════════════════════
# STEP 4: ENTITY EXTRACTION (reuse EXISTING pipeline)
# Calls entity_extraction_pipeline.py generate → submit → poll → load
# ═══════════════════════════════════════════════════════════════════

def step4_entity_extraction():
    log("=" * 60)
    log("STEP 4: Entity Extraction (Bedrock Batch Inference)")
    log("=" * 60)

    case_id = CONFIG["case_id"]
    scripts_dir = CONFIG["scripts_dir"]
    pipeline_script = os.path.join(scripts_dir, "entity_extraction_pipeline.py")

    if not os.path.exists(pipeline_script):
        log(f"  ERROR: {pipeline_script} not found")
        log_gate("entity_generate", False, "Pipeline script missing")

    # Step 4a: Generate JSONL — filter to DS12 docs only (not all 76K)
    dataset_tag = CONFIG["source_metadata"].get("dataset", "")
    log(f"  Step 4a: Generating JSONL prompts (dataset_filter={dataset_tag})...")
    generate_cmd = [
        sys.executable, pipeline_script, "generate",
        "--case-id", case_id,
    ]
    if dataset_tag:
        generate_cmd.extend(["--dataset-filter", dataset_tag])
    rc = subprocess.call(generate_cmd)
    log_gate("entity_generate", rc == 0, f"generate exit code: {rc}")

    # Step 4b: Submit batch job
    log("  Step 4b: Submitting Bedrock batch job...")
    rc = subprocess.call([
        sys.executable, pipeline_script, "submit",
        "--case-id", case_id,
    ])
    log_gate("entity_submit", rc == 0, f"submit exit code: {rc}")

    # Step 4c: Read job ARN from saved file
    job_arn = None
    arn_file = os.path.join(scripts_dir, f"batch-job-{case_id[:8]}.txt")
    # entity_extraction_pipeline.py writes to docs/ — check both locations
    candidates = [
        f"docs/batch-job-{case_id[:8]}.txt",
        arn_file,
        os.path.join("/tmp", f"batch-job-{case_id[:8]}.txt"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            with open(candidate) as f:
                for line in f:
                    if line.startswith("Job ARN:"):
                        job_arn = line.replace("Job ARN: ", "").strip()
                        break
            if job_arn:
                break

    if not job_arn:
        log("  Could not find job ARN file. Checking Bedrock for recent jobs...")
        try:
            jobs = bedrock.list_model_invocation_jobs(maxResults=5)
            for job in jobs.get("invocationJobSummaries", []):
                if case_id[:8] in job.get("jobName", ""):
                    job_arn = job.get("jobArn", "")
                    log(f"  Found job: {job_arn}")
                    break
        except Exception as e:
            log(f"  Bedrock list error: {str(e)[:200]}")

    log_gate("entity_job_arn", job_arn is not None, f"Job ARN: {job_arn}")

    # Step 4d: Poll until complete (up to 6 hours)
    log("  Step 4d: Polling batch job status...")
    max_polls = 360  # 6 hours at 60s intervals
    for i in range(max_polls):
        try:
            status_resp = bedrock.get_model_invocation_job(jobIdentifier=job_arn)
            status = status_resp.get("status", "UNKNOWN")
            log(f"  Poll {i + 1}: {status}")

            if status == "Completed":
                stats = status_resp.get("statistics", {})
                log(f"  Input records: {stats.get('inputRecordCount', '?')}")
                log(f"  Output records: {stats.get('outputRecordCount', '?')}")
                log(f"  Error records: {stats.get('errorRecordCount', '?')}")
                break
            elif status in ("Failed", "Stopped"):
                msg = status_resp.get("message", "")
                log(f"  Job {status}: {msg}")
                log_gate("entity_batch", False, f"Batch job {status}: {msg}")
            # Still running — wait 60s
            time.sleep(60)
        except Exception as e:
            log(f"  Poll error: {str(e)[:200]}")
            time.sleep(60)
    else:
        log_gate("entity_batch", False, "Batch job timed out after 6 hours")

    log_gate("entity_batch", True, f"Bedrock batch job completed: {job_arn}")

    # Step 4e: Load results into Aurora
    log("  Step 4e: Loading results into Aurora...")
    rc = subprocess.call([
        sys.executable, pipeline_script, "load",
        "--case-id", case_id,
        "--job-arn", job_arn,
    ])
    log_gate("entity_load", rc == 0, f"load exit code: {rc}")

    # Verify entity count increased
    entity_result = invoke_lambda({
        "action": "query_aurora_entities",
        "case_id": case_id,
        "limit": 1,
        "offset": 0,
    })
    entity_count = entity_result.get("total", 0)
    log(f"  Entity count after load: {entity_count}")
    log_gate("entity_count", entity_count > 0, f"Entities in Aurora: {entity_count}")

    return job_arn


# ═══════════════════════════════════════════════════════════════════
# STEP 5: NEPTUNE VERTEX SYNC (reuse EXISTING neptune_bulk_sync.py)
# Uses Neptune CSV Bulk Loader API — NOT individual Gremlin upserts
# ═══════════════════════════════════════════════════════════════════

def step5_neptune_vertex_sync():
    log("=" * 60)
    log("STEP 5: Neptune Vertex Sync (CSV Bulk Loader)")
    log("=" * 60)

    case_id = CONFIG["case_id"]
    scripts_dir = CONFIG["scripts_dir"]
    sync_script = os.path.join(scripts_dir, "neptune_bulk_sync.py")

    if not os.path.exists(sync_script):
        log(f"  ERROR: {sync_script} not found")
        log_gate("neptune_vertex", False, "Sync script missing")

    rc = subprocess.call([
        sys.executable, sync_script,
        "--case-id", case_id,
    ])
    log_gate("neptune_vertex", rc == 0, f"neptune_bulk_sync exit code: {rc}")


# ═══════════════════════════════════════════════════════════════════
# STEP 6: NEPTUNE EDGE SYNC (reuse EXISTING neptune_edge_sync.py)
# ═══════════════════════════════════════════════════════════════════

def step6_neptune_edge_sync():
    log("=" * 60)
    log("STEP 6: Neptune Edge Sync")
    log("=" * 60)

    case_id = CONFIG["case_id"]
    scripts_dir = CONFIG["scripts_dir"]
    edge_script = os.path.join(scripts_dir, "neptune_edge_sync.py")

    if not os.path.exists(edge_script):
        log(f"  ERROR: {edge_script} not found")
        log_gate("neptune_edge", False, "Edge sync script missing")

    rc = subprocess.call([
        sys.executable, edge_script,
        "--case-id", case_id,
    ])
    log_gate("neptune_edge", rc == 0, f"neptune_edge_sync exit code: {rc}")


# ═══════════════════════════════════════════════════════════════════
# LOG UPLOAD
# ═══════════════════════════════════════════════════════════════════

def upload_logs():
    """Upload pipeline log to S3."""
    try:
        bucket = CONFIG["bucket"]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = f"logs/ds12-ingest/pipeline_log_{ts}.txt"
        body = "\n".join(LOG_LINES)
        s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))
        log(f"  Log uploaded to s3://{bucket}/{key}")
    except Exception as e:
        print(f"Log upload failed: {e}", flush=True)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    start = time.time()

    log("=" * 60)
    log("DS12 DATASET INGESTION PIPELINE")
    log(f"  Dataset: {CONFIG['dataset_name']}")
    log(f"  Case ID: {CONFIG['case_id']}")
    log(f"  Expected docs: {CONFIG['expected_doc_count']}")
    log(f"  Started: {datetime.now().isoformat()}")
    log("=" * 60)

    # Step 1: Download
    zip_path = step1_download()

    # Step 2: Extract
    text_files = step2_extract(zip_path)

    # Step 3: Aurora insert (batch of 500 per Lambda call)
    inserted = step3_aurora_insert(text_files)

    # Step 4: Entity extraction (generate -> submit -> poll -> load)
    job_arn = step4_entity_extraction()

    # Step 5: Neptune vertex sync (CSV Bulk Loader)
    step5_neptune_vertex_sync()

    # Step 6: Neptune edge sync
    step6_neptune_edge_sync()

    # Final summary
    elapsed = time.time() - start
    log("=" * 60)
    log("PIPELINE COMPLETE")
    log(f"  Total time: {elapsed / 60:.1f} minutes")
    log(f"  Documents inserted: {inserted}")
    log(f"  Bedrock job: {job_arn}")
    log("=" * 60)

    # Upload final log
    upload_logs()


if __name__ == "__main__":
    main()
