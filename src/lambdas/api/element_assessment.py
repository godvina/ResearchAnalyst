"""API Lambda handlers for Element Assessment operations.

Endpoints:
    GET    /case-files/{id}/element-assessment — return existing evidence matrix
    POST   /case-files/{id}/element-assessment — trigger new element assessment
    POST   /case-files/{id}/charging-memo      — generate charging memo via Bedrock
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/case-files/{id}/element-assessment" and method == "GET":
        return get_element_assessment_handler(event, context)
    if resource == "/case-files/{id}/element-assessment" and method == "POST":
        return post_element_assessment_handler(event, context)
    if resource == "/case-files/{id}/charging-memo" and method == "POST":
        return generate_charging_memo_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


def _build_element_assessment_service():
    """Construct an ElementAssessmentService with dependencies from environment."""
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.element_assessment_service import ElementAssessmentService
    from services.decision_workflow_service import DecisionWorkflowService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )

    import boto3
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    decision_svc = DecisionWorkflowService(aurora_cm)

    return ElementAssessmentService(
        aurora_cm=aurora_cm,
        neptune_cm=neptune_cm,
        bedrock_client=bedrock,
        decision_workflow_svc=decision_svc,
    )


# ------------------------------------------------------------------
# GET /case-files/{id}/element-assessment
# ------------------------------------------------------------------

def get_element_assessment_handler(event, context):
    """Return existing evidence matrix for a case + statute."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        params = event.get("queryStringParameters") or {}
        statute_id = params.get("statute_id", "")
        if not statute_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required query parameter: statute_id", event)

        service = _build_element_assessment_service()
        matrix = service.assess_elements(case_id, statute_id)

        return success_response(matrix.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file or statute not found", event)
    except Exception as exc:
        logger.exception("Failed to get element assessment")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/element-assessment
# ------------------------------------------------------------------

def post_element_assessment_handler(event, context):
    """Trigger a new element assessment for a case + statute."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        statute_id = body.get("statute_id", "")
        if not statute_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: statute_id", event)

        service = _build_element_assessment_service()
        matrix = service.assess_elements(case_id, statute_id)

        return success_response(matrix.model_dump(mode="json"), 201, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file or statute not found", event)
    except Exception as exc:
        logger.exception("Failed to run element assessment")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/charging-memo
# ------------------------------------------------------------------

def generate_charging_memo_handler(event, context):
    """Generate a charging memo via Bedrock with Senior_Legal_Analyst_Persona."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        statute_id = body.get("statute_id", "")
        if not statute_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: statute_id", event)

        service = _build_element_assessment_service()
        recommendation = service.draft_charging_recommendation(case_id, statute_id)

        return success_response(recommendation.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", "Case file or statute not found", event)
    except Exception as exc:
        logger.exception("Failed to generate charging memo")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
