"""API Lambda handlers for the Case Assessment Dashboard.

Endpoints:
    GET  /case-files/{id}/assessment        — get case assessment dashboard data
    POST /case-files/{id}/assessment/brief   — generate AI case brief
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_assessment_service():
    """Construct CaseAssessmentService with dependencies."""
    import boto3

    from db.connection import ConnectionManager
    from services.case_assessment_service import CaseAssessmentService

    aurora_cm = ConnectionManager()
    bedrock_client = boto3.client("bedrock-runtime")
    return CaseAssessmentService(
        aurora_cm=aurora_cm,
        bedrock_client=bedrock_client,
        neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
        neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
        opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT", ""),
    )


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/case-files/{id}/assessment" and method == "GET":
        return get_assessment_handler(event, context)
    if resource == "/case-files/{id}/assessment/brief" and method == "POST":
        return generate_brief_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# GET /case-files/{id}/assessment
# ------------------------------------------------------------------

def get_assessment_handler(event, context):
    """Get case assessment dashboard data."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        svc = _build_assessment_service()
        assessment = svc.get_assessment(case_id)
        return success_response(assessment, 200, event)

    except ValueError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("get_assessment failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/assessment/brief
# ------------------------------------------------------------------

def generate_brief_handler(event, context):
    """Generate an AI case brief."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        svc = _build_assessment_service()
        brief = svc.generate_brief(case_id)
        return success_response({"case_id": case_id, "brief": brief}, 200, event)

    except ValueError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("generate_brief failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
