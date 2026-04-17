"""Unit tests for IngestionService."""

import io
import json
from unittest.mock import MagicMock, patch, call

import pytest

from src.models.case_file import CaseFileStatus
from src.models.document import BatchResult, ExtractionResult
from src.models.entity import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    RelationshipType,
)
from src.services.ingestion_service import (
    BULK_LOAD_THRESHOLD,
    IngestionService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding_response(embedding: list[float] | None = None) -> dict:
    """Build a mock Bedrock embedding response."""
    if embedding is None:
        embedding = [0.1] * 1536
    body_content = json.dumps({"embedding": embedding})
    return {"body": io.BytesIO(body_content.encode())}


def _make_entity(name: str, etype: EntityType = EntityType.PERSON) -> ExtractedEntity:
    return ExtractedEntity(
        entity_type=etype,
        canonical_name=name,
        confidence=0.9,
        occurrences=1,
        source_document_refs=["doc-1"],
    )


def _make_relationship(src: str, tgt: str) -> ExtractedRelationship:
    return ExtractedRelationship(
        source_entity=src,
        target_entity=tgt,
        relationship_type=RelationshipType.THEMATIC,
        confidence=0.8,
        source_document_ref="doc-1",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_parser():
    parser = MagicMock()
    parsed = MagicMock()
    parsed.raw_text = "Some document text"
    parsed.source_metadata = {"filename": "test.txt"}
    parsed.sections = [{"title": "", "content": "Some document text"}]
    parser.parse.return_value = parsed
    return parser


@pytest.fixture
def mock_extractor():
    extractor = MagicMock()
    extractor.extract_entities.return_value = [
        _make_entity("Alice"),
        _make_entity("Cairo", EntityType.LOCATION),
    ]
    extractor.extract_relationships.return_value = [
        _make_relationship("Alice", "Cairo"),
    ]
    return extractor


@pytest.fixture
def mock_graph_loader():
    loader = MagicMock()
    loader.generate_nodes_csv.return_value = "cases/c1/bulk-load/nodes.csv"
    loader.generate_edges_csv.return_value = "cases/c1/bulk-load/edges.csv"
    loader.bulk_load.return_value = {"nodes": {"load_id": "123", "status": "OK"}}
    loader.load_via_gremlin.return_value = {"nodes_created": 2, "edges_created": 1}
    return loader


@pytest.fixture
def mock_case_service():
    svc = MagicMock()
    return svc


@pytest.fixture
def mock_bedrock():
    client = MagicMock()
    client.invoke_model.return_value = _make_embedding_response()
    return client


@pytest.fixture
def mock_aurora():
    mgr = MagicMock()
    cursor = MagicMock()
    mgr.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mgr.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mgr


@pytest.fixture
def service(mock_parser, mock_extractor, mock_graph_loader, mock_case_service, mock_bedrock, mock_aurora):
    return IngestionService(
        document_parser=mock_parser,
        entity_extraction_service=mock_extractor,
        neptune_graph_loader=mock_graph_loader,
        case_file_service=mock_case_service,
        bedrock_client=mock_bedrock,
        aurora_connection_manager=mock_aurora,
        s3_bucket="test-bucket",
        iam_role_arn="arn:aws:iam::123456789012:role/test",
    )


# ---------------------------------------------------------------------------
# upload_documents — Requirement 2.1
# ---------------------------------------------------------------------------

class TestUploadDocuments:
    """Tests for upload_documents() — Requirement 2.1."""

    @patch("src.services.ingestion_service.upload_file")
    def test_returns_document_ids(self, mock_upload, service):
        files = [("report.txt", b"hello"), ("data.csv", b"a,b,c")]
        doc_ids = service.upload_documents("case-1", files)

        assert len(doc_ids) == 2
        assert all(isinstance(d, str) and len(d) > 0 for d in doc_ids)

    @patch("src.services.ingestion_service.upload_file")
    def test_uploads_to_s3_raw_prefix(self, mock_upload, service):
        files = [("report.txt", b"hello")]
        doc_ids = service.upload_documents("case-1", files)

        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert call_args[0][0] == "case-1"
        assert call_args[0][1] == "raw"
        # filename should be {document_id}.txt
        assert call_args[0][2].endswith(".txt")
        assert doc_ids[0] in call_args[0][2]

    @patch("src.services.ingestion_service.upload_file")
    def test_preserves_file_extension(self, mock_upload, service):
        files = [("data.csv", b"a,b")]
        service.upload_documents("case-1", files)

        s3_filename = mock_upload.call_args[0][2]
        assert s3_filename.endswith(".csv")

    @patch("src.services.ingestion_service.upload_file")
    def test_defaults_to_txt_extension(self, mock_upload, service):
        files = [("noext", b"content")]
        service.upload_documents("case-1", files)

        s3_filename = mock_upload.call_args[0][2]
        assert s3_filename.endswith(".txt")

    @patch("src.services.ingestion_service.upload_file")
    def test_unique_document_ids(self, mock_upload, service):
        files = [("a.txt", b"1"), ("b.txt", b"2"), ("c.txt", b"3")]
        doc_ids = service.upload_documents("case-1", files)

        assert len(set(doc_ids)) == 3

    @patch("src.services.ingestion_service.upload_file")
    def test_empty_file_list(self, mock_upload, service):
        doc_ids = service.upload_documents("case-1", [])
        assert doc_ids == []
        mock_upload.assert_not_called()


# ---------------------------------------------------------------------------
# process_document — Requirements 2.2, 2.3, 2.4, 2.5
# ---------------------------------------------------------------------------

class TestProcessDocument:
    """Tests for process_document() — Requirements 2.2, 2.3, 2.4, 2.5."""

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_returns_extraction_result(self, mock_list, mock_dl, mock_ul, service):
        result = service.process_document("case-1", "doc-1")

        assert isinstance(result, ExtractionResult)
        assert result.document_id == "doc-1"
        assert len(result.entities) == 2
        assert len(result.relationships) == 1

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_calls_parser(self, mock_list, mock_dl, mock_ul, service, mock_parser):
        service.process_document("case-1", "doc-1")
        mock_parser.parse.assert_called_once()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_calls_entity_extraction(self, mock_list, mock_dl, mock_ul, service, mock_extractor):
        service.process_document("case-1", "doc-1")
        mock_extractor.extract_entities.assert_called_once()
        mock_extractor.extract_relationships.assert_called_once()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_generates_embedding(self, mock_list, mock_dl, mock_ul, service, mock_bedrock):
        service.process_document("case-1", "doc-1")
        # Bedrock is called for embedding generation
        mock_bedrock.invoke_model.assert_called_once()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_stores_embedding_in_aurora(self, mock_list, mock_dl, mock_ul, service, mock_aurora):
        service.process_document("case-1", "doc-1")
        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_stores_extraction_artifact_to_s3(self, mock_list, mock_dl, mock_ul, service):
        service.process_document("case-1", "doc-1")
        # upload_file is called for the extraction artifact
        mock_ul.assert_called_once()
        call_args = mock_ul.call_args
        assert call_args[0][1] == "extractions"
        assert "doc-1_extraction.json" in call_args[0][2]

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_extraction_artifact_contains_entities_and_relationships(
        self, mock_list, mock_dl, mock_ul, service
    ):
        service.process_document("case-1", "doc-1")
        artifact_json = mock_ul.call_args[0][3]
        artifact = json.loads(artifact_json)
        assert "entities" in artifact
        assert "relationships" in artifact
        assert artifact["document_id"] == "doc-1"
        assert artifact["case_file_id"] == "case-1"

    @patch("src.services.ingestion_service.list_files", return_value=[])
    def test_raises_when_raw_file_not_found(self, mock_list, service):
        with pytest.raises(FileNotFoundError):
            service.process_document("case-1", "missing-doc")


# ---------------------------------------------------------------------------
# process_batch — Requirements 2.7, 2.8
# ---------------------------------------------------------------------------

class TestProcessBatch:
    """Tests for process_batch() — Requirements 2.7, 2.8."""

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_returns_batch_result(self, mock_list, mock_dl, mock_ul, service):
        mock_list.return_value = ["doc-1.txt"]
        result = service.process_batch("case-1", ["doc-1"])

        assert isinstance(result, BatchResult)
        assert result.case_file_id == "case-1"
        assert result.total_documents == 1
        assert result.successful == 1
        assert result.failed == 0

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_uses_gremlin_for_small_batch(self, mock_list, mock_dl, mock_ul, service, mock_graph_loader):
        mock_list.return_value = ["doc-1.txt"]
        service.process_batch("case-1", ["doc-1"])

        mock_graph_loader.load_via_gremlin.assert_called_once()
        mock_graph_loader.generate_nodes_csv.assert_not_called()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_uses_bulk_csv_for_large_batch(self, mock_list, mock_dl, mock_ul, service, mock_graph_loader):
        doc_ids = [f"doc-{i}" for i in range(BULK_LOAD_THRESHOLD)]
        mock_list.side_effect = lambda case_id, prefix, **kw: [f"{doc_ids[0]}.txt"]

        # Make list_files return matching file for each doc
        def list_side_effect(case_id, prefix, **kw):
            return [f"{d}.txt" for d in doc_ids]
        mock_list.side_effect = list_side_effect

        service.process_batch("case-1", doc_ids)

        mock_graph_loader.generate_nodes_csv.assert_called_once()
        mock_graph_loader.generate_edges_csv.assert_called_once()
        mock_graph_loader.bulk_load.assert_called_once()
        mock_graph_loader.load_via_gremlin.assert_not_called()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_continues_on_individual_failure(self, mock_list, mock_dl, mock_ul, service, mock_parser):
        # First doc fails, second succeeds
        mock_list.return_value = ["doc-1.txt", "doc-2.txt"]
        mock_parser.parse.side_effect = [
            Exception("Parse error"),
            mock_parser.parse.return_value,
        ]

        result = service.process_batch("case-1", ["doc-1", "doc-2"])

        assert result.successful == 1
        assert result.failed == 1
        assert len(result.failures) == 1
        assert result.failures[0]["document_id"] == "doc-1"
        assert "Parse error" in result.failures[0]["error"]

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_updates_case_status_to_indexed(self, mock_list, mock_dl, mock_ul, service, mock_case_service):
        mock_list.return_value = ["doc-1.txt"]
        service.process_batch("case-1", ["doc-1"])

        mock_case_service.update_status.assert_called_once_with(
            "case-1", CaseFileStatus.INDEXED
        )

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_updates_case_statistics(self, mock_list, mock_dl, mock_ul, service, mock_aurora):
        mock_list.return_value = ["doc-1.txt"]
        service.process_batch("case-1", ["doc-1"])

        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        # Last call should be the statistics update
        update_calls = [
            c for c in cursor.execute.call_args_list
            if "UPDATE case_files" in str(c)
        ]
        assert len(update_calls) >= 1

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_batch_result_statistics_match(self, mock_list, mock_dl, mock_ul, service):
        mock_list.return_value = ["doc-1.txt", "doc-2.txt"]
        result = service.process_batch("case-1", ["doc-1", "doc-2"])

        assert result.document_count == result.successful
        assert result.entity_count >= 0
        assert result.relationship_count >= 0

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_all_documents_fail(self, mock_list, mock_dl, mock_ul, service, mock_parser):
        mock_list.return_value = ["doc-1.txt"]
        mock_parser.parse.side_effect = Exception("fail")

        result = service.process_batch("case-1", ["doc-1", "doc-2"])

        assert result.successful == 0
        assert result.failed == 2
        assert result.entity_count == 0
        assert result.relationship_count == 0

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_empty_batch(self, mock_list, mock_dl, mock_ul, service, mock_graph_loader):
        result = service.process_batch("case-1", [])

        assert result.total_documents == 0
        assert result.successful == 0
        assert result.failed == 0
        mock_graph_loader.load_via_gremlin.assert_not_called()
        mock_graph_loader.generate_nodes_csv.assert_not_called()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_bulk_threshold_boundary(self, mock_list, mock_dl, mock_ul, service, mock_graph_loader):
        """Exactly BULK_LOAD_THRESHOLD docs should use bulk CSV."""
        doc_ids = [f"doc-{i}" for i in range(BULK_LOAD_THRESHOLD)]
        mock_list.return_value = [f"{d}.txt" for d in doc_ids]

        service.process_batch("case-1", doc_ids)

        mock_graph_loader.generate_nodes_csv.assert_called_once()
        mock_graph_loader.load_via_gremlin.assert_not_called()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files")
    def test_below_threshold_uses_gremlin(self, mock_list, mock_dl, mock_ul, service, mock_graph_loader):
        """BULK_LOAD_THRESHOLD - 1 docs should use Gremlin."""
        doc_ids = [f"doc-{i}" for i in range(BULK_LOAD_THRESHOLD - 1)]
        mock_list.return_value = [f"{d}.txt" for d in doc_ids]

        service.process_batch("case-1", doc_ids)

        mock_graph_loader.load_via_gremlin.assert_called_once()
        mock_graph_loader.generate_nodes_csv.assert_not_called()


# ---------------------------------------------------------------------------
# Backend factory routing — Task 6.1 (Requirements 3.1, 3.2, 3.3)
# ---------------------------------------------------------------------------

class TestBackendFactoryRouting:
    """Tests for IngestionService routing indexing through BackendFactory."""

    @pytest.fixture
    def mock_backend_factory(self):
        factory = MagicMock()
        backend = MagicMock()
        backend.index_documents.return_value = 1
        factory.get_backend.return_value = backend
        return factory

    @pytest.fixture
    def mock_case_file_standard(self):
        case_file = MagicMock()
        case_file.search_tier = "standard"
        return case_file

    @pytest.fixture
    def mock_case_file_enterprise(self):
        case_file = MagicMock()
        case_file.search_tier = "enterprise"
        return case_file

    @pytest.fixture
    def service_with_factory(
        self, mock_parser, mock_extractor, mock_graph_loader,
        mock_case_service, mock_bedrock, mock_aurora, mock_backend_factory,
        mock_case_file_standard,
    ):
        mock_case_service.get_case_file.return_value = mock_case_file_standard
        return IngestionService(
            document_parser=mock_parser,
            entity_extraction_service=mock_extractor,
            neptune_graph_loader=mock_graph_loader,
            case_file_service=mock_case_service,
            bedrock_client=mock_bedrock,
            aurora_connection_manager=mock_aurora,
            s3_bucket="test-bucket",
            iam_role_arn="arn:aws:iam::123456789012:role/test",
            backend_factory=mock_backend_factory,
        )

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_routes_indexing_through_backend_factory(
        self, mock_list, mock_dl, mock_ul,
        service_with_factory, mock_backend_factory, mock_case_service,
        mock_case_file_standard,
    ):
        """When backend_factory is provided, process_document uses it for indexing."""
        service_with_factory.process_document("case-1", "doc-1")

        mock_case_service.get_case_file.assert_called_with("case-1")
        mock_backend_factory.get_backend.assert_called_once_with(
            mock_case_file_standard.search_tier
        )
        backend = mock_backend_factory.get_backend.return_value
        backend.index_documents.assert_called_once()
        # Verify IndexDocumentRequest was built correctly
        call_args = backend.index_documents.call_args
        assert call_args[0][0] == "case-1"
        docs = call_args[0][1]
        assert len(docs) == 1
        assert docs[0].document_id == "doc-1"
        assert docs[0].case_file_id == "case-1"
        assert docs[0].text == "Some document text"
        assert len(docs[0].embedding) == 1536

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_does_not_call_aurora_directly_when_factory_present(
        self, mock_list, mock_dl, mock_ul,
        service_with_factory, mock_aurora,
    ):
        """When backend_factory is set, _store_document_embedding is NOT called."""
        service_with_factory.process_document("case-1", "doc-1")

        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        # Aurora cursor should NOT be called for document insert
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO documents" in str(c)
        ]
        assert len(insert_calls) == 0

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_falls_back_to_aurora_when_no_factory(
        self, mock_list, mock_dl, mock_ul, service, mock_aurora,
    ):
        """When backend_factory is None (default), falls back to direct Aurora storage."""
        service.process_document("case-1", "doc-1")

        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO documents" in str(c)
        ]
        assert len(insert_calls) == 1

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_routes_enterprise_tier_through_factory(
        self, mock_list, mock_dl, mock_ul,
        mock_parser, mock_extractor, mock_graph_loader,
        mock_case_service, mock_bedrock, mock_aurora,
        mock_case_file_enterprise,
    ):
        """Enterprise tier case files route through the factory with correct tier."""
        mock_case_service.get_case_file.return_value = mock_case_file_enterprise
        factory = MagicMock()
        backend = MagicMock()
        backend.index_documents.return_value = 1
        factory.get_backend.return_value = backend

        svc = IngestionService(
            document_parser=mock_parser,
            entity_extraction_service=mock_extractor,
            neptune_graph_loader=mock_graph_loader,
            case_file_service=mock_case_service,
            bedrock_client=mock_bedrock,
            aurora_connection_manager=mock_aurora,
            s3_bucket="test-bucket",
            backend_factory=factory,
        )
        svc.process_document("case-1", "doc-1")

        factory.get_backend.assert_called_once_with("enterprise")
        backend.index_documents.assert_called_once()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_index_request_metadata_includes_source_filename(
        self, mock_list, mock_dl, mock_ul,
        service_with_factory, mock_backend_factory,
    ):
        """IndexDocumentRequest metadata includes source_filename and sections."""
        service_with_factory.process_document("case-1", "doc-1")

        backend = mock_backend_factory.get_backend.return_value
        docs = backend.index_documents.call_args[0][1]
        assert docs[0].metadata["source_filename"] == "test.txt"
        assert "sections" in docs[0].metadata


# ---------------------------------------------------------------------------
# Batch error logging — Task 6.2 (Requirement 3.5)
# ---------------------------------------------------------------------------

class TestBatchErrorLogging:
    """Tests for process_batch logging indexing errors with document_id and backend type."""

    @pytest.fixture
    def mock_backend_factory(self):
        factory = MagicMock()
        backend = MagicMock()
        backend.index_documents.return_value = 1
        factory.get_backend.return_value = backend
        return factory

    @pytest.fixture
    def service_with_factory(
        self, mock_parser, mock_extractor, mock_graph_loader,
        mock_case_service, mock_bedrock, mock_aurora, mock_backend_factory,
    ):
        case_file = MagicMock()
        case_file.search_tier = "standard"
        mock_case_service.get_case_file.return_value = case_file
        return IngestionService(
            document_parser=mock_parser,
            entity_extraction_service=mock_extractor,
            neptune_graph_loader=mock_graph_loader,
            case_file_service=mock_case_service,
            bedrock_client=mock_bedrock,
            aurora_connection_manager=mock_aurora,
            s3_bucket="test-bucket",
            backend_factory=mock_backend_factory,
        )

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt", "doc-2.txt"])
    def test_logs_error_with_document_id_and_backend_type(
        self, mock_list, mock_dl, mock_ul,
        service_with_factory, mock_parser, mock_backend_factory,
    ):
        """Failures are logged with document_id and backend type."""
        mock_parser.parse.side_effect = [
            Exception("Parse error"),
            mock_parser.parse.return_value,
        ]

        with patch("src.services.ingestion_service.logger") as mock_logger:
            result = service_with_factory.process_batch("case-1", ["doc-1", "doc-2"])

        assert result.failed == 1
        assert result.successful == 1
        mock_logger.error.assert_called_once()
        log_args = mock_logger.error.call_args
        # Verify log message contains document_id and backend type
        assert "doc-1" in str(log_args)
        assert "MagicMock" in str(log_args) or "backend" in str(log_args[0][0]).lower()

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt", "doc-2.txt", "doc-3.txt"])
    def test_continues_processing_after_failure(
        self, mock_list, mock_dl, mock_ul,
        service_with_factory, mock_parser,
    ):
        """Batch continues processing remaining documents after individual failures."""
        mock_parser.parse.side_effect = [
            Exception("fail-1"),
            Exception("fail-2"),
            mock_parser.parse.return_value,
        ]

        result = service_with_factory.process_batch("case-1", ["doc-1", "doc-2", "doc-3"])

        assert result.failed == 2
        assert result.successful == 1
        assert result.total_documents == 3
        assert len(result.failures) == 2

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_logs_unknown_backend_when_factory_absent(
        self, mock_list, mock_dl, mock_ul,
        mock_parser, mock_extractor, mock_graph_loader,
        mock_case_service, mock_bedrock, mock_aurora,
    ):
        """When no backend_factory, error log shows 'unknown' backend type."""
        mock_parser.parse.side_effect = Exception("fail")
        svc = IngestionService(
            document_parser=mock_parser,
            entity_extraction_service=mock_extractor,
            neptune_graph_loader=mock_graph_loader,
            case_file_service=mock_case_service,
            bedrock_client=mock_bedrock,
            aurora_connection_manager=mock_aurora,
            s3_bucket="test-bucket",
        )

        with patch("src.services.ingestion_service.logger") as mock_logger:
            result = svc.process_batch("case-1", ["doc-1"])

        assert result.failed == 1
        mock_logger.error.assert_called_once()
        assert "unknown" in str(mock_logger.error.call_args)


# ---------------------------------------------------------------------------
# Enhancement 2 & 3: page_count, file_size_bytes, provenance metadata
# ---------------------------------------------------------------------------

class TestIngestionEnhancements:
    """Tests for page_count, file_size_bytes, and provenance metadata."""

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_extraction_artifact_contains_provenance(
        self, mock_list, mock_dl, mock_ul, service
    ):
        """Extraction artifact stored in S3 includes provenance metadata."""
        service.process_document("case-1", "doc-1")
        artifact_json = mock_ul.call_args[0][3]
        artifact = json.loads(artifact_json)
        assert "provenance" in artifact
        prov = artifact["provenance"]
        assert "ingested_at" in prov
        assert prov["source_s3_key"] == "cases/case-1/raw/doc-1"
        assert prov["parse_method"] == "DocumentParser.parse"
        assert prov["entity_count"] == 2
        assert prov["relationship_count"] == 1
        assert "file_size_bytes" in prov
        assert "page_count_estimate" in prov
        assert "chunk_count" in prov

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_file_size_bytes_captured(
        self, mock_list, mock_dl, mock_ul, service
    ):
        """file_size_bytes in provenance matches the raw file size."""
        service.process_document("case-1", "doc-1")
        artifact_json = mock_ul.call_args[0][3]
        artifact = json.loads(artifact_json)
        assert artifact["provenance"]["file_size_bytes"] == len(b"raw text")

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_page_count_estimate_at_least_one(
        self, mock_list, mock_dl, mock_ul, service
    ):
        """page_count_estimate is at least 1 even for short documents."""
        service.process_document("case-1", "doc-1")
        artifact_json = mock_ul.call_args[0][3]
        artifact = json.loads(artifact_json)
        assert artifact["provenance"]["page_count_estimate"] >= 1

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"x" * 9000)
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_page_count_scales_with_content(
        self, mock_list, mock_dl, mock_ul, service
    ):
        """page_count_estimate scales with content length (~3000 chars/page)."""
        service.process_document("case-1", "doc-1")
        artifact_json = mock_ul.call_args[0][3]
        artifact = json.loads(artifact_json)
        # 9000 chars / 3000 = 3 pages
        assert artifact["provenance"]["page_count_estimate"] == 3

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_aurora_insert_includes_new_columns(
        self, mock_list, mock_dl, mock_ul, service, mock_aurora
    ):
        """Aurora INSERT includes page_count, file_size_bytes, and document_type."""
        service.process_document("case-1", "doc-1")
        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO documents" in str(c)
        ]
        assert len(insert_calls) == 1
        sql = str(insert_calls[0])
        assert "page_count" in sql
        assert "file_size_bytes" in sql
        assert "document_type" in sql

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_alter_table_adds_columns_safely(
        self, mock_list, mock_dl, mock_ul, service, mock_aurora
    ):
        """ALTER TABLE ADD COLUMN IF NOT EXISTS is called for new columns."""
        service.process_document("case-1", "doc-1")
        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        alter_calls = [
            str(c) for c in cursor.execute.call_args_list
            if "ALTER TABLE" in str(c)
        ]
        assert len(alter_calls) == 3
        assert any("page_count" in c for c in alter_calls)
        assert any("file_size_bytes" in c for c in alter_calls)
        assert any("document_type" in c for c in alter_calls)

    @patch("src.services.ingestion_service.upload_file")
    @patch("src.services.ingestion_service.download_file", return_value=b"raw text")
    @patch("src.services.ingestion_service.list_files", return_value=["doc-1.txt"])
    def test_provenance_embedding_model_field(
        self, mock_list, mock_dl, mock_ul, service
    ):
        """Provenance includes the embedding model ID."""
        service.process_document("case-1", "doc-1")
        artifact_json = mock_ul.call_args[0][3]
        artifact = json.loads(artifact_json)
        assert artifact["provenance"]["embedding_model"] == "amazon.titan-embed-text-v1"
