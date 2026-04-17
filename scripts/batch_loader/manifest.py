"""Batch manifest generation and persistence.

Generates and persists batch manifest JSON files that record every source PDF
key, its extraction status, and pipeline outcome for a single batch. Manifests
are saved to S3 (batch-manifests/{case_id}/batch_{number}.json) and locally
(scripts/batch_manifests/) for auditability.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from scripts.batch_loader.config import BatchConfig

logger = logging.getLogger(__name__)

LOCAL_MANIFESTS_DIR = os.path.join("scripts", "batch_manifests")


@dataclass
class FileEntry:
    """Per-file record within a batch manifest."""

    s3_key: str
    file_size_bytes: int
    extraction_method: str       # "pypdf2" | "textract" | "failed"
    extracted_char_count: int
    blank_filtered: bool
    pipeline_status: str         # "sent" | "succeeded" | "failed" | "quarantined"
    sfn_execution_arn: str | None = None
    error_message: str | None = None


@dataclass
class BatchManifestData:
    """Top-level manifest data for a single batch."""

    batch_id: str
    batch_number: int
    started_at: str
    completed_at: str | None
    source_prefix: list[str]
    files: list[FileEntry] = field(default_factory=list)


class BatchManifest:
    """Generates and persists batch manifest JSON files."""

    def __init__(self, config: BatchConfig, s3_client):
        self._config = config
        self._s3 = s3_client

    def create(self, batch_number: int, source_prefixes: list[str]) -> BatchManifestData:
        """Initialize a new manifest for a batch."""
        return BatchManifestData(
            batch_id=f"batch_{batch_number:03d}",
            batch_number=batch_number,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            source_prefix=list(source_prefixes),
            files=[],
        )

    def add_file(self, manifest: BatchManifestData, entry: FileEntry) -> None:
        """Add a file entry to the manifest."""
        manifest.files.append(entry)

    def save(self, manifest: BatchManifestData) -> None:
        """Save manifest to S3 and local scripts/batch_manifests/.

        S3 key: batch-manifests/{case_id}/batch_{number}.json
        Local:  scripts/batch_manifests/batch_{number}.json
        """
        # Mark completion time
        if manifest.completed_at is None:
            manifest.completed_at = datetime.now(timezone.utc).isoformat()

        data = asdict(manifest)
        body = json.dumps(data, indent=2, default=str)

        # Save to S3
        s3_key = (
            f"batch-manifests/{self._config.case_id}/"
            f"batch_{manifest.batch_number:03d}.json"
        )
        try:
            self._s3.put_object(
                Bucket=self._config.data_lake_bucket,
                Key=s3_key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info("Saved manifest to s3://%s/%s", self._config.data_lake_bucket, s3_key)
        except Exception as exc:
            logger.error("Failed to save manifest to S3: %s", exc)

        # Save locally
        local_dir = LOCAL_MANIFESTS_DIR
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, f"batch_{manifest.batch_number:03d}.json")
        try:
            with open(local_path, "w") as f:
                f.write(body)
            logger.info("Saved manifest locally to %s", local_path)
        except OSError as exc:
            logger.error("Failed to save manifest locally: %s", exc)

    def load_completed_keys(self) -> set[str]:
        """Load all S3 keys from completed manifests stored in S3.

        Lists all manifest files under batch-manifests/{case_id}/ and
        collects every s3_key from the files array.
        """
        keys: set[str] = set()
        prefix = f"batch-manifests/{self._config.case_id}/"

        try:
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self._config.data_lake_bucket, Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    manifest_key = obj["Key"]
                    if not manifest_key.endswith(".json"):
                        continue
                    try:
                        resp = self._s3.get_object(
                            Bucket=self._config.data_lake_bucket, Key=manifest_key
                        )
                        manifest_data = json.loads(resp["Body"].read().decode("utf-8"))
                        for file_entry in manifest_data.get("files", []):
                            s3_key = file_entry.get("s3_key")
                            if s3_key:
                                keys.add(s3_key)
                    except Exception as exc:
                        logger.warning(
                            "Failed to read manifest %s: %s", manifest_key, exc
                        )
        except Exception as exc:
            logger.warning("Failed to list manifests from S3: %s", exc)

        logger.info("Loaded %d completed keys from S3 manifests", len(keys))
        return keys
