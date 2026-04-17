"""Unit tests for OrganizationService with mocked database connections."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock
from contextlib import contextmanager

import pytest

from src.models.hierarchy import Organization
from src.services.organization_service import OrganizationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_row(
    org_id="org-123",
    org_name="Test Org",
    settings=None,
    created_at=None,
):
    """Build a fake database row tuple matching the SELECT column order."""
    now = created_at or datetime.now(timezone.utc)
    return (
        org_id,
        org_name,
        settings if settings is not None else {},
        now,
    )


@pytest.fixture()
def mock_cursor():
    """Return a mock cursor that can be used as a context manager."""
    cursor = MagicMock()
    cursor.fetchone.return_value = _make_row()
    cursor.fetchall.return_value = [_make_row()]
    return cursor


@pytest.fixture()
def mock_db(mock_cursor):
    """Return a mock ConnectionManager whose cursor() yields *mock_cursor*."""
    db = MagicMock()

    @contextmanager
    def _cursor_ctx():
        yield mock_cursor

    db.cursor = _cursor_ctx
    return db


@pytest.fixture()
def service(mock_db):
    return OrganizationService(mock_db)


# ---------------------------------------------------------------------------
# create_organization
# ---------------------------------------------------------------------------


class TestCreateOrganization:
    def test_returns_organization_with_correct_fields(self, service, mock_cursor):
        org = service.create_organization("Acme Corp")
        assert type(org).__name__ == "Organization"
        assert org.org_name == "Acme Corp"
        assert org.settings == {}
        assert org.org_id  # non-empty UUID string
        assert org.created_at is not None

    def test_inserts_into_aurora(self, service, mock_cursor):
        service.create_organization("Acme Corp")
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO organizations" in sql

    def test_strips_whitespace(self, service):
        org = service.create_organization("  Acme Corp  ")
        assert org.org_name == "Acme Corp"

    def test_with_settings(self, service):
        settings = {"display_labels": {"matter_label": "Case"}}
        org = service.create_organization("Acme Corp", settings=settings)
        assert org.settings == settings

    def test_missing_org_name_raises(self, service):
        with pytest.raises(ValueError, match="org_name is required"):
            service.create_organization("")

    def test_none_org_name_raises(self, service):
        with pytest.raises(ValueError, match="org_name is required"):
            service.create_organization(None)

    def test_whitespace_only_org_name_raises(self, service):
        with pytest.raises(ValueError, match="org_name is required"):
            service.create_organization("   ")

    def test_org_id_is_valid_uuid(self, service):
        import uuid
        org = service.create_organization("Acme Corp")
        uuid.UUID(org.org_id)  # raises if invalid

    def test_default_settings_is_empty_dict(self, service):
        org = service.create_organization("Acme Corp")
        assert org.settings == {}

    def test_settings_none_becomes_empty_dict(self, service):
        org = service.create_organization("Acme Corp", settings=None)
        assert org.settings == {}


# ---------------------------------------------------------------------------
# get_organization
# ---------------------------------------------------------------------------


class TestGetOrganization:
    def test_returns_organization(self, service, mock_cursor):
        org = service.get_organization("org-123")
        assert type(org).__name__ == "Organization"
        assert org.org_id == "org-123"

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Organization not found"):
            service.get_organization("nonexistent")


# ---------------------------------------------------------------------------
# list_organizations
# ---------------------------------------------------------------------------


class TestListOrganizations:
    def test_returns_list(self, service, mock_cursor):
        orgs = service.list_organizations()
        assert isinstance(orgs, list)
        assert len(orgs) == 1
        assert type(orgs[0]).__name__ == "Organization"

    def test_empty_list(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        orgs = service.list_organizations()
        assert orgs == []

    def test_multiple_organizations(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = [
            _make_row(org_id="org-1", org_name="Org A"),
            _make_row(org_id="org-2", org_name="Org B"),
        ]
        orgs = service.list_organizations()
        assert len(orgs) == 2
        assert orgs[0].org_id == "org-1"
        assert orgs[1].org_id == "org-2"


# ---------------------------------------------------------------------------
# update_settings
# ---------------------------------------------------------------------------


class TestUpdateSettings:
    def test_returns_updated_organization(self, service, mock_cursor):
        new_settings = {"modules_enabled": ["ai_briefing"]}
        mock_cursor.fetchone.return_value = _make_row(settings=new_settings)
        org = service.update_settings("org-123", new_settings)
        assert org.settings == new_settings

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Organization not found"):
            service.update_settings("nonexistent", {"key": "value"})

    def test_executes_update_sql(self, service, mock_cursor):
        service.update_settings("org-123", {"key": "value"})
        sql = mock_cursor.execute.call_args[0][0]
        assert "UPDATE organizations" in sql
        assert "RETURNING" in sql

    def test_complex_settings(self, service, mock_cursor):
        settings = {
            "default_pipeline_config": {"steps": ["parse", "embed"]},
            "display_labels": {"matter_label": "Investigation"},
            "modules_enabled": ["ai_briefing", "prosecutor"],
        }
        mock_cursor.fetchone.return_value = _make_row(settings=settings)
        org = service.update_settings("org-123", settings)
        assert org.settings == settings
