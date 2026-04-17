"""S3 data lake helper with prefix conventions for the Research Analyst Platform.

Provides functions for building S3 key paths and performing upload, download,
list, and delete operations scoped to case-specific prefixes.

S3 Data Lake Structure:
    s3://{bucket}/
      └── cases/
          └── {case_id}/
              ├── raw/                    # Original uploaded files
              │   └── {document_id}.{ext}
              ├── processed/              # Parsed structured documents
              │   └── {document_id}.json
              ├── extractions/            # Entity extraction artifacts
              │   └── {document_id}_extraction.json
              └── bulk-load/             # Neptune bulk loader CSVs
                  ├── {batch_id}_nodes.csv
                  └── {batch_id}_edges.csv

Environment variables:
    S3_BUCKET_NAME — Name of the S3 bucket for the data lake
"""

import os
from enum import Enum
from typing import IO

import boto3
from botocore.exceptions import ClientError


# ---------------------------------------------------------------------------
# Prefix types
# ---------------------------------------------------------------------------


class PrefixType(str, Enum):
    """Valid S3 prefix types within a case directory."""

    RAW = "raw"
    PROCESSED = "processed"
    EXTRACTIONS = "extractions"
    BULK_LOAD = "bulk-load"
    EXTRACTED_IMAGES = "extracted-images"


# ---------------------------------------------------------------------------
# Path builders
# ---------------------------------------------------------------------------

_CASES_ROOT = "cases"


def _get_bucket_name() -> str:
    """Return the S3 bucket name from the environment."""
    name = os.environ.get("S3_BUCKET_NAME")
    if not name:
        raise EnvironmentError("Required environment variable S3_BUCKET_NAME is not set")
    return name


def case_prefix(case_id: str) -> str:
    """Return the root S3 prefix for a case: ``cases/{case_id}/``."""
    return f"{_CASES_ROOT}/{case_id}/"


def build_key(case_id: str, prefix_type: PrefixType | str, filename: str) -> str:
    """Build a full S3 object key for a file within a case prefix.

    Args:
        case_id: The case file identifier.
        prefix_type: One of ``raw``, ``processed``, ``extractions``, ``bulk-load``.
        filename: The object filename (e.g. ``doc123.pdf``).

    Returns:
        The full S3 key, e.g. ``cases/{case_id}/raw/doc123.pdf``.
    """
    pt = PrefixType(prefix_type)
    return f"{_CASES_ROOT}/{case_id}/{pt.value}/{filename}"


def prefix_path(case_id: str, prefix_type: PrefixType | str) -> str:
    """Return the S3 prefix for a specific type within a case.

    E.g. ``cases/{case_id}/raw/``
    """
    pt = PrefixType(prefix_type)
    return f"{_CASES_ROOT}/{case_id}/{pt.value}/"


# ---------------------------------------------------------------------------
# New hierarchy path builders (Organization > Matter > Collection)
# ---------------------------------------------------------------------------

_ORGS_ROOT = "orgs"


def org_matter_collection_prefix(org_id: str, matter_id: str, collection_id: str) -> str:
    """Return the S3 prefix for a collection under the new hierarchy.

    Returns:
        ``orgs/{org_id}/matters/{matter_id}/collections/{collection_id}/``
    """
    return f"{_ORGS_ROOT}/{org_id}/matters/{matter_id}/collections/{collection_id}/"


def build_collection_key(
    org_id: str,
    matter_id: str,
    collection_id: str,
    prefix_type: PrefixType | str,
    filename: str,
) -> str:
    """Build a full S3 object key under the new hierarchy path.

    Args:
        org_id: The organization identifier.
        matter_id: The matter identifier.
        collection_id: The collection identifier.
        prefix_type: One of ``raw``, ``processed``, ``extractions``, ``bulk-load``.
        filename: The object filename (e.g. ``doc123.pdf``).

    Returns:
        The full S3 key, e.g.
        ``orgs/{org_id}/matters/{matter_id}/collections/{collection_id}/raw/doc123.pdf``.
    """
    pt = PrefixType(prefix_type)
    base = org_matter_collection_prefix(org_id, matter_id, collection_id)
    return f"{base}{pt.value}/{filename}"


def resolve_document_path(
    case_id: str | None,
    org_id: str | None,
    matter_id: str | None,
    collection_id: str | None,
    prefix_type: PrefixType | str,
    filename: str,
) -> str:
    """Resolve the S3 key for a document, preferring the new hierarchy path.

    Tries the new ``orgs/…/collections/…`` path first when *org_id*,
    *matter_id*, and *collection_id* are all provided.  Falls back to the
    legacy ``cases/{case_id}/`` path when the new-hierarchy parameters are
    missing or when the new-path object does not exist.

    Args:
        case_id: Legacy case identifier (used for fallback).
        org_id: Organization identifier (new hierarchy).
        matter_id: Matter identifier (new hierarchy).
        collection_id: Collection identifier (new hierarchy).
        prefix_type: One of ``raw``, ``processed``, ``extractions``, ``bulk-load``.
        filename: The object filename.

    Returns:
        The resolved S3 key string.

    Raises:
        ValueError: If neither the new-hierarchy parameters nor *case_id* are
            provided.
    """
    # Try new hierarchy path first
    if org_id and matter_id and collection_id:
        return build_collection_key(org_id, matter_id, collection_id, prefix_type, filename)

    # Fall back to legacy path
    if case_id:
        return build_key(case_id, prefix_type, filename)

    raise ValueError(
        "Either (org_id, matter_id, collection_id) or case_id must be provided"
    )


# ---------------------------------------------------------------------------
# S3 client helper
# ---------------------------------------------------------------------------


def _get_s3_client():
    """Return a boto3 S3 client."""
    return boto3.client("s3")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def upload_file(
    case_id: str,
    prefix_type: PrefixType | str,
    filename: str,
    content: bytes | str | IO,
    *,
    bucket: str | None = None,
) -> str:
    """Upload content to S3 under the case-specific prefix.

    Args:
        case_id: The case file identifier.
        prefix_type: One of ``raw``, ``processed``, ``extractions``, ``bulk-load``.
        filename: The object filename.
        content: File content as bytes, string, or file-like object.
        bucket: Optional bucket name override (defaults to ``S3_BUCKET_NAME`` env var).

    Returns:
        The S3 key where the object was stored.
    """
    bucket = bucket or _get_bucket_name()
    key = build_key(case_id, prefix_type, filename)
    s3 = _get_s3_client()

    if isinstance(content, str):
        content = content.encode("utf-8")

    if isinstance(content, bytes):
        s3.put_object(Bucket=bucket, Key=key, Body=content)
    else:
        s3.upload_fileobj(content, bucket, key)

    return key


def download_file(
    case_id: str,
    prefix_type: PrefixType | str,
    filename: str,
    *,
    bucket: str | None = None,
) -> bytes:
    """Download a file from S3 under the case-specific prefix.

    Args:
        case_id: The case file identifier.
        prefix_type: One of ``raw``, ``processed``, ``extractions``, ``bulk-load``.
        filename: The object filename.
        bucket: Optional bucket name override.

    Returns:
        The file content as bytes.

    Raises:
        ClientError: If the object does not exist or access is denied.
    """
    bucket = bucket or _get_bucket_name()
    key = build_key(case_id, prefix_type, filename)
    s3 = _get_s3_client()

    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def list_files(
    case_id: str,
    prefix_type: PrefixType | str,
    *,
    bucket: str | None = None,
) -> list[str]:
    """List filenames under a case-specific prefix.

    Args:
        case_id: The case file identifier.
        prefix_type: One of ``raw``, ``processed``, ``extractions``, ``bulk-load``.
        bucket: Optional bucket name override.

    Returns:
        A list of filenames (keys stripped of the prefix).
    """
    bucket = bucket or _get_bucket_name()
    pfx = prefix_path(case_id, prefix_type)
    s3 = _get_s3_client()

    filenames: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=pfx):
        for obj in page.get("Contents", []):
            # Strip the prefix to return just the filename portion.
            name = obj["Key"][len(pfx):]
            if name:  # skip the prefix-only key if present
                filenames.append(name)

    return filenames


def delete_file(
    case_id: str,
    prefix_type: PrefixType | str,
    filename: str,
    *,
    bucket: str | None = None,
) -> None:
    """Delete a single file from S3 under the case-specific prefix.

    Args:
        case_id: The case file identifier.
        prefix_type: One of ``raw``, ``processed``, ``extractions``, ``bulk-load``.
        filename: The object filename.
        bucket: Optional bucket name override.
    """
    bucket = bucket or _get_bucket_name()
    key = build_key(case_id, prefix_type, filename)
    s3 = _get_s3_client()
    s3.delete_object(Bucket=bucket, Key=key)


def delete_case_prefix(
    case_id: str,
    *,
    bucket: str | None = None,
) -> int:
    """Delete all objects under a case's S3 prefix.

    Args:
        case_id: The case file identifier.
        bucket: Optional bucket name override.

    Returns:
        The number of objects deleted.
    """
    bucket = bucket or _get_bucket_name()
    pfx = case_prefix(case_id)
    s3 = _get_s3_client()

    deleted_count = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=pfx):
        contents = page.get("Contents", [])
        if not contents:
            continue

        # S3 delete_objects accepts up to 1000 keys per call.
        objects = [{"Key": obj["Key"]} for obj in contents]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": objects, "Quiet": True})
        deleted_count += len(objects)

    return deleted_count
