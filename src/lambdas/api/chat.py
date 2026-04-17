"""API Lambda handlers for the Investigative Case Assistant Chatbot.

Endpoints:
    POST /case-files/{id}/chat          — send message, get AI response with citations
    GET  /case-files/{id}/chat/history   — get conversation history
    POST /case-files/{id}/chat/share     — share finding from chat
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_chat_service():
    """Construct a ChatService with dependencies from environment."""
    import boto3

    from db.connection import ConnectionManager
    from services.chat_service import ChatService

    aurora_cm = ConnectionManager()
    bedrock_client = boto3.client("bedrock-runtime")

    return ChatService(
        aurora_cm=aurora_cm,
        bedrock_client=bedrock_client,
        opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT", ""),
        neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
        neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
        default_model_id=os.environ.get(
            "BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
        ),
    )


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/case-files/{id}/chat" and method == "POST":
        return send_message_handler(event, context)
    if resource == "/case-files/{id}/chat/history" and method == "GET":
        return get_history_handler(event, context)
    if resource == "/case-files/{id}/chat/share" and method == "POST":
        return share_finding_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# POST /case-files/{id}/chat
# ------------------------------------------------------------------

def send_message_handler(event, context):
    """Send a message to the investigative chatbot and get an AI response."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        message = body.get("message", "").strip()
        if not message:
            return error_response(400, "VALIDATION_ERROR", "Missing 'message' in request body", event)

        conversation_id = body.get("conversation_id")
        case_context = body.get("context", {})

        # Inject LLM model from pipeline config if provided in context
        if not case_context.get("llm_model_id"):
            case_context["llm_model_id"] = os.environ.get(
                "BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
            )

        service = _build_chat_service()
        result = service.send_message(
            case_id=case_id,
            message=message,
            conversation_id=conversation_id,
            context=case_context,
        )

        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Chat send_message failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/chat/history
# ------------------------------------------------------------------

def get_history_handler(event, context):
    """Get conversation history for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        params = event.get("queryStringParameters") or {}
        limit = int(params.get("limit", "50"))

        service = _build_chat_service()
        conversations = service.get_history(case_id=case_id, limit=limit)

        return success_response({"conversations": conversations}, 200, event)

    except Exception as exc:
        logger.exception("Chat get_history failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/chat/share
# ------------------------------------------------------------------

def share_finding_handler(event, context):
    """Share a chat finding — save as investigator finding attached to the case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        message_content = body.get("message_content", "").strip()
        if not message_content:
            return error_response(
                400, "VALIDATION_ERROR", "Missing 'message_content' in request body", event,
            )

        user_id = body.get("user_id", "investigator")

        service = _build_chat_service()
        result = service.share_finding(
            case_id=case_id,
            message_content=message_content,
            user_id=user_id,
        )

        return success_response(result, 201, event)

    except Exception as exc:
        logger.exception("Chat share_finding failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
