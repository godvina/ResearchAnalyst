"""Unit tests for AuditService — immutable audit trail for label changes."""

import time
from datetime import datetime, timezone, timedelta

from src.services.audit_service import AuditService


class TestLogLabelChange:
    def setup_method(self):
        self.service = AuditService()  # in-memory mode

    def test_inserts_correct_audit_entry(self):
        entry = self.service.log_label_change(
            entity_type="matter",
            entity_id="mat-001",
            previous_label="restricted",
            new_label="confidential",
            changed_by="admin-001",
            change_reason="Upgraded classification",
        )
        assert entry["entity_type"] == "matter"
        assert entry["entity_id"] == "mat-001"
        assert entry["previous_label"] == "restricted"
        assert entry["new_label"] == "confidential"
        assert entry["changed_by"] == "admin-001"
        assert entry["change_reason"] == "Upgraded classification"
        assert entry["audit_id"] is not None
        assert entry["changed_at"] is not None

    def test_entry_has_uuid_audit_id(self):
        import uuid
        entry = self.service.log_label_change(
            entity_type="document",
            entity_id="doc-001",
            previous_label=None,
            new_label="top_secret",
            changed_by="admin-001",
        )
        uuid.UUID(entry["audit_id"])  # raises if not valid UUID

    def test_change_reason_defaults_to_none(self):
        entry = self.service.log_label_change(
            entity_type="user",
            entity_id="user-001",
            previous_label="restricted",
            new_label="confidential",
            changed_by="admin-001",
        )
        assert entry["change_reason"] is None

    def test_multiple_entries_stored(self):
        self.service.log_label_change("matter", "m-1", "public", "restricted", "admin")
        self.service.log_label_change("matter", "m-2", "restricted", "confidential", "admin")
        results = self.service.query_audit_log()
        assert len(results) == 2


class TestLogAccessDenial:
    def setup_method(self):
        self.service = AuditService()

    def test_inserts_entity_type_access_denied(self):
        entry = self.service.log_access_denial(
            user_id="analyst-001",
            resource_id="doc-secret-001",
            reason="clearance_restricted_insufficient_for_top_secret",
        )
        assert entry["entity_type"] == "access_denied"
        assert entry["entity_id"] == "doc-secret-001"
        assert entry["changed_by"] == "analyst-001"
        assert entry["change_reason"] == "clearance_restricted_insufficient_for_top_secret"

    def test_labels_are_none_for_access_denial(self):
        entry = self.service.log_access_denial("user-1", "doc-1", "denied")
        assert entry["previous_label"] is None
        assert entry["new_label"] is None


class TestQueryAuditLog:
    def setup_method(self):
        self.service = AuditService()
        # Insert entries with slight time gaps for ordering
        self.service.log_label_change("matter", "m-1", "public", "restricted", "admin-a")
        time.sleep(0.01)
        self.service.log_label_change("document", "d-1", None, "confidential", "admin-b")
        time.sleep(0.01)
        self.service.log_label_change("user", "u-1", "restricted", "top_secret", "admin-a")
        time.sleep(0.01)
        self.service.log_access_denial("analyst-1", "doc-99", "insufficient_clearance")

    def test_returns_reverse_chronological_order(self):
        results = self.service.query_audit_log()
        assert len(results) == 4
        for i in range(len(results) - 1):
            assert results[i]["changed_at"] >= results[i + 1]["changed_at"]

    def test_filter_by_entity_type(self):
        results = self.service.query_audit_log(entity_type="matter")
        assert len(results) == 1
        assert results[0]["entity_id"] == "m-1"

    def test_filter_by_entity_type_access_denied(self):
        results = self.service.query_audit_log(entity_type="access_denied")
        assert len(results) == 1
        assert results[0]["entity_id"] == "doc-99"

    def test_filter_by_entity_id(self):
        results = self.service.query_audit_log(entity_id="d-1")
        assert len(results) == 1
        assert results[0]["entity_type"] == "document"

    def test_filter_by_changed_by(self):
        results = self.service.query_audit_log(changed_by="admin-a")
        assert len(results) == 2

    def test_filter_by_date_range(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        results = self.service.query_audit_log(date_from=past, date_to=now)
        assert len(results) == 4

    def test_filter_by_future_date_returns_empty(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        results = self.service.query_audit_log(date_from=future)
        assert len(results) == 0

    def test_limit_and_offset(self):
        results = self.service.query_audit_log(limit=2, offset=0)
        assert len(results) == 2

        results_page2 = self.service.query_audit_log(limit=2, offset=2)
        assert len(results_page2) == 2

    def test_combined_filters(self):
        results = self.service.query_audit_log(
            entity_type="matter", changed_by="admin-a"
        )
        assert len(results) == 1
        assert results[0]["entity_id"] == "m-1"

    def test_empty_log_returns_empty_list(self):
        empty_service = AuditService()
        results = empty_service.query_audit_log()
        assert results == []
