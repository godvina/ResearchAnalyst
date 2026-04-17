"""Unit tests for CollectionService with mocked database connections."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest

from src.models.hierarchy import Collection, CollectionStatus
from src.services.collection_service import CollectionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ORG_ID = "org-111"
_MATTER_ID = "mat-222"


def _make_row(
    collection_id="col-333",
    matter_id=_MATTER_ID,
    org_id=_ORG_ID,
    collection_name="Test Collection",
    source_description="Test source",
    status="staging",
    document_count=0,
    entity_count=0,
    relationship_count=0,
    uploaded_by="tester",
    uploaded_at=None,
    promoted_at=None,
    chain_of_custody=None,
    s3_prefix="orgs/org-111/matters/mat-222/collections/col-333/",
):
    """Build a fake database row tuple matching the SELECT column order."""
    now = uploaded_at or datetime.now(timezone.utc)
    return (
        collection_id,
        matter_id,
        org_id,
        collection_name,
        source_description,
        status,
        document_count,
        entity_count,
        relationship_count,
        uploaded_by,
        now,
        promoted_at,
        chain_of_custody or [],
        s3_prefix,
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
    return CollectionService(mock_db)


# ---------------------------------------------------------------------------
# create_collection
# ---------------------------------------------------------------------------


class TestCreateCollection:
    def test_returns_collection_with_correct_fields(self, service, mock_cursor):
        c = service.create_collection(_MATTER_ID, _ORG_ID, "Batch 1", "FBI docs")

        assert c.__class__.__name__ == "Collection"
        assert c.collection_name == "Batch 1"
        assert c.source_description == "FBI docs"
        assert c.org_id == _ORG_ID
        assert c.matter_id == _MATTER_ID
        assert c.status == CollectionStatus.STAGING
        assert c.document_count == 0
        assert c.entity_count == 0
        assert c.relationship_count == 0
        assert c.uploaded_at is not None

    def test_s3_prefix_uses_hierarchy_path(self, service):
        c = service.create_collection(_MATTER_ID, _ORG_ID, "Batch 1")
        expected = f"orgs/{_ORG_ID}/matters/{_MATTER_ID}/collections/{c.collection_id}/"
        assert c.s3_prefix == expected

    def test_inserts_into_aurora(self, service, mock_cursor):
        service.create_collection(_MATTER_ID, _ORG_ID, "Batch 1")
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO collections" in sql

    def test_strips_whitespace_from_name(self, service):
        c = service.create_collection(_MATTER_ID, _ORG_ID, "  Batch 1  ")
        assert c.collection_name == "Batch 1"

    def test_custom_uploaded_by(self, service):
        c = service.create_collection(
            _MATTER_ID, _ORG_ID, "Batch 1", uploaded_by="analyst@co.com"
        )
        assert c.uploaded_by == "analyst@co.com"

    def test_missing_collection_name_raises(self, service):
        with pytest.raises(ValueError, match="collection_name is required"):
            service.create_collection(_MATTER_ID, _ORG_ID, "")

    def test_none_collection_name_raises(self, service):
        with pytest.raises(ValueError, match="collection_name is required"):
            service.create_collection(_MATTER_ID, _ORG_ID, None)

    def test_whitespace_only_name_raises(self, service):
        with pytest.raises(ValueError, match="collection_name is required"):
            service.create_collection(_MATTER_ID, _ORG_ID, "   ")

    def test_collection_id_is_valid_uuid(self, service):
        import uuid

        c = service.create_collection(_MATTER_ID, _ORG_ID, "Batch 1")
        uuid.UUID(c.collection_id)  # raises if not valid


# ---------------------------------------------------------------------------
# get_collection
# ---------------------------------------------------------------------------


class TestGetCollection:
    def test_returns_collection(self, service, mock_cursor):
        c = service.get_collection("col-333", _ORG_ID)
        assert c.collection_id == "col-333"
        assert c.collection_name == "Test Collection"

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Collection not found"):
            service.get_collection("nonexistent", _ORG_ID)

    def test_query_includes_org_id_filter(self, service, mock_cursor):
        service.get_collection("col-333", _ORG_ID)
        sql = mock_cursor.execute.call_args[0][0]
        assert "org_id = %s" in sql


# ---------------------------------------------------------------------------
# list_collections
# ---------------------------------------------------------------------------


class TestListCollections:
    def test_returns_list(self, service, mock_cursor):
        result = service.list_collections(_MATTER_ID, _ORG_ID)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].collection_id == "col-333"

    def test_empty_list(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = service.list_collections(_MATTER_ID, _ORG_ID)
        assert result == []

    def test_query_includes_org_id_filter(self, service, mock_cursor):
        service.list_collections(_MATTER_ID, _ORG_ID)
        sql = mock_cursor.execute.call_args[0][0]
        assert "org_id = %s" in sql

    def test_query_includes_matter_id_filter(self, service, mock_cursor):
        service.list_collections(_MATTER_ID, _ORG_ID)
        sql = mock_cursor.execute.call_args[0][0]
        assert "matter_id = %s" in sql


# ---------------------------------------------------------------------------
# update_status — valid transitions
# ---------------------------------------------------------------------------


class TestUpdateStatusValid:
    def _setup_transition(self, mock_cursor, from_status, to_status):
        """Configure mock to return current status, then RETURNING, then updated row."""
        mock_cursor.fetchone.side_effect = [
            _make_row(status=from_status),       # get_collection (current)
            ("col-333",),                         # UPDATE RETURNING
            _make_row(status=to_status),          # get_collection (after update)
        ]

    def test_staging_to_processing(self, service, mock_cursor):
        self._setup_transition(mock_cursor, "staging", "processing")
        c = service.update_status("col-333", _ORG_ID, CollectionStatus.PROCESSING)
        assert c.__class__.__name__ == "Collection"

    def test_processing_to_qa_review(self, service, mock_cursor):
        self._setup_transition(mock_cursor, "processing", "qa_review")
        c = service.update_status("col-333", _ORG_ID, CollectionStatus.QA_REVIEW)
        assert c.__class__.__name__ == "Collection"

    def test_qa_review_to_promoted(self, service, mock_cursor):
        self._setup_transition(mock_cursor, "qa_review", "promoted")
        c = service.update_status("col-333", _ORG_ID, CollectionStatus.PROMOTED)
        assert c.__class__.__name__ == "Collection"

    def test_qa_review_to_rejected(self, service, mock_cursor):
        self._setup_transition(mock_cursor, "qa_review", "rejected")
        c = service.update_status("col-333", _ORG_ID, CollectionStatus.REJECTED)
        assert c.__class__.__name__ == "Collection"

    def test_promoted_to_archived(self, service, mock_cursor):
        self._setup_transition(mock_cursor, "promoted", "archived")
        c = service.update_status("col-333", _ORG_ID, CollectionStatus.ARCHIVED)
        assert c.__class__.__name__ == "Collection"

    def test_rejected_to_archived(self, service, mock_cursor):
        self._setup_transition(mock_cursor, "rejected", "archived")
        c = service.update_status("col-333", _ORG_ID, CollectionStatus.ARCHIVED)
        assert c.__class__.__name__ == "Collection"

    def test_string_status_accepted(self, service, mock_cursor):
        self._setup_transition(mock_cursor, "staging", "processing")
        c = service.update_status("col-333", _ORG_ID, "processing")
        assert c.__class__.__name__ == "Collection"


# ---------------------------------------------------------------------------
# update_status — invalid transitions
# ---------------------------------------------------------------------------


class TestUpdateStatusInvalid:
    def test_staging_to_qa_review_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="staging")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.QA_REVIEW)

    def test_staging_to_promoted_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="staging")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.PROMOTED)

    def test_processing_to_promoted_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="processing")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.PROMOTED)

    def test_promoted_to_staging_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="promoted")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.STAGING)

    def test_promoted_to_processing_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="promoted")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.PROCESSING)

    def test_promoted_to_qa_review_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="promoted")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.QA_REVIEW)

    def test_archived_to_anything_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="archived")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.STAGING)

    def test_rejected_to_staging_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="rejected")
        with pytest.raises(ValueError, match="Invalid transition"):
            service.update_status("col-333", _ORG_ID, CollectionStatus.STAGING)

    def test_invalid_status_string_raises(self, service):
        with pytest.raises(ValueError, match="Invalid status"):
            service.update_status("col-333", _ORG_ID, "bogus")

    def test_invalid_status_type_raises(self, service):
        with pytest.raises(ValueError, match="Invalid status"):
            service.update_status("col-333", _ORG_ID, 42)

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Collection not found"):
            service.update_status("nonexistent", _ORG_ID, CollectionStatus.PROCESSING)


# ---------------------------------------------------------------------------
# reject_collection
# ---------------------------------------------------------------------------


class TestRejectCollection:
    def test_rejects_from_qa_review(self, service, mock_cursor):
        # get_collection (current), UPDATE RETURNING, get_collection (after)
        mock_cursor.fetchone.side_effect = [
            _make_row(status="qa_review"),   # reject_collection → get_collection
            _make_row(status="qa_review"),   # update_status → get_collection (current)
            ("col-333",),                     # UPDATE RETURNING
            _make_row(status="rejected"),     # update_status → get_collection (after)
        ]
        c = service.reject_collection("col-333", _ORG_ID)
        assert c.__class__.__name__ == "Collection"

    def test_reject_from_staging_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="staging")
        with pytest.raises(ValueError, match="Cannot reject"):
            service.reject_collection("col-333", _ORG_ID)

    def test_reject_from_processing_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="processing")
        with pytest.raises(ValueError, match="Cannot reject"):
            service.reject_collection("col-333", _ORG_ID)

    def test_reject_from_promoted_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="promoted")
        with pytest.raises(ValueError, match="Cannot reject"):
            service.reject_collection("col-333", _ORG_ID)

    def test_reject_from_archived_raises(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(status="archived")
        with pytest.raises(ValueError, match="Cannot reject"):
            service.reject_collection("col-333", _ORG_ID)

    def test_reject_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Collection not found"):
            service.reject_collection("nonexistent", _ORG_ID)
