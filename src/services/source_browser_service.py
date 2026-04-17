"""Source Browser Service — inventories the source S3 bucket by prefix.

Provides prefix-level metadata (file counts, sizes, types), zip archive
central directory inspection via range reads, and bucket summary computation
for the Data Prep & Source Management UI.
"""

import io
import logging
import zipfile
from dataclasses import dataclass, field

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ZipFileInfo:
    """Metadata for a zip archive in the source bucket."""
    key: str
    size_bytes: int
    estimated_file_count: int = 0
    already_extracted: bool = False
    extraction_job_id: str | None = None


@dataclass
class PrefixInfo:
    """Metadata for a single S3 prefix in the source bucket."""
    prefix: str
    total_objects: int = 0
    total_size_bytes: int = 0
    pdf_count: int = 0
    zip_count: int = 0
    zip_files: list[ZipFileInfo] = field(default_factory=list)


@dataclass
class ZipMetadata:
    """Central directory metadata for a zip archive."""
    key: str
    total_entries: int = 0
    pdf_entries: int = 0
    filenames: list[str] = field(default_factory=list)
    total_uncompressed_bytes: int = 0


@dataclass
class BucketSummary:
    """Aggregate summary of the source bucket."""
    total_files: int = 0
    total_extracted_pdfs: int = 0
    already_processed: int = 0
    remaining_unprocessed: int = 0


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class SourceBrowserService:
    """Inventories the source S3 bucket by prefix."""

    def __init__(self, s3_client, source_bucket: str, data_lake_bucket: str):
        self.s3 = s3_client
        self.source_bucket = source_bucket
        self.data_lake_bucket = data_lake_bucket

    # ------------------------------------------------------------------
    # list_prefixes
    # ------------------------------------------------------------------

    def list_prefixes(self) -> list[PrefixInfo]:
        """List all top-level prefixes with file counts, sizes, and types.

        Uses S3 ``list_objects_v2`` with ``Delimiter='/'`` to discover
        top-level prefixes, then paginates each prefix to count objects,
        sum sizes, and identify PDF vs zip files.
        """
        prefixes: list[PrefixInfo] = []

        # Step 1: discover top-level prefixes
        top_level = self._list_top_level_prefixes()

        # Step 2: for each prefix, paginate and gather stats
        for prefix_str in top_level:
            info = self._inventory_prefix(prefix_str)
            prefixes.append(info)

        return prefixes

    # ------------------------------------------------------------------
    # get_zip_metadata
    # ------------------------------------------------------------------

    def get_zip_metadata(self, zip_key: str) -> ZipMetadata:
        """Read zip central directory to get file count and names.

        Downloads only the last ~64 KB of the zip (where the central
        directory typically lives) using an S3 range read, then parses
        with the ``zipfile`` module.
        """
        try:
            # Get object size first
            head = self.s3.head_object(Bucket=self.source_bucket, Key=zip_key)
            file_size = head["ContentLength"]

            # Read the last 64 KB (or the whole file if smaller)
            read_size = min(file_size, 65536)
            range_start = file_size - read_size
            range_header = f"bytes={range_start}-{file_size - 1}"

            resp = self.s3.get_object(
                Bucket=self.source_bucket,
                Key=zip_key,
                Range=range_header,
            )
            tail_bytes = resp["Body"].read()

            # Parse central directory
            buf = io.BytesIO(tail_bytes)
            with zipfile.ZipFile(buf) as zf:
                entries = zf.infolist()
                all_names = [e.filename for e in entries if not e.is_dir()]
                pdf_names = [n for n in all_names if n.lower().endswith(".pdf")]
                total_uncompressed = sum(e.file_size for e in entries if not e.is_dir())

                return ZipMetadata(
                    key=zip_key,
                    total_entries=len(all_names),
                    pdf_entries=len(pdf_names),
                    filenames=all_names[:100],  # first 100 for preview
                    total_uncompressed_bytes=total_uncompressed,
                )

        except (zipfile.BadZipFile, KeyError, Exception) as exc:
            logger.warning("Failed to read zip metadata for %s: %s", zip_key, exc)
            return ZipMetadata(key=zip_key)

    # ------------------------------------------------------------------
    # get_summary
    # ------------------------------------------------------------------

    def get_summary(self, prefixes: list[PrefixInfo]) -> BucketSummary:
        """Compute summary: total files, extracted PDFs, processed, unprocessed.

        ``already_processed`` is derived from completed batch manifests
        stored in the data lake bucket.
        """
        total_files = sum(p.total_objects for p in prefixes)
        total_extracted_pdfs = sum(p.pdf_count for p in prefixes)

        # Count processed files from manifests
        already_processed = self._count_processed_from_manifests()

        remaining = max(0, total_extracted_pdfs - already_processed)

        return BucketSummary(
            total_files=total_files,
            total_extracted_pdfs=total_extracted_pdfs,
            already_processed=already_processed,
            remaining_unprocessed=remaining,
        )

    # ------------------------------------------------------------------
    # get_extraction_records
    # ------------------------------------------------------------------

    def get_extraction_records(self) -> dict[str, dict]:
        """Read completion records from ``extract-jobs/`` prefix in data lake bucket.

        Returns a dict mapping zip_key to its completion record.
        """
        records: dict[str, dict] = {}
        try:
            import json

            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self.data_lake_bucket, Prefix="extract-jobs/"
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith("/completion.json"):
                        continue
                    try:
                        resp = self.s3.get_object(
                            Bucket=self.data_lake_bucket, Key=key
                        )
                        record = json.loads(resp["Body"].read().decode("utf-8"))
                        zip_key = record.get("zip_key")
                        if zip_key:
                            records[zip_key] = record
                    except (ClientError, Exception) as exc:
                        logger.warning("Failed to read completion record %s: %s", key, exc)
        except ClientError as exc:
            logger.warning("Failed to list extraction records: %s", exc)

        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _list_top_level_prefixes(self) -> list[str]:
        """Discover top-level prefixes using Delimiter='/'."""
        prefixes: list[str] = []
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self.source_bucket, Delimiter="/"
            ):
                for cp in page.get("CommonPrefixes", []):
                    prefixes.append(cp["Prefix"])
        except ClientError:
            raise
        return prefixes

    def _inventory_prefix(self, prefix: str) -> PrefixInfo:
        """Paginate a single prefix and gather object stats."""
        info = PrefixInfo(prefix=prefix)
        zip_files: list[ZipFileInfo] = []

        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.source_bucket, Prefix=prefix
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                size = obj.get("Size", 0)
                info.total_objects += 1
                info.total_size_bytes += size

                lower_key = key.lower()
                if lower_key.endswith(".pdf"):
                    info.pdf_count += 1
                elif lower_key.endswith(".zip"):
                    info.zip_count += 1
                    zip_files.append(ZipFileInfo(key=key, size_bytes=size))

        info.zip_files = zip_files
        return info

    def _count_processed_from_manifests(self) -> int:
        """Count unique processed S3 keys across all batch manifests."""
        import json

        processed_keys: set[str] = set()
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self.data_lake_bucket, Prefix="batch-manifests/"
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith(".json"):
                        continue
                    try:
                        resp = self.s3.get_object(
                            Bucket=self.data_lake_bucket, Key=key
                        )
                        manifest = json.loads(resp["Body"].read().decode("utf-8"))
                        for entry in manifest.get("files", []):
                            s3_key = entry.get("s3_key")
                            if s3_key:
                                processed_keys.add(s3_key)
                    except (ClientError, Exception) as exc:
                        logger.warning("Failed to read manifest %s: %s", key, exc)
        except ClientError as exc:
            logger.warning("Failed to list manifests: %s", exc)

        return len(processed_keys)
