"""API Lambda handler for court document assembly.

Endpoints:
    POST /case-files/{id}/documents/generate     — generate a court document
    GET  /case-files/{id}/documents               — list documents for a case
    GET  /case-files/{id}/documents/{doc_id}      — get document with sections
    POST /case-files/{id}/documents/{doc_id}/sign-off — attorney sign-off
    GET  /case-files/{id}/documents/{doc_id}/export   — export document
    GET  /case-files/{id}/discovery               — discovery status dashboard
    POST /case-files/{id}/discovery/produce       — create production set
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def _build_service():
    import boto3
    from db.connection import ConnectionManager
    from services.document_assembly_service import DocumentAssemblyService
    from services.decision_workflow_service import DecisionWorkflowService

    aurora_cm = ConnectionManager()
    bedrock = boto3.client("bedrock-runtime")
    dws = DecisionWorkflowService(aurora_cm)
    return DocumentAssemblyService(
        aurora_cm=aurora_cm,
        neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
        neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
        bedrock_client=bedrock,
        decision_workflow_svc=dws,
    )


def generate_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        doc_type = body.get("document_type", "")
        if not doc_type:
            return error_response(400, "VALIDATION_ERROR", "Missing document_type", event)
        svc = _build_service()
        draft = svc.generate_document(case_id, doc_type, body.get("statute_id"), body.get("defendant_id"))
        status_code = 202 if draft.status.value == "processing" else 200
        return success_response(draft.model_dump(mode="json"), status_code, event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Document generation failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def list_documents_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        params = event.get("queryStringParameters") or {}
        svc = _build_service()
        docs = svc.list_documents(case_id, params.get("document_type"), params.get("status"))
        return success_response({"documents": [d.model_dump(mode="json") for d in docs]}, 200, event)
    except Exception as exc:
        logger.exception("List documents failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def get_document_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        doc_id = (event.get("pathParameters") or {}).get("doc_id", "")
        if not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing document ID", event)
        svc = _build_service()
        doc = svc.get_document(doc_id)
        return success_response(doc.model_dump(mode="json"), 200, event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Get document failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def sign_off_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        doc_id = (event.get("pathParameters") or {}).get("doc_id", "")
        if not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing document ID", event)
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        attorney_id = body.get("attorney_id", "")
        attorney_name = body.get("attorney_name", "")
        if not attorney_id or not attorney_name:
            return error_response(400, "VALIDATION_ERROR", "Missing attorney_id or attorney_name", event)
        svc = _build_service()
        doc = svc.sign_off_document(doc_id, attorney_id, attorney_name)
        return success_response(doc.model_dump(mode="json"), 200, event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Sign-off failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def export_handler(event, context):
    from lambdas.api.response_helper import error_response
    try:
        doc_id = (event.get("pathParameters") or {}).get("doc_id", "")
        params = event.get("queryStringParameters") or {}
        fmt = params.get("format", "html")
        svc = _build_service()
        content = svc.export_document(doc_id, fmt)
        content_types = {"html": "text/html", "pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        import base64
        return {
            "statusCode": 200,
            "headers": {"Content-Type": content_types.get(fmt, "application/octet-stream"), "Access-Control-Allow-Origin": "*"},
            "body": base64.b64encode(content).decode("utf-8"),
            "isBase64Encoded": True,
        }
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Export failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def get_discovery_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        svc = _build_service()
        status = svc.get_discovery_status(case_id)
        return success_response(status.model_dump(mode="json"), 200, event)
    except Exception as exc:
        logger.exception("Discovery status failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def produce_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        recipient = body.get("recipient", "")
        doc_ids = body.get("document_ids", [])
        if not recipient or not doc_ids:
            return error_response(400, "VALIDATION_ERROR", "Missing recipient or document_ids", event)
        svc = _build_service()
        ps = svc.create_production_set(case_id, recipient, doc_ids)
        return success_response(ps.model_dump(mode="json"), 201, event)
    except Exception as exc:
        logger.exception("Production set creation failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def dispatch_handler(event, context):
    from lambdas.api.response_helper import error_response
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    routes = {
        ("POST", "/case-files/{id}/documents/generate"): generate_handler,
        ("GET", "/case-files/{id}/documents"): list_documents_handler,
        ("GET", "/case-files/{id}/documents/{doc_id}"): get_document_handler,
        ("POST", "/case-files/{id}/documents/{doc_id}/sign-off"): sign_off_handler,
        ("GET", "/case-files/{id}/documents/{doc_id}/export"): export_handler,
        ("GET", "/case-files/{id}/discovery"): get_discovery_handler,
        ("POST", "/case-files/{id}/discovery/produce"): produce_handler,
    }
    handler = routes.get((method, resource))
    if handler:
        return handler(event, context)
    return error_response(404, "NOT_FOUND", f"Unknown route: {method} {resource}", event)
