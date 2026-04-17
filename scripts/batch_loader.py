#!/usr/bin/env python3
"""Incremental Batch Loader — process raw PDFs through the DOJ pipeline.

Orchestrates the full batch loading pipeline: discovery, text extraction,
blank filtering, sub-batch ingestion via the existing ingest API, SFN polling,
entity resolution, and ledger/manifest updates.

Usage:
    python scripts/batch_loader.py --dry-run              # preview batch
    python scripts/batch_loader.py --confirm               # run without prompt
    python scripts/batch_loader.py --max-batches 5         # run up to 5 batches
    python scripts/batch_loader.py --no-entity-resolution  # skip ER step
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error

# Ensure project root is on sys.path so "scripts.batch_loader" resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3

from scripts.batch_loader.config import BatchConfig, parse_args
from scripts.batch_loader.discovery import BatchDiscovery
from scripts.batch_loader.extractor import TextExtractor
from scripts.batch_loader.filter import BlankFilter
from scripts.batch_loader.ingestion import PipelineIngestion
from scripts.batch_loader.entity_index import CanonicalEntityIndex
from scripts.batch_loader.cost_estimator import CostEstimator
from scripts.batch_loader.manifest import BatchManifest, FileEntry
from scripts.batch_loader.ledger_integration import LedgerIntegration
from scripts.batch_loader.quarantine import QuarantineManager, check_failure_threshold

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _run_entity_resolution(config: BatchConfig) -> dict:
    """POST /case-files/{case_id}/entity-resolution with no-LLM mode.

    Returns the JSON response body as a dict, or an error dict on failure.
    """
    url = f"{config.api_url}/case-files/{config.case_id}/entity-resolution"
    body = json.dumps({"mode": "no-llm"}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.error("Entity resolution failed: %s", exc)
        return {"error": str(exc)}



def _print_file_list(keys: list[str], limit: int = 20):
    """Print a sample of file keys for dry-run preview."""
    for key in keys[:limit]:
        print(f"    {key}")
    if len(keys) > limit:
        print(f"    ... and {len(keys) - limit} more")


def _build_batch_stats(
    batch_keys: list[str],
    extraction_methods: dict[str, int],
    blank_count: int,
    docs_sent: int,
    sfn_results: dict[str, str],
    er_result: dict,
    textract_ocr_count: int,
    cost_estimate_total: float,
    batch_number: int,
) -> dict:
    """Build the stats dict expected by LedgerIntegration.record_batch."""
    sfn_succeeded = sum(1 for s in sfn_results.values() if s == "SUCCEEDED")
    sfn_failed = sum(1 for s in sfn_results.values() if s in ("FAILED", "TIMED_OUT", "ABORTED"))

    return {
        "source_files_total": len(batch_keys),
        "blanks_skipped": blank_count,
        "docs_sent_to_pipeline": docs_sent,
        "sfn_executions": len(sfn_results),
        "sfn_succeeded": sfn_succeeded,
        "sfn_failed": sfn_failed,
        "entity_resolution_result": er_result,
        "textract_ocr_count": textract_ocr_count,
        "extraction_method_breakdown": extraction_methods,
        "cost_actual": cost_estimate_total,
        "notes": (
            f"Batch {batch_number}. "
            f"{blank_count} blanks filtered from {len(batch_keys)} source files. "
            f"{sfn_failed} pipeline failures."
        ),
    }



def main():
    config = parse_args()

    # --- Initialize clients and modules ---
    s3 = boto3.client("s3", region_name="us-east-1")
    textract = boto3.client("textract", region_name="us-east-1")

    discovery = BatchDiscovery(config, s3)
    extractor = TextExtractor(config, s3, textract)
    blank_filter = BlankFilter(config)
    ingestion = PipelineIngestion(config)
    cost_estimator = CostEstimator(config)
    manifest_mgr = BatchManifest(config, s3)
    ledger = LedgerIntegration(config)
    quarantine = QuarantineManager()
    quarantine.load()
    entity_index = CanonicalEntityIndex(config, s3)

    # --- Cumulative counters for final summary ---
    total_processed = 0
    total_blanks = 0
    total_quarantined = 0
    total_cost = 0.0
    total_er_clusters = 0
    batches_completed = 0
    last_cursor: str | None = None

    print("=" * 60)
    print("  Incremental Batch Loader")
    print(f"  Case: {config.case_id}")
    print(f"  Batch size: {config.batch_size:,}  |  Max batches: {config.max_batches}")
    print(f"  Source prefixes: {', '.join(config.source_prefixes)}")
    print("=" * 60)

    # --- Determine starting batch number from progress file ---
    progress_path = os.path.join("scripts", "batch_progress.json")
    start_batch = 1
    if os.path.exists(progress_path):
        try:
            with open(progress_path) as f:
                prog = json.load(f)
            start_batch = prog.get("current_batch_number", 0) + 1
        except (json.JSONDecodeError, OSError):
            pass

    # ===== Main batch loop =====
    for batch_idx in range(config.max_batches):
        batch_number = start_batch + batch_idx
        print(f"\n{'─' * 60}")
        print(f"  Batch {batch_number}")
        print(f"{'─' * 60}")

        # 1. Discover next batch of unprocessed keys
        batch_keys = discovery.discover_batch()
        if not batch_keys:
            print("  No unprocessed files remaining.")
            break

        print(f"  Discovered {len(batch_keys):,} unprocessed files")

        # 2. Cost estimate
        estimate = cost_estimator.estimate(len(batch_keys))

        # 3. Dry-run: show estimate, file list, exit
        if config.dry_run:
            cost_estimator.display(estimate)
            print("\n  Files that would be processed:")
            _print_file_list(batch_keys)
            print("\n  [DRY RUN] No changes made.")
            break

        # 4. Confirmation prompt (unless --confirm)
        if not config.confirm:
            cost_estimator.display(estimate)
            answer = input("  Proceed? [y/N]: ").strip().lower()
            if answer not in ("y", "yes"):
                print("  Aborted by user.")
                break

        # 5. Create batch manifest
        batch_id = f"batch_{batch_number:03d}"
        manifest = manifest_mgr.create(batch_number, config.source_prefixes)

        # 6. Extract text for each PDF
        print(f"\n  Extracting text from {len(batch_keys):,} PDFs...")
        extraction_methods: dict[str, int] = {}
        textract_ocr_count = 0
        non_blank_docs: list[tuple[str, str]] = []  # (filename, text)
        blank_count = 0

        for i, s3_key in enumerate(batch_keys, 1):
            # Extract
            result = extractor.extract(s3_key, batch_id)
            extraction_methods[result.method] = extraction_methods.get(result.method, 0) + 1
            if result.method == "textract":
                textract_ocr_count += 1

            # 7. Filter blanks
            filter_result = blank_filter.filter(result)

            # Build file entry for manifest
            file_entry = FileEntry(
                s3_key=s3_key,
                file_size_bytes=0,  # size not tracked at extraction time
                extraction_method=result.method,
                extracted_char_count=result.char_count,
                blank_filtered=filter_result.is_blank,
                pipeline_status="blank_filtered" if filter_result.is_blank else "pending",
                error_message=result.error,
            )

            if result.method == "failed":
                # Quarantine failed extractions
                quarantine.add(
                    s3_key=s3_key,
                    reason=result.error or "extraction failed",
                    retry_count=config.max_retries,
                    batch_number=batch_number,
                )
                file_entry.pipeline_status = "quarantined"
                total_quarantined += 1
            elif filter_result.is_blank:
                blank_count += 1
            else:
                filename = os.path.basename(s3_key).replace(".pdf", ".txt")
                non_blank_docs.append((filename, result.text))

            manifest_mgr.add_file(manifest, file_entry)

            if i % 500 == 0:
                print(f"    Extracted {i:,}/{len(batch_keys):,}...")

        print(f"  Extraction complete: {len(non_blank_docs):,} non-blank, "
              f"{blank_count:,} blank, {extraction_methods.get('failed', 0)} failed")

        # 8. Send non-blank docs through ingest API in sub-batches
        execution_arns: list[str] = []
        if non_blank_docs:
            print(f"\n  Sending {len(non_blank_docs):,} docs to pipeline...")
            execution_arns = ingestion.send_sub_batches(non_blank_docs)
            print(f"  Triggered {len(execution_arns)} Step Functions executions")

        # 9. Poll Step Functions until all terminal
        sfn_results: dict[str, str] = {}
        if execution_arns:
            print("\n  Polling Step Functions executions...")
            sfn_results = ingestion.poll_executions(execution_arns)
            succeeded = sum(1 for s in sfn_results.values() if s == "SUCCEEDED")
            failed = sum(1 for s in sfn_results.values() if s != "SUCCEEDED")
            print(f"  Pipeline complete: {succeeded} succeeded, {failed} failed")

        # 10. Update manifest with pipeline results
        arn_list = list(sfn_results.keys())
        arn_idx = 0
        for entry in manifest.files:
            if entry.pipeline_status == "pending" and arn_idx < len(arn_list):
                arn = arn_list[arn_idx]
                status = sfn_results[arn]
                entry.sfn_execution_arn = arn
                entry.pipeline_status = "succeeded" if status == "SUCCEEDED" else "failed"
                arn_idx += 1

        # 11. Quarantine failed docs
        for entry in manifest.files:
            if entry.pipeline_status == "failed" and not entry.blank_filtered:
                if not quarantine.is_quarantined(entry.s3_key):
                    quarantine.add(
                        s3_key=entry.s3_key,
                        reason=f"Pipeline {entry.pipeline_status}",
                        retry_count=config.max_retries,
                        batch_number=batch_number,
                    )
                    entry.pipeline_status = "quarantined"
                    total_quarantined += 1

        quarantine.save()

        # 12. Entity resolution (unless --no-entity-resolution)
        er_result: dict = {}
        if not config.no_entity_resolution and non_blank_docs:
            print("\n  Running entity resolution (no-LLM mode)...")
            er_result = _run_entity_resolution(config)
            if "error" in er_result:
                print(f"  Entity resolution failed: {er_result['error']}")
            else:
                clusters = er_result.get("clusters_merged", 0)
                total_er_clusters += clusters
                print(f"  Entity resolution: {clusters} clusters merged")

            # Update canonical entity index
            entity_index.load()
            entity_index.save()

        # 13. Save manifest to S3 and local
        manifest_mgr.save(manifest)

        # 14. Record batch in ledger, update progress, update Aurora doc counts
        batch_stats = _build_batch_stats(
            batch_keys=batch_keys,
            extraction_methods=extraction_methods,
            blank_count=blank_count,
            docs_sent=len(non_blank_docs),
            sfn_results=sfn_results,
            er_result=er_result,
            textract_ocr_count=textract_ocr_count,
            cost_estimate_total=estimate.total_estimated,
            batch_number=batch_number,
        )
        ledger.record_batch(batch_number, batch_stats)

        ledger.update_progress({
            "total_files_discovered": len(discovery.list_all_raw_keys()),
            "total_processed": total_processed + len(batch_keys),
            "total_remaining": max(0, len(discovery.list_all_raw_keys()) - total_processed - len(batch_keys)),
            "current_batch_number": batch_number,
            "cursor": batch_keys[-1] if batch_keys else None,
            "cumulative_blanks": total_blanks + blank_count,
            "cumulative_quarantined": total_quarantined,
            "cumulative_cost": total_cost + estimate.total_estimated,
        })

        try:
            ledger.update_aurora_doc_counts()
        except Exception as exc:
            logger.warning("Aurora doc count update failed: %s", exc)

        # 14b. Refresh case stats after each batch (so sidebar shows updated counts)
        try:
            _lam = boto3.client("lambda", region_name="us-east-1")
            _lam.invoke(
                FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
                InvocationType="RequestResponse",
                Payload=json.dumps({"action": "refresh_case_stats", "case_id": config.case_id}),
            )
            print(f"  Stats refreshed for case {config.case_id}")
        except Exception as exc:
            logger.warning("Per-batch stats refresh failed: %s", exc)

        # 15. Save cursor for next batch
        if batch_keys:
            discovery.save_cursor(batch_keys[-1])
            last_cursor = batch_keys[-1]

        # Update cumulative counters
        total_processed += len(batch_keys)
        total_blanks += blank_count
        total_cost += estimate.total_estimated
        batches_completed += 1

        # 16. Check failure threshold
        failed_count = sum(
            1 for e in manifest.files
            if e.pipeline_status in ("failed", "quarantined")
        )
        if check_failure_threshold(failed_count, len(batch_keys), config.failure_threshold):
            print(f"\n  WARNING: Failure rate ({failed_count}/{len(batch_keys)}) "
                  f"exceeds threshold ({config.failure_threshold:.0%}). Pausing.")
            break

        # 17. Print batch summary
        print(f"\n  Batch {batch_number} Summary:")
        print(f"    Files processed:  {len(batch_keys):,}")
        print(f"    Non-blank sent:   {len(non_blank_docs):,}")
        print(f"    Blanks filtered:  {blank_count:,}")
        print(f"    Pipeline success: {sum(1 for s in sfn_results.values() if s == 'SUCCEEDED'):,}")
        print(f"    Pipeline failed:  {sum(1 for s in sfn_results.values() if s != 'SUCCEEDED'):,}")
        print(f"    Quarantined:      {total_quarantined:,}")
        print(f"    Est. cost:        ${estimate.total_estimated:,.4f}")

    # ===== Final summary =====
    print(f"\n{'=' * 60}")
    print("  Final Summary")
    print(f"{'=' * 60}")
    print(f"  Batches completed:    {batches_completed}")
    print(f"  Total files processed:{total_processed:,}")
    print(f"  Total blanks:         {total_blanks:,}")
    print(f"  Total quarantined:    {total_quarantined:,}")
    print(f"  Total est. cost:      ${total_cost:,.4f}")
    print(f"  ER clusters merged:   {total_er_clusters:,}")
    print(f"  Next cursor:          {last_cursor or '(none)'}")
    print(f"{'=' * 60}")

    # ===== Post-batch: Neptune sync + stats refresh =====
    if batches_completed > 0:
        print(f"\n  Running Neptune → Aurora entity sync for case {config.case_id}...")
        try:
            lam = boto3.client("lambda", region_name="us-east-1")
            sync_resp = lam.invoke(
                FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
                InvocationType="RequestResponse",
                Payload=json.dumps({"action": "sync_neptune_to_aurora", "case_id": config.case_id}),
            )
            sync_body = json.loads(sync_resp["Payload"].read().decode())
            print(f"  Neptune sync: {sync_body.get('aurora_upserted', '?')} entities upserted")
        except Exception as exc:
            print(f"  Neptune sync failed: {exc}")
            print(f"  Run manually: python scripts/sync_neptune_to_aurora.py --case-id {config.case_id}")

        print(f"\n  Refreshing case stats for case {config.case_id}...")
        try:
            refresh_resp = lam.invoke(
                FunctionName="ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq",
                InvocationType="RequestResponse",
                Payload=json.dumps({"action": "refresh_case_stats", "case_id": config.case_id}),
            )
            refresh_body = json.loads(refresh_resp["Payload"].read().decode())
            print(f"  Stats refreshed: docs={refresh_body.get('document_count', '?')}, "
                  f"entities={refresh_body.get('entity_count', '?')}, "
                  f"rels={refresh_body.get('relationship_count', '?')}")
        except Exception as exc:
            print(f"  Stats refresh failed: {exc}")


if __name__ == "__main__":
    main()
