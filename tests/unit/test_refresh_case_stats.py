"""Unit tests for the refresh_case_stats action handler."""

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_event(case_id=None):
    """Build a minimal event for refresh_case_stats."""
    event = {"action": "refresh_case_stats"}
    if case_id is not None:
        event["case_id"] = case_id
    return event


class TestRefreshCaseStats:
    """Tests for _refresh_case_stats_handler."""

    @patch("db.connection.ConnectionManager")
    def test_returns_correct_counts(self, MockCM):
        """Handler returns document, entity, and relationship counts."""
        from src.lambdas.api.case_files import _refresh_case_stats_handler

        mock_cur = MagicMock()
        # fetchone returns: doc count, entity count, rel count
        mock_cur.fetchone.side_effect = [(345898,), (77900,), (1200,)]
        mock_cur.execute = MagicMock()
        mock_cm = MagicMock()
        mock_cm.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_cm.cursor.return_value.__exit__ = MagicMock(return_value=False)
        MockCM.return_value = mock_cm

        result = _refresh_case_stats_handler(
            _make_event("7f05e8d5-4492-4f19-8894-25367606db96"), None
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["document_count"] == 345898
        assert body["entity_count"] == 77900
        assert body["relationship_count"] == 1200

    def test_missing_case_id_returns_400(self):
        """Handler returns 400 when case_id is missing."""
        from src.lambdas.api.case_files import _refresh_case_stats_handler

        result = _refresh_case_stats_handler(_make_event(), None)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"]["code"] == "MISSING_PARAM"
