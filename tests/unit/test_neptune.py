"""Unit tests for Neptune graph schema constants and connection helper."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.db.neptune import (
    BULK_LOAD_EDGES_COLUMNS,
    BULK_LOAD_NODES_COLUMNS,
    CROSS_CASE_LABEL_PREFIX,
    EDGE_CROSS_CASE_LINK,
    EDGE_PROP_CONFIDENCE,
    EDGE_PROP_CROSS_CASE_GRAPH_ID,
    EDGE_PROP_RELATIONSHIP_TYPE,
    EDGE_PROP_SOURCE_DOCUMENT_REF,
    EDGE_RELATED_TO,
    ENTITY_LABEL_PREFIX,
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_CASE_FILE_ID,
    NODE_PROP_COLLECTION_ID,
    NODE_PROP_CONFIDENCE,
    NODE_PROP_ENTITY_ID,
    NODE_PROP_ENTITY_TYPE,
    NODE_PROP_MATTER_ID,
    NODE_PROP_OCCURRENCE_COUNT,
    NODE_PROP_SOURCE_DOCUMENT_REFS,
    VALID_ENTITY_TYPES,
    VALID_RELATIONSHIP_TYPES,
    NeptuneConnectionManager,
    collection_staging_label,
    cross_case_label,
    entity_label,
)


@pytest.fixture(autouse=True)
def _enable_neptune():
    """Enable Neptune feature flag for all tests in this module."""
    import src.db.neptune as neptune_mod
    original = neptune_mod._NEPTUNE_ENABLED
    neptune_mod._NEPTUNE_ENABLED = True
    yield
    neptune_mod._NEPTUNE_ENABLED = original


# ---------------------------------------------------------------------------
# Label template tests
# ---------------------------------------------------------------------------


class TestEntityLabel:
    def test_basic_case_id(self):
        assert entity_label("abc-123") == "Entity_abc-123"

    def test_uuid_case_id(self):
        cid = "550e8400-e29b-41d4-a716-446655440000"
        assert entity_label(cid) == f"Entity_{cid}"

    def test_prefix_constant(self):
        assert entity_label("x").startswith(ENTITY_LABEL_PREFIX)


class TestCrossCaseLabel:
    def test_basic_graph_id(self):
        assert cross_case_label("graph-1") == "CrossCase_graph-1"

    def test_uuid_graph_id(self):
        gid = "660e8400-e29b-41d4-a716-446655440000"
        assert cross_case_label(gid) == f"CrossCase_{gid}"

    def test_prefix_constant(self):
        assert cross_case_label("y").startswith(CROSS_CASE_LABEL_PREFIX)


class TestCollectionStagingLabel:
    def test_basic_collection_id(self):
        assert collection_staging_label("col-123") == "Entity_col-123"

    def test_uuid_collection_id(self):
        cid = "770e8400-e29b-41d4-a716-446655440000"
        assert collection_staging_label(cid) == f"Entity_{cid}"

    def test_prefix_constant(self):
        assert collection_staging_label("z").startswith(ENTITY_LABEL_PREFIX)

    def test_same_format_as_entity_label(self):
        """Staging labels use the same Entity_ prefix as matter labels."""
        some_id = "test-id-42"
        assert collection_staging_label(some_id) == entity_label(some_id)


# ---------------------------------------------------------------------------
# Edge label tests
# ---------------------------------------------------------------------------


class TestEdgeLabels:
    def test_related_to(self):
        assert EDGE_RELATED_TO == "RELATED_TO"

    def test_cross_case_link(self):
        assert EDGE_CROSS_CASE_LINK == "CROSS_CASE_LINK"


# ---------------------------------------------------------------------------
# Property name tests
# ---------------------------------------------------------------------------


class TestNodeProperties:
    def test_all_node_properties_defined(self):
        expected = {
            "entity_id",
            "entity_type",
            "canonical_name",
            "occurrence_count",
            "confidence",
            "source_document_refs",
            "case_file_id",
            "matter_id",
            "collection_id",
        }
        actual = {
            NODE_PROP_ENTITY_ID,
            NODE_PROP_ENTITY_TYPE,
            NODE_PROP_CANONICAL_NAME,
            NODE_PROP_OCCURRENCE_COUNT,
            NODE_PROP_CONFIDENCE,
            NODE_PROP_SOURCE_DOCUMENT_REFS,
            NODE_PROP_CASE_FILE_ID,
            NODE_PROP_MATTER_ID,
            NODE_PROP_COLLECTION_ID,
        }
        assert actual == expected

    def test_backward_compat_case_file_id_preserved(self):
        """NODE_PROP_CASE_FILE_ID must remain for backward compatibility."""
        assert NODE_PROP_CASE_FILE_ID == "case_file_id"

    def test_matter_id_constant(self):
        assert NODE_PROP_MATTER_ID == "matter_id"

    def test_collection_id_constant(self):
        assert NODE_PROP_COLLECTION_ID == "collection_id"


class TestEdgeProperties:
    def test_all_edge_properties_defined(self):
        expected = {
            "relationship_type",
            "confidence",
            "source_document_ref",
            "cross_case_graph_id",
        }
        actual = {
            EDGE_PROP_RELATIONSHIP_TYPE,
            EDGE_PROP_CONFIDENCE,
            EDGE_PROP_SOURCE_DOCUMENT_REF,
            EDGE_PROP_CROSS_CASE_GRAPH_ID,
        }
        assert actual == expected


# ---------------------------------------------------------------------------
# Valid value sets
# ---------------------------------------------------------------------------


class TestValidValues:
    def test_entity_types_match_design(self):
        assert VALID_ENTITY_TYPES == frozenset(
            {"person", "location", "date", "artifact", "civilization", "theme", "event"}
        )

    def test_relationship_types_match_design(self):
        assert VALID_RELATIONSHIP_TYPES == frozenset(
            {"co-occurrence", "causal", "temporal", "geographic", "thematic"}
        )


# ---------------------------------------------------------------------------
# Bulk loader CSV column tests
# ---------------------------------------------------------------------------


class TestBulkLoadColumns:
    def test_nodes_csv_has_required_columns(self):
        assert BULK_LOAD_NODES_COLUMNS[0] == "~id"
        assert BULK_LOAD_NODES_COLUMNS[1] == "~label"
        # Remaining columns carry typed property names
        assert len(BULK_LOAD_NODES_COLUMNS) == 7

    def test_edges_csv_has_required_columns(self):
        assert BULK_LOAD_EDGES_COLUMNS[0] == "~id"
        assert BULK_LOAD_EDGES_COLUMNS[1] == "~from"
        assert BULK_LOAD_EDGES_COLUMNS[2] == "~to"
        assert BULK_LOAD_EDGES_COLUMNS[3] == "~label"
        assert len(BULK_LOAD_EDGES_COLUMNS) == 7

    def test_nodes_columns_include_typed_properties(self):
        col_str = ",".join(BULK_LOAD_NODES_COLUMNS)
        assert "entity_type:String" in col_str
        assert "canonical_name:String" in col_str
        assert "confidence:Float" in col_str
        assert "occurrence_count:Int" in col_str
        assert "case_file_id:String" in col_str

    def test_edges_columns_include_typed_properties(self):
        col_str = ",".join(BULK_LOAD_EDGES_COLUMNS)
        assert "relationship_type:String" in col_str
        assert "confidence:Float" in col_str
        assert "source_document_ref:String" in col_str


# ---------------------------------------------------------------------------
# Connection manager tests
# ---------------------------------------------------------------------------


class TestNeptuneConnectionManager:
    def test_ws_url_format(self):
        mgr = NeptuneConnectionManager(endpoint="my-cluster.neptune.amazonaws.com", port="8182")
        assert mgr.ws_url == "wss://my-cluster.neptune.amazonaws.com:8182/gremlin"

    def test_custom_port(self):
        mgr = NeptuneConnectionManager(endpoint="host", port="9999")
        assert ":9999/" in mgr.ws_url

    def test_env_fallback(self):
        with patch.dict(os.environ, {"NEPTUNE_ENDPOINT": "env-host", "NEPTUNE_PORT": "1234"}):
            mgr = NeptuneConnectionManager()
            assert mgr.ws_url == "wss://env-host:1234/gremlin"

    def test_missing_endpoint_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError, match="NEPTUNE_ENDPOINT"):
                NeptuneConnectionManager()

    def test_default_port_when_env_missing(self):
        with patch.dict(os.environ, {"NEPTUNE_ENDPOINT": "host"}, clear=True):
            mgr = NeptuneConnectionManager()
            assert ":8182/" in mgr.ws_url

    @patch("src.db.neptune.DriverRemoteConnection")
    def test_connection_context_manager(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn

        mgr = NeptuneConnectionManager(endpoint="host", port="8182")
        with mgr.connection() as conn:
            assert conn is mock_conn
        mock_conn.close.assert_called_once()

    @patch("src.db.neptune.traversal")
    @patch("src.db.neptune.DriverRemoteConnection")
    def test_traversal_source_context_manager(self, mock_conn_cls, mock_traversal):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_g = MagicMock()
        mock_traversal.return_value.with_remote.return_value = mock_g

        mgr = NeptuneConnectionManager(endpoint="host", port="8182")
        with mgr.traversal_source() as g:
            assert g is mock_g
        mock_conn.close.assert_called_once()
