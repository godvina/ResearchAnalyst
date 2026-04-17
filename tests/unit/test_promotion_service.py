"""Unit tests for PromotionService with mocked ConnectionManager and NeptuneConnectionManager."""

from datetime import datetime, timezone
from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import pytest

from src.models.hierarchy import PromotionSnapshot
from src.services.promotion_service import PromotionService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ORG_ID = "org-111"
_MATTER_ID = "mat-222"
_COLLECTION_ID = "col-333"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collection_row(
    collection_id=_COLLECTION_ID,
    matter_id=_MATTER_ID,
    org_id=_ORG_ID,
    status="qa_review",
    entity_count=5,
    relationship_count=3,
):
    """Build a fake collection row matching the SELECT column order in promote_collection."""
    return (collection_id, matter_id, org_id, status, entity_count, relationship_count)


def _snapshot_row(
    snapshot_id="snap-001",
    collection_id=_COLLECTION_ID,
    matter_id=_MATTER_ID,
    entities_added=5,
    relationships_added=3,
    promoted_at=None,
    promoted_by="",
):
    now = promoted_at or datetime.now(timezone.utc)
    return (snapshot_id, collection_id, matter_id, entities_added, relationships_added, now, promoted_by)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_cursor():
    """Return a mock cursor."""
    cursor = MagicMock()
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
def mock_g():
    """Return a mock Gremlin traversal source with chainable methods."""
    g = MagicMock()
    # Make chainable: g.V().hasLabel().toList() etc.
    g.V.return_value = g
    g.hasLabel.return_value = g
    g.has.return_value = g
    g.toList.return_value = []
    g.addV.return_value = g
    g.property.return_value = g
    g.next.return_value = "new-node"
    g.outE.return_value = g
    g.inE.return_value = g
    g.inV.return_value = g
    g.outV.return_value = g
    g.addE.return_value = g
    g.to.return_value = g
    g.label.return_value = g
    g.values.return_value = g
    g.valueMap.return_value = g
    g.drop.return_value = g
    g.iterate.return_value = None
    g.E.return_value = g
    return g


@pytest.fixture()
def mock_neptune(mock_g):
    """Return a mock NeptuneConnectionManager whose traversal_source() yields *mock_g*."""
    neptune = MagicMock()

    @contextmanager
    def _ts_ctx():
        yield mock_g

    neptune.traversal_source = _ts_ctx
    return neptune


@pytest.fixture()
def service(mock_db, mock_neptune):
    return PromotionService(mock_db, mock_neptune)


# ---------------------------------------------------------------------------
# promote_collection
# ---------------------------------------------------------------------------


class TestPromoteCollection:
    def test_returns_promotion_snapshot(self, service, mock_cursor, mock_g):
        """Successful promotion returns a PromotionSnapshot."""
        mock_cursor.fetchone.return_value = _collection_row()
        # No staging nodes (empty graph)
        mock_g.toList.return_value = []

        result = service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        assert result.__class__.__name__ == "PromotionSnapshot"
        assert result.collection_id == _COLLECTION_ID
        assert result.matter_id == _MATTER_ID
        assert result.promoted_at is not None
        assert result.snapshot_id  # non-empty UUID

    def test_snapshot_id_is_valid_uuid(self, service, mock_cursor, mock_g):
        import uuid

        mock_cursor.fetchone.return_value = _collection_row()
        mock_g.toList.return_value = []

        result = service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)
        uuid.UUID(result.snapshot_id)  # raises if not valid

    def test_collection_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None

        with pytest.raises(KeyError, match="Collection not found"):
            service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

    def test_collection_not_in_qa_review_raises_value_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _collection_row(status="staging")

        with pytest.raises(ValueError, match="qa_review"):
            service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

    def test_already_promoted_raises_value_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _collection_row(status="promoted")

        with pytest.raises(ValueError, match="qa_review"):
            service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

    def test_updates_collection_status_to_promoted(self, service, mock_cursor, mock_g):
        mock_cursor.fetchone.return_value = _collection_row()
        mock_g.toList.return_value = []

        service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        # Find the UPDATE collections call
        update_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE collections" in str(c)
        ]
        assert len(update_calls) >= 1
        sql = update_calls[0][0][0]
        assert "status = 'promoted'" in sql

    def test_creates_promotion_snapshot_row(self, service, mock_cursor, mock_g):
        mock_cursor.fetchone.return_value = _collection_row()
        mock_g.toList.return_value = []

        service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO promotion_snapshots" in str(c)
        ]
        assert len(insert_calls) == 1

    def test_updates_matter_aggregated_counts(self, service, mock_cursor, mock_g):
        mock_cursor.fetchone.return_value = _collection_row()
        mock_g.toList.return_value = []

        service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        update_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE matters" in str(c)
        ]
        assert len(update_calls) >= 1

    def test_select_for_update_lock(self, service, mock_cursor, mock_g):
        mock_cursor.fetchone.return_value = _collection_row()
        mock_g.toList.return_value = []

        service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        first_call = mock_cursor.execute.call_args_list[0]
        sql = first_call[0][0]
        assert "FOR UPDATE" in sql

    def test_query_includes_org_id(self, service, mock_cursor, mock_g):
        mock_cursor.fetchone.return_value = _collection_row()
        mock_g.toList.return_value = []

        service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        first_call = mock_cursor.execute.call_args_list[0]
        sql = first_call[0][0]
        assert "org_id" in sql

    def test_empty_staging_graph_returns_zero_counts(self, service, mock_cursor, mock_g):
        mock_cursor.fetchone.return_value = _collection_row()
        mock_g.toList.return_value = []

        result = service.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        assert result.entities_added == 0
        assert result.relationships_added == 0

    def test_neptune_failure_leaves_collection_in_qa_review(self, mock_db, mock_cursor):
        """On Neptune failure, collection status should NOT be updated."""
        mock_cursor.fetchone.return_value = _collection_row()

        # Create a neptune mock that raises on traversal_source
        neptune = MagicMock()

        @contextmanager
        def _failing_ts():
            raise ConnectionError("Neptune unavailable")
            yield  # noqa: unreachable

        neptune.traversal_source = _failing_ts

        svc = PromotionService(mock_db, neptune)

        with pytest.raises(ConnectionError, match="Neptune unavailable"):
            svc.promote_collection(_MATTER_ID, _COLLECTION_ID, _ORG_ID)

        # Verify no UPDATE collections call was made (only the initial SELECT)
        update_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE collections" in str(c)
        ]
        assert len(update_calls) == 0


# ---------------------------------------------------------------------------
# get_promotion_snapshot
# ---------------------------------------------------------------------------


class TestGetPromotionSnapshot:
    def test_returns_snapshot(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _snapshot_row()

        result = service.get_promotion_snapshot(_COLLECTION_ID)

        assert result.__class__.__name__ == "PromotionSnapshot"
        assert result.snapshot_id == "snap-001"
        assert result.collection_id == _COLLECTION_ID
        assert result.matter_id == _MATTER_ID
        assert result.entities_added == 5
        assert result.relationships_added == 3
        assert result.promoted_at is not None

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None

        with pytest.raises(KeyError, match="Promotion snapshot not found"):
            service.get_promotion_snapshot("nonexistent")

    def test_promoted_by_defaults_to_empty(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _snapshot_row(promoted_by=None)

        result = service.get_promotion_snapshot(_COLLECTION_ID)
        assert result.promoted_by == ""

    def test_query_filters_by_collection_id(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _snapshot_row()

        service.get_promotion_snapshot(_COLLECTION_ID)

        sql = mock_cursor.execute.call_args[0][0]
        assert "collection_id = %s" in sql
