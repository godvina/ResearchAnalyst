"""Unit tests for QuestionAnswerService — progressive intelligence drilldown."""

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from services.question_answer_service import (
    ANALYST_PERSONA,
    BEDROCK_MODEL_ID,
    QuestionAnswerService,
)

CASE_ID = "case-001"
ENTITY_NAME = "John Doe"
QUESTION = "What are the financial connections?"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_aurora():
    cm = MagicMock()
    cursor = MagicMock()
    cm.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    cm.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return cm


@pytest.fixture
def mock_bedrock():
    return MagicMock()


def _bedrock_response(text: str) -> dict:
    """Build a mock Bedrock invoke_model response."""
    body = json.dumps({
        "content": [{"type": "text", "text": text}],
    }).encode()
    return {"body": io.BytesIO(body)}


def _embedding_response(dims: int = 5) -> dict:
    """Build a mock Bedrock embedding response."""
    body = json.dumps({"embedding": [0.1] * dims}).encode()
    return {"body": io.BytesIO(body)}


@pytest.fixture
def service(mock_aurora, mock_bedrock):
    return QuestionAnswerService(
        aurora_cm=mock_aurora,
        bedrock_client=mock_bedrock,
        neptune_endpoint="neptune.example.com",
        neptune_port="8182",
        opensearch_endpoint="",
    )


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_accepts_dependencies(self, mock_aurora, mock_bedrock):
        svc = QuestionAnswerService(
            aurora_cm=mock_aurora,
            bedrock_client=mock_bedrock,
            neptune_endpoint="nep.example.com",
            neptune_port="8182",
            opensearch_endpoint="os.example.com",
        )
        assert svc._db is mock_aurora
        assert svc._bedrock is mock_bedrock
        assert svc._neptune_endpoint == "nep.example.com"
        assert svc._neptune_port == "8182"
        assert svc._os_endpoint == "os.example.com"


# ---------------------------------------------------------------------------
# Graceful degradation tests
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Verify the service continues when context sources fail."""

    def test_neptune_failure_proceeds_with_doc_context_only(
        self, service, mock_bedrock,
    ):
        """Neptune timeout → continues with empty graph context."""
        # Mock embedding call + Bedrock analysis call
        mock_bedrock.invoke_model.side_effect = [
            _embedding_response(),
            _bedrock_response(json.dumps({
                "analysis": "Analysis from docs only.",
                "citations": [],
            })),
        ]
        # Mock Aurora to return doc results
        cursor = service._db.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ("doc-1", "Some text about John", "report.pdf", 0.85),
        ]

        with patch.object(service, "_neptune_query", side_effect=Exception("timeout")):
            result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        assert result["level"] == 2
        assert result["analysis"]  # Should still have analysis

    def test_semantic_search_failure_proceeds_with_graph_only(
        self, service, mock_bedrock,
    ):
        """Semantic search failure → continues with empty document context."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "analysis": "Analysis from graph only.",
            "citations": [],
        }))

        with patch.object(service, "_get_graph_context", return_value=[
            {"rel": "financial", "target": "Corp A", "conf": 0.9},
        ]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        assert result["level"] == 2
        assert result["analysis"]

    def test_both_context_sources_fail_still_produces_response(
        self, service, mock_bedrock,
    ):
        """Both Neptune and search fail → Bedrock with question+entity only."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "analysis": "Based on the question alone.",
            "citations": [],
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        assert result["level"] == 2
        assert result["analysis"]

    def test_bedrock_json_parse_error_returns_partial_response(
        self, service, mock_bedrock,
    ):
        """Bedrock returns malformed JSON → graceful handling with partial response."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(
            "This is not valid JSON but still useful text."
        )

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        assert result["level"] == 2
        # Should use the raw text as analysis since JSON parse failed
        assert result["analysis"]


# ---------------------------------------------------------------------------
# Level 2 response structure tests
# ---------------------------------------------------------------------------


class TestLevel2Response:
    def test_level2_has_required_fields(self, service, mock_bedrock):
        """Level 2 response contains analysis + citations with correct structure."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "analysis": "Detailed analytical brief about the entity.",
            "citations": [
                {"document_name": "report.pdf", "relevance": "high", "excerpt": "Key finding"},
                {"document_name": "memo.txt", "relevance": "medium", "excerpt": "Supporting info"},
            ],
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        assert result["level"] == 2
        assert result["entity_name"] == ENTITY_NAME
        assert result["question"] == QUESTION
        assert isinstance(result["analysis"], str)
        assert len(result["analysis"]) > 0
        assert isinstance(result["citations"], list)
        for c in result["citations"]:
            assert "document_name" in c
            assert c["relevance"] in ("high", "medium", "low")

    def test_level2_normalizes_invalid_relevance(self, service, mock_bedrock):
        """Invalid relevance values are normalized to 'medium'."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "analysis": "Brief analysis.",
            "citations": [
                {"document_name": "doc.pdf", "relevance": "very_high", "excerpt": "text"},
            ],
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        assert result["citations"][0]["relevance"] == "medium"


# ---------------------------------------------------------------------------
# Level 3 response structure tests
# ---------------------------------------------------------------------------


class TestLevel3Response:
    def test_level3_has_all_required_sections(self, service, mock_bedrock):
        """Level 3 response contains all required sections."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "executive_summary": "Executive summary paragraph.",
            "evidence_analysis": "Detailed evidence analysis.",
            "source_citations": [
                {"document_name": "report.pdf", "relevance": "high", "excerpt": "key text", "document_id": "doc-1"},
            ],
            "confidence_assessment": {
                "level": "high",
                "justification": "Strong evidence from multiple sources.",
            },
            "recommended_next_steps": [
                "Subpoena financial records.",
                "Interview witness.",
            ],
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 3)

        assert result["level"] == 3
        assert result["entity_name"] == ENTITY_NAME
        assert result["question"] == QUESTION
        assert isinstance(result["executive_summary"], str)
        assert len(result["executive_summary"]) > 0
        assert isinstance(result["evidence_analysis"], str)
        assert len(result["evidence_analysis"]) > 0
        assert isinstance(result["source_citations"], list)
        assert isinstance(result["confidence_assessment"], dict)
        assert result["confidence_assessment"]["level"] in ("high", "medium", "low")
        assert "justification" in result["confidence_assessment"]
        assert isinstance(result["recommended_next_steps"], list)
        assert all(isinstance(s, str) for s in result["recommended_next_steps"])

    def test_level3_normalizes_invalid_confidence(self, service, mock_bedrock):
        """Invalid confidence level is normalized to 'medium'."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "executive_summary": "Summary.",
            "evidence_analysis": "Analysis.",
            "source_citations": [],
            "confidence_assessment": {"level": "very_high", "justification": "reason"},
            "recommended_next_steps": ["step 1"],
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 3)

        assert result["confidence_assessment"]["level"] == "medium"

    def test_level3_bedrock_failure_returns_structured_error(self, service, mock_bedrock):
        """Bedrock failure returns a structured error response with all fields."""
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock unavailable")

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 3)

        assert result["level"] == 3
        assert "unavailable" in result["executive_summary"].lower() or "retry" in result["executive_summary"].lower()
        assert isinstance(result["source_citations"], list)
        assert result["confidence_assessment"]["level"] == "low"
        assert isinstance(result["recommended_next_steps"], list)


# ---------------------------------------------------------------------------
# Level 1 response tests
# ---------------------------------------------------------------------------


class TestLevel1Response:
    def test_level1_returns_quick_answer(self, service, mock_bedrock):
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "answer": "Financial links trace through Corp A.",
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 1)

        assert result["level"] == 1
        assert len(result["answer"]) <= 150

    def test_level1_truncates_long_answer(self, service, mock_bedrock):
        long_answer = "A" * 200
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "answer": long_answer,
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                result = service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 1)

        assert len(result["answer"]) <= 150


# ---------------------------------------------------------------------------
# Bedrock configuration tests
# ---------------------------------------------------------------------------


class TestBedrockConfig:
    def test_uses_correct_model_id(self, service, mock_bedrock):
        """Bedrock calls use the correct model ID."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "analysis": "test", "citations": [],
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == BEDROCK_MODEL_ID

    def test_prompt_contains_analyst_persona(self, service, mock_bedrock):
        """Bedrock prompt includes the senior investigative analyst persona."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(json.dumps({
            "analysis": "test", "citations": [],
        }))

        with patch.object(service, "_get_graph_context", return_value=[]):
            with patch.object(service, "_get_document_context", return_value=[]):
                service.answer_question(CASE_ID, ENTITY_NAME, QUESTION, 2)

        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        body = json.loads(call_kwargs["body"])
        prompt_text = body["messages"][0]["content"]
        assert "senior federal investigative analyst" in prompt_text


# ---------------------------------------------------------------------------
# Context building tests
# ---------------------------------------------------------------------------


class TestContextBuilding:
    def test_graph_context_empty_when_no_neptune_endpoint(self, mock_aurora, mock_bedrock):
        """No Neptune endpoint → empty graph context."""
        svc = QuestionAnswerService(
            aurora_cm=mock_aurora,
            bedrock_client=mock_bedrock,
            neptune_endpoint="",
            neptune_port="8182",
        )
        result = svc._get_graph_context(CASE_ID, ENTITY_NAME)
        assert result == []

    def test_document_context_empty_when_no_aurora(self, mock_bedrock):
        """No Aurora connection → empty document context."""
        svc = QuestionAnswerService(
            aurora_cm=None,
            bedrock_client=mock_bedrock,
            neptune_endpoint="nep.example.com",
        )
        result = svc._get_document_context(CASE_ID, ENTITY_NAME, QUESTION)
        assert result == []

    def test_build_context_text_with_both_sources(self, service):
        """Context text includes both graph and document sections."""
        graph_ctx = [{"rel": "financial", "target": "Corp A", "conf": 0.9}]
        doc_ctx = [{"document_name": "report.pdf", "passage": "Key finding about entity."}]

        text = service._build_context_text(ENTITY_NAME, graph_ctx, doc_ctx)

        assert "KNOWLEDGE GRAPH CONTEXT" in text
        assert "Corp A" in text
        assert "DOCUMENT CONTEXT" in text
        assert "report.pdf" in text

    def test_build_context_text_with_no_sources(self, service):
        """Context text shows 'no data available' when both sources empty."""
        text = service._build_context_text(ENTITY_NAME, [], [])

        assert "No graph data available" in text
        assert "No document references available" in text


# ---------------------------------------------------------------------------
# JSON parsing tests
# ---------------------------------------------------------------------------


class TestJsonParsing:
    def test_parse_json_with_markdown_fences(self):
        """Handles Bedrock responses wrapped in markdown code fences."""
        text = '```json\n{"analysis": "test"}\n```'
        result = QuestionAnswerService._parse_json_response(text)
        assert result == {"analysis": "test"}

    def test_parse_plain_json(self):
        text = '{"analysis": "test"}'
        result = QuestionAnswerService._parse_json_response(text)
        assert result == {"analysis": "test"}

    def test_parse_invalid_json_returns_empty_dict(self):
        text = "This is not JSON"
        result = QuestionAnswerService._parse_json_response(text)
        assert result == {}
