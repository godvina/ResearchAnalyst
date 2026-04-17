"""Unit tests for multi-backend search data models and SearchBackend Protocol."""

from dataclasses import FrozenInstanceError
from typing import Optional

import pytest
from pydantic import ValidationError

from src.models.case_file import CaseFile, CaseFileStatus, SearchTier
from src.models.search import (
    FacetedFilter,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from src.services.search_backend import IndexDocumentRequest, SearchBackend


# ---------------------------------------------------------------------------
# SearchTier enum
# ---------------------------------------------------------------------------

class TestSearchTier:
    def test_values(self):
        assert SearchTier.STANDARD == "standard"
        assert SearchTier.ENTERPRISE == "enterprise"

    def test_is_str_enum(self):
        assert isinstance(SearchTier.STANDARD, str)

    def test_all_values(self):
        assert {t.value for t in SearchTier} == {"standard", "enterprise"}


# ---------------------------------------------------------------------------
# CaseFile with search_tier
# ---------------------------------------------------------------------------

class TestCaseFileSearchTier:
    def _make(self, **overrides):
        from datetime import datetime, timezone
        defaults = dict(
            case_id="c-1",
            topic_name="Test",
            description="desc",
            created_at=datetime.now(timezone.utc),
            s3_prefix="cases/c-1/",
            neptune_subgraph_label="Entity_c-1",
        )
        defaults.update(overrides)
        return CaseFile(**defaults)

    def test_default_tier_is_standard(self):
        cf = self._make()
        assert cf.search_tier == SearchTier.STANDARD

    def test_explicit_standard(self):
        cf = self._make(search_tier="standard")
        assert cf.search_tier == SearchTier.STANDARD

    def test_explicit_enterprise(self):
        cf = self._make(search_tier="enterprise")
        assert cf.search_tier == SearchTier.ENTERPRISE

    def test_invalid_tier_rejected(self):
        with pytest.raises(ValidationError):
            self._make(search_tier="premium")


# ---------------------------------------------------------------------------
# FacetedFilter
# ---------------------------------------------------------------------------

class TestFacetedFilter:
    def test_all_none_by_default(self):
        f = FacetedFilter()
        assert f.date_from is None
        assert f.date_to is None
        assert f.person is None
        assert f.document_type is None
        assert f.entity_type is None

    def test_partial_fields(self):
        f = FacetedFilter(person="John Doe", document_type="transcript")
        assert f.person == "John Doe"
        assert f.document_type == "transcript"
        assert f.date_from is None

    def test_all_fields(self):
        f = FacetedFilter(
            date_from="2024-01-01",
            date_to="2024-12-31",
            person="Jane",
            document_type="report",
            entity_type="person",
        )
        assert f.date_from == "2024-01-01"
        assert f.entity_type == "person"


# ---------------------------------------------------------------------------
# SearchRequest
# ---------------------------------------------------------------------------

class TestSearchRequest:
    def test_defaults(self):
        r = SearchRequest(query="ancient aliens")
        assert r.search_mode == "semantic"
        assert r.filters is None
        assert r.top_k == 10

    def test_custom_values(self):
        r = SearchRequest(
            query="pyramids",
            search_mode="hybrid",
            filters=FacetedFilter(person="Erich"),
            top_k=25,
        )
        assert r.search_mode == "hybrid"
        assert r.filters.person == "Erich"
        assert r.top_k == 25

    def test_top_k_min_bound(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="q", top_k=0)

    def test_top_k_max_bound(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="q", top_k=101)


# ---------------------------------------------------------------------------
# SearchResponse
# ---------------------------------------------------------------------------

class TestSearchResponse:
    def test_valid(self):
        result = SearchResult(
            document_id="d-1",
            passage="text",
            relevance_score=0.9,
            source_document_ref="doc-1",
        )
        resp = SearchResponse(
            results=[result],
            search_tier="enterprise",
            available_modes=["semantic", "keyword", "hybrid"],
        )
        assert len(resp.results) == 1
        assert resp.search_tier == "enterprise"
        assert "hybrid" in resp.available_modes

    def test_empty_results(self):
        resp = SearchResponse(
            results=[],
            search_tier="standard",
            available_modes=["semantic"],
        )
        assert resp.results == []


# ---------------------------------------------------------------------------
# IndexDocumentRequest
# ---------------------------------------------------------------------------

class TestIndexDocumentRequest:
    def test_create(self):
        req = IndexDocumentRequest(
            document_id="d-1",
            case_file_id="c-1",
            text="some text",
            embedding=[0.1, 0.2, 0.3],
            metadata={"source": "test.txt"},
        )
        assert req.document_id == "d-1"
        assert req.embedding == [0.1, 0.2, 0.3]
        assert req.metadata == {"source": "test.txt"}

    def test_default_metadata(self):
        req = IndexDocumentRequest(
            document_id="d-1",
            case_file_id="c-1",
            text="text",
            embedding=[],
        )
        assert req.metadata == {}


# ---------------------------------------------------------------------------
# SearchBackend Protocol
# ---------------------------------------------------------------------------

class TestSearchBackendProtocol:
    def test_conforming_class_is_instance(self):
        """A class implementing all required methods satisfies the Protocol."""

        class _FakeBackend:
            def index_documents(self, case_id, documents):
                return 0

            def search(self, case_id, query, *, mode="semantic",
                       embedding=None, filters=None, top_k=10):
                return []

            def delete_documents(self, case_id, document_ids=None):
                return 0

            @property
            def supported_modes(self):
                return ["semantic"]

        assert isinstance(_FakeBackend(), SearchBackend)

    def test_non_conforming_class_is_not_instance(self):
        """A class missing methods does not satisfy the Protocol."""

        class _Incomplete:
            def search(self, case_id, query):
                return []

        assert not isinstance(_Incomplete(), SearchBackend)
