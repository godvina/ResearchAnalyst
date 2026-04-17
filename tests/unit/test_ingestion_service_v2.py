"""Unit tests for IngestionServiceV2."""

import json
from unittest.mock import MagicMock, patch, call

import pytest

from src.models.document import BatchResult, ExtractionResult
from src.models.entity import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    RelationshipType,
)
from src.models.hierarchy import Collection, CollectionStatus
from src.services.ingestion_service_v2 import IngestionServiceV2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_collection(
    collection_id: str = "col-1",
    matter_id: str = "mat-1",
    org_id: str = "org-1",
    status: CollectionStatus = CollectionStatus.STAGING,
) -> Collection:
    from datetime import datetime, timezone
    return Collection(
        collection_id=collection_id,
        matter_id=matter_id,
        org_id=org_id,
        collection_name="Test Collection",
        source_description="test",
        status=status,
        uploaded_at=datetime.now(timezone.utc),
        s3_prefix=f"orgs/{org_id}/matters/{matter_id}/collections/{collection_id}/",
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
        ExtractedEntity(
            entity_type=EntityType.PERSON,
            canonical_name="Alice",
            confidence=0.9,
            occurrences=1,
            source_document_refs=["doc-1"],
        ),
    ]
    extractor.extract_relationships.return_value = [
        ExtractedRelationship(
            source_entity="Alice",
            target_entity="Bob",
            relationship_type=RelationshipType.THEMATIC,
            confidence=0.8,
            source_document_ref="doc-1",
        ),
    ]
    extractor.chunk_text.return_value = ["chunk1"]
    return extractor


@pytest.fixture
def mock_graph_loader():
    loader = MagicMock()
    loader.load_via_gremlin.return_value = {"nodes_created": 1, "edges_created": 1}
    return loader


@pytest.fixture
def mock_case_service():
    return MagicMock()


@pytest.fixture
def mock_bedrock():
    import io
    client = MagicMock()
    body_content = json.dumps({"embedding": [0.1] * 1536})
    client.invoke_model.return_value = {"body": io.BytesIO(body_content.encode())}
    return client


@pytest.fixture
def mock_aurora():
    mgr = MagicMock()
    cursor = MagicMock()
    mgr.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    mgr.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mgr


@pytest.fixture
def mock_collection_service():
    svc = MagicMock()
    svc.create_collection.return_value = _make_collection()
    svc.get_collection.return_value = _make_collection()
    svc.update_status.return_value = _make_collection(status=CollectionStatus.QA_REVIEW)
    return svc


@pytest.fixture
def service(
    mock_parser, mock_extractor, mock_graph_loader,
    mock_case_service, mock_bedrock, mock_aurora, mock_collection_service,
):
    return IngestionServiceV2(
        document_parser=mock_parser,
        entity_extraction_service=mock_extractor,
        neptune_graph_loader=mock_graph_loader,
        case_file_service=mock_case_service,
        bedrock_client=mock_bedrock,
        aurora_connection_manager=mock_aurora,
        s3_bucket="test-bucket",
        iam_role_arn="arn:aws:iam::123456789012:role/test",
        collection_service=mock_collection_service,
    )


# ---------------------------------------------------------------------------
# upload_documents — Requirements 3.3, 3.5, 4.1, 10.1
# ---------------------------------------------------------------------------

class TestUploadDocumentsV2:
    """Tests for IngestionServiceV2.upload_documents()."""

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_creates_collection_in_staging(self, mock_s3, service, mock_collection_service):
        files = [("report.txt", b"hello")]
        col_id, doc_ids = service.upload_documents(
            "mat-1", "org-1", files, "My Collection", "source desc",
        )

        mock_collection_service.create_collection.assert_called_once_with(
            matter_id="mat-1",
            org_id="org-1",
            collection_name="My Collection",
            source_description="source desc",
        )

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_returns_collection_id_and_document_ids(self, mock_s3, service):
        files = [("a.txt", b"1"), ("b.txt", b"2")]
        col_id, doc_ids = service.upload_documents(
            "mat-1", "org-1", files, "Test",
        )

        assert col_id == "col-1"
        assert len(doc_ids) == 2
        assert all(isinstance(d, str) and len(d) > 0 for d in doc_ids)

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_uploads_to_new_s3_hierarchy_path(self, mock_s3, service):
        files = [("report.pdf", b"content")]
        service.upload_documents("mat-1", "org-1", files, "Test")

        mock_s3.assert_called_once()
        s3_key = mock_s3.call_args[0][0]
        assert s3_key.startswith("orgs/org-1/matters/mat-1/collections/col-1/raw/")

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_inserts_document_rows_with_hierarchy_ids(self, mock_s3, service, mock_aurora):
        files = [("report.txt", b"hello")]
        service.upload_documents("mat-1", "org-1", files, "Test")

        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO documents" in str(c)
        ]
        assert len(insert_calls) == 1
        # Verify org_id, matter_id, collection_id are in the params
        params = insert_calls[0][0][1]
        assert "org-1" in params
        assert "mat-1" in params
        assert "col-1" in params

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_preserves_file_extension(self, mock_s3, service):
        files = [("data.csv", b"a,b")]
        service.upload_documents("mat-1", "org-1", files, "Test")

        s3_key = mock_s3.call_args[0][0]
        assert s3_key.endswith(".csv")

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_defaults_to_txt_extension(self, mock_s3, service):
        files = [("noext", b"content")]
        service.upload_documents("mat-1", "org-1", files, "Test")

        s3_key = mock_s3.call_args[0][0]
        assert s3_key.endswith(".txt")

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_empty_file_list(self, mock_s3, service, mock_collection_service):
        col_id, doc_ids = service.upload_documents("mat-1", "org-1", [], "Test")

        assert col_id == "col-1"
        assert doc_ids == []
        mock_s3.assert_not_called()

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._upload_to_s3")
    def test_default_collection_name_when_empty(self, mock_s3, service, mock_collection_service):
        files = [("a.txt", b"1")]
        service.upload_documents("mat-1", "org-1", files)

        call_kwargs = mock_collection_service.create_collection.call_args
        assert "Upload" in call_kwargs.kwargs.get("collection_name", call_kwargs[1].get("collection_name", ""))


# ---------------------------------------------------------------------------
# process_batch — Requirements 3.4
# ---------------------------------------------------------------------------

class TestProcessBatchV2:
    """Tests for IngestionServiceV2.process_batch()."""

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._process_document_v2")
    def test_returns_batch_result(self, mock_proc, service):
        mock_proc.return_value = ExtractionResult(
            document_id="doc-1", entities=[], relationships=[],
        )
        result = service.process_batch("col-1", ["doc-1"])

        assert result.case_file_id == "col-1"
        assert result.total_documents == 1
        assert result.successful == 1
        assert result.failed == 0

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._process_document_v2")
    def test_loads_entities_via_gremlin(self, mock_proc, service, mock_graph_loader):
        mock_proc.return_value = ExtractionResult(
            document_id="doc-1",
            entities=[{
                "entity_type": "person",
                "canonical_name": "Alice",
                "confidence": 0.9,
                "occurrences": 1,
                "source_document_refs": ["doc-1"],
            }],
            relationships=[],
        )
        service.process_batch("col-1", ["doc-1"])

        mock_graph_loader.load_via_gremlin.assert_called_once()
        call_args = mock_graph_loader.load_via_gremlin.call_args[0]
        assert call_args[0] == "col-1"  # collection_id used as scope

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._process_document_v2")
    def test_transitions_collection_to_qa_review(self, mock_proc, service, mock_collection_service, mock_aurora):
        mock_proc.return_value = ExtractionResult(
            document_id="doc-1", entities=[], relationships=[],
        )
        # Set up aurora to return org_id for collection lookup
        cursor = mock_aurora.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("org-1",)

        service.process_batch("col-1", ["doc-1"])

        # Should transition staging -> processing -> qa_review
        status_calls = mock_collection_service.update_status.call_args_list
        assert len(status_calls) == 2
        assert status_calls[0][0] == ("col-1", "org-1", CollectionStatus.PROCESSING)
        assert status_calls[1][0] == ("col-1", "org-1", CollectionStatus.QA_REVIEW)

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._process_document_v2")
    def test_continues_on_individual_failure(self, mock_proc, service):
        mock_proc.side_effect = [
            Exception("Parse error"),
            ExtractionResult(document_id="doc-2", entities=[], relationships=[]),
        ]

        result = service.process_batch("col-1", ["doc-1", "doc-2"])

        assert result.successful == 1
        assert result.failed == 1
        assert len(result.failures) == 1
        assert result.failures[0]["document_id"] == "doc-1"

    @patch("src.services.ingestion_service_v2.IngestionServiceV2._process_document_v2")
    def test_empty_batch(self, mock_proc, service, mock_graph_loader):
        result = service.process_batch("col-1", [])

        assert result.total_documents == 0
        assert result.successful == 0
        mock_graph_loader.load_via_gremlin.assert_not_called()


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    """Tests for IngestionServiceV2 constructor."""

    def test_accepts_collection_service(
        self, mock_parser, mock_extractor, mock_graph_loader,
        mock_case_service, mock_bedrock, mock_aurora, mock_collection_service,
    ):
        svc = IngestionServiceV2(
            document_parser=mock_parser,
            entity_extraction_service=mock_extractor,
            neptune_graph_loader=mock_graph_loader,
            case_file_service=mock_case_service,
            bedrock_client=mock_bedrock,
            aurora_connection_manager=mock_aurora,
            collection_service=mock_collection_service,
        )
        assert svc._collection_service is mock_collection_service

    def test_inherits_from_ingestion_service(self, service):
        # IngestionServiceV2 extends IngestionService
        assert hasattr(service, '_parser')
        assert hasattr(service, '_extractor')
        assert hasattr(service, '_graph_loader')
        assert hasattr(service, '_collection_service')
