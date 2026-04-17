"""Unit tests for Chat Lambda handler and ChatService.

Tests cover:
- dispatch_handler routing
- send_message_handler request validation and delegation
- get_history_handler
- share_finding_handler
- ChatService.classify_intent for all command types
- ChatService._extract_citations
- ChatService._build_prompt
- ChatService._suggest_actions
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.chat_service import ChatService, INTENT_PATTERNS


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _api_event(body=None, path_params=None, query_params=None, method="POST", resource=""):
    """Build a minimal API Gateway proxy event."""
    event = {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": path_params or {},
        "queryStringParameters": query_params,
        "body": json.dumps(body) if body else None,
        "requestContext": {"requestId": "test-req-id"},
    }
    return event


def _make_chat_service():
    """Create a ChatService with mocked dependencies."""
    return ChatService(
        aurora_cm=MagicMock(),
        bedrock_client=MagicMock(),
        opensearch_endpoint="",
        neptune_endpoint="",
        neptune_port="8182",
        default_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    )


# -----------------------------------------------------------------------
# ChatService.classify_intent
# -----------------------------------------------------------------------

class TestClassifyIntent:
    def test_summarize_case(self):
        assert ChatService.classify_intent("Summarize this case") == "summarize"

    def test_summarize_case_brief(self):
        assert ChatService.classify_intent("Generate a case brief") == "summarize"

    def test_who_is(self):
        assert ChatService.classify_intent("Who is John Smith?") == "who_is"

    def test_connections_between(self):
        assert ChatService.classify_intent("Find connections between Alice and Bob") == "connections"

    def test_links_between(self):
        assert ChatService.classify_intent("What are the links between X and Y?") == "connections"

    def test_documents_mention(self):
        assert ChatService.classify_intent("What documents mention offshore accounts?") == "documents_mention"

    def test_flag_suspicious(self):
        assert ChatService.classify_intent("Flag this as suspicious") == "flag"

    def test_timeline(self):
        assert ChatService.classify_intent("Generate a timeline") == "timeline"

    def test_show_timeline(self):
        assert ChatService.classify_intent("Show timeline of events") == "timeline"

    def test_whats_missing(self):
        assert ChatService.classify_intent("What's missing from the evidence?") == "whats_missing"

    def test_gap_analysis(self):
        assert ChatService.classify_intent("Run a gap analysis") == "whats_missing"

    def test_subpoena_list(self):
        assert ChatService.classify_intent("Draft a subpoena list") == "subpoena_list"

    def test_general_question(self):
        assert ChatService.classify_intent("Tell me about the financial records") == "question"

    def test_empty_message(self):
        assert ChatService.classify_intent("") == "question"


# -----------------------------------------------------------------------
# ChatService._extract_citations
# -----------------------------------------------------------------------

class TestExtractCitations:
    def test_extracts_source_references(self):
        doc_context = [
            {"document_id": "doc-1", "document_name": "Report.pdf", "page_number": 5, "content": "Some content here"},
            {"document_id": "doc-2", "document_name": "Evidence.pdf", "page_number": 12, "content": "Other content"},
        ]
        response = "According to [Source 1], the suspect was seen. Also [Source 2] confirms this."
        citations = ChatService._extract_citations(response, doc_context)

        assert len(citations) == 2
        assert citations[0]["document_id"] == "doc-1"
        assert citations[0]["source_index"] == 1
        assert citations[1]["document_id"] == "doc-2"

    def test_no_citations_when_no_sources(self):
        response = "This is a general response with no source references."
        citations = ChatService._extract_citations(response, [])
        assert citations == []

    def test_ignores_out_of_range_sources(self):
        doc_context = [{"document_id": "doc-1", "document_name": "A.pdf", "content": "text"}]
        response = "See [Source 1] and [Source 5]."
        citations = ChatService._extract_citations(response, doc_context)
        assert len(citations) == 1
        assert citations[0]["source_index"] == 1

    def test_deduplicates_citations(self):
        doc_context = [{"document_id": "doc-1", "document_name": "A.pdf", "content": "text"}]
        response = "[Source 1] says X. As noted in [Source 1], Y."
        citations = ChatService._extract_citations(response, doc_context)
        assert len(citations) == 1


# -----------------------------------------------------------------------
# ChatService._suggest_actions
# -----------------------------------------------------------------------

class TestSuggestActions:
    def test_question_suggestions(self):
        actions = ChatService._suggest_actions("question", "some response")
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_summarize_suggestions(self):
        actions = ChatService._suggest_actions("summarize", "case brief")
        assert "Generate timeline" in actions

    def test_unknown_intent_defaults(self):
        actions = ChatService._suggest_actions("unknown_intent", "response")
        assert isinstance(actions, list)
        assert len(actions) > 0


# -----------------------------------------------------------------------
# Chat Lambda dispatch_handler
# -----------------------------------------------------------------------

class TestDispatchHandler:
    def test_options_returns_200(self):
        from src.lambdas.api.chat import dispatch_handler
        event = _api_event(method="OPTIONS", resource="/case-files/{id}/chat")
        result = dispatch_handler(event, None)
        assert result["statusCode"] == 200

    def test_unknown_route_returns_404(self):
        from src.lambdas.api.chat import dispatch_handler
        event = _api_event(method="DELETE", resource="/case-files/{id}/chat")
        result = dispatch_handler(event, None)
        assert result["statusCode"] == 404

    def test_routes_post_chat(self):
        from src.lambdas.api.chat import dispatch_handler
        event = _api_event(
            method="POST",
            resource="/case-files/{id}/chat",
            body={"message": "test"},
            path_params={"id": "case-001"},
        )
        with patch("src.lambdas.api.chat._build_chat_service") as mock_build:
            mock_svc = MagicMock()
            mock_svc.send_message.return_value = {
                "response": "AI answer",
                "citations": [],
                "conversation_id": "conv-1",
                "intent": "question",
                "suggested_actions": [],
            }
            mock_build.return_value = mock_svc
            result = dispatch_handler(event, None)
            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert body["response"] == "AI answer"

    def test_routes_get_history(self):
        from src.lambdas.api.chat import dispatch_handler
        event = _api_event(
            method="GET",
            resource="/case-files/{id}/chat/history",
            path_params={"id": "case-001"},
        )
        with patch("src.lambdas.api.chat._build_chat_service") as mock_build:
            mock_svc = MagicMock()
            mock_svc.get_history.return_value = []
            mock_build.return_value = mock_svc
            result = dispatch_handler(event, None)
            assert result["statusCode"] == 200

    def test_routes_post_share(self):
        from src.lambdas.api.chat import dispatch_handler
        event = _api_event(
            method="POST",
            resource="/case-files/{id}/chat/share",
            body={"message_content": "Important finding", "user_id": "agent-1"},
            path_params={"id": "case-001"},
        )
        with patch("src.lambdas.api.chat._build_chat_service") as mock_build:
            mock_svc = MagicMock()
            mock_svc.share_finding.return_value = {
                "finding_id": "f-1",
                "case_id": "case-001",
                "user_id": "agent-1",
                "finding_type": "chat_finding",
                "content": "Important finding",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
            mock_build.return_value = mock_svc
            result = dispatch_handler(event, None)
            assert result["statusCode"] == 201


# -----------------------------------------------------------------------
# send_message_handler validation
# -----------------------------------------------------------------------

class TestSendMessageHandler:
    def test_missing_case_id(self):
        from src.lambdas.api.chat import send_message_handler
        event = _api_event(body={"message": "hello"}, path_params={})
        result = send_message_handler(event, None)
        assert result["statusCode"] == 400

    def test_missing_message(self):
        from src.lambdas.api.chat import send_message_handler
        event = _api_event(body={}, path_params={"id": "case-001"})
        result = send_message_handler(event, None)
        assert result["statusCode"] == 400

    def test_empty_message(self):
        from src.lambdas.api.chat import send_message_handler
        event = _api_event(body={"message": "  "}, path_params={"id": "case-001"})
        result = send_message_handler(event, None)
        assert result["statusCode"] == 400

    @patch("src.lambdas.api.chat._build_chat_service")
    def test_success(self, mock_build):
        from src.lambdas.api.chat import send_message_handler
        mock_svc = MagicMock()
        mock_svc.send_message.return_value = {
            "response": "answer",
            "citations": [],
            "conversation_id": "c-1",
            "intent": "question",
            "suggested_actions": [],
        }
        mock_build.return_value = mock_svc
        event = _api_event(
            body={"message": "Who is John?", "conversation_id": "c-1"},
            path_params={"id": "case-001"},
        )
        result = send_message_handler(event, None)
        assert result["statusCode"] == 200
        mock_svc.send_message.assert_called_once()


# -----------------------------------------------------------------------
# get_history_handler validation
# -----------------------------------------------------------------------

class TestGetHistoryHandler:
    def test_missing_case_id(self):
        from src.lambdas.api.chat import get_history_handler
        event = _api_event(method="GET", path_params={})
        result = get_history_handler(event, None)
        assert result["statusCode"] == 400

    @patch("src.lambdas.api.chat._build_chat_service")
    def test_success_with_default_limit(self, mock_build):
        from src.lambdas.api.chat import get_history_handler
        mock_svc = MagicMock()
        mock_svc.get_history.return_value = [{"conversation_id": "c-1", "messages": []}]
        mock_build.return_value = mock_svc
        event = _api_event(method="GET", path_params={"id": "case-001"})
        result = get_history_handler(event, None)
        assert result["statusCode"] == 200
        mock_svc.get_history.assert_called_once_with(case_id="case-001", limit=50)


# -----------------------------------------------------------------------
# share_finding_handler validation
# -----------------------------------------------------------------------

class TestShareFindingHandler:
    def test_missing_case_id(self):
        from src.lambdas.api.chat import share_finding_handler
        event = _api_event(body={"message_content": "finding"}, path_params={})
        result = share_finding_handler(event, None)
        assert result["statusCode"] == 400

    def test_missing_message_content(self):
        from src.lambdas.api.chat import share_finding_handler
        event = _api_event(body={}, path_params={"id": "case-001"})
        result = share_finding_handler(event, None)
        assert result["statusCode"] == 400

    @patch("src.lambdas.api.chat._build_chat_service")
    def test_success(self, mock_build):
        from src.lambdas.api.chat import share_finding_handler
        mock_svc = MagicMock()
        mock_svc.share_finding.return_value = {
            "finding_id": "f-1",
            "case_id": "case-001",
            "user_id": "investigator",
            "finding_type": "chat_finding",
            "content": "Important finding",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        mock_build.return_value = mock_svc
        event = _api_event(
            body={"message_content": "Important finding"},
            path_params={"id": "case-001"},
        )
        result = share_finding_handler(event, None)
        assert result["statusCode"] == 201
