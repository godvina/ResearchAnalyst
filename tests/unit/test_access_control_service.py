"""Unit tests for AccessControlService."""

import os
from unittest.mock import patch

from src.models.access_control import AccessDecision, SecurityLabel, UserContext
from src.services.access_control_service import AccessControlService
from src.services.audit_service import AuditService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user_ctx(clearance=SecurityLabel.RESTRICTED, user_id="analyst-001"):
    return UserContext(
        user_id=user_id,
        username="analyst",
        clearance_level=clearance,
        role="analyst",
        groups=[],
    )


def _make_doc(doc_id="doc-1", case_id="case-1", security_label="restricted",
              override=None):
    d = {
        "document_id": doc_id,
        "case_id": case_id,
        "security_label": security_label,
    }
    if override is not None:
        d["security_label_override"] = override
    return d


# ---------------------------------------------------------------------------
# resolve_user_context
# ---------------------------------------------------------------------------


class TestResolveUserContext:
    def setup_method(self):
        self.service = AccessControlService()

    def test_extracts_from_authorizer_claims(self):
        self.service.register_user({
            "user_id": "cognito-sub-123",
            "username": "jdoe",
            "clearance_level": SecurityLabel.CONFIDENTIAL,
            "role": "analyst",
            "groups": [],
        })
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "cognito-sub-123"}
                }
            }
        }
        ctx = self.service.resolve_user_context(event)
        assert ctx.user_id == "cognito-sub-123"
        assert ctx.clearance_level == SecurityLabel.CONFIDENTIAL

    def test_extracts_from_x_user_id_header(self):
        event = {"headers": {"X-User-Id": "admin-001"}}
        ctx = self.service.resolve_user_context(event)
        assert ctx.user_id == "admin-001"
        assert ctx.clearance_level == SecurityLabel.TOP_SECRET

    def test_extracts_from_lowercase_header(self):
        event = {"headers": {"x-user-id": "analyst-001"}}
        ctx = self.service.resolve_user_context(event)
        assert ctx.user_id == "analyst-001"

    def test_extracts_from_direct_user_id(self):
        event = {"_user_id": "admin-001"}
        ctx = self.service.resolve_user_context(event)
        assert ctx.user_id == "admin-001"

    def test_raises_when_no_identity(self):
        import pytest
        event = {}
        with pytest.raises(KeyError, match="User identity not resolvable"):
            self.service.resolve_user_context(event)

    def test_raises_when_user_not_found(self):
        import pytest
        event = {"_user_id": "nonexistent-user"}
        with pytest.raises(KeyError, match="User not found"):
            self.service.resolve_user_context(event)

    def test_returns_user_context_with_all_fields(self):
        event = {"_user_id": "admin-001"}
        ctx = self.service.resolve_user_context(event)
        assert ctx.user_id is not None
        assert ctx.username is not None
        assert ctx.clearance_level is not None
        assert ctx.role is not None
        assert ctx.groups is not None


# ---------------------------------------------------------------------------
# filter_documents
# ---------------------------------------------------------------------------


class TestFilterDocuments:
    def setup_method(self):
        self._orig = os.environ.get("ACCESS_CONTROL_ENABLED")
        os.environ["ACCESS_CONTROL_ENABLED"] = "true"
        self.service = AccessControlService()

    def teardown_method(self):
        if self._orig is None:
            os.environ.pop("ACCESS_CONTROL_ENABLED", None)
        else:
            os.environ["ACCESS_CONTROL_ENABLED"] = self._orig

    def test_excludes_documents_above_clearance(self):
        user = _make_user_ctx(SecurityLabel.RESTRICTED)
        docs = [
            _make_doc("d-1", security_label="public"),
            _make_doc("d-2", security_label="restricted"),
            _make_doc("d-3", security_label="confidential"),
            _make_doc("d-4", security_label="top_secret"),
        ]
        result = self.service.filter_documents(user, docs)
        ids = [d["document_id"] for d in result]
        assert "d-1" in ids
        assert "d-2" in ids
        assert "d-3" not in ids
        assert "d-4" not in ids

    def test_override_takes_precedence(self):
        user = _make_user_ctx(SecurityLabel.CONFIDENTIAL)
        docs = [
            _make_doc("d-1", security_label="public", override="top_secret"),
            _make_doc("d-2", security_label="top_secret", override="public"),
        ]
        result = self.service.filter_documents(user, docs)
        ids = [d["document_id"] for d in result]
        assert "d-1" not in ids  # override is top_secret
        assert "d-2" in ids      # override is public

    def test_top_secret_user_sees_all(self):
        user = _make_user_ctx(SecurityLabel.TOP_SECRET)
        docs = [
            _make_doc("d-1", security_label="public"),
            _make_doc("d-2", security_label="restricted"),
            _make_doc("d-3", security_label="confidential"),
            _make_doc("d-4", security_label="top_secret"),
        ]
        result = self.service.filter_documents(user, docs)
        assert len(result) == 4

    def test_empty_documents_returns_empty(self):
        user = _make_user_ctx()
        result = self.service.filter_documents(user, [])
        assert result == []

    def test_logs_denial_for_filtered_docs(self):
        user = _make_user_ctx(SecurityLabel.PUBLIC)
        docs = [_make_doc("d-secret", security_label="top_secret")]
        self.service.filter_documents(user, docs)
        audit_entries = self.service._audit.query_audit_log(entity_type="access_denied")
        assert len(audit_entries) == 1
        assert audit_entries[0]["entity_id"] == "d-secret"


# ---------------------------------------------------------------------------
# check_document_access
# ---------------------------------------------------------------------------


class TestCheckDocumentAccess:
    def setup_method(self):
        self._orig = os.environ.get("ACCESS_CONTROL_ENABLED")
        os.environ["ACCESS_CONTROL_ENABLED"] = "true"
        self.service = AccessControlService()

    def teardown_method(self):
        if self._orig is None:
            os.environ.pop("ACCESS_CONTROL_ENABLED", None)
        else:
            os.environ["ACCESS_CONTROL_ENABLED"] = self._orig

    def test_returns_denial_for_above_clearance(self):
        user = _make_user_ctx(SecurityLabel.PUBLIC)
        doc = _make_doc("d-1", security_label="confidential")
        decision = self.service.check_document_access(user, doc)
        assert decision.allowed is False

    def test_returns_allowed_for_within_clearance(self):
        user = _make_user_ctx(SecurityLabel.CONFIDENTIAL)
        doc = _make_doc("d-1", security_label="restricted")
        decision = self.service.check_document_access(user, doc)
        assert decision.allowed is True

    def test_logs_denial_to_audit(self):
        user = _make_user_ctx(SecurityLabel.PUBLIC)
        doc = _make_doc("d-1", security_label="top_secret")
        self.service.check_document_access(user, doc)
        entries = self.service._audit.query_audit_log(entity_type="access_denied")
        assert len(entries) == 1


# ---------------------------------------------------------------------------
# build_label_filter_clause
# ---------------------------------------------------------------------------


class TestBuildLabelFilterClause:
    def setup_method(self):
        self.service = AccessControlService()

    def test_returns_sql_fragment_and_params(self):
        sql, params = self.service.build_label_filter_clause(2)
        assert "COALESCE" in sql
        assert "%s" in sql
        assert params == [2]

    def test_params_match_clearance_rank(self):
        for rank in range(4):
            _, params = self.service.build_label_filter_clause(rank)
            assert params == [rank]


# ---------------------------------------------------------------------------
# ACCESS_CONTROL_ENABLED=false bypass
# ---------------------------------------------------------------------------


class TestAccessControlDisabled:
    def test_filter_documents_returns_all_when_disabled(self):
        with patch.dict(os.environ, {"ACCESS_CONTROL_ENABLED": "false"}):
            service = AccessControlService()
        user = _make_user_ctx(SecurityLabel.PUBLIC)
        docs = [
            _make_doc("d-1", security_label="top_secret"),
            _make_doc("d-2", security_label="confidential"),
        ]
        result = service.filter_documents(user, docs)
        assert len(result) == 2

    def test_check_document_access_returns_allowed_when_disabled(self):
        with patch.dict(os.environ, {"ACCESS_CONTROL_ENABLED": "false"}):
            service = AccessControlService()
        user = _make_user_ctx(SecurityLabel.PUBLIC)
        doc = _make_doc("d-1", security_label="top_secret")
        decision = service.check_document_access(user, doc)
        assert decision.allowed is True
        assert decision.reason == "access_control_disabled"


# ---------------------------------------------------------------------------
# log_access_denial delegation
# ---------------------------------------------------------------------------


class TestLogAccessDenial:
    def setup_method(self):
        self.service = AccessControlService()

    def test_delegates_to_audit_service(self):
        user = _make_user_ctx()
        resource = {"document_id": "doc-123"}
        entry = self.service.log_access_denial(user, resource, "test_reason")
        assert entry["entity_type"] == "access_denied"
        assert entry["entity_id"] == "doc-123"
        assert entry["changed_by"] == "analyst-001"
        assert entry["change_reason"] == "test_reason"
