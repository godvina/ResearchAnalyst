"""Unit tests for scripts/batch_loader/entity_index.py — CanonicalEntityIndex."""

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.entity_index import CanonicalEntry, CanonicalEntityIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_s3_with_index(index_data: dict) -> MagicMock:
    """Build a mock S3 client that returns the given index JSON."""
    client = MagicMock()
    body = io.BytesIO(json.dumps(index_data).encode("utf-8"))
    client.get_object.return_value = {"Body": body}
    return client


def _make_s3_no_index() -> MagicMock:
    """Build a mock S3 client that raises NoSuchKey."""
    client = MagicMock()
    error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
    client.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    client.get_object.side_effect = client.exceptions.NoSuchKey(error_response, "GetObject")
    return cli