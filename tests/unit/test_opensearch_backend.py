"""Unit tests for OpenSearchServerlessBackend."""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.models.search import FacetedFilter, SearchResult
from src.services.opensearch_serverless_backend import OpenSearchServerlessBackend
from src.services.search_backend import IndexDocumentRequest, SearchBackend


@pytest.fixture(autouse=True)
def _enable_opensearch():
    """Enable OpenSearch feature flag for all tests in this module."""
    import src.services.opensearch_serverless_backend as oss_mod
    original = oss_mod._OPENSEARCH_ENABLED
    oss_mod._OPENSEARCH_ENABLED = True
    yield
    oss_mod._OPENSEARCH_ENABLED = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backend(**kwargs):
    """Create an OpenSearchServerlessBackend with a mocked endpoint."""
    with patch.dict("os.environ", {"OPENSEARCH_ENDPOINT": "https://test.us-east-1.aoss.amazonaws.com"}):
        return OpenSearchServerlessBackend(**kwargs)


def _sample_docs(n=2):
    """Return a list of sample IndexDocumentRequest objects."""
    return [
        IndexDocumentRequest(
            document_id=f"d-{i}",
            case_file_id="c-1",
            text=f"Document text {i}",
            embedding=[0.1] * 1536,
            metadata={
                "source_filename": f"file{i}.txt",
                "document_type": "report",
                "persons": ["Alice"],
                "entity_types": ["person"],
            },
        )
        for i in range(n)
    ]


def _mock_search_response(hits):
    """Build a mock OpenSearch search response."""
    return {
        "hits": {
            "total": {"value": len(hits)},
            "hits": [
                {
                    "_id": h["id"],
                    "_score": h.get("score", 0.9),
                    "_source": {
                        "document_id": h["id"],
                        "text": h.get("text", "passage text"),
                        "source_filename": h.get("filename", "doc.txt"),
                    },
                }
                for h in hits
            ],
        }
    }


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------

class TestOpenSearchBackendInit:
    def test_raises_without_endpoint(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(EnvironmentError, match="endpoint not configured"):
                OpenSearchServerlessBackend()

    def test_accepts_explicit_endpoint(self):
        backend = _make_backend(collection_endpoint="https://my-endpoint.aoss.amazonaws.com")
        assert "my-endpoint" in backend._endpoint

    def test_adds_https_prefix(self):
        backend = _make_backend(collection_endpoint="my-endpoint.aoss.amazonaws.com")
        assert backend._endpoint.startswith("https://")

    def test_strips_trailing_slash(self):
        backend = _make_backend(collection_endpoint="https://my-endpoint.aoss.amazonaws.com/")
        assert not backend._endpoint.endswith("/")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestOpenSearchBackendProtocol:
    def test_satisfies_search_backend_protocol(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        assert isinstance(backend, SearchBackend)

    def test_supported_modes(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        assert backend.supported_modes == ["semantic", "keyword", "hybrid"]


# ---------------------------------------------------------------------------
# _ensure_index / _build_index_mapping
# ---------------------------------------------------------------------------

class TestIndexManagement:
    def test_build_index_mapping_has_knn_vector(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        mapping = backend._build_index_mapping()

        props = mapping["mappings"]["properties"]
        assert props["embedding"]["type"] == "knn_vector"
        assert props["embedding"]["dimension"] == 1536
        assert props["embedding"]["method"]["engine"] == "nmslib"
        assert props["embedding"]["method"]["space_type"] == "cosinesimil"

    def test_build_index_mapping_has_text_field(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        mapping = backend._build_index_mapping()
        assert mapping["mappings"]["properties"]["text"]["type"] == "text"

    def test_build_index_mapping_has_metadata_fields(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        mapping = backend._build_index_mapping()
        props = mapping["mappings"]["properties"]
        assert props["document_id"]["type"] == "keyword"
        assert props["source_filename"]["type"] == "keyword"
        assert props["document_type"]["type"] == "keyword"
        assert props["persons"]["type"] == "keyword"
        assert props["entity_types"]["type"] == "keyword"
        assert props["date_indexed"]["type"] == "date"

    def test_build_index_mapping_knn_settings(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        mapping = backend._build_index_mapping()
        assert mapping["settings"]["index"]["knn"] is True

    def test_index_name(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        assert backend._index_name("abc-123") == "case-abc-123"


# ---------------------------------------------------------------------------
# index_documents
# ---------------------------------------------------------------------------

class TestIndexDocuments:
    def test_empty_list_returns_zero(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        count = backend.index_documents("c-1", [])
        assert count == 0

    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_ensure_index")
    def test_bulk_index_success(self, mock_ensure, mock_request):
        mock_request.return_value = {"errors": False, "items": []}
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        docs = _sample_docs(3)

        count = backend.index_documents("c-1", docs)

        assert count == 3
        mock_ensure.assert_called_once_with("c-1")
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/_bulk"

    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_ensure_index")
    def test_bulk_index_partial_failure(self, mock_ensure, mock_request):
        mock_request.return_value = {
            "errors": True,
            "items": [
                {"index": {"_id": "d-0", "status": 201}},
                {"index": {"_id": "d-1", "status": 400, "error": {"reason": "bad"}}},
            ],
        }
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        docs = _sample_docs(2)

        count = backend.index_documents("c-1", docs)
        assert count == 1


# ---------------------------------------------------------------------------
# search — keyword mode
# ---------------------------------------------------------------------------

class TestSearchKeyword:
    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_keyword_search_builds_match_query(self, mock_exists, mock_request):
        mock_request.return_value = _mock_search_response([
            {"id": "d-1", "score": 0.9, "text": "aliens"},
        ])
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")

        results = backend.search("c-1", "aliens", mode="keyword", top_k=5)

        assert len(results) == 1
        assert results[0].document_id == "d-1"
        # Verify the query structure
        call_body = json.loads(mock_request.call_args[1]["body"])
        assert "match" in str(call_body["query"])

    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=False)
    def test_keyword_search_missing_index_returns_empty(self, mock_exists):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        results = backend.search("c-1", "aliens", mode="keyword")
        assert results == []


# ---------------------------------------------------------------------------
# search — semantic mode
# ---------------------------------------------------------------------------

class TestSearchSemantic:
    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_semantic_search_builds_knn_query(self, mock_exists, mock_request):
        mock_request.return_value = _mock_search_response([
            {"id": "d-1", "score": 0.85},
        ])
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        embedding = [0.1] * 1536

        results = backend.search("c-1", "aliens", mode="semantic", embedding=embedding)

        assert len(results) == 1
        call_body = json.loads(mock_request.call_args[1]["body"])
        assert "knn" in str(call_body["query"])

    def test_semantic_search_requires_embedding(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        with patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True):
            with pytest.raises(ValueError, match="Embedding is required"):
                backend.search("c-1", "aliens", mode="semantic")


# ---------------------------------------------------------------------------
# search — hybrid mode
# ---------------------------------------------------------------------------

class TestSearchHybrid:
    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_hybrid_search_builds_compound_query(self, mock_exists, mock_request):
        mock_request.return_value = _mock_search_response([
            {"id": "d-1", "score": 0.9},
            {"id": "d-2", "score": 0.7},
        ])
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        embedding = [0.1] * 1536

        results = backend.search("c-1", "aliens", mode="hybrid", embedding=embedding)

        assert len(results) == 2
        call_body = json.loads(mock_request.call_args[1]["body"])
        assert "hybrid" in str(call_body["query"])

    def test_hybrid_search_requires_embedding(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        with patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True):
            with pytest.raises(ValueError, match="Embedding is required"):
                backend.search("c-1", "aliens", mode="hybrid")

    def test_unsupported_mode_raises(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        with patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True):
            with pytest.raises(ValueError, match="not supported"):
                backend.search("c-1", "aliens", mode="fulltext")


# ---------------------------------------------------------------------------
# search — faceted filters
# ---------------------------------------------------------------------------

class TestFacetedFilters:
    def test_build_filter_clauses_date_range(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter(date_from="2024-01-01", date_to="2024-12-31")
        clauses = backend._build_filter_clauses(f)
        assert len(clauses) == 1
        assert "range" in clauses[0]
        assert clauses[0]["range"]["date_indexed"]["gte"] == "2024-01-01"
        assert clauses[0]["range"]["date_indexed"]["lte"] == "2024-12-31"

    def test_build_filter_clauses_person(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter(person="Alice")
        clauses = backend._build_filter_clauses(f)
        assert len(clauses) == 1
        assert clauses[0] == {"term": {"persons": "Alice"}}

    def test_build_filter_clauses_document_type(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter(document_type="report")
        clauses = backend._build_filter_clauses(f)
        assert len(clauses) == 1
        assert clauses[0] == {"term": {"document_type": "report"}}

    def test_build_filter_clauses_entity_type(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter(entity_type="person")
        clauses = backend._build_filter_clauses(f)
        assert len(clauses) == 1
        assert clauses[0] == {"term": {"entity_types": "person"}}

    def test_build_filter_clauses_multiple(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter(person="Bob", document_type="memo", date_from="2024-06-01")
        clauses = backend._build_filter_clauses(f)
        assert len(clauses) == 3

    def test_build_filter_clauses_empty(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter()
        clauses = backend._build_filter_clauses(f)
        assert clauses == []

    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_keyword_search_with_filters(self, mock_exists, mock_request):
        mock_request.return_value = _mock_search_response([])
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter(person="Alice")

        backend.search("c-1", "query", mode="keyword", filters=f)

        call_body = json.loads(mock_request.call_args[1]["body"])
        assert call_body["query"]["bool"]["filter"] == [{"term": {"persons": "Alice"}}]

    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_semantic_search_with_filters_uses_post_filter(self, mock_exists, mock_request):
        mock_request.return_value = _mock_search_response([])
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        f = FacetedFilter(document_type="report")
        embedding = [0.1] * 1536

        backend.search("c-1", "query", mode="semantic", embedding=embedding, filters=f)

        call_body = json.loads(mock_request.call_args[1]["body"])
        assert "post_filter" in call_body


# ---------------------------------------------------------------------------
# delete_documents
# ---------------------------------------------------------------------------

class TestDeleteDocuments:
    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_get_doc_count", return_value=10)
    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_delete_all_deletes_index(self, mock_exists, mock_count, mock_request):
        mock_request.return_value = {}
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")

        count = backend.delete_documents("c-1")

        assert count == 10
        mock_request.assert_called_once_with("DELETE", "/case-c-1")

    @patch.object(OpenSearchServerlessBackend, "_request")
    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_delete_specific_docs(self, mock_exists, mock_request):
        mock_request.return_value = {"deleted": 2}
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")

        count = backend.delete_documents("c-1", ["d-1", "d-2"])

        assert count == 2
        call_body = json.loads(mock_request.call_args[1]["body"])
        assert call_body["query"]["terms"]["document_id"] == ["d-1", "d-2"]

    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=False)
    def test_delete_missing_index_returns_zero(self, mock_exists):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        count = backend.delete_documents("c-1")
        assert count == 0

    @patch.object(OpenSearchServerlessBackend, "_index_exists", return_value=True)
    def test_delete_empty_list_returns_zero(self, mock_exists):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        count = backend.delete_documents("c-1", [])
        assert count == 0


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

class TestResponseParsing:
    def test_parse_search_response_basic(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        resp = _mock_search_response([
            {"id": "d-1", "score": 0.9, "text": "hello world", "filename": "a.txt"},
            {"id": "d-2", "score": 0.5, "text": "foo bar", "filename": "b.txt"},
        ])
        results = backend._parse_search_response(resp)

        assert len(results) == 2
        assert results[0].document_id == "d-1"
        assert results[0].passage == "hello world"
        assert results[0].source_document_ref == "a.txt"
        assert 0.0 <= results[0].relevance_score <= 1.0

    def test_parse_search_response_empty(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        results = backend._parse_search_response({"hits": {"hits": []}})
        assert results == []

    def test_parse_search_response_truncates_passage(self):
        backend = _make_backend(collection_endpoint="https://test.aoss.amazonaws.com")
        long_text = "x" * 1000
        resp = _mock_search_response([{"id": "d-1", "score": 0.5, "text": long_text}])
        results = backend._parse_search_response(resp)
        assert len(results[0].passage) == 500
