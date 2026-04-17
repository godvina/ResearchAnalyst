"""API Lambda handler for conspiracy network discovery.

Endpoints:
    POST /case-files/{id}/network-analysis   — trigger network analysis
    GET  /case-files/{id}/network-analysis   — get cached analysis results
    GET  /case-files/{id}/persons-of-interest — list persons of interest
    GET  /case-files/{id}/persons-of-interest/{pid} — get full profile
    POST /case-files/{id}/sub-cases          — create sub-case for confirmed POI
    GET  /case-files/{id}/network-patterns   — get detected hidden patterns
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_network_discovery_service():
    """Construct NetworkDiscoveryService with all dependencies from environment."""
    import boto3

    from db.connection import ConnectionManager
    from services.cross_case_service import CrossCaseService
    from services.case_file_service import CaseFileService
    from services.decision_workflow_service import DecisionWorkflowService
    from services.network_discovery_service import NetworkDiscoveryService
    from services.pattern_discovery_service import PatternDiscoveryService
    from db.neptune import NeptuneConnectionManager

    aurora_cm = ConnectionManager()
    bedrock = boto3.client("bedrock-runtime")
    neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")
    opensearch_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")

    decision_svc = DecisionWorkflowService(aurora_cm)
    neptune_cm = NeptuneConnectionManager(endpoint=neptune_endpoint)
    case_file_svc = CaseFileService(aurora_cm, neptune_cm)
    cross_case_svc = CrossCaseService(neptune_cm, aurora_cm, case_file_svc, bedrock)
    pattern_svc = PatternDiscoveryService(neptune_cm, aurora_cm, bedrock)

    return NetworkDiscoveryService(
        neptune_endpoint=neptune_endpoint,
        neptune_port=neptune_port,
        aurora_cm=aurora_cm,
        bedrock_client=bedrock,
        opensearch_endpoint=opensearch_endpoint,
        decision_workflow_svc=decision_svc,
        cross_case_svc=cross_case_svc,
        pattern_discovery_svc=pattern_svc,
    )


# ------------------------------------------------------------------
# POST /case-files/{id}/network-analysis
# ------------------------------------------------------------------

def trigger_analysis_handler(event, context):
    """Trigger network analysis for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        svc = _build_network_discovery_service()
        result = svc.analyze_network(case_id)

        return success_response(result.model_dump(mode="json"), 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to trigger network analysis")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/network-analysis
# ------------------------------------------------------------------

def get_analysis_handler(event, context):
    """Get cached network analysis results."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        svc = _build_network_discovery_service()
        result = svc.get_analysis(case_id)

        if not result:
            return error_response(404, "NOT_FOUND", f"No analysis found for case {case_id}", event)

        return success_response(result.model_dump(mode="json"), 200, event)

    except Exception as exc:
        logger.exception("Failed to get network analysis")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/persons-of-interest
# ------------------------------------------------------------------

def list_persons_handler(event, context):
    """List persons of interest with optional filters."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        params = event.get("queryStringParameters") or {}
        risk_level = params.get("risk_level")
        min_score = int(params.get("min_score", 0))

        svc = _build_network_discovery_service()
        persons = svc.get_persons_of_interest(case_id, risk_level=risk_level, min_score=min_score)

        return success_response(
            {"persons": [p.model_dump(mode="json") for p in persons]},
            200, event,
        )

    except Exception as exc:
        logger.exception("Failed to list persons of interest")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/persons-of-interest/{pid}
# ------------------------------------------------------------------

def get_person_handler(event, context):
    """Get full co-conspirator profile."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        person_id = (event.get("pathParameters") or {}).get("pid", "")
        if not case_id or not person_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID or person ID", event)

        svc = _build_network_discovery_service()
        profile = svc.get_person_profile(case_id, person_id)

        return success_response(profile.model_dump(mode="json"), 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get person profile")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/sub-cases
# ------------------------------------------------------------------

def create_sub_case_handler(event, context):
    """Create sub-case for a confirmed person of interest."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        person_id = body.get("person_id", "")
        if not person_id:
            return error_response(400, "VALIDATION_ERROR", "Missing person_id", event)

        svc = _build_network_discovery_service()
        proposal = svc.spawn_sub_case(case_id, person_id)

        return success_response(proposal.model_dump(mode="json"), 201, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create sub-case")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/network-patterns
# ------------------------------------------------------------------

def get_patterns_handler(event, context):
    """Get detected hidden patterns."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        params = event.get("queryStringParameters") or {}
        pattern_type = params.get("pattern_type")

        svc = _build_network_discovery_service()
        patterns = svc.get_network_patterns(case_id, pattern_type=pattern_type)

        return success_response(
            {"patterns": [p.model_dump(mode="json") for p in patterns]},
            200, event,
        )

    except Exception as exc:
        logger.exception("Failed to get network patterns")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# Dispatch handler (Lambda entry point)
# ------------------------------------------------------------------

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def dispatch_handler(event, context):
    """Route by HTTP method + resource path."""
    from lambdas.api.response_helper import error_response

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    routes = {
        ("POST", "/case-files/{id}/network-analysis"): trigger_analysis_handler,
        ("GET", "/case-files/{id}/network-analysis"): get_analysis_handler,
        ("GET", "/case-files/{id}/persons-of-interest"): list_persons_handler,
        ("GET", "/case-files/{id}/persons-of-interest/{pid}"): get_person_handler,
        ("POST", "/case-files/{id}/sub-cases"): create_sub_case_handler,
        ("GET", "/case-files/{id}/network-patterns"): get_patterns_handler,
    }

    handler = routes.get((method, resource))
    if handler:
        return handler(event, context)

    return error_response(404, "NOT_FOUND", f"Unknown route: {method} {resource}", event)
