"""Unit tests for SemanticSearchService with mocked Bedrock responses."""

import json
import uuid
from unittest.mock import MagicMock, call, PropertyMock

import pytest

from src.models.case_file import CaseFile, CaseFileStatus, SearchTier
from src.models.search import AnalysisSummary, FacetedFilter, SearchResult
from src.services.semantic_search_service import (
    DEFAULT_TOP_K,
    SemanticSearchService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CASE_ID = "case-001"
KB_ID = "kb-test-123"
AGENT_ID = "agent-test-456"
AGENT_ALIAS = "alias-test"


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture(autouse=True)
def _enable_opensearch():
    """Enable OpenSearch feature flag for all tests in this module."""
    import src.services.semantic_search_service as sss_mod
    original = sss_mod._OPENSEARCH_ENABLED
    sss_mod._OPENSEARCH_ENABLED = True
    yield
    sss_mod._OPENSEARCH_ENABLED = original


@pytest.fixture
def service(mock_client):
    return SemanticSearchService(
        bedrock_agent_runtime_client=mock_client,
        knowledge_base_id=KB_ID,
        agent_id=AGENT_ID,
        agent_alias_id=AGENT_ALIAS,
    )


def _make_retrieval_result(
    doc_id: str = "doc-1",
    passage: str = "Ancient structures found in Peru.",
    score: float = 0.92,
    s3_uri: str = "s3://bucket/cases/case-001/raw/doc-1.txt",
    context: str = "Surrounding paragraph about Peru.",
) -> dict:
    return {
        "content": {"text": passage},
        "score": score,
        "location": {"s3Location": {"uri": s3_uri}},
        "metadata": {
            "document_id": doc_id,
            "surrounding_context": context,
        },
    }


def _make_agent_event_stream(text: str) -> list[dict]:
    """Build a mock Bedrock Agent EventStream with a single completion chunk."""
    return [{"chunk": {"bytes": text.encode("utf-8")}}]


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestServiceInit:
    def test_accepts_dependencies(self, mock_client):
        svc = SemanticSearchService(
            bedrock_agent_runtime_client=mock_client,
            knowledge_base_id=KB_ID,
            agent_id=AGENT_ID,
            agent_alias_id=AGENT_ALIAS,
        )
        assert svc._client is mock_client
        assert svc._knowledge_base_id == KB_ID
        assert svc._agent_id == AGENT_ID
        assert svc._agent_alias_id == AGENT_ALIAS

    def test_default_agent_alias(self, mock_client):
        svc = SemanticSearchService(
            bedrock_agent_runtime_client=mock_client,
            knowledge_base_id=KB_ID,
        )
        assert svc._agent_id == ""


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestSearch:
    def test_returns_results_sorted_by_relevance_descending(
        self, service, mock_client
    ):
        mock_client.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieval_result(doc_id="doc-low", score=0.3),
                _make_retrieval_result(doc_id="doc-high", score=0.95),
                _make_retrieval_result(doc_id="doc-mid", score=0.7),
            ]
        }

        results = service.search(case_id=CASE_ID, query="ancient structures")

        assert len(results) == 3
        assert results[0].document_id == "doc-high"
        assert results[1].document_id == "doc-mid"
        assert results[2].document_id == "doc-low"
        assert results[0].relevance_score >= results[1].relevance_score
        assert results[1].relevance_score >= results[2].relevance_score

    def test_each_result_has_complete_fields(self, service, mock_client):
        mock_client.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieval_result(
                    doc_id="doc-1",
                    passage="Test passage",
                    score=0.85,
                    s3_uri="s3://bucket/doc-1.txt",
                    context="Context text",
                ),
            ]
        }

        results = service.search(case_id=CASE_ID, query="test")

        assert len(results) == 1
        r = results[0]
        assert r.document_id == "doc-1"
        assert r.passage == "Test passage"
        assert r.relevance_score == 0.85
        assert r.source_document_ref == "s3://bucket/doc-1.txt"
        assert r.surrounding_context == "Context text"

    def test_passes_case_id_filter_to_retrieve(self, service, mock_client):
        mock_client.retrieve.return_value = {"retrievalResults": []}

        service.search(case_id=CASE_ID, query="query")

        mock_client.retrieve.assert_called_once()
        call_kwargs = mock_client.retrieve.call_args[1]
        assert call_kwargs["knowledgeBaseId"] == KB_ID
        assert call_kwargs["retrievalQuery"] == {"text": "query"}
        vec_config = call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]
        assert vec_config["filter"]["equals"]["key"] == "case_file_id"
        assert vec_config["filter"]["equals"]["value"] == CASE_ID

    def test_respects_top_k_parameter(self, service, mock_client):
        mock_client.retrieve.return_value = {"retrievalResults": []}

        service.search(case_id=CASE_ID, query="query", top_k=5)

        call_kwargs = mock_client.retrieve.call_args[1]
        vec_config = call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]
        assert vec_config["numberOfResults"] == 5

    def test_uses_default_top_k(self, service, mock_client):
        mock_client.retrieve.return_value = {"retrievalResults": []}

        service.search(case_id=CASE_ID, query="query")

        call_kwargs = mock_client.retrieve.call_args[1]
        vec_config = call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]
        assert vec_config["numberOfResults"] == DEFAULT_TOP_K

    def test_empty_results(self, service, mock_client):
        mock_client.retrieve.return_value = {"retrievalResults": []}

        results = service.search(case_id=CASE_ID, query="nothing")

        assert results == []

    def test_clamps_score_above_one(self, service, mock_client):
        mock_client.retrieve.return_value = {
            "retrievalResults": [_make_retrieval_result(score=1.5)]
        }

        results = service.search(case_id=CASE_ID, query="test")

        assert results[0].relevance_score == 1.0

    def test_clamps_negative_score(self, service, mock_client):
        mock_client.retrieve.return_value = {
            "retrievalResults": [_make_retrieval_result(score=-0.3)]
        }

        results = service.search(case_id=CASE_ID, query="test")

        assert results[0].relevance_score == 0.0

    def test_handles_missing_metadata_fields(self, service, mock_client):
        mock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "some passage"},
                    "score": 0.8,
                    "location": {},
                    "metadata": {},
                }
            ]
        }

        results = service.search(case_id=CASE_ID, query="test")

        assert len(results) == 1
        assert results[0].document_id == ""
        assert results[0].source_document_ref == ""
        assert results[0].surrounding_context == ""


# ---------------------------------------------------------------------------
# analyze_entity()
# ---------------------------------------------------------------------------


class TestAnalyzeEntity:
    def _setup_agent_and_search(self, mock_client, summary_text, confidence=0.85):
        """Configure mock for both invoke_agent and retrieve calls."""
        agent_body = json.dumps({"summary": summary_text, "confidence": confidence})
        mock_client.invoke_agent.return_value = {
            "completion": _make_agent_event_stream(agent_body),
        }
        mock_client.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieval_result(doc_id="doc-support", score=0.9),
            ]
        }

    def test_returns_analysis_summary(self, service, mock_client):
        self._setup_agent_and_search(mock_client, "Entity analysis text", 0.85)

        result = service.analyze_entity(case_id=CASE_ID, entity_name="Erich von Däniken")

        assert isinstance(result, AnalysisSummary)
        assert result.subject == "Erich von Däniken"
        assert result.summary == "Entity analysis text"
        assert result.confidence == 0.85

    def test_includes_supporting_passages(self, service, mock_client):
        self._setup_agent_and_search(mock_client, "Analysis", 0.7)

        result = service.analyze_entity(case_id=CASE_ID, entity_name="Nazca Lines")

        assert len(result.supporting_passages) == 1
        assert result.supporting_passages[0].document_id == "doc-support"

    def test_invokes_agent_with_entity_prompt(self, service, mock_client):
        self._setup_agent_and_search(mock_client, "Analysis", 0.7)

        service.analyze_entity(case_id=CASE_ID, entity_name="Puma Punku")

        mock_client.invoke_agent.assert_called_once()
        call_kwargs = mock_client.invoke_agent.call_args[1]
        assert call_kwargs["agentId"] == AGENT_ID
        assert call_kwargs["agentAliasId"] == AGENT_ALIAS
        assert "Puma Punku" in call_kwargs["inputText"]
        assert CASE_ID in call_kwargs["inputText"]

    def test_handles_non_json_agent_response(self, service, mock_client):
        """When agent returns plain text instead of JSON, use it as summary."""
        mock_client.invoke_agent.return_value = {
            "completion": _make_agent_event_stream("Plain text analysis"),
        }
        mock_client.retrieve.return_value = {"retrievalResults": []}

        result = service.analyze_entity(case_id=CASE_ID, entity_name="Test Entity")

        assert result.summary == "Plain text analysis"
        assert result.confidence == 0.5  # default fallback

    def test_clamps_confidence_to_valid_range(self, service, mock_client):
        self._setup_agent_and_search(mock_client, "Analysis", 1.5)

        result = service.analyze_entity(case_id=CASE_ID, entity_name="Test")

        assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# analyze_pattern()
# ---------------------------------------------------------------------------


class TestAnalyzePattern:
    def _setup_agent_and_search(self, mock_client, summary_text, confidence=0.75):
        agent_body = json.dumps({"summary": summary_text, "confidence": confidence})
        mock_client.invoke_agent.return_value = {
            "completion": _make_agent_event_stream(agent_body),
        }
        mock_client.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieval_result(doc_id="doc-pattern", score=0.88),
            ]
        }

    def test_returns_analysis_summary(self, service, mock_client):
        self._setup_agent_and_search(mock_client, "Pattern analysis text", 0.75)

        result = service.analyze_pattern(case_id=CASE_ID, pattern_id="pat-001")

        assert isinstance(result, AnalysisSummary)
        assert result.subject == "pat-001"
        assert result.summary == "Pattern analysis text"
        assert result.confidence == 0.75

    def test_includes_supporting_passages(self, service, mock_client):
        self._setup_agent_and_search(mock_client, "Analysis", 0.8)

        result = service.analyze_pattern(case_id=CASE_ID, pattern_id="pat-002")

        assert len(result.supporting_passages) == 1
        assert result.supporting_passages[0].document_id == "doc-pattern"

    def test_invokes_agent_with_pattern_prompt(self, service, mock_client):
        self._setup_agent_and_search(mock_client, "Analysis", 0.8)

        service.analyze_pattern(case_id=CASE_ID, pattern_id="pat-003")

        mock_client.invoke_agent.assert_called_once()
        call_kwargs = mock_client.invoke_agent.call_args[1]
        assert "pat-003" in call_kwargs["inputText"]
        assert CASE_ID in call_kwargs["inputText"]

    def test_handles_non_json_agent_response(self, service, mock_client):
        mock_client.invoke_agent.return_value = {
            "completion": _make_agent_event_stream("Freeform pattern analysis"),
        }
        mock_client.retrieve.return_value = {"retrievalResults": []}

        result = service.analyze_pattern(case_id=CASE_ID, pattern_id="pat-004")

        assert result.summary == "Freeform pattern analysis"
        assert result.confidence == 0.5


# ---------------------------------------------------------------------------
# _collect_agent_completion()
# ---------------------------------------------------------------------------


class TestCollectAgentCompletion:
    def test_concatenates_multiple_chunks(self):
        response = {
            "completion": [
                {"chunk": {"bytes": b"Hello "}},
                {"chunk": {"bytes": b"World"}},
            ]
        }

        text = SemanticSearchService._collect_agent_completion(response)

        assert text == "Hello World"

    def test_empty_event_stream(self):
        response = {"completion": []}

        text = SemanticSearchService._collect_agent_completion(response)

        assert text == ""

    def test_skips_events_without_bytes(self):
        response = {
            "completion": [
                {"chunk": {"bytes": b"Valid"}},
                {"chunk": {}},
                {"other": "data"},
            ]
        }

        text = SemanticSearchService._collect_agent_completion(response)

        assert text == "Valid"


# ---------------------------------------------------------------------------
# Fixtures for multi-backend tests
# ---------------------------------------------------------------------------

def _make_case_file(search_tier=SearchTier.STANDARD, **overrides):
    from datetime import datetime, timezone
    defaults = dict(
        case_id="case-001",
        topic_name="Test",
        description="Test case",
        status=CaseFileStatus.CREATED,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        s3_prefix="cases/case-001/",
        neptune_subgraph_label="Entity_case-001",
        search_tier=search_tier,
    )
    defaults.update(overrides)
    return CaseFile(**defaults)


@pytest.fixture
def mock_backend_factory():
    factory = MagicMock()
    return factory


@pytest.fixture
def mock_case_file_service():
    svc = MagicMock()
    return svc


@pytest.fixture
def mock_bedrock_client():
    client = MagicMock()
    return client


@pytest.fixture
def multi_backend_service(mock_client, mock_backend_factory, mock_case_file_service, mock_bedrock_client):
    return SemanticSearchService(
        bedrock_agent_runtime_client=mock_client,
        knowledge_base_id=KB_ID,
        agent_id=AGENT_ID,
        agent_alias_id=AGENT_ALIAS,
        backend_factory=mock_backend_factory,
        case_file_service=mock_case_file_service,
        bedrock_client=mock_bedrock_client,
        embedding_model_id="amazon.titan-embed-text-v2:0",
        enterprise_knowledge_base_id="kb-enterprise-456",
    )


# ---------------------------------------------------------------------------
# Multi-backend search tests
# ---------------------------------------------------------------------------


class TestMultiBackendSearch:
    def test_delegates_to_backend_for_semantic_mode(
        self, multi_backend_service, mock_backend_factory, mock_case_file_service, mock_bedrock_client
    ):
        case_file = _make_case_file(search_tier=SearchTier.STANDARD)
        mock_case_file_service.get_case_file.return_value = case_file

        mock_backend = MagicMock()
        mock_backend.search.return_value = [
            SearchResult(document_id="doc-1", passage="found", relevance_score=0.9, source_document_ref="s3://...")
        ]
        mock_backend_factory.get_backend.return_value = mock_backend

        # Mock embedding generation
        mock_bedrock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({"embedding": [0.1] * 1536}).encode()))
        }

        results = multi_backend_service.search(case_id="case-001", query="test query")

        assert len(results) == 1
        mock_backend_factory.validate_search_mode.assert_called_once_with(SearchTier.STANDARD, "semantic")
        mock_backend.search.assert_called_once()

    def test_generates_embedding_for_semantic_mode(
        self, multi_backend_service, mock_backend_factory, mock_case_file_service, mock_bedrock_client
    ):
        case_file = _make_case_file(search_tier=SearchTier.ENTERPRISE)
        mock_case_file_service.get_case_file.return_value = case_file

        mock_backend = MagicMock()
        mock_backend.search.return_value = []
        mock_backend_factory.get_backend.return_value = mock_backend

        embedding = [0.5] * 1536
        mock_bedrock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({"embedding": embedding}).encode()))
        }

        multi_backend_service.search(case_id="case-001", query="test", mode="semantic")

        # Verify embedding was passed to backend
        call_kwargs = mock_backend.search.call_args
        assert call_kwargs[1]["embedding"] == embedding

    def test_generates_embedding_for_hybrid_mode(
        self, multi_backend_service, mock_backend_factory, mock_case_file_service, mock_bedrock_client
    ):
        case_file = _make_case_file(search_tier=SearchTier.ENTERPRISE)
        mock_case_file_service.get_case_file.return_value = case_file

        mock_backend = MagicMock()
        mock_backend.search.return_value = []
        mock_backend_factory.get_backend.return_value = mock_backend

        embedding = [0.3] * 1536
        mock_bedrock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({"embedding": embedding}).encode()))
        }

        multi_backend_service.search(case_id="case-001", query="test", mode="hybrid")

        call_kwargs = mock_backend.search.call_args
        assert call_kwargs[1]["embedding"] == embedding

    def test_no_embedding_for_keyword_mode(
        self, multi_backend_service, mock_backend_factory, mock_case_file_service, mock_bedrock_client
    ):
        case_file = _make_case_file(search_tier=SearchTier.ENTERPRISE)
        mock_case_file_service.get_case_file.return_value = case_file

        mock_backend = MagicMock()
        mock_backend.search.return_value = []
        mock_backend_factory.get_backend.return_value = mock_backend

        multi_backend_service.search(case_id="case-001", query="test", mode="keyword")

        # Embedding should be None for keyword mode
        call_kwargs = mock_backend.search.call_args
        assert call_kwargs[1]["embedding"] is None
        mock_bedrock_client.invoke_model.assert_not_called()

    def test_rejects_filters_on_standard_tier(
        self, multi_backend_service, mock_backend_factory, mock_case_file_service
    ):
        case_file = _make_case_file(search_tier=SearchTier.STANDARD)
        mock_case_file_service.get_case_file.return_value = case_file

        with pytest.raises(ValueError, match="not available for the standard tier"):
            multi_backend_service.search(
                case_id="case-001", query="test",
                filters=FacetedFilter(person="John"),
            )

    def test_passes_filters_to_enterprise_backend(
        self, multi_backend_service, mock_backend_factory, mock_case_file_service, mock_bedrock_client
    ):
        case_file = _make_case_file(search_tier=SearchTier.ENTERPRISE)
        mock_case_file_service.get_case_file.return_value = case_file

        mock_backend = MagicMock()
        mock_backend.search.return_value = []
        mock_backend_factory.get_backend.return_value = mock_backend

        mock_bedrock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({"embedding": [0.1] * 10}).encode()))
        }

        filters = FacetedFilter(person="John", document_type="report")
        multi_backend_service.search(case_id="case-001", query="test", filters=filters)

        call_kwargs = mock_backend.search.call_args
        assert call_kwargs[1]["filters"] == filters

    def test_falls_back_to_legacy_without_backend_factory(self, service, mock_client):
        """When no backend_factory is configured, uses legacy KB path."""
        mock_client.retrieve.return_value = {
            "retrievalResults": [_make_retrieval_result(doc_id="doc-legacy", score=0.8)]
        }

        results = service.search(case_id=CASE_ID, query="test")

        assert len(results) == 1
        assert results[0].document_id == "doc-legacy"
        mock_client.retrieve.assert_called_once()


# ---------------------------------------------------------------------------
# _generate_embedding tests
# ---------------------------------------------------------------------------


class TestGenerateEmbedding:
    def test_generates_embedding_successfully(self, multi_backend_service, mock_bedrock_client):
        expected = [0.1, 0.2, 0.3]
        mock_bedrock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({"embedding": expected}).encode()))
        }

        result = multi_backend_service._generate_embedding("test query")

        assert result == expected
        mock_bedrock_client.invoke_model.assert_called_once_with(
            modelId="amazon.titan-embed-text-v2:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": "test query"}),
        )

    def test_raises_runtime_error_without_bedrock_client(self, mock_client):
        svc = SemanticSearchService(
            bedrock_agent_runtime_client=mock_client,
            knowledge_base_id=KB_ID,
        )
        with pytest.raises(RuntimeError, match="Bedrock client is not configured"):
            svc._generate_embedding("test")

    def test_raises_runtime_error_on_api_failure(self, multi_backend_service, mock_bedrock_client):
        mock_bedrock_client.invoke_model.side_effect = Exception("API error")

        with pytest.raises(RuntimeError, match="Embedding generation failed"):
            multi_backend_service._generate_embedding("test")


# ---------------------------------------------------------------------------
# _resolve_kb_id tests
# ---------------------------------------------------------------------------


class TestResolveKbId:
    def test_standard_tier_returns_default_kb_id(self, multi_backend_service):
        assert multi_backend_service._resolve_kb_id(SearchTier.STANDARD) == KB_ID

    def test_enterprise_tier_returns_enterprise_kb_id(self, multi_backend_service):
        assert multi_backend_service._resolve_kb_id(SearchTier.ENTERPRISE) == "kb-enterprise-456"

    def test_enterprise_tier_falls_back_to_default_when_no_enterprise_kb(self, mock_client):
        svc = SemanticSearchService(
            bedrock_agent_runtime_client=mock_client,
            knowledge_base_id=KB_ID,
            enterprise_knowledge_base_id="",
        )
        assert svc._resolve_kb_id(SearchTier.ENTERPRISE) == KB_ID

    def test_accepts_string_tier(self, multi_backend_service):
        assert multi_backend_service._resolve_kb_id("standard") == KB_ID
        assert multi_backend_service._resolve_kb_id("enterprise") == "kb-enterprise-456"


# ---------------------------------------------------------------------------
# Constructor with new params
# ---------------------------------------------------------------------------


class TestExtendedInit:
    def test_accepts_all_new_params(self, mock_client):
        factory = MagicMock()
        case_svc = MagicMock()
        bedrock = MagicMock()

        svc = SemanticSearchService(
            bedrock_agent_runtime_client=mock_client,
            knowledge_base_id=KB_ID,
            backend_factory=factory,
            case_file_service=case_svc,
            bedrock_client=bedrock,
            embedding_model_id="custom-model",
            enterprise_knowledge_base_id="kb-ent",
        )

        assert svc._backend_factory is factory
        assert svc._case_service is case_svc
        assert svc._bedrock_client is bedrock
        assert svc._embedding_model_id == "custom-model"
        assert svc._enterprise_kb_id == "kb-ent"

    def test_new_params_default_to_none(self, mock_client):
        svc = SemanticSearchService(
            bedrock_agent_runtime_client=mock_client,
            knowledge_base_id=KB_ID,
        )
        assert svc._backend_factory is None
        assert svc._case_service is None
        assert svc._bedrock_client is None
