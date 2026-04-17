"""Theory-Driven Investigation API handlers."""
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
}


def _build_theory_engine():
    from db.connection import ConnectionManager
    from services.hypothesis_testing_service import HypothesisTestingService
    from services.theory_engine_service import TheoryEngineService

    aurora_cm = ConnectionManager()
    bedrock_client = boto3.client("bedrock-runtime", config=boto3.session.Config(read_timeout=60))
    hypothesis_svc = HypothesisTestingService(aurora_cm=aurora_cm, bedrock_client=bedrock_client)
    neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")
    return TheoryEngineService(
        aurora_cm=aurora_cm, bedrock_client=bedrock_client,
        hypothesis_svc=hypothesis_svc,
        neptune_endpoint=neptune_ep, neptune_port=neptune_port,
    )


def success_response(body, status=200, event=None):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body, default=str)}


def error_response(status, code, message, event=None):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps({"error": code, "message": message})}


def generate_theories_handler(event, context):
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID")
        svc = _build_theory_engine()
        theories = svc.generate_theories(case_id)
        return success_response({"theories": theories, "message": f"Generated {len(theories)} theories"})
    except Exception as exc:
        logger.exception("Theory generation failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def list_theories_handler(event, context):
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID")
        svc = _build_theory_engine()
        theories = svc.get_theories(case_id)
        return success_response({"theories": theories})
    except Exception as exc:
        logger.exception("List theories failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def get_theory_handler(event, context):
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        theory_id = (event.get("pathParameters") or {}).get("theory_id", "")
        if not case_id or not theory_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID or theory ID")
        svc = _build_theory_engine()
        theory = svc.get_theory_detail(case_id, theory_id)
        if not theory:
            return error_response(404, "NOT_FOUND", f"Theory {theory_id} not found")
        return success_response({"theory": theory})
    except Exception as exc:
        logger.exception("Get theory detail failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def create_theory_handler(event, context):
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID")
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        title = body.get("title", "").strip()
        description = body.get("description", "").strip()
        if not title or not description:
            return error_response(400, "VALIDATION_ERROR", "Title and description are required")
        svc = _build_theory_engine()
        theory = svc.create_manual_theory(
            case_id, title, description,
            theory_type=body.get("theory_type"),
            supporting_entities=body.get("supporting_entities"),
        )
        return success_response({"theory": theory})
    except Exception as exc:
        logger.exception("Create theory failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def set_verdict_handler(event, context):
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        theory_id = (event.get("pathParameters") or {}).get("theory_id", "")
        if not case_id or not theory_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID or theory ID")
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        verdict = body.get("verdict", "")
        if verdict not in ("confirmed", "refuted", "inconclusive"):
            return error_response(400, "VALIDATION_ERROR", "Verdict must be confirmed, refuted, or inconclusive")
        svc = _build_theory_engine()
        result = svc.set_verdict(case_id, theory_id, verdict)
        if not result:
            return error_response(404, "NOT_FOUND", f"Theory {theory_id} not found")
        return success_response({"theory": result})
    except ValueError as ve:
        return error_response(400, "VALIDATION_ERROR", str(ve))
    except Exception as exc:
        logger.exception("Set verdict failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def score_theory_handler(event, context):
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        theory_id = (event.get("pathParameters") or {}).get("theory_id", "")
        if not case_id or not theory_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID or theory ID")
        svc = _build_theory_engine()
        result = svc.score_theory(case_id, theory_id)
        if not result:
            return error_response(404, "NOT_FOUND", f"Theory {theory_id} not found")
        return success_response({"theory": result})
    except Exception as exc:
        logger.exception("Score theory failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def get_case_file_handler(event, context):
    """GET /case-files/{id}/theories/{theory_id}/case-file"""
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        theory_id = (event.get("pathParameters") or {}).get("theory_id", "")
        if not case_id or not theory_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID or theory ID")
        svc = _build_theory_engine()
        result = svc.get_or_generate_case_file(case_id, theory_id)
        if result is None:
            return error_response(404, "NOT_FOUND", f"Theory {theory_id} not found")
        return success_response({"case_file": result})
    except Exception as exc:
        logger.exception("Get case file failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def update_section_handler(event, context):
    """PUT /case-files/{id}/theories/{theory_id}/case-file/sections/{section_index}"""
    try:
        params = event.get("pathParameters") or {}
        case_id = params.get("id", "")
        theory_id = params.get("theory_id", "")
        section_index = params.get("section_index", "")
        if not case_id or not theory_id or section_index == "":
            return error_response(400, "VALIDATION_ERROR", "Missing case ID, theory ID, or section index")
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        content = body.get("content")
        if content is None:
            return error_response(400, "VALIDATION_ERROR", "Missing content in request body")
        svc = _build_theory_engine()
        result = svc.update_section(case_id, theory_id, int(section_index), content)
        if result is None:
            return error_response(404, "NOT_FOUND", f"Theory {theory_id} not found")
        return success_response({"case_file": result})
    except ValueError as ve:
        return error_response(400, "VALIDATION_ERROR", str(ve))
    except json.JSONDecodeError:
        return error_response(400, "VALIDATION_ERROR", "Invalid JSON in request body")
    except Exception as exc:
        logger.exception("Update section failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def regenerate_case_file_handler(event, context):
    """POST /case-files/{id}/theories/{theory_id}/case-file/regenerate"""
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        theory_id = (event.get("pathParameters") or {}).get("theory_id", "")
        if not case_id or not theory_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID or theory ID")
        svc = _build_theory_engine()
        result = svc.regenerate_case_file(case_id, theory_id)
        if result is None:
            return error_response(404, "NOT_FOUND", f"Theory {theory_id} not found")
        return success_response({"case_file": result})
    except Exception as exc:
        logger.exception("Regenerate case file failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def promote_theory_handler(event, context):
    """POST /case-files/{id}/theories/{theory_id}/promote"""
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        theory_id = (event.get("pathParameters") or {}).get("theory_id", "")
        if not case_id or not theory_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID or theory ID")
        svc = _build_theory_engine()
        result = svc.promote_to_sub_case(case_id, theory_id)
        if result is None:
            return error_response(404, "NOT_FOUND", f"Theory {theory_id} not found")
        return success_response(result)
    except ValueError as ve:
        msg = str(ve)
        if "already promoted" in msg.lower():
            return error_response(409, "ALREADY_PROMOTED", msg)
        return error_response(400, "VALIDATION_ERROR", msg)
    except Exception as exc:
        logger.exception("Promote theory failed")
        return error_response(500, "INTERNAL_ERROR", str(exc))


def dispatch_handler(event, context):
    from lambdas.api.response_helper import error_response as err_resp
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    routes = {
        ("POST", "/case-files/{id}/theories/generate"): generate_theories_handler,
        ("GET", "/case-files/{id}/theories"): list_theories_handler,
        ("GET", "/case-files/{id}/theories/{theory_id}"): get_theory_handler,
        ("POST", "/case-files/{id}/theories"): create_theory_handler,
        ("PUT", "/case-files/{id}/theories/{theory_id}/verdict"): set_verdict_handler,
        ("POST", "/case-files/{id}/theories/{theory_id}/score"): score_theory_handler,
        ("GET", "/case-files/{id}/theories/{theory_id}/case-file"): get_case_file_handler,
        ("PUT", "/case-files/{id}/theories/{theory_id}/case-file/sections/{section_index}"): update_section_handler,
        ("POST", "/case-files/{id}/theories/{theory_id}/case-file/regenerate"): regenerate_case_file_handler,
        ("POST", "/case-files/{id}/theories/{theory_id}/promote"): promote_theory_handler,
    }

    handler = routes.get((method, resource))
    if handler:
        return handler(event, context)
    return err_resp(404, "NOT_FOUND", f"Unknown route: {method} {resource}", event)
