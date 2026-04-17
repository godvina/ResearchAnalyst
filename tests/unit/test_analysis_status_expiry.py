"""Tests for the 15-minute expiry check in get_analysis_status().

Validates Requirements 1.3, 1.4, 2.3, 2.4 from the case-file-evidence-starvation bugfix.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call

import pytest

from src.services.investigator_ai_engine import InvestigatorAIEngine


@pytest.fixture
def mock_cursor():
    """A mock DB cursor that supports context-manager usage."""
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


@pytest.fixture
def engine(mock_cursor):
    aurora_cm = MagicMock()
    aurora_cm.cursor.return_value = mock_cursor
    return InvestigatorAIEngine(aurora_cm=aurora_cm, bedrock_client=MagicMock())


# ── No row → None ──────────────────────────────────────────────────

def test_returns_none_when_no_row(engine, mock_cursor):
    mock_cursor.fetchone.return_value = None
    result = engine.get_analysis_status("case-1")
    assert result is None


# ── Completed status is unaffected by expiry ───────────────────────

def test_completed_status_returned_regardless_of_age(engine, mock_cursor):
    old_ts = datetime.now(timezone.utc) - timedelta(hours=2)
    analysis = {"case_id": "case-1", "status": "completed"}
    mock_cursor.fetchone.return_value = (json.dumps(analysis), "completed", old_ts)

    result = engine.get_analysis_status("case-1")
    assert result is not None
    assert result.status == "completed"


# ── Error status is unaffected by expiry ───────────────────────────

def test_error_status_returned_regardless_of_age(engine, mock_cursor):
    old_ts = datetime.now(timezone.utc) - timedelta(hours=2)
    analysis = {"error_message": "boom", "case_id": "case-1", "status": "error"}
    mock_cursor.fetchone.return_value = (json.dumps(analysis), "error", old_ts)

    result = engine.get_analysis_status("case-1")
    assert result is not None
    assert result.status == "error"


# ── Fresh processing row → still processing ────────────────────────

def test_fresh_processing_row_returns_processing(engine, mock_cursor):
    recent_ts = datetime.now(timezone.utc) - timedelta(minutes=5)
    mock_cursor.fetchone.return_value = (None, "processing", recent_ts)

    result = engine.get_analysis_status("case-1")
    assert result is not None
    assert result.status == "processing"


# ── Stale processing row → expired (deleted) and returns None ──────

def test_stale_processing_row_is_expired(engine, mock_cursor):
    stale_ts = datetime.now(timezone.utc) - timedelta(minutes=20)
    mock_cursor.fetchone.return_value = (None, "processing", stale_ts)

    result = engine.get_analysis_status("case-1")
    assert result is None
    # Verify DELETE was issued
    delete_call = mock_cursor.execute.call_args_list[-1]
    assert "DELETE" in delete_call[0][0]
    assert "case-1" in delete_call[0][1]


# ── Exactly 15 minutes → not yet expired ──────────────────────────

def test_just_under_15_minutes_is_not_expired(engine, mock_cursor):
    # Use 14 minutes to avoid sub-second timing drift at the boundary
    boundary_ts = datetime.now(timezone.utc) - timedelta(minutes=14)
    mock_cursor.fetchone.return_value = (None, "processing", boundary_ts)

    result = engine.get_analysis_status("case-1")
    assert result is not None
    assert result.status == "processing"


# ── Naive timestamp (no tzinfo) is handled correctly ───────────────

def test_naive_timestamp_treated_as_utc(engine, mock_cursor):
    stale_naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    mock_cursor.fetchone.return_value = (None, "processing", stale_naive)

    result = engine.get_analysis_status("case-1")
    assert result is None


# ── NULL updated_at → processing returned (no crash) ──────────────

def test_null_updated_at_returns_processing(engine, mock_cursor):
    mock_cursor.fetchone.return_value = (None, "processing", None)

    result = engine.get_analysis_status("case-1")
    assert result is not None
    assert result.status == "processing"
