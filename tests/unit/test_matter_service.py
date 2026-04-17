"""Unit tests for MatterService with mocked database connections."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from contextlib import contextmanager

import pytest

from src.models.hierarchy import Matter, MatterStatus
from src.services.matter_service import MatterService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ORG_ID = "org-111"


def _make_row(
    matter_id="mat-123",
    org_id=_ORG_ID,
    matter_name="Test Matter",
    description="A test matter",
    status="created",
    matter_type="investigation",
    created_by="tester",
    created_at=None,
    last_activity=None,
    s3_prefix="orgs/org-111/matters/mat-123/",
    neptune_subgraph_label="Entity_mat-123",
    total_documents=0,
    total_entities=0,
    total_relationships=0,
    search_tier="standard",
    error_details=None,
):
    """Build a fake database row tuple matching the SELECT column order."""
    now = created_at or datetime.now(timezone.utc)
    return (
        matter_id,
        org_id,
        matter_name,
        description,
        status,
        matter_type,
        created_by,
        now,
        last_activity or now,
        s3_prefix,
        neptune_subgraph_label,
        total_documents,
        total_entities,
        total_relationships,
        search_tier,
        error_details,
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
    return MatterService(mock_db)


# ---------------------------------------------------------------------------
# create_matter
# ---------------------------------------------------------------------------


class TestCreateMatter:
    def test_returns_matter_with_correct_fields(self, service, mock_cursor):
        m = service.create_matter(_ORG_ID, "Investigation Alpha", "Desc")

        assert m.__class__.__name__ == "Matter"
        assert m.matter_name == "Investigation Alpha"
        assert m.description == "Desc"
        assert m.org_id == _ORG_ID
        assert m.status == MatterStatus.CREATED
        assert m.matter_type == "investigation"
        assert m.s3_prefix == f"orgs/{_ORG_ID}/matters/{m.matter_id}/"
        assert m.neptune_subgraph_label == f"Entity_{m.matter_id}"
        assert m.total_documents == 0
        assert m.total_entities == 0
        assert m.total_relationships == 0
        assert m.created_at is not None
        assert m.last_activity is not None

    def test_inserts_into_aurora(self, service, mock_cursor):
        service.create_matter(_ORG_ID, "Topic", "Desc")
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO matters" in sql

    def test_strips_whitespace(self, service):
        m = service.create_matter(_ORG_ID, "  Topic  ", "  Desc  ")
        assert m.matter_name == "Topic"
        assert m.description == "Desc"

    def test_custom_matter_type(self, service):
        m = service.create_matter(_ORG_ID, "Review", "Desc", matter_type="contract_review")
        assert m.matter_type == "contract_review"

    def test_custom_created_by(self, service):
        m = service.create_matter(_ORG_ID, "Review", "Desc", created_by="analyst@co.com")
        assert m.created_by == "analyst@co.com"

    def test_missing_matter_name_raises(self, service):
        with pytest.raises(ValueError, match="matter_name is required"):
            service.create_matter(_ORG_ID, "", "desc")

    def test_none_matter_name_raises(self, service):
        with pytest.raises(ValueError, match="matter_name is required"):
            service.create_matter(_ORG_ID, None, "desc")

    def test_whitespace_only_matter_name_raises(self, service):
        with pytest.raises(ValueError, match="matter_name is required"):
            service.create_matter(_ORG_ID, "   ", "desc")

    def test_missing_description_raises(self, service):
        with pytest.raises(ValueError, match="description is required"):
            service.create_matter(_ORG_ID, "topic", "")

    def test_none_description_raises(self, service):
        with pytest.raises(ValueError, match="description is required"):
            service.create_matter(_ORG_ID, "topic", None)

    def test_matter_id_is_valid_uuid(self, service):
        import uuid
        m = service.create_matter(_ORG_ID, "Topic", "Desc")
        uuid.UUID(m.matter_id)  # raises if not valid


# ---------------------------------------------------------------------------
# get_matter
# ---------------------------------------------------------------------------


class TestGetMatter:
    def test_returns_matter(self, service, mock_cursor):
        m = service.get_matter("mat-123", _ORG_ID)
        assert m.matter_id == "mat-123"
        assert m.matter_name == "Test Matter"

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Matter not found"):
            service.get_matter("nonexistent", _ORG_ID)

    def test_query_includes_org_id_filter(self, service, mock_cursor):
        service.get_matter("mat-123", _ORG_ID)
        sql = mock_cursor.execute.call_args[0][0]
        assert "org_id = %s" in sql


# ---------------------------------------------------------------------------
# list_matters
# ---------------------------------------------------------------------------


class TestListMatters:
    def test_returns_list(self, service, mock_cursor):
        result = service.list_matters(_ORG_ID)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].matter_id == "mat-123"

    def test_empty_list(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = service.list_matters(_ORG_ID)
        assert result == []

    def test_filter_by_status(self, service, mock_cursor):
        service.list_matters(_ORG_ID, status="archived")
        sql = mock_cursor.execute.call_args[0][0]
        assert "status = %s" in sql

    def test_query_always_includes_org_id(self, service, mock_cursor):
        service.list_matters(_ORG_ID)
        sql = mock_cursor.execute.call_args[0][0]
        assert "org_id = %s" in sql


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    def test_valid_status_enum(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("mat-123",), _make_row(status="ingesting")]
        m = service.update_status("mat-123", _ORG_ID, MatterStatus.INGESTING)
        assert m.__class__.__name__ == "Matter"

    def test_valid_status_string(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("mat-123",), _make_row(status="indexed")]
        m = service.update_status("mat-123", _ORG_ID, "indexed")
        assert m.__class__.__name__ == "Matter"

    def test_invalid_status_string_raises(self, service):
        with pytest.raises(ValueError, match="Invalid status"):
            service.update_status("mat-123", _ORG_ID, "bogus")

    def test_invalid_status_type_raises(self, service):
        with pytest.raises(ValueError, match="Invalid status"):
            service.update_status("mat-123", _ORG_ID, 42)

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Matter not found"):
            service.update_status("nonexistent", _ORG_ID, MatterStatus.INGESTING)

    def test_error_details_passed(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("mat-123",), _make_row(status="error", error_details="boom")]
        service.update_status("mat-123", _ORG_ID, MatterStatus.ERROR, error_details="boom")
        sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "UPDATE matters" in sql

    def test_all_valid_statuses_accepted(self, service, mock_cursor):
        for s in MatterStatus:
            mock_cursor.fetchone.side_effect = [("mat-123",), _make_row(status=s.value)]
            m = service.update_status("mat-123", _ORG_ID, s)
            assert m is not None

    def test_update_query_includes_org_id(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("mat-123",), _make_row(status="ingesting")]
        service.update_status("mat-123", _ORG_ID, MatterStatus.INGESTING)
        sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "org_id = %s" in sql


# ---------------------------------------------------------------------------
# delete_matter
# ---------------------------------------------------------------------------


class TestDeleteMatter:
    def test_deletes_aurora_record(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row()
        service.delete_matter("mat-123", _ORG_ID)

        delete_call = mock_cursor.execute.call_args_list[-1]
        assert "DELETE FROM matters" in delete_call[0][0]

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Matter not found"):
            service.delete_matter("nonexistent", _ORG_ID)

    def test_delete_query_includes_org_id(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row()
        service.delete_matter("mat-123", _ORG_ID)

        delete_call = mock_cursor.execute.call_args_list[-1]
        assert "org_id = %s" in delete_call[0][0]


# ---------------------------------------------------------------------------
# get_aggregated_counts
# ---------------------------------------------------------------------------


class TestGetAggregatedCounts:
    def test_returns_summed_counts(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (10, 50, 30)
        result = service.get_aggregated_counts("mat-123", _ORG_ID)

        assert result == {
            "total_documents": 10,
            "total_entities": 50,
            "total_relationships": 30,
        }

    def test_returns_zeros_when_no_promoted_collections(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (0, 0, 0)
        result = service.get_aggregated_counts("mat-123", _ORG_ID)

        assert result["total_documents"] == 0
        assert result["total_entities"] == 0
        assert result["total_relationships"] == 0

    def test_query_filters_by_promoted_status(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (0, 0, 0)
        service.get_aggregated_counts("mat-123", _ORG_ID)

        sql = mock_cursor.execute.call_args[0][0]
        assert "status = 'promoted'" in sql

    def test_query_includes_org_id_filter(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = (0, 0, 0)
        service.get_aggregated_counts("mat-123", _ORG_ID)

        sql = mock_cursor.execute.call_args[0][0]
        assert "org_id = %s" in sql
