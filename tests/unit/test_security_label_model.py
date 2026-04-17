"""Unit tests for SecurityLabel model and access control data models."""

from src.models.access_control import (
    AccessDecision,
    LabelAuditEntry,
    PlatformUser,
    ResourceContext,
    SecurityLabel,
    UserContext,
)


class TestSecurityLabel:
    def test_has_four_members(self):
        assert len(SecurityLabel) == 4

    def test_correct_values(self):
        assert SecurityLabel.PUBLIC == 0
        assert SecurityLabel.RESTRICTED == 1
        assert SecurityLabel.CONFIDENTIAL == 2
        assert SecurityLabel.TOP_SECRET == 3

    def test_ordering_public_lt_restricted(self):
        assert SecurityLabel.PUBLIC < SecurityLabel.RESTRICTED

    def test_ordering_restricted_lt_confidential(self):
        assert SecurityLabel.RESTRICTED < SecurityLabel.CONFIDENTIAL

    def test_ordering_confidential_lt_top_secret(self):
        assert SecurityLabel.CONFIDENTIAL < SecurityLabel.TOP_SECRET

    def test_full_ordering_chain(self):
        labels = [SecurityLabel.TOP_SECRET, SecurityLabel.PUBLIC, SecurityLabel.CONFIDENTIAL, SecurityLabel.RESTRICTED]
        sorted_labels = sorted(labels)
        assert sorted_labels == [
            SecurityLabel.PUBLIC,
            SecurityLabel.RESTRICTED,
            SecurityLabel.CONFIDENTIAL,
            SecurityLabel.TOP_SECRET,
        ]


class TestAccessDecision:
    def test_allowed_decision(self):
        d = AccessDecision(allowed=True, reason="clearance_sufficient")
        assert d.allowed is True
        assert d.reason == "clearance_sufficient"

    def test_denied_decision(self):
        d = AccessDecision(allowed=False, reason="insufficient_clearance")
        assert d.allowed is False


class TestUserContext:
    def test_defaults(self):
        u = UserContext(
            user_id="u-1",
            username="analyst1",
            clearance_level=SecurityLabel.RESTRICTED,
            role="analyst",
        )
        assert u.groups == []

    def test_with_groups(self):
        u = UserContext(
            user_id="u-1",
            username="analyst1",
            clearance_level=SecurityLabel.CONFIDENTIAL,
            role="analyst",
            groups=["team-a", "team-b"],
        )
        assert u.groups == ["team-a", "team-b"]


class TestResourceContext:
    def test_without_override(self):
        r = ResourceContext(
            document_id="d-1",
            case_id="c-1",
            effective_label=SecurityLabel.RESTRICTED,
        )
        assert r.security_label_override is None

    def test_with_override(self):
        r = ResourceContext(
            document_id="d-1",
            case_id="c-1",
            effective_label=SecurityLabel.CONFIDENTIAL,
            security_label_override=SecurityLabel.TOP_SECRET,
        )
        assert r.security_label_override == SecurityLabel.TOP_SECRET
