"""Unit tests for scripts/batch_loader/discovery.py — BatchDiscovery."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.discovery import (
    BATCH_MANIFESTS_DIR,
    BATCH_PROGRESS_FILE,
    QUARANTINE_FILE,
    BatchDiscovery,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_s3_paginator(pages: list[list[dict]]) -> MagicMock:
    """Build a mock S3 client whose paginator yields the given pages.

    Each inner list is a list of {"Key": ..., "Size": ...} dicts for one page.
    """
    client = MagicMock()
    paginator = MagicMock()

    page_responses = [{"Contents": objs} for objs in pages]
    paginator.paginate.return_value = iter(page_responses)
    client.get_paginator.return_value = paginator
    return client


def _make_multi_prefix_paginator(prefix_pages: dict[str, list[list[dict]]]) -> MagicMock:
    """Build a mock S3 client that returns different pages per prefix."""
    client = MagicMock()
    paginator = MagicMock()

    def paginate_side_effect(Bucket, Prefix):
        pages = prefix_pages.get(Prefix, [])
        return iter([{"Contents": objs} for objs in pages])

    paginator.paginate.side_effect = paginate_side_effect
    client.get_paginator.return_value = paginator
    return client


# ===========================================================================
# list_all_raw_keys — mocked S3 paginator
# ===========================================================================

class TestListAllRawKeys:
    """Verify list_all_raw_keys uses S3 paginator and filters for .pdf."""

    def test_single_prefix_single_page(self):
        s3 = _make_s3_paginator([
            [{"Key": "pdfs/a.pdf"}, {"Key": "pdfs/b.pdf"}],
        ])
        disc = BatchDiscovery(BatchConfig(source_prefixes=["pdfs/"]), s3)
        keys = disc.list_all_raw_keys()
        assert keys == ["pdfs/a.pdf", "pdfs/b.pdf"]

    def test_filters_non_pdf_files(self):
        s3 = _make_s3_paginator([
            [
                {"Key": "pdfs/a.pdf"},
                {"Key": "pdfs/b.json"},
                {"Key": "pdfs/c.txt"},
                {"Key": "pdfs/d.PDF"},
            ],
        ])
        disc = BatchDiscovery(BatchConfig(source_prefixes=["pdfs/"]), s3)
        keys = disc.list_all_raw_keys()
        assert keys == ["pdfs/a.pdf", "pdfs/d.PDF"]

    def test_multiple_pages(self):
        s3 = _make_s3_paginator([
            [{"Key": "pdfs/a.pdf"}],
            [{"Key": "pdfs/b.pdf"}],
        ])
        # Paginator returns an iterator over pages — need to handle this
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "pdfs/a.pdf"}]},
            {"Contents": [{"Key": "pdfs/b.pdf"}]},
        ]
        s3.get_paginator.return_value = paginator
        disc = BatchDiscovery(BatchConfig(source_prefixes=["pdfs/"]), s3)
        keys = disc.list_all_raw_keys()
        assert keys == ["pdfs/a.pdf", "pdfs/b.pdf"]

    def test_multiple_prefixes(self):
        s3 = _make_multi_prefix_paginator({
            "pdfs/": [[{"Key": "pdfs/a.pdf"}]],
            "bw-documents/": [[{"Key": "bw-documents/x.pdf"}]],
        })
        disc = BatchDiscovery(
            BatchConfig(source_prefixes=["pdfs/", "bw-documents/"]), s3
        )
        keys = disc.list_all_raw_keys()
        assert keys == ["pdfs/a.pdf", "bw-documents/x.pdf"]

    def test_empty_prefix(self):
        s3 = _make_s3_paginator([[]])
        disc = BatchDiscovery(BatchConfig(source_prefixes=["pdfs/"]), s3)
        keys = disc.list_all_raw_keys()
        assert keys == []

    def test_page_with_no_contents_key(self):
        """S3 returns pages without Contents when prefix is empty."""
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{}]  # no "Contents" key
        client.get_paginator.return_value = paginator
        disc = BatchDiscovery(BatchConfig(source_prefixes=["pdfs/"]), client)
        keys = disc.list_all_raw_keys()
        assert keys == []

    def test_case_insensitive_pdf_extension(self):
        s3 = _make_s3_paginator([
            [
                {"Key": "pdfs/a.pdf"},
                {"Key": "pdfs/b.PDF"},
                {"Key": "pdfs/c.Pdf"},
                {"Key": "pdfs/d.pDf"},
            ],
        ])
        disc = BatchDiscovery(BatchConfig(source_prefixes=["pdfs/"]), s3)
        keys = disc.list_all_raw_keys()
        assert len(keys) == 4


# ===========================================================================
# load_processed_keys — manifest files and quarantine
# ===========================================================================

class TestLoadProcessedKeys:
    """Verify load_processed_keys reads from manifests and quarantine."""

    def test_no_manifests_no_quarantine(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(tmp_path / "manifests"),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(tmp_path / "quarantine.json"),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.load_processed_keys() == set()

    def test_reads_manifest_keys(self, tmp_path, monkeypatch):
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()
        manifest = {
            "files": [
                {"s3_key": "pdfs/a.pdf"},
                {"s3_key": "pdfs/b.pdf"},
            ]
        }
        (manifests_dir / "batch_001.json").write_text(json.dumps(manifest))

        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(manifests_dir),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(tmp_path / "quarantine.json"),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.load_processed_keys() == {"pdfs/a.pdf", "pdfs/b.pdf"}

    def test_reads_quarantine_keys(self, tmp_path, monkeypatch):
        quarantine = {
            "quarantined_keys": [
                {"s3_key": "pdfs/bad.pdf", "reason": "corrupted"},
            ]
        }
        q_path = tmp_path / "quarantine.json"
        q_path.write_text(json.dumps(quarantine))

        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(tmp_path / "manifests"),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(q_path),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.load_processed_keys() == {"pdfs/bad.pdf"}

    def test_combines_manifest_and_quarantine(self, tmp_path, monkeypatch):
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()
        manifest = {"files": [{"s3_key": "pdfs/a.pdf"}]}
        (manifests_dir / "batch_001.json").write_text(json.dumps(manifest))

        quarantine = {
            "quarantined_keys": [{"s3_key": "pdfs/bad.pdf", "reason": "err"}]
        }
        q_path = tmp_path / "quarantine.json"
        q_path.write_text(json.dumps(quarantine))

        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(manifests_dir),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(q_path),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.load_processed_keys() == {"pdfs/a.pdf", "pdfs/bad.pdf"}

    def test_multiple_manifests(self, tmp_path, monkeypatch):
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()
        (manifests_dir / "batch_001.json").write_text(
            json.dumps({"files": [{"s3_key": "pdfs/a.pdf"}]})
        )
        (manifests_dir / "batch_002.json").write_text(
            json.dumps({"files": [{"s3_key": "pdfs/b.pdf"}]})
        )

        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(manifests_dir),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(tmp_path / "quarantine.json"),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.load_processed_keys() == {"pdfs/a.pdf", "pdfs/b.pdf"}

    def test_corrupt_manifest_skipped(self, tmp_path, monkeypatch):
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()
        (manifests_dir / "batch_001.json").write_text("NOT JSON")
        (manifests_dir / "batch_002.json").write_text(
            json.dumps({"files": [{"s3_key": "pdfs/ok.pdf"}]})
        )

        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(manifests_dir),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(tmp_path / "quarantine.json"),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.load_processed_keys() == {"pdfs/ok.pdf"}

    def test_corrupt_quarantine_returns_empty(self, tmp_path, monkeypatch):
        q_path = tmp_path / "quarantine.json"
        q_path.write_text("NOT JSON")

        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(tmp_path / "manifests"),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(q_path),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.load_processed_keys() == set()


# ===========================================================================
# get_cursor / save_cursor round-trip
# ===========================================================================

class TestCursorRoundTrip:
    """Verify get_cursor and save_cursor persist and read cursor correctly."""

    def test_no_progress_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_PROGRESS_FILE",
            str(tmp_path / "batch_progress.json"),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.get_cursor() is None

    def test_save_then_get_returns_same_key(self, tmp_path, monkeypatch):
        progress_file = str(tmp_path / "batch_progress.json")
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_PROGRESS_FILE",
            progress_file,
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        disc.save_cursor("pdfs/EPSTEIN_DOC_045123.pdf")
        assert disc.get_cursor() == "pdfs/EPSTEIN_DOC_045123.pdf"

    def test_save_overwrites_previous_cursor(self, tmp_path, monkeypatch):
        progress_file = str(tmp_path / "batch_progress.json")
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_PROGRESS_FILE",
            progress_file,
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        disc.save_cursor("pdfs/first.pdf")
        disc.save_cursor("pdfs/second.pdf")
        assert disc.get_cursor() == "pdfs/second.pdf"

    def test_save_preserves_other_fields(self, tmp_path, monkeypatch):
        progress_file = tmp_path / "batch_progress.json"
        progress_file.write_text(json.dumps({
            "total_files_discovered": 331000,
            "cursor": "pdfs/old.pdf",
        }))
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_PROGRESS_FILE",
            str(progress_file),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        disc.save_cursor("pdfs/new.pdf")

        with open(progress_file) as f:
            data = json.load(f)
        assert data["cursor"] == "pdfs/new.pdf"
        assert data["total_files_discovered"] == 331000

    def test_corrupt_progress_returns_none(self, tmp_path, monkeypatch):
        progress_file = tmp_path / "batch_progress.json"
        progress_file.write_text("NOT JSON")
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_PROGRESS_FILE",
            str(progress_file),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.get_cursor() is None

    def test_progress_without_cursor_returns_none(self, tmp_path, monkeypatch):
        progress_file = tmp_path / "batch_progress.json"
        progress_file.write_text(json.dumps({"total_files_discovered": 100}))
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_PROGRESS_FILE",
            str(progress_file),
        )
        disc = BatchDiscovery(BatchConfig(), MagicMock())
        assert disc.get_cursor() is None


# ===========================================================================
# discover_batch — excluding processed/quarantined, batch_size, cursor
# ===========================================================================

class TestDiscoverBatch:
    """Verify discover_batch filters, sorts, applies cursor, and caps size."""

    def _setup_discovery(
        self,
        tmp_path,
        monkeypatch,
        all_keys: list[str],
        manifest_keys: list[str] | None = None,
        quarantine_keys: list[str] | None = None,
        cursor: str | None = None,
        batch_size: int = 5000,
    ) -> BatchDiscovery:
        """Wire up a BatchDiscovery with mocked S3 and local state."""
        # Mock S3 paginator
        s3 = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Contents": [{"Key": k} for k in all_keys]}
        ]
        s3.get_paginator.return_value = paginator

        # Set up manifests dir
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir(exist_ok=True)
        if manifest_keys:
            manifest = {"files": [{"s3_key": k} for k in manifest_keys]}
            (manifests_dir / "batch_001.json").write_text(json.dumps(manifest))

        # Set up quarantine
        q_path = tmp_path / "quarantine.json"
        if quarantine_keys:
            quarantine = {
                "quarantined_keys": [
                    {"s3_key": k, "reason": "test"} for k in quarantine_keys
                ]
            }
            q_path.write_text(json.dumps(quarantine))

        # Set up cursor
        progress_file = tmp_path / "batch_progress.json"
        if cursor is not None:
            progress_file.write_text(json.dumps({"cursor": cursor}))

        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_MANIFESTS_DIR",
            str(manifests_dir),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.QUARANTINE_FILE",
            str(q_path),
        )
        monkeypatch.setattr(
            "scripts.batch_loader.discovery.BATCH_PROGRESS_FILE",
            str(progress_file),
        )

        config = BatchConfig(batch_size=batch_size, source_prefixes=["pdfs/"])
        return BatchDiscovery(config, s3)

    def test_excludes_processed_keys(self, tmp_path, monkeypatch):
        disc = self._setup_discovery(
            tmp_path,
            monkeypatch,
            all_keys=["pdfs/a.pdf", "pdfs/b.pdf", "pdfs/c.pdf"],
            manifest_keys=["pdfs/a.pdf"],
        )
        batch = disc.discover_batch()
        assert "pdfs/a.pdf" not in batch
        assert "pdfs/b.pdf" in batch
        assert "pdfs/c.pdf" in batch

    def test_excludes_quarantined_keys(self, tmp_path, monkeypatch):
        disc = self._setup_discovery(
            tmp_path,
            monkeypatch,
            all_keys=["pdfs/a.pdf", "pdfs/b.pdf", "pdfs/c.pdf"],
            quarantine_keys=["pdfs/b.pdf"],
        )
        batch = disc.discover_batch()
        assert "pdfs/b.pdf" not in batch
        assert set(batch) == {"pdfs/a.pdf", "pdfs/c.pdf"}

    def test_excludes_both_processed_and_quarantined(self, tmp_path, monkeypatch):
        disc = self._setup_discovery(
            tmp_path,
            monkeypatch,
            all_keys=["pdfs/a.pdf", "pdfs/b.pdf", "pdfs/c.pdf", "pdfs/d.pdf"],
            manifest_keys=["pdfs/a.pdf"],
            quarantine_keys=["pdfs/c.pdf"],
        )
        batch = disc.discover_batch()
        assert set(batch) == {"pdfs/b.pdf", "pdfs/d.pdf"}

    def test_respects_batch_size_cap(self, tmp_path, monkeypatch):
        all_keys = [f"pdfs/doc_{i:04d}.pdf" for i in range(100)]
        disc = self._setup_discovery(
            tmp_path, monkeypatch, all_keys=all_keys, batch_size=10
        )
        batch = disc.discover_batch()
        assert len(batch) == 10

    def test_returns_all_when_fewer_than_batch_size(self, tmp_path, monkeypatch):
        all_keys = [f"pdfs/doc_{i:04d}.pdf" for i in range(3)]
        disc = self._setup_discovery(
            tmp_path, monkeypatch, all_keys=all_keys, batch_size=100
        )
        batch = disc.discover_batch()
        assert len(batch) == 3

    def test_cursor_resumption(self, tmp_path, monkeypatch):
        all_keys = ["pdfs/a.pdf", "pdfs/b.pdf", "pdfs/c.pdf", "pdfs/d.pdf"]
        disc = self._setup_discovery(
            tmp_path, monkeypatch, all_keys=all_keys, cursor="pdfs/b.pdf"
        )
        batch = disc.discover_batch()
        # Should only include keys > "pdfs/b.pdf" alphabetically
        assert "pdfs/a.pdf" not in batch
        assert "pdfs/b.pdf" not in batch
        assert "pdfs/c.pdf" in batch
        assert "pdfs/d.pdf" in batch

    def test_cursor_with_batch_size(self, tmp_path, monkeypatch):
        all_keys = [f"pdfs/doc_{i:04d}.pdf" for i in range(20)]
        disc = self._setup_discovery(
            tmp_path,
            monkeypatch,
            all_keys=all_keys,
            cursor="pdfs/doc_0009.pdf",
            batch_size=5,
        )
        batch = disc.discover_batch()
        assert len(batch) == 5
        # All returned keys should be > cursor
        assert all(k > "pdfs/doc_0009.pdf" for k in batch)

    def test_sorted_alphabetically(self, tmp_path, monkeypatch):
        all_keys = ["pdfs/c.pdf", "pdfs/a.pdf", "pdfs/b.pdf"]
        disc = self._setup_discovery(
            tmp_path, monkeypatch, all_keys=all_keys
        )
        batch = disc.discover_batch()
        assert batch == sorted(batch)

    def test_empty_when_all_processed(self, tmp_path, monkeypatch):
        all_keys = ["pdfs/a.pdf", "pdfs/b.pdf"]
        disc = self._setup_discovery(
            tmp_path,
            monkeypatch,
            all_keys=all_keys,
            manifest_keys=["pdfs/a.pdf", "pdfs/b.pdf"],
        )
        batch = disc.discover_batch()
        assert batch == []

    def test_empty_when_cursor_past_all_keys(self, tmp_path, monkeypatch):
        all_keys = ["pdfs/a.pdf", "pdfs/b.pdf"]
        disc = self._setup_discovery(
            tmp_path, monkeypatch, all_keys=all_keys, cursor="pdfs/z.pdf"
        )
        batch = disc.discover_batch()
        assert batch == []

    def test_no_s3_keys_returns_empty(self, tmp_path, monkeypatch):
        disc = self._setup_discovery(
            tmp_path, monkeypatch, all_keys=[]
        )
        batch = disc.discover_batch()
        assert batch == []
