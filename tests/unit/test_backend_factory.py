"""Unit tests for BackendFactory and AuroraPgvectorBackend."""

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from src.models.case_file import SearchTier
from src.models.search import FacetedFilter, SearchResult
from src.services.backend_factory import BackendFactory
from src.services.aurora_pgvector_backend import AuroraPgvectorBackend
from src.services.search_backend import IndexDocumentRequest, SearchBackend


# ---------------------------------------------------------------------------
# Helpers — lightweight fake backends
# ---------------------------------------------------------------------------

class FakeAuroraBackend:
    @property
    def supported_modes(self) -> list[str]:
        return ["semantic"]

    def index_documents(self, case_id, documents):
        return len(documents)

    def search(self, case_id, query, *, mode="semantic", embedding=None,
               filters=None, top_k=10):
        return []

    def delete_documents(self, case_id, document_ids=None):
        return 0


class FakeOpenSearchBackend:
    @property
    def supported_modes(self) -> list[str]:
        return ["semantic", "keyword", "hybrid"]

    def index_documents(self, case_id, documents):
        return len(documents)

    def search(self, case_id, query, *, mode="semantic", embedding=None,
               filters=None, top_k=10):
        return []

    def delete_documents(self, case_id, document_ids=None):
        return 0


# ---------------------------------------------------------------------------
# BackendFactory tests
# ---------------------------------------------------------------------------

class TestBackendFactory:
    def _make_factory(self):
        aurora = FakeAuroraBackend()
        opensearch = FakeOpenSearchBackend()
        return BackendFactory(aurora, opensearch), aurora, opensearch

    def test_get_backend_standard_returns_aurora(self):
        factory, aurora, _ = self._make_factory()
        assert factory.get_backend("standard") is aurora

    def test_get_backend_enterprise_returns_opensearch(self):
        factory, _, opensearch = self._make_factory()
        assert factory.get_backend("enterprise") is opensearch

    def test_get_backend_accepts_enum(self):
        factory, aurora, _ = self._make_factory()
        assert factory.get_backend(SearchTier.STANDARD) is aurora

    def test_get_backend_unknown_tier_raises(self):
        factory, _, _ = self._make_factory()
        with pytest.raises(ValueError, match="Unknown search tier"):
            factory.get_backend("premium")

    def test_get_backend_empty_string_raises(self):
        factory, _, _ = self._make_factory()
        with pytest.raises(ValueError, match="Unknown search tier"):
            factory.get_backend("")

    def test_validate_search_mode_semantic_standard_ok(self):
        factory, _, _ = self._make_factory()
        factory.validate_search_mode("standard", "semantic")  # no error

    def test_validate_search_mode_keyword_standard_raises(self):
        factory, _, _ = self._make_factory()
        with pytest.raises(ValueError, match="not available"):
            factory.validate_search_mode("standard", "keyword")

    def test_validate_search_mode_hybrid_standard_raises(self):
        factory, _, _ = self._make_factory()
        with pytest.raises(ValueError, match="not available"):
            factory.validate_search_mode("standard", "hybrid")

    def test_validate_search_mode_all_enterprise_modes_ok(self):
        factory, _, _ = self._make_factory()
        for mode in ("semantic", "keyword", "hybrid"):
            factory.validate_search_mode("enterprise", mode)

    def test_validate_search_mode_unknown_mode_enterprise_raises(self):
        factory, _, _ = self._make_factory()
        with pytest.raises(ValueError, match="not available"):
            factory.validate_search_mode("enterprise", "fulltext")

    def test_validate_search_mode_unknown_tier_raises(self):
        factory, _, _ = self._make_factory()
        with pytest.raises(ValueError, match="Unknown search tier"):
            factory.validate_search_mode("gold", "semantic")

    def test_factory_without_opensearch(self):
        aurora = FakeAuroraBackend()
        factory = BackendFactory(aurora)
        assert factory.get_backend("standard") is aurora
        with pytest.raises(ValueError, match="No backend configured"):
            factory.get_backend("enterprise")


# ---------------------------------------------------------------------------
# AuroraPgvectorBackend — protocol conformance
# ---------------------------------------------------------------------------

class TestAuroraPgvectorBackendProtocol:
    def test_satisfies_search_backend_protocol(self):
        cm = MagicMock()
        backend = AuroraPgvectorBackend(cm)
        assert isinstance(backend, SearchBackend)

    def test_supported_modes(self):
        cm = MagicMock()
        backend = AuroraPgvectorBackend(cm)
        assert backend.supported_modes == ["semantic"]


# ---------------------------------------------------------------------------
# AuroraPgvectorBackend — search
# ---------------------------------------------------------------------------

class TestAuroraPgvectorSearch:
    def test_search_rejects_keyword_mode(self):
        cm = MagicMock()
        backend = AuroraPgvectorBackend(cm)
        with pytest.raises(ValueError, match="not available"):
            backend.search("c-1", "query", mode="keyword", embedding=[0.1])

    def test_search_rejects_hybrid_mode(self):
        cm = MagicMock()
        backend = AuroraPgvectorBackend(cm)
        with pytest.raises(ValueError, match="not available"):
            backend.search("c-1", "query", mode="hybrid", embedding=[0.1])

    def test_search_requires_embedding(self):
        cm = MagicMock()
        backend = AuroraPgvectorBackend(cm)
        with pytest.raises(ValueError, match="Embedding is required"):
            backend.search("c-1", "query", mode="semantic")

    def test_search_returns_results(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("d-1", "Some text about aliens", "doc1.txt", 0.95),
            ("d-2", "Another passage", "doc2.txt", 0.80),
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        cm = MagicMock()
        cm.cursor.return_value = mock_cursor

        backend = AuroraPgvectorBackend(cm)
        results = backend.search("c-1", "aliens", embedding=[0.1, 0.2], top_k=5)

        assert len(results) == 2
        assert results[0].document_id == "d-1"
        assert results[0].relevance_score == 0.95
        assert results[1].document_id == "d-2"


# ---------------------------------------------------------------------------
# AuroraPgvectorBackend — index_documents
# ---------------------------------------------------------------------------

class TestAuroraPgvectorIndex:
    def test_index_documents_returns_count(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        cm = MagicMock()
        cm.cursor.return_value = mock_cursor

        backend = AuroraPgvectorBackend(cm)
        docs = [
            IndexDocumentRequest(
                document_id="d-1",
                case_file_id="c-1",
                text="hello",
                embedding=[0.1, 0.2],
                metadata={"source_filename": "test.txt"},
            ),
            IndexDocumentRequest(
                document_id="d-2",
                case_file_id="c-1",
                text="world",
                embedding=[0.3, 0.4],
            ),
        ]
        count = backend.index_documents("c-1", docs)
        assert count == 2
        assert mock_cursor.execute.call_count == 2

    def test_index_empty_list(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        cm = MagicMock()
        cm.cursor.return_value = mock_cursor

        backend = AuroraPgvectorBackend(cm)
        count = backend.index_documents("c-1", [])
        assert count == 0


# ---------------------------------------------------------------------------
# AuroraPgvectorBackend — delete_documents
# ---------------------------------------------------------------------------

class TestAuroraPgvectorDelete:
    def test_delete_all_for_case(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        cm = MagicMock()
        cm.cursor.return_value = mock_cursor

        backend = AuroraPgvectorBackend(cm)
        count = backend.delete_documents("c-1")
        assert count == 5

    def test_delete_specific_documents(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        cm = MagicMock()
        cm.cursor.return_value = mock_cursor

        backend = AuroraPgvectorBackend(cm)
        count = backend.delete_documents("c-1", ["d-1", "d-2"])
        assert count == 2

    def test_delete_empty_list_returns_zero(self):
        cm = MagicMock()
        backend = AuroraPgvectorBackend(cm)
        count = backend.delete_documents("c-1", [])
        assert count == 0
