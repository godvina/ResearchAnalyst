"""Unit tests for LabelBasedProvider access policy."""

from src.models.access_control import SecurityLabel
from src.services.label_based_provider import LabelBasedProvider


class TestLabelBasedProvider:
    def setup_method(self):
        self.provider = LabelBasedProvider()

    def test_allows_when_clearance_equals_effective(self):
        decision = self.provider.check_access(
            user_context={"clearance_level": SecurityLabel.RESTRICTED, "groups": []},
            resource_context={"effective_label": SecurityLabel.RESTRICTED, "document_id": "d-1", "case_id": "c-1"},
        )
        assert decision.allowed is True
        assert decision.reason == "clearance_sufficient"

    def test_allows_when_clearance_exceeds_effective(self):
        decision = self.provider.check_access(
            user_context={"clearance_level": SecurityLabel.TOP_SECRET, "groups": []},
            resource_context={"effective_label": SecurityLabel.PUBLIC, "document_id": "d-1", "case_id": "c-1"},
        )
        assert decision.allowed is True
        assert decision.reason == "clearance_sufficient"

    def test_denies_when_clearance_below_effective(self):
        decision = self.provider.check_access(
            user_context={"clearance_level": SecurityLabel.PUBLIC, "groups": []},
            resource_context={"effective_label": SecurityLabel.CONFIDENTIAL, "document_id": "d-1", "case_id": "c-1"},
        )
        assert decision.allowed is False
        assert "public" in decision.reason
        assert "confidential" in decision.reason

    def test_denies_restricted_accessing_top_secret(self):
        decision = self.provider.check_access(
            user_context={"clearance_level": SecurityLabel.RESTRICTED, "groups": []},
            resource_context={"effective_label": SecurityLabel.TOP_SECRET, "document_id": "d-1", "case_id": "c-1"},
        )
        assert decision.allowed is False

    def test_ignores_groups_field(self):
        """Groups should have no effect on the access decision."""
        base_ctx = {"clearance_level": SecurityLabel.RESTRICTED}
        resource = {"effective_label": SecurityLabel.CONFIDENTIAL, "document_id": "d-1", "case_id": "c-1"}

        decision_no_groups = self.provider.check_access(
            user_context={**base_ctx, "groups": []},
            resource_context=resource,
        )
        decision_with_groups = self.provider.check_access(
            user_context={**base_ctx, "groups": ["admin", "super-users", "top-secret-team"]},
            resource_context=resource,
        )
        assert decision_no_groups.allowed == decision_with_groups.allowed
        assert decision_no_groups.reason == decision_with_groups.reason

    def test_ignores_groups_when_allowed(self):
        """Groups should not affect allowed decisions either."""
        base_ctx = {"clearance_level": SecurityLabel.TOP_SECRET}
        resource = {"effective_label": SecurityLabel.PUBLIC, "document_id": "d-1", "case_id": "c-1"}

        decision_no_groups = self.provider.check_access(
            user_context={**base_ctx, "groups": []},
            resource_context=resource,
        )
        decision_with_groups = self.provider.check_access(
            user_context={**base_ctx, "groups": ["vip", "classified"]},
            resource_context=resource,
        )
        assert decision_no_groups.allowed == decision_with_groups.allowed
        assert decision_no_groups.reason == decision_with_groups.reason

    def test_top_secret_can_access_all_levels(self):
        """Top secret clearance should access every label level."""
        for label in SecurityLabel:
            decision = self.provider.check_access(
                user_context={"clearance_level": SecurityLabel.TOP_SECRET, "groups": []},
                resource_context={"effective_label": label, "document_id": "d-1", "case_id": "c-1"},
            )
            assert decision.allowed is True

    def test_public_can_only_access_public(self):
        """Public clearance should only access public documents."""
        for label in SecurityLabel:
            decision = self.provider.check_access(
                user_context={"clearance_level": SecurityLabel.PUBLIC, "groups": []},
                resource_context={"effective_label": label, "document_id": "d-1", "case_id": "c-1"},
            )
            if label == SecurityLabel.PUBLIC:
                assert decision.allowed is True
            else:
                assert decision.allowed is False
