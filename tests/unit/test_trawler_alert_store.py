"""Unit tests for TrawlerAlertStore with mocked database connections."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock
from contextlib import contextmanager

import pytest

from src.services.trawler_alert_store import TrawlerAlertStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_alert_row(
    alert_id="alert-001",
    case_id="case-001",
    scan_id="scan-001",
    alert_type="new_connection",
    severity="high",
    title="New connection detected",
    summary="Entity A linked to Entity B",
    entity_names=None,
    evidence_refs=None,
    source_type="internal",
    is_read=False,
    is_dismissed=False,
    created_at=None,
    updated_at=None,
):
    return (
        alert_id,
        case_id,
        scan_id,
        alert_type,
        severity,
        title,
        summary,
        entity_names or ["Entity A", "Entity B"],
        evidence_refs or [{"ref_id": "r1", "ref_type": "graph_edge", "source_label": "edge-1", "excerpt": "link"}],
        source_type,
        is_read,
        is_dismissed,
        created_at or _NOW,
        updated_at or _NOW,
    )


def _make_scan_row(
    scan_id="scan-001",
    case_id="case-001",
    started_at=None,
    completed_at=None,
    alerts_generated=3,
    scan_status="completed",
    scan_type="full",
    phase_timings=None,
    error_message=None,
    pattern_baseline=None,
):
    return (
        scan_id,
        case_id,
        started_at or _NOW,
        completed_at or _NOW,
        alerts_generated,
        scan_status,
        scan_type,
        phase_timings or {},
        error_message,
        pattern_baseline or {},
    )


@pytest.fixture()
def mock_cursor():
    cursor = MagicMock()
    cursor.fetchone.return_value = _make_alert_row()
    cursor.fetchall.return_value = [_make_alert_row()]
    return cursor


@pytest.fixture()
def mock_db(mock_cursor):
    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield mock_cursor

    db.cursor = _cursor_ctx
    return db


@pytest.fixture()
def store(mock_db):
    return TrawlerAlertStore(mock_db)


# ---------------------------------------------------------------------------
# list_alerts
# ---------------------------------------------------------------------------


class TestListAlerts:
    def test_returns_list_of_dicts(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = [_make_alert_row(), _make_alert_row(alert_id="alert-002")]
        result = store.list_alerts("case-001")
        assert len(result) == 2
        assert result[0]["alert_id"] == "alert-001"
        assert result[1]["alert_id"] == "alert-002"

    def test_empty_list(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = store.list_alerts("case-001")
        assert result == []

    def test_filter_by_alert_type(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = [_make_alert_row(alert_type="entity_spike")]
        result = store.list_alerts("case-001", alert_type="entity_spike")
        assert len(result) == 1
        sql = mock_cursor.execute.call_args[0][0]
        assert "alert_type = %s" in sql

    def test_filter_by_severity(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = [_make_alert_row(severity="critical")]
        result = store.list_alerts("case-001", severity="critical")
        assert len(result) == 1
        sql = mock_cursor.execute.call_args[0][0]
        assert "severity = %s" in sql

    def test_filter_by_source_type(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = [_make_alert_row(source_type="osint")]
        result = store.list_alerts("case-001", source_type="osint")
        assert len(result) == 1
        sql = mock_cursor.execute.call_args[0][0]
        assert "source_type = %s" in sql

    def test_filter_by_is_read(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = [_make_alert_row(is_read=True)]
        result = store.list_alerts("case-001", is_read=True)
        assert len(result) == 1
        sql = mock_cursor.execute.call_args[0][0]
        assert "is_read = %s" in sql

    def test_filter_by_is_dismissed(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = []
        store.list_alerts("case-001", is_dismissed=True)
        sql = mock_cursor.execute.call_args[0][0]
        assert "is_dismissed = %s" in sql

    def test_multi_filter(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = [_make_alert_row()]
        store.list_alerts("case-001", alert_type="new_connection", severity="high", is_read=False)
        sql = mock_cursor.execute.call_args[0][0]
        assert "alert_type = %s" in sql
        assert "severity = %s" in sql
        assert "is_read = %s" in sql

    def test_db_error_returns_empty(self, store, mock_cursor):
        mock_cursor.execute.side_effect = Exception("connection lost")
        result = store.list_alerts("case-001")
        assert result == []


# ---------------------------------------------------------------------------
# get_alert
# ---------------------------------------------------------------------------


class TestGetAlert:
    def test_returns_alert_dict(self, store, mock_cursor):
        result = store.get_alert("alert-001")
        assert result is not None
        assert result["alert_id"] == "alert-001"
        assert result["alert_type"] == "new_connection"

    def test_not_found_returns_none(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = store.get_alert("nonexistent")
        assert result is None

    def test_db_error_returns_none(self, store, mock_cursor):
        mock_cursor.execute.side_effect = Exception("timeout")
        result = store.get_alert("alert-001")
        assert result is None


# ---------------------------------------------------------------------------
# update_alert
# ---------------------------------------------------------------------------


class TestUpdateAlert:
    def test_mark_read(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = _make_alert_row(is_read=True)
        result = store.update_alert("alert-001", is_read=True)
        assert result is not None
        sql = mock_cursor.execute.call_args[0][0]
        assert "is_read = %s" in sql

    def test_mark_dismissed(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = _make_alert_row(is_dismissed=True)
        result = store.update_alert("alert-001", is_dismissed=True)
        assert result is not None
        sql = mock_cursor.execute.call_args[0][0]
        assert "is_dismissed = %s" in sql

    def test_not_found_returns_none(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = store.update_alert("nonexistent", is_read=True)
        assert result is None

    def test_db_error_returns_none(self, store, mock_cursor):
        mock_cursor.execute.side_effect = Exception("fail")
        result = store.update_alert("alert-001", is_read=True)
        assert result is None


# ---------------------------------------------------------------------------
# get_unread_count
# ---------------------------------------------------------------------------


class TestGetUnreadCount:
    def test_returns_count(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = (5,)
        result = store.get_unread_count("case-001")
        assert result == 5

    def test_zero_count(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = (0,)
        result = store.get_unread_count("case-001")
        assert result == 0

    def test_db_error_returns_zero(self, store, mock_cursor):
        mock_cursor.execute.side_effect = Exception("fail")
        result = store.get_unread_count("case-001")
        assert result == 0


# ---------------------------------------------------------------------------
# list_scan_history
# ---------------------------------------------------------------------------


class TestListScanHistory:
    def test_returns_scan_list(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = [_make_scan_row()]
        result = store.list_scan_history("case-001")
        assert len(result) == 1
        assert result[0]["scan_id"] == "scan-001"
        assert result[0]["scan_status"] == "completed"

    def test_empty_history(self, store, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = store.list_scan_history("case-001")
        assert result == []

    def test_db_error_returns_empty(self, store, mock_cursor):
        mock_cursor.execute.side_effect = Exception("fail")
        result = store.list_scan_history("case-001")
        assert result == []


# ---------------------------------------------------------------------------
# find_duplicate
# ---------------------------------------------------------------------------


class TestFindDuplicate:
    def test_finds_matching_alert(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = _make_alert_row()
        result = store.find_duplicate("case-001", "new_connection", ["Entity A"])
        assert result is not None
        assert result["alert_id"] == "alert-001"

    def test_no_match_returns_none(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = store.find_duplicate("case-001", "new_connection", ["Entity X"])
        assert result is None

    def test_empty_entity_names_returns_none(self, store, mock_cursor):
        result = store.find_duplicate("case-001", "new_connection", [])
        assert result is None
        mock_cursor.execute.assert_not_called()

    def test_db_error_returns_none(self, store, mock_cursor):
        mock_cursor.execute.side_effect = Exception("fail")
        result = store.find_duplicate("case-001", "new_connection", ["Entity A"])
        assert result is None


# ---------------------------------------------------------------------------
# merge_into_existing
# ---------------------------------------------------------------------------


class TestMergeIntoExisting:
    def test_merges_evidence_and_resets_read(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = _make_alert_row(is_read=False)
        new_refs = [{"ref_id": "r2", "ref_type": "document", "source_label": "doc.pdf", "excerpt": "new"}]
        result = store.merge_into_existing("alert-001", new_refs, "Updated summary")
        assert result is not None
        sql = mock_cursor.execute.call_args[0][0]
        assert "evidence_refs = evidence_refs ||" in sql
        assert "is_read = FALSE" in sql
        assert "created_at = NOW()" in sql

    def test_not_found_returns_empty(self, store, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = store.merge_into_existing("nonexistent", [], "summary")
        assert result == {}

    def test_db_error_returns_empty(self, store, mock_cursor):
        mock_cursor.execute.side_effect = Exception("fail")
        result = store.merge_into_existing("alert-001", [], "summary")
        assert result == {}
