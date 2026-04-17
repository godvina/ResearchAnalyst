"""Batch Loader State — centralizes all S3 reads/writes for batch state.

Manages batch progress, quarantine, ledger, and manifest state in S3.
Adapts the existing batch_loader modules to use S3 paths instead of local files.
"""

import json
import logging

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Terminal statuses — batch is no longer running
TERMINAL_STATUSES = {"completed", "failed"}

# All valid batch statuses
VALID_STATUSES = {
    "discovery", "extracting", "filtering", "ingesting",
    "polling_sfn", "entity_resolution", "completed", "failed", "paused",
}


class BatchLoaderState:
    """Manages batch loader state in S3."""

    def __init__(self, s3_client, data_lake_bucket: str, case_id: str):
        self.s3 = s3_client
        self.bucket = data_lake_bucket
        self.case_id = case_id
        self.progress_key = f"batch-progress/{case_id}/batch_progress.json"
        self.quarantine_key = f"batch-progress/{case_id}/quarantine.json"
        self.ledger_key = f"batch-progress/{case_id}/ingestion_ledger.json"
        self.manifests_prefix = f"batch-manifests/{case_id}/"

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def read_progress(self) -> dict | None:
        """Read batch_progress.json from S3. Returns None if not found."""
        return self._read_json(self.progress_key)

    def write_progress(self, progress: dict) -> None:
        """Write batch_progress.json to S3."""
        self._write_json(self.progress_key, progress)

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------

    def read_quarantine(self) -> list[dict]:
        """Read quarantine.json from S3. Returns empty list if not found."""
        data = self._read_json(self.quarantine_key)
        if data is None:
            return []
        return data.get("quarantined_keys", [])

    def write_quarantine(self, entries: list[dict]) -> None:
        """Write quarantine.json to S3."""
        self._write_json(self.quarantine_key, {"quarantined_keys": entries})

    # ------------------------------------------------------------------
    # Ledger
    # ------------------------------------------------------------------

    def read_ledger(self) -> dict:
        """Read ingestion_ledger.json from S3. Returns empty structure if missing."""
        data = self._read_json(self.ledger_key)
        if data is None:
            return {"cases": {}}
        return data

    def append_ledger_entry(self, entry: dict) -> None:
        """Append a load entry to the ledger in S3 (read-modify-write)."""
        ledger = self.read_ledger()
        cases = ledger.setdefault("cases", {})
        case_data = cases.setdefault(self.case_id, {
            "name": "Unknown",
            "loads": [],
            "running_total_s3_docs": 0,
        })
        case_data["loads"].append(entry)
        self._write_json(self.ledger_key, ledger)

    # ------------------------------------------------------------------
    # Manifests
    # ------------------------------------------------------------------

    def list_manifests(self) -> list[dict]:
        """List all batch manifests with summary stats."""
        summaries = []
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self.bucket, Prefix=self.manifests_prefix
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith(".json"):
                        continue
                    manifest = self._read_json(key)
                    if manifest is None:
                        continue
                    summaries.append(self._summarize_manifest(manifest))
        except Exception as exc:
            logger.warning("Failed to list manifests: %s", exc)
        return summaries

    def read_manifest(self, batch_id: str) -> dict | None:
        """Read a specific batch manifest from S3. Returns None if missing."""
        key = f"{self.manifests_prefix}{batch_id}.json"
        return self._read_json(key)

    # ------------------------------------------------------------------
    # Batch-in-progress check
    # ------------------------------------------------------------------

    def is_batch_in_progress(self) -> tuple[bool, str | None]:
        """Check if a batch is currently running.

        Returns (True, batch_id) if status is non-terminal,
        (False, None) otherwise.
        """
        progress = self.read_progress()
        if progress is None:
            return (False, None)
        status = progress.get("status")
        if status is None or status in TERMINAL_STATUSES:
            return (False, None)
        return (True, progress.get("batch_id"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_json(self, key: str) -> dict | None:
        """Read and parse a JSON object from S3. Returns None if NoSuchKey."""
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def _write_json(self, key: str, data: dict | list) -> None:
        """Write a JSON object to S3."""
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data, default=str).encode("utf-8"),
            ContentType="application/json",
        )

    @staticmethod
    def _summarize_manifest(manifest: dict) -> dict:
        """Extract summary stats from a full manifest dict."""
        files = manifest.get("files", [])
        succeeded = sum(
            1 for f in files if f.get("pipeline_status") == "succeeded"
        )
        failed = sum(
            1 for f in files if f.get("pipeline_status") == "failed"
        )
        blank_filtered = sum(
            1 for f in files if f.get("blank_filtered", False)
        )
        quarantined = sum(
            1 for f in files if f.get("pipeline_status") == "quarantined"
        )
        return {
            "batch_id": manifest.get("batch_id"),
            "batch_number": manifest.get("batch_number"),
            "started_at": manifest.get("started_at"),
            "completed_at": manifest.get("completed_at"),
            "total_files": len(files),
            "succeeded": succeeded,
            "failed": failed,
            "blank_filtered": blank_filtered,
            "quarantined": quarantined,
        }


# ------------------------------------------------------------------
# Standalone filter / aggregation helpers (used by frontend & handler)
# ------------------------------------------------------------------


def filter_manifest_files(
    files: list[dict],
    pipeline_status: str | None = None,
    extraction_method: str | None = None,
) -> list[dict]:
    """Filter manifest file entries by pipeline_status and/or extraction_method.

    If both filters are None, returns all files unchanged.
    """
    result = files
    if pipeline_status is not None:
        result = [f for f in result if f.get("pipeline_status") == pipeline_status]
    if extraction_method is not None:
        result = [f for f in result if f.get("extraction_method") == extraction_method]
    return result


def compute_quarantine_summary(entries: list[dict]) -> dict:
    """Compute quarantine summary: total, by_reason breakdown, most_recent timestamp.

    Categorises each entry's reason into extraction_failed, pipeline_failed, or timeout.
    """
    by_reason: dict[str, int] = {}
    most_recent: str | None = None

    for entry in entries:
        reason = entry.get("reason", "unknown")
        reason_lower = reason.lower()
        if "extraction" in reason_lower or "pypdf" in reason_lower or "textract" in reason_lower:
            category = "extraction_failed"
        elif "timeout" in reason_lower:
            category = "timeout"
        else:
            category = "pipeline_failed"
        by_reason[category] = by_reason.get(category, 0) + 1

        failed_at = entry.get("failed_at")
        if failed_at and (most_recent is None or failed_at > most_recent):
            most_recent = failed_at

    return {
        "total_quarantined": len(entries),
        "by_reason": by_reason,
        "most_recent": most_recent,
    }


def filter_quarantine(entries: list[dict], search: str) -> list[dict]:
    """Filter quarantine entries by case-insensitive substring match on s3_key or reason."""
    if not search:
        return entries
    needle = search.lower()
    return [
        e for e in entries
        if needle in e.get("s3_key", "").lower()
        or needle in e.get("reason", "").lower()
    ]


def sort_history_entries(entries: list[dict]) -> list[dict]:
    """Sort history entries in reverse-chronological order by timestamp field."""
    return sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)


def compute_cumulative_stats(entries: list[dict]) -> dict:
    """Sum docs_sent_to_pipeline, blanks_skipped, and cost_actual across entries."""
    return {
        "total_processed": sum(e.get("docs_sent_to_pipeline", 0) for e in entries),
        "total_blanks_filtered": sum(e.get("blanks_skipped", 0) for e in entries),
        "total_estimated_cost": sum(e.get("cost_actual", 0) for e in entries),
    }
