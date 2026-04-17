"""Unit tests for CaseFileService with mocked database connections."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest

from src.models.case_file import CaseFile, CaseFileStatus, SearchTier
from src.services.case_file_service import CaseFileService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_row(
    case_id="abc-123",
    topic_name="Ancient Aliens",
    description="Research topic",
    status="created",
    parent_case_id=None,
    s3_prefix="cases/abc-123/",
    neptune_subgraph_label="Entity_abc-123",
    document_count=0,
    entity_count=0,
    relationship_count=0,
    error_details=None,
    created_at=None,
    last_activity=None,
    search_tier="standard",
):
    """Build a fake database row tuple matching the SELECT column order."""
    now = created_at or datetime.now(timezone.utc)
    return (
        case_id,
        topic_name,
        description,
        status,
        parent_case_id,
        s3_prefix,
        neptune_subgraph_label,
        document_count,
        entity_count,
        relationship_count,
        error_details,
        now,
        last_activity or now,
        search_tier,
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
def mock_neptune():
    """Return a mock NeptuneConnectionManager."""
    neptune = MagicMock()
    g = MagicMock()
    # Chain: g.V().has_label(label).drop().iterate()
    g.V.return_value.has_label.return_value.drop.return_value.iterate.return_value = None

    @contextmanager
    def _traversal_ctx():
        yield g

    neptune.traversal_source = _traversal_ctx
    neptune._g = g  # expose for assertions
    return neptune


@pytest.fixture()
def service(mock_db, mock_neptune):
    return CaseFileService(mock_db, mock_neptune)


# ---------------------------------------------------------------------------
# create_case_file
# ---------------------------------------------------------------------------


class TestCreateCaseFile:
    def test_returns_case_file_with_correct_fields(self, service, mock_cursor):
        cf = service.create_case_file("Ancient Aliens", "Research topic")

        assert isinstance(cf, CaseFile)
        assert cf.topic_name == "Ancient Aliens"
        assert cf.description == "Research topic"
        assert cf.status == CaseFileStatus.CREATED
        assert cf.s3_prefix == f"cases/{cf.case_id}/"
        assert cf.neptune_subgraph_label == f"Entity_{cf.case_id}"
        assert cf.document_count == 0
        assert cf.entity_count == 0
        assert cf.relationship_count == 0
        assert cf.findings == []
        assert cf.parent_case_id is None
        assert cf.created_at is not None
        assert cf.last_activity is not None
        assert cf.search_tier == SearchTier.STANDARD

    def test_inserts_into_aurora(self, service, mock_cursor):
        service.create_case_file("Topic", "Desc")
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO case_files" in sql

    def test_strips_whitespace(self, service):
        cf = service.create_case_file("  Topic  ", "  Desc  ")
        assert cf.topic_name == "Topic"
        assert cf.description == "Desc"

    def test_with_parent_case_id(self, service):
        cf = service.create_case_file("Sub", "Drill-down", parent_case_id="parent-1")
        assert cf.parent_case_id == "parent-1"

    def test_missing_topic_name_raises(self, service):
        with pytest.raises(ValueError, match="topic_name is required"):
            service.create_case_file("", "desc")

    def test_none_topic_name_raises(self, service):
        with pytest.raises(ValueError, match="topic_name is required"):
            service.create_case_file(None, "desc")

    def test_whitespace_only_topic_name_raises(self, service):
        with pytest.raises(ValueError, match="topic_name is required"):
            service.create_case_file("   ", "desc")

    def test_missing_description_raises(self, service):
        with pytest.raises(ValueError, match="description is required"):
            service.create_case_file("topic", "")

    def test_none_description_raises(self, service):
        with pytest.raises(ValueError, match="description is required"):
            service.create_case_file("topic", None)

    def test_whitespace_only_description_raises(self, service):
        with pytest.raises(ValueError, match="description is required"):
            service.create_case_file("topic", "   ")

    def test_case_id_is_valid_uuid(self, service):
        import uuid

        cf = service.create_case_file("Topic", "Desc")
        uuid.UUID(cf.case_id)  # raises if not valid


# ---------------------------------------------------------------------------
# get_case_file
# ---------------------------------------------------------------------------


class TestGetCaseFile:
    def test_returns_case_file(self, service, mock_cursor):
        cf = service.get_case_file("abc-123")
        assert cf.case_id == "abc-123"
        assert cf.topic_name == "Ancient Aliens"

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Case file not found"):
            service.get_case_file("nonexistent")


# ---------------------------------------------------------------------------
# list_case_files
# ---------------------------------------------------------------------------


class TestListCaseFiles:
    def test_returns_list(self, service, mock_cursor):
        result = service.list_case_files()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].case_id == "abc-123"

    def test_empty_list(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = service.list_case_files()
        assert result == []

    def test_filter_by_status(self, service, mock_cursor):
        service.list_case_files(status="archived")
        sql = mock_cursor.execute.call_args[0][0]
        assert "status = %s" in sql

    def test_filter_by_topic_keyword(self, service, mock_cursor):
        service.list_case_files(topic_keyword="aliens")
        sql = mock_cursor.execute.call_args[0][0]
        assert "plainto_tsquery" in sql

    def test_filter_by_date_range(self, service, mock_cursor):
        now = datetime.now(timezone.utc)
        service.list_case_files(date_from=now, date_to=now)
        sql = mock_cursor.execute.call_args[0][0]
        assert "created_at >= %s" in sql
        assert "created_at <= %s" in sql

    def test_filter_by_entity_count_range(self, service, mock_cursor):
        service.list_case_files(entity_count_min=5, entity_count_max=100)
        sql = mock_cursor.execute.call_args[0][0]
        assert "entity_count >= %s" in sql
        assert "entity_count <= %s" in sql

    def test_multiple_filters_combined(self, service, mock_cursor):
        service.list_case_files(status="indexed", topic_keyword="aliens")
        sql = mock_cursor.execute.call_args[0][0]
        assert "status = %s" in sql
        assert "plainto_tsquery" in sql
        assert "AND" in sql


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    def test_valid_status_enum(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("abc-123",), _make_row(status="ingesting")]
        cf = service.update_status("abc-123", CaseFileStatus.INGESTING)
        assert isinstance(cf, CaseFile)

    def test_valid_status_string(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("abc-123",), _make_row(status="indexed")]
        cf = service.update_status("abc-123", "indexed")
        assert isinstance(cf, CaseFile)

    def test_invalid_status_string_raises(self, service):
        with pytest.raises(ValueError, match="Invalid status"):
            service.update_status("abc-123", "bogus")

    def test_invalid_status_type_raises(self, service):
        with pytest.raises(ValueError, match="Invalid status"):
            service.update_status("abc-123", 42)

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Case file not found"):
            service.update_status("nonexistent", CaseFileStatus.INGESTING)

    def test_error_details_passed(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("abc-123",), _make_row(status="error", error_details="boom")]
        service.update_status("abc-123", CaseFileStatus.ERROR, error_details="boom")
        params = mock_cursor.execute.call_args_list[0][0][1]
        assert params[1] == "boom"

    def test_all_valid_statuses_accepted(self, service, mock_cursor):
        for s in CaseFileStatus:
            mock_cursor.fetchone.side_effect = [("abc-123",), _make_row(status=s.value)]
            cf = service.update_status("abc-123", s)
            assert cf is not None


# ---------------------------------------------------------------------------
# archive_case_file
# ---------------------------------------------------------------------------


class TestArchiveCaseFile:
    def test_sets_status_to_archived(self, service, mock_cursor):
        mock_cursor.fetchone.side_effect = [("abc-123",), _make_row(status="archived")]
        cf = service.archive_case_file("abc-123")
        assert cf.status == CaseFileStatus.ARCHIVED

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Case file not found"):
            service.archive_case_file("nonexistent")


# ---------------------------------------------------------------------------
# delete_case_file
# ---------------------------------------------------------------------------


class TestDeleteCaseFile:
    @patch("src.services.case_file_service.delete_case_prefix")
    def test_deletes_all_resources(self, mock_s3_delete, service, mock_cursor, mock_neptune):
        mock_cursor.fetchone.return_value = _make_row()
        service.delete_case_file("abc-123")

        # Neptune subgraph dropped
        g = mock_neptune._g
        g.V.assert_called()
        g.V().has_label.assert_called_with("Entity_abc-123")

        # S3 prefix deleted
        mock_s3_delete.assert_called_once_with("abc-123")

        # Aurora record deleted
        delete_call = mock_cursor.execute.call_args_list[-1]
        assert "DELETE FROM case_files" in delete_call[0][0]

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Case file not found"):
            service.delete_case_file("nonexistent")


# ---------------------------------------------------------------------------
# Imports for cross-case graph tests
# ---------------------------------------------------------------------------

from src.models.case_file import CrossCaseGraph


# ---------------------------------------------------------------------------
# create_cross_case_graph
# ---------------------------------------------------------------------------


class TestCreateCrossCaseGraph:
    def test_returns_cross_case_graph_with_correct_fields(self, service, mock_cursor):
        ccg = service.create_cross_case_graph("Shared Entities", ["case-1", "case-2"])

        assert isinstance(ccg, CrossCaseGraph)
        assert ccg.name == "Shared Entities"
        assert ccg.linked_case_ids == ["case-1", "case-2"]
        assert ccg.neptune_subgraph_label == f"CrossCase_{ccg.graph_id}"
        assert ccg.status == "active"
        assert ccg.analyst_notes == ""
        assert ccg.created_at is not None

    def test_graph_id_is_valid_uuid(self, service, mock_cursor):
        import uuid

        ccg = service.create_cross_case_graph("Test", ["c1", "c2"])
        uuid.UUID(ccg.graph_id)  # raises if not valid

    def test_inserts_metadata_and_members_into_aurora(self, service, mock_cursor):
        service.create_cross_case_graph("Graph", ["c1", "c2", "c3"])

        # 1 metadata insert + 3 member inserts = 4 execute calls
        assert mock_cursor.execute.call_count == 4
        sql_calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
        assert "INSERT INTO cross_case_graphs" in sql_calls[0]
        assert all("INSERT INTO cross_case_graph_members" in s for s in sql_calls[1:])

    def test_strips_whitespace_from_name(self, service, mock_cursor):
        ccg = service.create_cross_case_graph("  Trimmed  ", ["c1", "c2"])
        assert ccg.name == "Trimmed"

    def test_missing_name_raises(self, service):
        with pytest.raises(ValueError, match="name is required"):
            service.create_cross_case_graph("", ["c1", "c2"])

    def test_none_name_raises(self, service):
        with pytest.raises(ValueError, match="name is required"):
            service.create_cross_case_graph(None, ["c1", "c2"])

    def test_whitespace_only_name_raises(self, service):
        with pytest.raises(ValueError, match="name is required"):
            service.create_cross_case_graph("   ", ["c1", "c2"])

    def test_fewer_than_two_case_ids_raises(self, service):
        with pytest.raises(ValueError, match="At least two case IDs"):
            service.create_cross_case_graph("Graph", ["only-one"])

    def test_empty_case_ids_raises(self, service):
        with pytest.raises(ValueError, match="At least two case IDs"):
            service.create_cross_case_graph("Graph", [])

    def test_none_case_ids_raises(self, service):
        with pytest.raises(ValueError, match="At least two case IDs"):
            service.create_cross_case_graph("Graph", None)


# ---------------------------------------------------------------------------
# get_cross_case_graph
# ---------------------------------------------------------------------------


def _make_ccg_row(
    graph_id="graph-1",
    name="Test Graph",
    neptune_subgraph_label="CrossCase_graph-1",
    analyst_notes="",
    status="active",
    created_at=None,
):
    """Build a fake cross_case_graphs row tuple."""
    now = created_at or datetime.now(timezone.utc)
    return (graph_id, name, neptune_subgraph_label, analyst_notes, status, now)


class TestGetCrossCaseGraph:
    def test_returns_cross_case_graph(self, service, mock_cursor):
        ccg_row = _make_ccg_row()
        member_rows = [("case-1",), ("case-2",)]
        mock_cursor.fetchone.return_value = ccg_row
        mock_cursor.fetchall.return_value = member_rows

        ccg = service.get_cross_case_graph("graph-1")

        assert isinstance(ccg, CrossCaseGraph)
        assert ccg.graph_id == "graph-1"
        assert ccg.name == "Test Graph"
        assert ccg.neptune_subgraph_label == "CrossCase_graph-1"
        assert ccg.linked_case_ids == ["case-1", "case-2"]
        assert ccg.status == "active"

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Cross-case graph not found"):
            service.get_cross_case_graph("nonexistent")


# ---------------------------------------------------------------------------
# update_cross_case_graph
# ---------------------------------------------------------------------------


class TestUpdateCrossCaseGraph:
    def _setup_existing_graph(self, mock_cursor, case_ids=None):
        """Configure mock to return an existing graph, then return it on re-fetch."""
        case_ids = case_ids or ["case-1", "case-2"]
        ccg_row = _make_ccg_row()
        member_rows = [(cid,) for cid in case_ids]

        # get_cross_case_graph is called twice: once to verify existence,
        # once to return the updated graph. Each call does fetchone + fetchall.
        mock_cursor.fetchone.side_effect = [ccg_row, ccg_row]
        mock_cursor.fetchall.side_effect = [member_rows, member_rows]

    def test_add_case_ids(self, service, mock_cursor, mock_neptune):
        updated_members = [("case-1",), ("case-2",), ("case-3",)]
        ccg_row = _make_ccg_row()
        mock_cursor.fetchone.side_effect = [ccg_row, ccg_row]
        mock_cursor.fetchall.side_effect = [
            [("case-1",), ("case-2",)],  # initial fetch
            updated_members,              # re-fetch after update
        ]

        ccg = service.update_cross_case_graph("graph-1", add_case_ids=["case-3"])

        assert isinstance(ccg, CrossCaseGraph)
        # Verify an INSERT was issued for the new member
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO cross_case_graph_members" in c[0][0]
        ]
        assert len(insert_calls) == 1
        assert insert_calls[0][0][1] == ("graph-1", "case-3")

    def test_remove_case_ids(self, service, mock_cursor, mock_neptune):
        ccg_row = _make_ccg_row()
        mock_cursor.fetchone.side_effect = [ccg_row, ccg_row]
        mock_cursor.fetchall.side_effect = [
            [("case-1",), ("case-2",), ("case-3",)],  # initial: 3 members
            [("case-1",), ("case-2",)],                 # after removal
        ]

        ccg = service.update_cross_case_graph("graph-1", remove_case_ids=["case-3"])

        assert isinstance(ccg, CrossCaseGraph)
        # Verify a DELETE was issued for the removed member
        delete_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "DELETE FROM cross_case_graph_members" in c[0][0]
        ]
        assert len(delete_calls) == 1
        assert delete_calls[0][0][1] == ("graph-1", "case-3")

    def test_update_drops_neptune_edges_for_removed_cases(self, service, mock_cursor, mock_neptune):
        ccg_row = _make_ccg_row()
        mock_cursor.fetchone.side_effect = [ccg_row, ccg_row]
        mock_cursor.fetchall.side_effect = [
            [("case-1",), ("case-2",), ("case-3",)],
            [("case-1",), ("case-2",)],
        ]

        service.update_cross_case_graph("graph-1", remove_case_ids=["case-3"])

        g = mock_neptune._g
        g.V.assert_called()

    def test_not_found_raises_key_error(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = None
        with pytest.raises(KeyError, match="Cross-case graph not found"):
            service.update_cross_case_graph("nonexistent", add_case_ids=["c1"])

    def test_update_below_minimum_raises(self, service, mock_cursor, mock_neptune):
        ccg_row = _make_ccg_row()
        mock_cursor.fetchone.side_effect = [ccg_row]
        mock_cursor.fetchall.side_effect = [
            [("case-1",), ("case-2",)],  # only 2 members
        ]

        with pytest.raises(ValueError, match="at least 2 case files"):
            service.update_cross_case_graph("graph-1", remove_case_ids=["case-1"])

    def test_add_and_remove_simultaneously(self, service, mock_cursor, mock_neptune):
        ccg_row = _make_ccg_row()
        mock_cursor.fetchone.side_effect = [ccg_row, ccg_row]
        mock_cursor.fetchall.side_effect = [
            [("case-1",), ("case-2",), ("case-3",)],
            [("case-1",), ("case-2",), ("case-4",)],
        ]

        ccg = service.update_cross_case_graph(
            "graph-1",
            add_case_ids=["case-4"],
            remove_case_ids=["case-3"],
        )

        assert isinstance(ccg, CrossCaseGraph)

    def test_add_already_existing_case_id_is_noop(self, service, mock_cursor, mock_neptune):
        ccg_row = _make_ccg_row()
        mock_cursor.fetchone.side_effect = [ccg_row, ccg_row]
        mock_cursor.fetchall.side_effect = [
            [("case-1",), ("case-2",)],
            [("case-1",), ("case-2",)],
        ]

        ccg = service.update_cross_case_graph("graph-1", add_case_ids=["case-1"])

        # No INSERT should be issued for an already-existing member
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO cross_case_graph_members" in c[0][0]
        ]
        assert len(insert_calls) == 0

    def test_remove_nonexistent_case_id_is_noop(self, service, mock_cursor, mock_neptune):
        ccg_row = _make_ccg_row()
        mock_cursor.fetchone.side_effect = [ccg_row, ccg_row]
        mock_cursor.fetchall.side_effect = [
            [("case-1",), ("case-2",)],
            [("case-1",), ("case-2",)],
        ]

        ccg = service.update_cross_case_graph("graph-1", remove_case_ids=["case-99"])

        # No DELETE should be issued for a non-member
        delete_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "DELETE FROM cross_case_graph_members" in c[0][0]
        ]
        assert len(delete_calls) == 0


# ---------------------------------------------------------------------------
# create_sub_case_file
# ---------------------------------------------------------------------------


class TestCreateSubCaseFile:
    """Tests for drill-down sub-case file creation (Requirements 4.1–4.4)."""

    def _setup_parent(self, mock_cursor, parent_id="parent-1"):
        """Configure mock to return a parent case file on get_case_file."""
        mock_cursor.fetchone.return_value = _make_row(
            case_id=parent_id,
            topic_name="Parent Topic",
            description="Parent desc",
            neptune_subgraph_label=f"Entity_{parent_id}",
        )

    def test_returns_sub_case_with_parent_link(self, service, mock_cursor, mock_neptune):
        """Sub-case file has parent_case_id set (Req 4.1, 4.4)."""
        self._setup_parent(mock_cursor)
        # element_map().to_list() returns empty — no nodes to copy
        g = mock_neptune._g
        g.V.return_value.has_label.return_value.element_map.return_value.to_list.return_value = []

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Drill-down",
            description="Focused investigation",
        )

        assert isinstance(sub, CaseFile)
        assert sub.parent_case_id == "parent-1"
        assert sub.topic_name == "Drill-down"
        assert sub.description == "Focused investigation"
        assert sub.status == CaseFileStatus.CREATED

    def test_sub_case_has_own_s3_prefix_and_neptune_label(self, service, mock_cursor, mock_neptune):
        """Sub-case gets its own S3 prefix and Neptune label (Req 4.3)."""
        self._setup_parent(mock_cursor)
        g = mock_neptune._g
        g.V.return_value.has_label.return_value.element_map.return_value.to_list.return_value = []

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Sub",
            description="Desc",
        )

        assert sub.s3_prefix == f"cases/{sub.case_id}/"
        assert sub.neptune_subgraph_label == f"Entity_{sub.case_id}"
        # Must differ from parent
        assert sub.case_id != "parent-1"

    def test_parent_not_found_raises_key_error(self, service, mock_cursor):
        """KeyError when parent case does not exist."""
        mock_cursor.fetchone.return_value = None

        with pytest.raises(KeyError, match="Case file not found"):
            service.create_sub_case_file(
                parent_case_id="nonexistent",
                topic_name="Sub",
                description="Desc",
            )

    def test_missing_topic_name_raises(self, service, mock_cursor):
        """Validation delegated to create_case_file."""
        self._setup_parent(mock_cursor)

        with pytest.raises(ValueError, match="topic_name is required"):
            service.create_sub_case_file(
                parent_case_id="parent-1",
                topic_name="",
                description="Desc",
            )

    def test_missing_description_raises(self, service, mock_cursor):
        self._setup_parent(mock_cursor)

        with pytest.raises(ValueError, match="description is required"):
            service.create_sub_case_file(
                parent_case_id="parent-1",
                topic_name="Sub",
                description="",
            )

    def test_copies_entity_nodes_from_parent(self, service, mock_cursor, mock_neptune):
        """Entity nodes from parent subgraph are copied to sub-case (Req 4.2)."""
        self._setup_parent(mock_cursor)
        g = mock_neptune._g

        # Simulate parent subgraph with 2 entity nodes
        fake_nodes = [
            {
                "entity_id": "ent-1",
                "entity_type": "person",
                "canonical_name": "Erich von Däniken",
                "occurrence_count": 5,
                "confidence": 0.9,
                "source_document_refs": '["doc-1"]',
                "case_file_id": "parent-1",
            },
            {
                "entity_id": "ent-2",
                "entity_type": "location",
                "canonical_name": "Nazca Lines",
                "occurrence_count": 3,
                "confidence": 0.85,
                "source_document_refs": '["doc-1"]',
                "case_file_id": "parent-1",
            },
        ]
        g.V.return_value.has_label.return_value.element_map.return_value.to_list.return_value = (
            fake_nodes
        )

        # Edge query returns empty
        (
            g.V.return_value.has_label.return_value
            .has.return_value.outE.return_value
            .as_.return_value.inV.return_value
            .has.return_value.select.return_value
            .element_map.return_value.to_list.return_value
        ) = []

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Nazca Investigation",
            description="Drill-down on Nazca entities",
        )

        # add_v should have been called for each node
        assert g.add_v.call_count == 2

    def test_copies_edges_between_copied_entities(self, service, mock_cursor, mock_neptune):
        """Relationship edges between copied entities are also copied (Req 4.2)."""
        self._setup_parent(mock_cursor)
        g = mock_neptune._g

        fake_nodes = [
            {
                "entity_id": "ent-1",
                "entity_type": "person",
                "canonical_name": "Entity A",
                "occurrence_count": 1,
                "confidence": 0.8,
                "source_document_refs": "[]",
                "case_file_id": "parent-1",
            },
        ]
        g.V.return_value.has_label.return_value.element_map.return_value.to_list.return_value = (
            fake_nodes
        )

        fake_edges = [
            {
                "OUT_V": "ent-1",
                "IN_V": "ent-1",
                "relationship_type": "thematic",
                "confidence": 0.7,
                "source_document_ref": "doc-1",
            },
        ]
        (
            g.V.return_value.has_label.return_value
            .has.return_value.outE.return_value
            .as_.return_value.inV.return_value
            .has.return_value.select.return_value
            .element_map.return_value.to_list.return_value
        ) = fake_edges

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Edge test",
            description="Desc",
        )

        # Verify that edge traversal was initiated (V() called for edge copy)
        assert g.V.call_count >= 2  # at least node fetch + edge fetch

    def test_no_nodes_skips_edge_copy(self, service, mock_cursor, mock_neptune):
        """When parent has no entities, no edges are queried."""
        self._setup_parent(mock_cursor)
        g = mock_neptune._g
        g.V.return_value.has_label.return_value.element_map.return_value.to_list.return_value = []

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Empty parent",
            description="Desc",
        )

        # add_v should not be called
        g.add_v.assert_not_called()

    def test_entity_names_filter_scopes_copy(self, service, mock_cursor, mock_neptune):
        """When entity_names is provided, only matching entities are copied."""
        self._setup_parent(mock_cursor)
        g = mock_neptune._g

        # has() is called with P.within when entity_names is provided
        filtered_traversal = (
            g.V.return_value.has_label.return_value.has.return_value
        )
        filtered_traversal.element_map.return_value.to_list.return_value = [
            {
                "entity_id": "ent-1",
                "entity_type": "person",
                "canonical_name": "Erich von Däniken",
                "occurrence_count": 5,
                "confidence": 0.9,
                "source_document_refs": "[]",
                "case_file_id": "parent-1",
            },
        ]

        # Edge query returns empty
        (
            g.V.return_value.has_label.return_value
            .has.return_value.outE.return_value
            .as_.return_value.inV.return_value
            .has.return_value.select.return_value
            .element_map.return_value.to_list.return_value
        ) = []

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Scoped drill-down",
            description="Only specific entities",
            entity_names=["Erich von Däniken"],
        )

        assert sub.parent_case_id == "parent-1"
        # has() was called with the canonical_name filter
        g.V.return_value.has_label.return_value.has.assert_called()

    def test_pattern_id_accepted(self, service, mock_cursor, mock_neptune):
        """pattern_id parameter is accepted without error."""
        self._setup_parent(mock_cursor)
        g = mock_neptune._g
        g.V.return_value.has_label.return_value.element_map.return_value.to_list.return_value = []

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Pattern drill-down",
            description="From pattern",
            pattern_id="pattern-42",
        )

        assert sub.parent_case_id == "parent-1"

    def test_sub_case_can_be_retrieved(self, service, mock_cursor, mock_neptune):
        """Sub-case file is a regular CaseFile usable with standard pipeline (Req 4.3)."""
        self._setup_parent(mock_cursor)
        g = mock_neptune._g
        g.V.return_value.has_label.return_value.element_map.return_value.to_list.return_value = []

        sub = service.create_sub_case_file(
            parent_case_id="parent-1",
            topic_name="Sub",
            description="Desc",
        )

        # The returned object is a standard CaseFile — it can ingest data
        # through the normal pipeline since it has its own s3_prefix and
        # neptune_subgraph_label.
        assert sub.s3_prefix.startswith("cases/")
        assert sub.neptune_subgraph_label.startswith("Entity_")
        assert sub.document_count == 0  # ready for ingestion


# ---------------------------------------------------------------------------
# search_tier on create
# ---------------------------------------------------------------------------


class TestCreateCaseFileSearchTier:
    def test_default_search_tier_is_standard(self, service, mock_cursor):
        cf = service.create_case_file("Topic", "Desc")
        assert cf.search_tier == SearchTier.STANDARD

    def test_explicit_standard_tier(self, service, mock_cursor):
        cf = service.create_case_file("Topic", "Desc", search_tier="standard")
        assert cf.search_tier == SearchTier.STANDARD

    def test_enterprise_tier(self, service, mock_cursor):
        cf = service.create_case_file("Topic", "Desc", search_tier="enterprise")
        assert cf.search_tier == SearchTier.ENTERPRISE

    def test_none_search_tier_defaults_to_standard(self, service, mock_cursor):
        cf = service.create_case_file("Topic", "Desc", search_tier=None)
        assert cf.search_tier == SearchTier.STANDARD

    def test_invalid_search_tier_raises(self, service):
        with pytest.raises(ValueError, match="Invalid search_tier"):
            service.create_case_file("Topic", "Desc", search_tier="premium")

    def test_search_tier_persisted_in_insert(self, service, mock_cursor):
        service.create_case_file("Topic", "Desc", search_tier="enterprise")
        sql = mock_cursor.execute.call_args[0][0]
        assert "search_tier" in sql
        params = mock_cursor.execute.call_args[0][1]
        assert "enterprise" in params


# ---------------------------------------------------------------------------
# search_tier immutability
# ---------------------------------------------------------------------------


class TestSearchTierImmutability:
    def test_update_search_tier_raises(self, service):
        with pytest.raises(ValueError, match="TIER_IMMUTABLE"):
            service.update_search_tier("abc-123", "enterprise")

    def test_update_search_tier_raises_same_value(self, service):
        with pytest.raises(ValueError, match="TIER_IMMUTABLE"):
            service.update_search_tier("abc-123", "standard")

    def test_update_status_with_search_tier_kwarg_raises(self, service, mock_cursor):
        with pytest.raises(ValueError, match="TIER_IMMUTABLE"):
            service.update_status("abc-123", CaseFileStatus.INGESTING, search_tier="enterprise")


# ---------------------------------------------------------------------------
# search_tier read from DB
# ---------------------------------------------------------------------------


class TestSearchTierRead:
    def test_get_case_file_reads_search_tier(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(search_tier="enterprise")
        cf = service.get_case_file("abc-123")
        assert cf.search_tier == SearchTier.ENTERPRISE

    def test_get_case_file_defaults_missing_tier(self, service, mock_cursor):
        mock_cursor.fetchone.return_value = _make_row(search_tier=None)
        cf = service.get_case_file("abc-123")
        assert cf.search_tier == SearchTier.STANDARD

    def test_list_case_files_reads_search_tier(self, service, mock_cursor):
        mock_cursor.fetchall.return_value = [
            _make_row(case_id="c1", search_tier="standard"),
            _make_row(case_id="c2", search_tier="enterprise"),
        ]
        results = service.list_case_files()
        assert results[0].search_tier == SearchTier.STANDARD
        assert results[1].search_tier == SearchTier.ENTERPRISE
