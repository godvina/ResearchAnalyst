"""Batch discovery and cursor management for incremental PDF processing."""

import json
import os
from pathlib import Path

from batch_loader.config import BatchConfig

# Local state file paths
BATCH_PROGRESS_FILE = os.path.join("scripts", "batch_progress.json")
QUARANTINE_FILE = os.path.join("scripts", "quarantine.json")
BATCH_MANIFESTS_DIR = os.path.join("scripts", "batch_manifests")


class BatchDiscovery:
    """Discovers next batch of unprocessed raw PDFs from S3."""

    def __init__(self, config: BatchConfig, s3_client):
        self.config = config
        self.s3 = s3_client

    # Supported file extensions for discovery
    _SUPPORTED_EXTENSIONS = (".pdf", ".txt")

    def list_all_raw_keys(self) -> list[str]:
        """List all document keys under configured source prefixes.

        Uses S3 paginator to iterate over all objects in each source prefix,
        filtering for files with supported extensions (.pdf, .txt).
        """
        keys: list[str] = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for prefix in self.config.source_prefixes:
            for page in paginator.paginate(
                Bucket=self.config.source_bucket, Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.lower().endswith(self._SUPPORTED_EXTENSIONS):
                        keys.append(key)
        return keys

    def load_processed_keys(self) -> set[str]:
        """Load keys from completed manifests and quarantine.

        Reads all s3_key fields from batch manifest JSON files in
        scripts/batch_manifests/ plus quarantined_keys from scripts/quarantine.json.
        """
        processed: set[str] = set()

        # Read keys from all local batch manifest files
        manifests_dir = Path(BATCH_MANIFESTS_DIR)
        if manifests_dir.is_dir():
            for manifest_file in sorted(manifests_dir.glob("*.json")):
                try:
                    with open(manifest_file, "r") as f:
                        manifest = json.load(f)
                    for entry in manifest.get("files", []):
                        s3_key = entry.get("s3_key")
                        if s3_key:
                            processed.add(s3_key)
                except (json.JSONDecodeError, OSError):
                    continue

        # Read quarantined keys
        quarantine_path = Path(QUARANTINE_FILE)
        if quarantine_path.is_file():
            try:
                with open(quarantine_path, "r") as f:
                    quarantine = json.load(f)
                for entry in quarantine.get("quarantined_keys", []):
                    s3_key = entry.get("s3_key") if isinstance(entry, dict) else entry
                    if s3_key:
                        processed.add(s3_key)
            except (json.JSONDecodeError, OSError):
                pass

        return processed

    def get_cursor(self) -> str | None:
        """Read cursor from batch_progress.json.

        Returns the cursor string (last processed S3 key) or None if no
        progress file exists or no cursor is set.
        """
        progress_path = Path(BATCH_PROGRESS_FILE)
        if not progress_path.is_file():
            return None
        try:
            with open(progress_path, "r") as f:
                progress = json.load(f)
            return progress.get("cursor")
        except (json.JSONDecodeError, OSError):
            return None

    def discover_batch(self) -> list[str]:
        """Return next batch_size unprocessed keys, starting from cursor.

        Sorts all raw keys alphabetically, excludes processed and quarantined
        keys, starts from the cursor position, and returns up to batch_size keys.
        """
        all_keys = self.list_all_raw_keys()
        processed = self.load_processed_keys()
        cursor = self.get_cursor()

        # Filter out already-processed keys
        unprocessed = sorted(k for k in all_keys if k not in processed)

        # Apply cursor — skip keys <= cursor
        if cursor is not None:
            unprocessed = [k for k in unprocessed if k > cursor]

        # Return up to batch_size
        return unprocessed[: self.config.batch_size]

    def save_cursor(self, last_key: str) -> None:
        """Persist cursor to batch_progress.json.

        Reads existing progress data (if any), updates the cursor field,
        and writes back to disk.
        """
        progress_path = Path(BATCH_PROGRESS_FILE)
        progress: dict = {}
        if progress_path.is_file():
            try:
                with open(progress_path, "r") as f:
                    progress = json.load(f)
            except (json.JSONDecodeError, OSError):
                progress = {}

        progress["cursor"] = last_key

        # Ensure parent directory exists
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        with open(progress_path, "w") as f:
            json.dump(progress, f, indent=2)
