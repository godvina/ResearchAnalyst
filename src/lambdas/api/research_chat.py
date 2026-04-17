"""API Lambda handler for conversational external research.

Endpoint:
    POST /case-files/{id}/research/chat — start or continue a research conversation
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_research_service():
    """Construct a ConversationalResearchService with dependencies from environment."""
    import boto3
    from botocore.config import Config

    from db.connection import ConnectionManager
    from services.ai_research_agent import AIResearchAgent
    from services.conversational_research_service import ConversationalResearchService

    aurora_cm = ConnectionManager()
    cfg = Config(read_timeout=120, connect_timeout=10,
                 retries={"max_attempts": 2, "mode": "adaptive"})
    bedrock_client = boto3.client("bedrock-runtime", config=cfg)
    research_agent = AIResearchAgent(bedrock_client=bedrock_client)

    return ConversationalResearchService(
        aurora_cm=aurora_cm,
        bedrock_client=bedrock_client,
        research_agent=research_agent,
    )


def research_chat_handler(event, context):
    """Handle POST /case-files/{id}/research/chat.

    Starts a new research conversation (no conversation_id) or continues
    an existing one (with conversation_id).
    """
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))

        # --- Validate required fields ---
        message = (body.get("message") or "").strip()
        subject = body.get("subject")

        missing = []
        if not message:
            missing.append("message")
        if not subject or not isinstance(subject, dict) or not subject.get("name"):
            missing.append("subject (object with name and type)")
        if missing:
            return error_response(
                400, "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing)}", event,
            )

        conversation_id = body.get("conversation_id")

        service = _build_research_service()

        if conversation_id:
            # Continue existing conversation
            result = service.continue_conversation(
                case_id=case_id,
                conversation_id=conversation_id,
                message=message,
            )
        else:
            # Start new conversation
            result = service.start_conversation(
                case_id=case_id,
                subject=subject,
            )

        return success_response(result, 200, event)

    except ValueError as exc:
        # Raised by continue_conversation when conversation_id not found
        return error_response(404, "CONVERSATION_NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Research chat failed")
        return error_response(500, "RESEARCH_FAILED", str(exc), event)
