"""API Lambda handlers for Precedent Analysis operations.

Endpoints:
    POST   /case-files/{id}/precedent-analysis — run precedent analysis
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

    if resource == "/case-files/{id}/precedent-analysis" and method == "POST":
        return post_precedent_analysis_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


def _build_precedent_analysis_service():
    """Construct a PrecedentAnalysisService with dependencies from environment."""
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.precedent_analysis_service import PrecedentAnalysisService

    aurora_cm = ConnectionManager()
    neptune_cm = NeptuneConnectionManager(
        endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
    )

    import boto3
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    opensearch_client = None
    try:
        from opensearchpy import OpenSearch
        os_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
        if os_endpoint:
            opensearch_client = OpenSearch(
                hosts=[{"host": os_endpoint, "port": 443}],
                use_ssl=True,
            )
    except Exception:
        pass

    return PrecedentAnalysisService(
        aurora_cm=aurora_cm,
        neptune_cm=neptune_cm,
        bedrock_client=bedrock,
        opensearch_client=opensearch_client,
    )


# ------------------------------------------------------------------
# POST /case-files/{id}/precedent-analysis
# ------------------------------------------------------------------

def post_precedent_analysis_handler(event, context):
    """Run precedent analysis with charge_type from request body."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        charge_type = body.get("charge_type", "")
        if not charge_type:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: charge_type", event)

        service = _build_precedent_analysis_service()

        matches = service.find_precedents(case_id, charge_type)
        distribution = service.compute_ruling_distribution(matches)
        advisory = service.generate_sentencing_advisory(case_id, matches)

        result = {
            "case_id": case_id,
            "charge_type": charge_type,
            "matches": [m.model_dump(mode="json") for m in matches],
            "ruling_distribution": distribution.model_dump(mode="json"),
            "sentencing_advisory": advisory.model_dump(mode="json"),
        }

        return success_response(result, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found", event)
    except Exception as exc:
        logger.exception("Failed to run precedent analysis")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
