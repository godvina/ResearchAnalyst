"""Unit tests for invalidate_signature_ancestors utility function."""

from unittest.mock import MagicMock, patch

import pytest


def test_invalidate_signature_ancestors_calls_invalidate_by_path_with_domain_prefix():
    """Given a full signature context_key, invalidation uses the domain prefix."""
    from services.summary_cache_manager import (
        SummaryCacheManager,
        invalidate_signature_ancestors,
    )

    mock_cache_manager = MagicMock(spec=SummaryCacheManager)
    mock_cache_manager.invalidate_by_path.return_value = 3

    result = invalidate_signature_ancestors(
        "antitrust/procurement_collusion/bid_rotation/atr-pc-br-001",
        cache_manager=mock_cache_manager,
    )

    mock_cache_manager.invalidate_by_path.assert_called_once_with("antitrust")
    assert result == 3


def test_invalidate_signature_ancestors_returns_zero_for_invalid_key():
    """Returns 0 and does not call invalidation for keys without slash separators."""
    from services.summary_cache_manager import invalidate_signature_ancestors

    result = invalidate_signature_ancestors("no_slashes_here")
    assert result == 0


def test_invalidate_signature_ancestors_returns_zero_for_empty_key():
    """Returns 0 for empty or None context_key."""
    from services.summary_cache_manager import invalidate_signature_ancestors

    assert invalidate_signature_ancestors("") == 0
    assert invalidate_signature_ancestors(None) == 0


def test_invalidate_signature_ancestors_two_level_key():
    """Works with a typology-level key (domain/typology) — still uses domain prefix."""
    from services.summary_cache_manager import (
        SummaryCacheManager,
        invalidate_signature_ancestors,
    )

    mock_cache_manager = MagicMock(spec=SummaryCacheManager)
    mock_cache_manager.invalidate_by_path.return_value = 2

    result = invalidate_signature_ancestors(
        "ancient_mysteries/lost_civilizations",
        cache_manager=mock_cache_manager,
    )

    mock_cache_manager.invalidate_by_path.assert_called_once_with("ancient_mysteries")
    assert result == 2


def test_invalidate_signature_ancestors_creates_cache_manager_when_none_provided():
    """When no cache_manager is passed, one is created from ConnectionManager."""
    from services.summary_cache_manager import invalidate_signature_ancestors

    with patch("services.summary_cache_manager.SummaryCacheManager") as MockCM, \
         patch("db.connection.ConnectionManager") as MockConn:
        mock_instance = MockCM.return_value
        mock_instance.invalidate_by_path.return_value = 5

        result = invalidate_signature_ancestors(
            "antitrust/procurement_collusion/bid_rotation/atr-pc-br-001"
        )

        MockConn.assert_called_once()
        MockCM.assert_called_once_with(MockConn.return_value)
        mock_instance.invalidate_by_path.assert_called_once_with("antitrust")
        assert result == 5
