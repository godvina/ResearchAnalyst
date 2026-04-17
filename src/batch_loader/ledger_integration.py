"""Ledger integration — record batch results and update progress tracking.

Integrates batch processing results with the existing ingestion ledger
(scripts/ingestion_ledger.json) and maintains a separate batch_progress.json
for running totals and cursor state.
"""

import json
import os
from datetime import datetime, timezone

from batch_loader.config import BatchConfig
from scripts.ledger import load_ledger, save_ledger
from scripts.update_case_doc_counts import count_s3_docs, update_count

# Paths relative to the scripts/ directory
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)))
LEDGER_FILE = os.path.join(SCRIPTS_DIR, "ingestion_ledger.json")
PROGRESS_FILE = os.path.join(SCRIPTS_DIR, "batch_progress.json")


class LedgerIntegration:
    """Integrates batch results with the existing ingestion ledger."""

    def __init__(self, config: BatchConfig):
        self.config = config

    def record_batch(self, batch_number: int, stats: dict):
        """Append a load entry to ingestion_ledger.json.

        Uses the existing ledger format to append a fully-formed load entry
        with all required fields for batch audit trail.

        Args:
            batch_number: The sequential batch number.
            stats: Dict containing batch statistics with keys:
                source_files_total, blanks_skipped, docs_sent_to_pipeline,
                sfn_executions, sfn_succeeded, sfn_failed,
                entity_resolution_result, textract_ocr_count,
                extraction_method_breakdown, notes
        """
        load_entry = {
            "load_id": f"batch_{batch_number}",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": f"Raw PDFs batch {batch_number}",
            "source_bucket": self.config.source_bucket,
            "source_prefixes": list(self.config.source_prefixes),
            "source_files_total": stats.get("source_files_total", 0),
            "blanks_skipped": stats.get("blanks_skipped", 0),
            "docs_sent_to_pipeline": stats.get("docs_sent_to_pipeline", 0),
            "sfn_executions": stats.get("sfn_executions", 0),
            "sfn_succeeded": stats.get("sfn_succeeded", 0),
            "sfn_failed": stats.get("sfn_failed", 0),
            "entity_resolution_result": stats.get("entity_resolution_result", {}),
            "textract_ocr_count": stats.get("textract_ocr_count", 0),
            "extraction_method_breakdown": stats.get("extraction_method_breakdown", {}),
            "notes": stats.get("notes", f"Batch {batch_number}."),
        }

        ledger = load_ledger()
        cases = ledger.setdefault("cases", {})
        case_id = self.config.case_id

        if case_id not in cases:
            cases[case_id] = {"name": "Unknown", "loads": [], "running_total_s3_docs": 0}

        case = cases[case_id]
        case["loads"].append(load_entry)

        # Update running total using docs_sent_to_pipeline
        case["running_total_s3_docs"] = sum(
            l.get("s3_docs_after", l.get("docs_sent_to_pipeline", 0))
            for l in case["loads"]
        )

        save_ledger(ledger)

    def update_progress(self, progress: dict):
        """Update batch_progress.json with running totals.

        Args:
            progress: Dict containing progress fields:
                total_files_discovered, total_processed, total_remaining,
                current_batch_number, cursor, cumulative_blanks,
                cumulative_quarantined, cumulative_cost
        """
        progress_data = {
            "case_id": self.config.case_id,
            "total_files_discovered": progress.get("total_files_discovered", 0),
            "total_processed": progress.get("total_processed", 0),
            "total_remaining": progress.get("total_remaining", 0),
            "current_batch_number": progress.get("current_batch_number", 0),
            "cursor": progress.get("cursor"),
            "cumulative_blanks": progress.get("cumulative_blanks", 0),
            "cumulative_quarantined": progress.get("cumulative_quarantined", 0),
            "cumulative_cost": progress.get("cumulative_cost", 0.0),
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress_data, f, indent=2)

    def update_aurora_doc_counts(self):
        """Update Aurora document counts via the existing update pattern.

        Calls the same logic as scripts/update_case_doc_counts.py to sync
        S3 document counts into Aurora so the UI reflects current totals.
        """
        case_id = self.config.case_id
        s3_count = count_s3_docs(case_id)
        if s3_count > 0:
            update_count(case_id, s3_count)

    def update_running_total(self, docs_added: int):
        """Update running_total_s3_docs for the target case in the ledger.

        Args:
            docs_added: Number of documents added in this batch.
        """
        ledger = load_ledger()
        cases = ledger.get("cases", {})
        case_id = self.config.case_id

        if case_id in cases:
            case = cases[case_id]
            current_total = case.get("running_total_s3_docs", 0)
            case["running_total_s3_docs"] = current_total + docs_added
            save_ledger(ledger)
