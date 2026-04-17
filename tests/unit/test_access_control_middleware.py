"""Unit tests for access_control_middleware.py."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from services.access_control_middleware import (
    _default_restricted_user,
    _is_enabled,
    _transition_period,
    with_access_control,
)
from models.access_control import SecurityLabel, UserContext


# ------------------------------------------------------------------
# Helper function tests
# ------------------------------------------------------------------


class TestIsEnabled:
    def test_default_is_true(self, monkeypatch):
        monkeypatch.delenv("ACCESS_CONTROL_ENABLED", raising=False)
        assert _is_enabled() is True

    def test_explicit_true(self, monkeypatch):
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "true")
        assert _is_enabled() is True

    def test_false(self, monkeypatch):
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "false")
        assert _is_enabled() is False

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "False")
        assert _is_enabled() is False


class TestTransitionPeriod:
    def test_default_is_false(self, monkeypatch):
        monkeypatch.delenv("TRANSITION_PERIOD_ENABLED", raising=False)
        assert _transition_period() is False

    def test_explicit_true(self, monkeypatch):
        monkeypatch.setenv("TRANSITION_PERIOD_ENABLED", "true")
        assert _transition_period() is True

    def test_explicit_false(self, monkeypatch):
        monkeypatch.setenv("TRANSITION_PERIOD_ENABLED", "false")
        assert _transition_period() is False


class TestDefaultRestrictedUser:
    def test_returns_user_context(self):
        user = _default_restricted_user()
        assert isinstance(user, UserContext)

    def test_clearance_is_restricted(self):
        user = _default_restricted_user()
        assert user.clearance_level == SecurityLabel.RESTRICTED

    def test_user_id_is_anonymous(self):
        user = _default_restricted_user()
        assert user.user_id == "anonymous"

    def test_groups_empty(self):
        user = _default_restricted_user()
        assert user.groups == []


# ------------------------------------------------------------------
# Decorator tests
# ------------------------------------------------------------------

def _make_user_ctx(**overrides):
    defaults = {
        "user_id": "test-001",
        "username": "tester",
        "clearance_level": SecurityLabel.CONFIDENTIAL,
        "role": "analyst",
        "groups": [],
    }
    defaults.update(overrides)
    return UserContext(**defaults)


class TestWithAccessControl:
    """Tests for the with_access_control decorator."""

    def test_bypass_when_disabled(self, monkeypatch):
        """When ACCESS_CONTROL_ENABLED=false, handler runs without user resolution."""
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "false")

        handler = MagicMock(return_value={"statusCode": 200})
        wrapped = with_access_control(handler)

        event = {"httpMethod": "GET"}
        result = wrapped(event, {})

        handler.assert_called_once_with(event, {})
        assert result["statusCode"] == 200
        # _user_context should NOT be injected
        assert "_user_context" not in event

    def test_injects_user_context_on_success(self, monkeypatch):
        """Resolved user context is injected into event['_user_context']."""
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "true")

        user_ctx = _make_user_ctx()
        mock_service = MagicMock()
        mock_service.resolve_user_context.return_value = user_ctx

        handler = MagicMock(return_value={"statusCode": 200})
        wrapped = with_access_control(handler)

        event = {"httpMethod": "GET"}
        with patch(
            "services.access_control_middleware._build_access_control_service",
            return_value=mock_service,
        ):
            result = wrapped(event, {})

        handler.assert_called_once()
        assert event["_user_context"]["user_id"] == "test-001"
        assert event["_user_context"]["clearance_level"] == SecurityLabel.CONFIDENTIAL

    def test_returns_401_when_unresolvable_no_transition(self, monkeypatch):
        """Returns 401 when user can't be resolved and transition period is off."""
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "true")
        monkeypatch.setenv("TRANSITION_PERIOD_ENABLED", "false")

        mock_service = MagicMock()
        mock_service.resolve_user_context.side_effect = KeyError("User identity not resolvable")

        handler = MagicMock()
        wrapped = with_access_control(handler)

        event = {"httpMethod": "GET"}
        with patch(
            "services.access_control_middleware._build_access_control_service",
            return_value=mock_service,
        ):
            result = wrapped(event, {})

        handler.assert_not_called()
        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error"]["code"] == "UNAUTHORIZED"

    def test_falls_back_to_restricted_during_transition(self, monkeypatch):
        """Falls back to restricted clearance when transition period is on."""
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "true")
        monkeypatch.setenv("TRANSITION_PERIOD_ENABLED", "true")

        mock_service = MagicMock()
        mock_service.resolve_user_context.side_effect = KeyError("User identity not resolvable")

        handler = MagicMock(return_value={"statusCode": 200})
        wrapped = with_access_control(handler)

        event = {"httpMethod": "GET"}
        with patch(
            "services.access_control_middleware._build_access_control_service",
            return_value=mock_service,
        ):
            result = wrapped(event, {})

        handler.assert_called_once()
        assert event["_user_context"]["user_id"] == "anonymous"
        assert event["_user_context"]["clearance_level"] == SecurityLabel.RESTRICTED

    def test_401_response_has_cors_headers(self, monkeypatch):
        """401 response includes CORS headers."""
        monkeypatch.setenv("ACCESS_CONTROL_ENABLED", "true")
        monkeypatch.setenv("TRANSITION_PERIOD_ENABLED", "false")

        mock_service = MagicMock()
        mock_service.resolve_user_context.side_effect = KeyError("nope")

        wrapped = with_access_control(lambda e, c: {"statusCode": 200})

        with patch(
            "services.access_control_middleware._build_access_control_service",
            return_value=mock_service,
        ):
            result = wrapped({}, {})

        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
        assert result["headers"]["Content-Type"] == "application/json"

    def test_preserves_handler_name(self):
        """Decorator preserves the original function name via functools.wraps."""
        def my_handler(event, context):
            pass

        wrapped = with_access_control(my_handler)
        assert wrapped.__name__ == "my_handler"
