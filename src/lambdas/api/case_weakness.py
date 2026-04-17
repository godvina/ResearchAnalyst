"""API Lambda handlers for Case Weakness Analysis operations.

Endpoints:
    GET    /case-files/{id}/case-weaknesses — return weakness analysis
"""

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

    if resource == "/case-files/{id}/case-weaknesses" and method == "GET":
        return get_case_weaknesses_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


def _build_case_weakness_service():
    """Construct a CaseWeaknessService with dependencies from environment."""
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.case_weakness_service import CaseWeaknessService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )

    import boto3
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    return CaseWeaknessService(
        aurora_cm=aurora_cm,
        neptune_cm=neptune_cm,
        bedrock_client=bedrock,
    )


# ------------------------------------------------------------------
# GET /case-files/{id}/case-weaknesses
# ------------------------------------------------------------------

def get_case_weaknesses_handler(event, context):
    """Return weakness analysis for a case, with optional statute_id filter."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        params = event.get("queryStringParameters") or {}
        statute_id = params.get("statute_id")

        service = _build_case_weakness_service()
        weaknesses = service.analyze_weaknesses(case_id, statute_id=statute_id)

        result = {
            "case_id": case_id,
            "weaknesses": [w.model_dump(mode="json") for w in weaknesses],
            "total": len(weaknesses),
        }

        return success_response(result, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found", event)
    except Exception as exc:
        logger.exception("Failed to get case weaknesses")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
