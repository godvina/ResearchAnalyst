"""Zip Extractor Service — streams zip archives from S3 and extracts PDFs.

Runs inside Lambda. Supports chunked extraction with resume for large zips
that exceed the Lambda timeout. Tracks progress in S3 JSON files and writes
completion records for already-extracted detection.
"""

import io
import json
import logging
import os
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Minimum remaining Lambda time (ms) before we stop and re-invoke
_TIMEOUT_BUFFER_MS = 30_000  # 30 seconds

# How often to flush progress to S3 (every N files)
_PROGRESS_FLUSH_INTERVAL = 50


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ExtractionJobProgress:
    """Progress state for a running extraction job.

    Stored at ``extract-jobs/{job_id}/progress.json`` in the data lake bucket.
    """
    job_id: str
    status: str = "pending"  # pending | extracting | completed | failed
    zip_keys: list[str] = field(default_factory=list)
    current_zip: str = ""
    files_extracted: int = 0
    files_total: int = 0
    files_skipped: int = 0
    bytes_uploaded: int = 0
    started_at: str = ""
    last_updated: str = ""
    elapsed_seconds: float = 0.0
    errors: list[dict] = field(default_factory=list)
    resume_index: int = 0
    chunk_number: int = 1


@dataclass
class ExtractionCompletionRecord:
    """Written once extraction of a single zip finishes successfully.

    Stored at ``extract-jobs/{job_id}/completion.json`` in the data lake bucket.
    """
    job_id: str
    zip_key: str
    total_extracted: int = 0
    total_skipped: int = 0
    total_bytes_uploaded: int = 0
    duration_seconds: float = 0.0
    completed_at: str = ""
    target_prefix: str = "pdfs/"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ZipExtractorService:
    """Streams zip archives from S3 and extracts PDFs to the source bucket."""

    def __init__(self, s3_client, source_bucket: str, data_lake_bucket: str):
        self.s3 = s3_client
        self.source_bucket = source_bucket
        self.data_lake_bucket = data_lake_bucket

    # ------------------------------------------------------------------
    # start_extraction
    # ------------------------------------------------------------------

    def start_extraction(self, zip_keys: list[str], job_id: str) -> dict:
        """Write initial progress JSON and return job metadata.

        Progress is stored at ``extract-jobs/{job_id}/progress.json``
        in the data lake bucket.
        """
        now = _utcnow_iso()
        progress = ExtractionJobProgress(
            job_id=job_id,
            status="pending",
            zip_keys=list(zip_keys),
            current_zip=zip_keys[0] if zip_keys else "",
            started_at=now,
            last_updated=now,
        )
        self._write_progress(progress)
        return asdict(progress)

    # ------------------------------------------------------------------
    # extract_zip
    # ------------------------------------------------------------------

    def extract_zip(
        self,
        zip_key: str,
        job_id: str,
        start_index: int = 0,
        remaining_ms: int | None = None,
    ) -> dict:
        """Stream a zip from S3, extract PDFs to ``pdfs/`` prefix.

        Parameters
        ----------
        zip_key:
            S3 key of the zip archive in the source bucket.
        job_id:
            Extraction job identifier.
        start_index:
            Entry index to resume from (for chunked extraction).
        remaining_ms:
            Remaining Lambda execution time in milliseconds.  The caller
            should pass ``context.get_remaining_time_in_millis()``.  When
            ``None`` the timeout check is disabled.

        Returns a dict with ``status`` (``completed`` | ``timeout``),
        ``files_extracted``, ``files_skipped``, ``bytes_uploaded``, and
        ``resume_index`` (meaningful only on timeout).
        """
        start_time = time.time()

        # Read current progress (or create fresh)
        progress = self._read_progress_obj(job_id)
        if progress is None:
            progress = ExtractionJobProgress(
                job_id=job_id,
                status="extracting",
                zip_keys=[zip_key],
                current_zip=zip_key,
                started_at=_utcnow_iso(),
                last_updated=_utcnow_iso(),
            )
        progress.status = "extracting"
        progress.current_zip = zip_key

        dataset_prefix = _dataset_prefix_from_key(zip_key)

        # Download the full zip into memory
        try:
            resp = self.s3.get_object(Bucket=self.source_bucket, Key=zip_key)
            zip_bytes = resp["Body"].read()
        except ClientError as exc:
            logger.error("Failed to download zip %s: %s", zip_key, exc)
            progress.status = "failed"
            progress.errors.append({"file": zip_key, "error": str(exc)})
            progress.last_updated = _utcnow_iso()
            self._write_progress(progress)
            return asdict(progress)

        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile as exc:
            logger.error("Bad zip file %s: %s", zip_key, exc)
            progress.status = "failed"
            progress.errors.append({"file": zip_key, "error": str(exc)})
            progress.last_updated = _utcnow_iso()
            self._write_progress(progress)
            return asdict(progress)

        entries = [e for e in zf.infolist() if not e.is_dir()]
        progress.files_total = len(entries)

        files_extracted = 0
        files_skipped = 0
        bytes_uploaded = 0
        last_index = start_index

        for idx in range(start_index, len(entries)):
            # Timeout check
            if remaining_ms is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if (remaining_ms - elapsed_ms) < _TIMEOUT_BUFFER_MS:
                    # Save resume point
                    progress.resume_index = idx
                    progress.files_extracted += files_extracted
                    progress.files_skipped += files_skipped
                    progress.bytes_uploaded += bytes_uploaded
                    progress.chunk_number += 1
                    progress.elapsed_seconds += time.time() - start_time
                    progress.last_updated = _utcnow_iso()
                    self._write_progress(progress)
                    return {
                        "status": "timeout",
                        "files_extracted": progress.files_extracted,
                        "files_skipped": progress.files_skipped,
                        "bytes_uploaded": progress.bytes_uploaded,
                        "resume_index": idx,
                    }

            entry = entries[idx]
            try:
                data = zf.read(entry.filename)
            except Exception as exc:
                logger.warning(
                    "Corrupted entry %s in %s: %s", entry.filename, zip_key, exc
                )
                files_skipped += 1
                progress.errors.append(
                    {"file": entry.filename, "error": str(exc)}
                )
                last_index = idx + 1
                continue

            # Build target key with dataset prefix to avoid collisions
            basename = os.path.basename(entry.filename)
            target_key = f"pdfs/{dataset_prefix}_{basename}"

            try:
                self.s3.put_object(
                    Bucket=self.source_bucket,
                    Key=target_key,
                    Body=data,
                )
                files_extracted += 1
                bytes_uploaded += len(data)
            except ClientError as exc:
                logger.warning(
                    "Failed to upload %s: %s", target_key, exc
                )
                files_skipped += 1
                progress.errors.append(
                    {"file": entry.filename, "error": str(exc)}
                )

            last_index = idx + 1

            # Periodic progress flush
            if (files_extracted + files_skipped) % _PROGRESS_FLUSH_INTERVAL == 0:
                progress.files_extracted += files_extracted
                progress.files_skipped += files_skipped
                progress.bytes_uploaded += bytes_uploaded
                progress.elapsed_seconds += time.time() - start_time
                progress.last_updated = _utcnow_iso()
                self._write_progress(progress)
                # Reset local counters (already accumulated into progress)
                files_extracted = 0
                files_skipped = 0
                bytes_uploaded = 0
                start_time = time.time()

        # Final accumulation
        progress.files_extracted += files_extracted
        progress.files_skipped += files_skipped
        progress.bytes_uploaded += bytes_uploaded
        progress.elapsed_seconds += time.time() - start_time
        progress.status = "completed"
        progress.resume_index = last_index
        progress.last_updated = _utcnow_iso()
        self._write_progress(progress)

        zf.close()

        return {
            "status": "completed",
            "files_extracted": progress.files_extracted,
            "files_skipped": progress.files_skipped,
            "bytes_uploaded": progress.bytes_uploaded,
            "resume_index": last_index,
        }

    # ------------------------------------------------------------------
    # read_progress
    # ------------------------------------------------------------------

    def read_progress(self, job_id: str) -> dict | None:
        """Read extraction progress JSON from S3.

        Returns the parsed dict, or ``None`` if the progress file
        does not exist.
        """
        key = f"extract-jobs/{job_id}/progress.json"
        try:
            resp = self.s3.get_object(Bucket=self.data_lake_bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    # ------------------------------------------------------------------
    # write_completion_record
    # ------------------------------------------------------------------

    def write_completion_record(
        self, job_id: str, zip_key: str, stats: dict
    ) -> None:
        """Write a completion record for already-extracted detection.

        Stored at ``extract-jobs/{job_id}/completion.json`` in the
        data lake bucket.
        """
        record = ExtractionCompletionRecord(
            job_id=job_id,
            zip_key=zip_key,
            total_extracted=stats.get("files_extracted", 0),
            total_skipped=stats.get("files_skipped", 0),
            total_bytes_uploaded=stats.get("bytes_uploaded", 0),
            duration_seconds=stats.get("duration_seconds", 0.0),
            completed_at=_utcnow_iso(),
        )
        key = f"extract-jobs/{job_id}/completion.json"
        self.s3.put_object(
            Bucket=self.data_lake_bucket,
            Key=key,
            Body=json.dumps(asdict(record), default=str).encode("utf-8"),
            ContentType="application/json",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_progress(self, progress: ExtractionJobProgress) -> None:
        """Persist progress dataclass to S3."""
        key = f"extract-jobs/{progress.job_id}/progress.json"
        self.s3.put_object(
            Bucket=self.data_lake_bucket,
            Key=key,
            Body=json.dumps(asdict(progress), default=str).encode("utf-8"),
            ContentType="application/json",
        )

    def _read_progress_obj(self, job_id: str) -> ExtractionJobProgress | None:
        """Read progress JSON and hydrate into dataclass."""
        data = self.read_progress(job_id)
        if data is None:
            return None
        return ExtractionJobProgress(**{
            k: v for k, v in data.items()
            if k in ExtractionJobProgress.__dataclass_fields__
        })


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _dataset_prefix_from_key(zip_key: str) -> str:
    """Derive a dataset prefix from a zip S3 key.

    Examples::

        "DataSet_11_v2.zip"       -> "DataSet_11_v2"
        "archives/DS8.zip"        -> "DS8"
        "foo/bar/MyData.ZIP"      -> "MyData"
    """
    basename = os.path.basename(zip_key)
    name, _ = os.path.splitext(basename)
    return name
