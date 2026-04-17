"""Unit tests for NeptuneGraphLoader with mocked dependencies."""

import csv
import io
from unittest.mock import MagicMock, call, patch

import pytest

from src.db.neptune import (
    BULK_LOAD_EDGES_COLUMNS,
    BULK_LOAD_NODES_COLUMNS,
    EDGE_PROP_CONFIDENCE,
    EDGE_PROP_RELATIONSHIP_TYPE,
    EDGE_PROP_SOURCE_DOCUMENT_REF,
    EDGE_RELATED_TO,
    NODE_PROP_CANONICAL_NAME,
    NODE_PROP_CASE_FILE_ID,
    NODE_PROP_CONFIDENCE,
    NODE_PROP_ENTITY_TYPE,
    NODE_PROP_OCCURRENCE_COUNT,
    NeptuneConnectionManager,
    entity_label,
)
from src.models.entity import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    RelationshipType,
)
from src.services.neptune_graph_loader import (
    LOAD_COMPLETED,
    LOAD_FAILED,
    NeptuneGraphLoader,
)


@pytest.fixture(autouse=True)
def _enable_neptune():
    """Enable Neptune feature flag for all tests in this module."""
    import src.services.neptune_graph_loader as ngl_mod
    import src.db.neptune as neptune_mod
    orig_ngl = ngl_mod._NEPTUNE_ENABLED
    orig_nep = neptune_mod._NEPTUNE_ENABLED
    ngl_mod._NEPTUNE_ENABLED = True
    neptune_mod._NEPTUNE_ENABLED = True
    yield
    ngl_mod._NEPTUNE_ENABLED = orig_ngl
    neptune_mod._NEPTUNE_ENABLED = orig_nep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-001"


def _make_entity(
    name: str = "Erich von Däniken",
    etype: EntityType = EntityType.PERSON,
    confidence: float = 0.9,
    occurrences: int = 3,
    refs: list[str] | None = None,
) -> ExtractedEntity:
    return ExtractedEntity(
        entity_type=etype,
        canonical_name=name,
        confidence=confidence,
        occurrences=occurrences,
        source_document_refs=refs or ["doc-1"],
    )


def _make_relationship(
    source: str = "Erich von Däniken",
    target: str = "Nazca Lines",
    rtype: RelationshipType = RelationshipType.THEMATIC,
    confidence: float = 0.85,
    doc_ref: str = "doc-1",
) -> ExtractedRelationship:
    return ExtractedRelationship(
        source_entity=source,
        target_entity=target,
        relationship_type=rtype,
        confidence=confidence,
        source_document_ref=doc_ref,
    )


@pytest.fixture
def conn_manager():
    return NeptuneConnectionManager(endpoint="test-host", port="8182")


@pytest.fixture
def mock_http():
    return MagicMock()


@pytest.fixture
def loader(conn_manager, mock_http):
    return NeptuneGraphLoader(
        connection_manager=conn_manager,
        http_client=mock_http,
        s3_bucket="test-bucket",
    )


# ---------------------------------------------------------------------------
# generate_nodes_csv
# ---------------------------------------------------------------------------


class TestGenerateNodesCsv:
    @patch("src.services.neptune_graph_loader.upload_file")
    def test_returns_s3_key(self, mock_upload, loader):
        mock_upload.return_value = "cases/case-001/bulk-load/abc_nodes.csv"
        entities = [_make_entity()]

        key = loader.generate_nodes_csv(CASE_ID, entities)

        assert key == "cases/case-001/bulk-load/abc_nodes.csv"
        mock_upload.assert_called_once()

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_csv_header_matches_schema(self, mock_upload, loader):
        mock_upload.return_value = "key"
        entities = [_make_entity()]

        loader.generate_nodes_csv(CASE_ID, entities)

        # Grab the CSV content passed to upload_file
        csv_content = mock_upload.call_args[0][3]  # 4th positional arg = content
        reader = csv.reader(io.StringIO(csv_content))
        header = next(reader)
        assert header == BULK_LOAD_NODES_COLUMNS

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_csv_row_values(self, mock_upload, loader):
        mock_upload.return_value = "key"
        ent = _make_entity(name="Nazca Lines", etype=EntityType.LOCATION, confidence=0.75, occurrences=5)

        loader.generate_nodes_csv(CASE_ID, [ent])

        csv_content = mock_upload.call_args[0][3]
        reader = csv.reader(io.StringIO(csv_content))
        next(reader)  # skip header
        row = next(reader)

        assert row[0] == f"{CASE_ID}_location_Nazca Lines"  # ~id
        assert row[1] == entity_label(CASE_ID)  # ~label
        assert row[2] == "location"  # entity_type
        assert row[3] == "Nazca Lines"  # canonical_name
        assert row[4] == "0.75"  # confidence
        assert row[5] == "5"  # occurrence_count
        assert row[6] == CASE_ID  # case_file_id

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_multiple_entities(self, mock_upload, loader):
        mock_upload.return_value = "key"
        entities = [
            _make_entity(name="A", etype=EntityType.PERSON),
            _make_entity(name="B", etype=EntityType.LOCATION),
        ]

        loader.generate_nodes_csv(CASE_ID, entities)

        csv_content = mock_upload.call_args[0][3]
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 data rows

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_empty_entities(self, mock_upload, loader):
        mock_upload.return_value = "key"

        loader.generate_nodes_csv(CASE_ID, [])

        csv_content = mock_upload.call_args[0][3]
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) == 1  # header only

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_uploads_to_bulk_load_prefix(self, mock_upload, loader):
        mock_upload.return_value = "key"

        loader.generate_nodes_csv(CASE_ID, [_make_entity()])

        args = mock_upload.call_args
        assert args[0][0] == CASE_ID
        assert args[0][1] == "bulk-load"
        assert args[0][2].endswith("_nodes.csv")


# ---------------------------------------------------------------------------
# generate_edges_csv
# ---------------------------------------------------------------------------


class TestGenerateEdgesCsv:
    @patch("src.services.neptune_graph_loader.upload_file")
    def test_returns_s3_key(self, mock_upload, loader):
        mock_upload.return_value = "cases/case-001/bulk-load/abc_edges.csv"
        ent_a = _make_entity(name="A", etype=EntityType.PERSON)
        ent_b = _make_entity(name="B", etype=EntityType.LOCATION)
        rel = _make_relationship(source="A", target="B")

        key = loader.generate_edges_csv(CASE_ID, [ent_a, ent_b], [rel])

        assert key == "cases/case-001/bulk-load/abc_edges.csv"

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_csv_header_matches_schema(self, mock_upload, loader):
        mock_upload.return_value = "key"
        rel = _make_relationship()

        loader.generate_edges_csv(CASE_ID, [_make_entity()], [rel])

        csv_content = mock_upload.call_args[0][3]
        reader = csv.reader(io.StringIO(csv_content))
        header = next(reader)
        assert header == BULK_LOAD_EDGES_COLUMNS

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_csv_row_resolves_entity_ids(self, mock_upload, loader):
        mock_upload.return_value = "key"
        ent_a = _make_entity(name="Erich von Däniken", etype=EntityType.PERSON)
        ent_b = _make_entity(name="Nazca Lines", etype=EntityType.LOCATION)
        rel = _make_relationship(
            source="Erich von Däniken",
            target="Nazca Lines",
            rtype=RelationshipType.THEMATIC,
            confidence=0.85,
            doc_ref="doc-1",
        )

        loader.generate_edges_csv(CASE_ID, [ent_a, ent_b], [rel])

        csv_content = mock_upload.call_args[0][3]
        reader = csv.reader(io.StringIO(csv_content))
        next(reader)  # skip header
        row = next(reader)

        assert row[1] == f"{CASE_ID}_person_Erich von Däniken"  # ~from
        assert row[2] == f"{CASE_ID}_location_Nazca Lines"  # ~to
        assert row[3] == EDGE_RELATED_TO  # ~label
        assert row[4] == "thematic"  # relationship_type
        assert row[5] == "0.85"  # confidence
        assert row[6] == "doc-1"  # source_document_ref

    @patch("src.services.neptune_graph_loader.upload_file")
    def test_uploads_to_bulk_load_prefix(self, mock_upload, loader):
        mock_upload.return_value = "key"

        loader.generate_edges_csv(CASE_ID, [], [])

        args = mock_upload.call_args
        assert args[0][0] == CASE_ID
        assert args[0][1] == "bulk-load"
        assert args[0][2].endswith("_edges.csv")


# ---------------------------------------------------------------------------
# bulk_load
# ---------------------------------------------------------------------------


class TestBulkLoad:
    def test_posts_to_loader_endpoint(self, loader, mock_http):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "200 OK",
            "payload": {"loadId": "load-123"},
        }
        mock_http.post.return_value = mock_response

        result = loader.bulk_load(
            "cases/c/bulk-load/nodes.csv",
            "cases/c/bulk-load/edges.csv",
            iam_role_arn="arn:aws:iam::123:role/NeptuneLoad",
            s3_bucket="test-bucket",
        )

        assert mock_http.post.call_count == 2
        assert "nodes" in result
        assert "edges" in result
        assert result["nodes"]["load_id"] == "load-123"

    def test_loader_url_derived_from_connection(self, loader, mock_http):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "200 OK",
            "payload": {"loadId": "x"},
        }
        mock_http.post.return_value = mock_response

        loader.bulk_load("n.csv", "e.csv", "arn:role", s3_bucket="b")

        url = mock_http.post.call_args_list[0][0][0]
        assert url == "https://test-host:8182/loader"

    def test_payload_contains_required_fields(self, loader, mock_http):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "200 OK",
            "payload": {"loadId": "x"},
        }
        mock_http.post.return_value = mock_response

        loader.bulk_load("nodes.csv", "edges.csv", "arn:role", s3_bucket="mybucket")

        payload = mock_http.post.call_args_list[0][1]["json"]
        assert payload["source"] == "s3://mybucket/nodes.csv"
        assert payload["format"] == "csv"
        assert payload["iamRoleArn"] == "arn:role"
        assert payload["failOnError"] == "FALSE"


# ---------------------------------------------------------------------------
# poll_bulk_load_status
# ---------------------------------------------------------------------------


class TestPollBulkLoadStatus:
    @patch("src.services.neptune_graph_loader.time.sleep", return_value=None)
    def test_returns_completed(self, _sleep, loader, mock_http):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "payload": {"overallStatus": {"status": LOAD_COMPLETED}},
        }
        mock_http.get.return_value = mock_response

        status = loader.poll_bulk_load_status("load-123")

        assert status == LOAD_COMPLETED

    @patch("src.services.neptune_graph_loader.time.sleep", return_value=None)
    def test_returns_failed(self, _sleep, loader, mock_http):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "payload": {"overallStatus": {"status": LOAD_FAILED}},
        }
        mock_http.get.return_value = mock_response

        status = loader.poll_bulk_load_status("load-456")

        assert status == LOAD_FAILED

    @patch("src.services.neptune_graph_loader.time.sleep", return_value=None)
    def test_polls_until_complete(self, _sleep, loader, mock_http):
        in_progress = MagicMock()
        in_progress.json.return_value = {
            "payload": {"overallStatus": {"status": "LOAD_IN_PROGRESS"}},
        }
        completed = MagicMock()
        completed.json.return_value = {
            "payload": {"overallStatus": {"status": LOAD_COMPLETED}},
        }
        mock_http.get.side_effect = [in_progress, in_progress, completed]

        status = loader.poll_bulk_load_status("load-789")

        assert status == LOAD_COMPLETED
        assert mock_http.get.call_count == 3

    @patch("src.services.neptune_graph_loader.time.sleep", return_value=None)
    @patch("src.services.neptune_graph_loader.MAX_POLL_ATTEMPTS", 2)
    def test_raises_timeout(self, _sleep, loader, mock_http):
        in_progress = MagicMock()
        in_progress.json.return_value = {
            "payload": {"overallStatus": {"status": "LOAD_IN_PROGRESS"}},
        }
        mock_http.get.return_value = in_progress

        with pytest.raises(TimeoutError, match="did not complete"):
            loader.poll_bulk_load_status("load-stuck")

    @patch("src.services.neptune_graph_loader.time.sleep", return_value=None)
    def test_polls_correct_url(self, _sleep, loader, mock_http):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "payload": {"overallStatus": {"status": LOAD_COMPLETED}},
        }
        mock_http.get.return_value = mock_response

        loader.poll_bulk_load_status("load-abc")

        url = mock_http.get.call_args[0][0]
        assert url == "https://test-host:8182/loader/load-abc"


# ---------------------------------------------------------------------------
# load_via_gremlin
# ---------------------------------------------------------------------------


class TestLoadViaGremlin:
    @patch.object(NeptuneConnectionManager, "traversal_source")
    def test_creates_nodes_and_edges(self, mock_ts, loader):
        mock_g = MagicMock()
        # Chain mock for addV
        mock_g.addV.return_value = mock_g
        mock_g.property.return_value = mock_g
        mock_g.next.return_value = None
        # Chain mock for V().addE()
        mock_g.V.return_value = mock_g
        mock_g.addE.return_value = mock_g
        mock_g.to.return_value = mock_g

        mock_ts.return_value.__enter__ = MagicMock(return_value=mock_g)
        mock_ts.return_value.__exit__ = MagicMock(return_value=False)

        entities = [
            _make_entity(name="A", etype=EntityType.PERSON),
            _make_entity(name="B", etype=EntityType.LOCATION),
        ]
        rels = [_make_relationship(source="A", target="B")]

        result = loader.load_via_gremlin(CASE_ID, entities, rels)

        assert result["nodes_created"] == 2
        assert result["edges_created"] == 1

    @patch.object(NeptuneConnectionManager, "traversal_source")
    def test_empty_inputs(self, mock_ts, loader):
        mock_g = MagicMock()
        mock_ts.return_value.__enter__ = MagicMock(return_value=mock_g)
        mock_ts.return_value.__exit__ = MagicMock(return_value=False)

        result = loader.load_via_gremlin(CASE_ID, [], [])

        assert result["nodes_created"] == 0
        assert result["edges_created"] == 0

    @patch.object(NeptuneConnectionManager, "traversal_source")
    def test_skips_edges_with_unknown_entities(self, mock_ts, loader):
        mock_g = MagicMock()
        mock_g.addV.return_value = mock_g
        mock_g.property.return_value = mock_g
        mock_g.next.return_value = None

        mock_ts.return_value.__enter__ = MagicMock(return_value=mock_g)
        mock_ts.return_value.__exit__ = MagicMock(return_value=False)

        entities = [_make_entity(name="A", etype=EntityType.PERSON)]
        # Relationship references entity "B" which is not in entities
        rels = [_make_relationship(source="A", target="B")]

        result = loader.load_via_gremlin(CASE_ID, entities, rels)

        assert result["nodes_created"] == 1
        assert result["edges_created"] == 0

    @patch.object(NeptuneConnectionManager, "traversal_source")
    def test_uses_correct_label(self, mock_ts, loader):
        mock_g = MagicMock()
        mock_g.addV.return_value = mock_g
        mock_g.property.return_value = mock_g
        mock_g.next.return_value = None

        mock_ts.return_value.__enter__ = MagicMock(return_value=mock_g)
        mock_ts.return_value.__exit__ = MagicMock(return_value=False)

        loader.load_via_gremlin(CASE_ID, [_make_entity()], [])

        mock_g.addV.assert_called_once_with(entity_label(CASE_ID))


# ---------------------------------------------------------------------------
# merge_duplicate_nodes
# ---------------------------------------------------------------------------


class TestMergeDuplicateNodes:
    @patch.object(NeptuneConnectionManager, "traversal_source")
    def test_no_merge_when_single_node(self, mock_ts, loader):
        mock_g = MagicMock()
        # V().hasLabel().has().has().toList() returns 1 node
        mock_g.V.return_value = mock_g
        mock_g.hasLabel.return_value = mock_g
        mock_g.has.return_value = mock_g
        mock_g.toList.return_value = ["node-1"]

        mock_ts.return_value.__enter__ = MagicMock(return_value=mock_g)
        mock_ts.return_value.__exit__ = MagicMock(return_value=False)

        loader.merge_duplicate_nodes(CASE_ID, "Erich von Däniken", "person")

        # Should not attempt to update or drop anything
        mock_g.drop.assert_not_called()

    @patch.object(NeptuneConnectionManager, "traversal_source")
    def test_no_merge_when_no_nodes(self, mock_ts, loader):
        mock_g = MagicMock()
        mock_g.V.return_value = mock_g
        mock_g.hasLabel.return_value = mock_g
        mock_g.has.return_value = mock_g
        mock_g.toList.return_value = []

        mock_ts.return_value.__enter__ = MagicMock(return_value=mock_g)
        mock_ts.return_value.__exit__ = MagicMock(return_value=False)

        loader.merge_duplicate_nodes(CASE_ID, "Nobody", "person")

        mock_g.drop.assert_not_called()

    @patch.object(NeptuneConnectionManager, "traversal_source")
    def test_merges_duplicates(self, mock_ts, loader):
        mock_g = MagicMock()
        node_a = MagicMock(name="node-a")
        node_b = MagicMock(name="node-b")

        # First call: V().hasLabel().has().has().toList() -> [node_a, node_b]
        mock_g.V.return_value = mock_g
        mock_g.hasLabel.return_value = mock_g
        mock_g.has.return_value = mock_g
        mock_g.toList.side_effect = [
            [node_a, node_b],  # duplicate nodes
            [],  # in_edges for node_b
            [],  # out_edges for node_b
        ]

        # values() for occurrence counts
        mock_g.values.return_value = mock_g
        mock_g.next.side_effect = [3, 5, None, None]  # counts for a, b, then property update, drop

        # property update
        mock_g.property.return_value = mock_g

        # drop
        mock_g.drop.return_value = mock_g
        mock_g.iterate.return_value = None

        mock_ts.return_value.__enter__ = MagicMock(return_value=mock_g)
        mock_ts.return_value.__exit__ = MagicMock(return_value=False)

        loader.merge_duplicate_nodes(CASE_ID, "Erich von Däniken", "person")

        # Verify occurrence count was updated to sum (3 + 5 = 8)
        mock_g.property.assert_any_call(NODE_PROP_OCCURRENCE_COUNT, 8)


# ---------------------------------------------------------------------------
# Constructor / helper tests
# ---------------------------------------------------------------------------


class TestLoaderInit:
    def test_loader_url(self, loader):
        assert loader._loader_url() == "https://test-host:8182/loader"

    def test_default_http_client_import(self, conn_manager):
        """When no http_client is provided, _get_http_client imports requests."""
        loader = NeptuneGraphLoader(connection_manager=conn_manager)
        mock_requests = MagicMock()
        with patch.dict("sys.modules", {"requests": mock_requests}):
            client = loader._get_http_client()
            assert client is mock_requests
