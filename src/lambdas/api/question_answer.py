"""API Lambda handler for progressive intelligence question-answer drilldown.

Endpoint:
    POST /case-files/{id}/question-answer — generate Level 1/2/3 answers
"""

import json
import logging
import os

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

VALID_LEVELS = {1, 2, 3}


def _build_question_answer_service():
    """Construct a QuestionAnswerService with dependencies from environment."""
    import boto3

    from db.connection import ConnectionManager
    from services.question_answer_service import QuestionAnswerService

    aurora_cm = ConnectionManager()
    bedrock_client = boto3.client("bedrock-runtime")

    return QuestionAnswerService(
        aurora_cm=aurora_cm,
        bedrock_client=bedrock_client,
        neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
        neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
        opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT", ""),
    )


# ------------------------------------------------------------------
# POST /case-files/{id}/question-answer
# ------------------------------------------------------------------

@with_access_control
def question_answer_handler(event, context):
    """Generate a progressive intelligence answer for an investigative question."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))

        entity_name = body.get("entity_name", "")
        if not entity_name:
            return error_response(400, "VALIDATION_ERROR", "Missing 'entity_name' in request body", event)

        question = body.get("question", "")
        if not question or not question.strip():
            return error_response(400, "VALIDATION_ERROR", "Missing or empty 'question' in request body", event)

        level = body.get("level", 2)
        if not isinstance(level, int) or level not in VALID_LEVELS:
            return error_response(
                400, "VALIDATION_ERROR",
                f"Invalid 'level': {level}. Must be 1, 2, or 3.", event,
            )

        entity_type = body.get("entity_type")
        neighbors = body.get("neighbors")

        service = _build_question_answer_service()
        result = service.answer_question(
            case_id=case_id,
            entity_name=entity_name,
            question=question.strip(),
            level=level,
            entity_type=entity_type,
            neighbors=neighbors,
        )

        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Question-answer handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
