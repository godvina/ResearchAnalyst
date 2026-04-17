"""API handlers for Investigation Findings (Research Notebook).

Endpoints:
    POST   /case-files/{id}/findings              — save finding
    GET    /case-files/{id}/findings              — list findings
    PUT    /case-files/{id}/findings/{finding_id} — update finding
    DELETE /case-files/{id}/findings/{finding_id} — delete finding
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_findings_service():
    from db.connection import ConnectionManager
    from services.findings_service import FindingsService
    return FindingsService(
        aurora_cm=ConnectionManager(),
        s3_bucket=os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", "")),
    )


def save_finding_handler(event, context):
    """POST /case-files/{id}/findings"""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        title = body.get("title", "").strip()
        if not title:
            return error_response(400, "VALIDATION_ERROR", "Missing 'title'", event)

        svc = _build_findings_service()
        finding_id = svc.save_finding(
            case_id=case_id, user_id=body.get("user_id", "investigator"),
            query=body.get("query"), finding_type=body.get("finding_type", "search_result"),
            title=title, summary=body.get("summary"),
            full_assessment=body.get("full_assessment"),
            source_citations=body.get("source_citations", []),
            entity_names=body.get("entity_names", []),
            tags=body.get("tags", []),
            notes=body.get("investigator_notes"),
            confidence=body.get("confidence_level"),
        )
        return success_response({"finding_id": finding_id, "status": "saved"}, 201, event)
    except Exception as exc:
        logger.exception("Save finding failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


def list_findings_handler(event, context):
    """GET /case-files/{id}/findings"""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        params = event.get("queryStringParameters") or {}
        sort_by = params.get("sort_by", "created_at")
        limit = min(int(params.get("limit", 50)), 100)

        svc = _build_findings_service()
        findings = svc.list_findings(case_id=case_id, sort_by=sort_by, limit=limit)
        return success_response({"findings": findings, "total": len(findings)}, 200, event)
    except Exception as exc:
        logger.exception("List findings failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


def update_finding_handler(event, context):
    """PUT /case-files/{id}/findings/{finding_id}"""
    from lambdas.api.response_helper import error_response, success_response
    try:
        finding_id = (event.get("pathParameters") or {}).get("finding_id", "")
        if not finding_id:
            return error_response(400, "VALIDATION_ERROR", "Missing finding_id", event)
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))

        svc = _build_findings_service()
        result = svc.update_finding(
            finding_id=finding_id,
            notes=body.get("investigator_notes"),
            tags=body.get("tags"),
            is_key_evidence=body.get("is_key_evidence"),
            needs_follow_up=body.get("needs_follow_up"),
        )
        if not result:
            return error_response(404, "NOT_FOUND", "Finding not found", event)
        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("Update finding failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


def delete_finding_handler(event, context):
    """DELETE /case-files/{id}/findings/{finding_id}"""
    from lambdas.api.response_helper import error_response, success_response
    try:
        finding_id = (event.get("pathParameters") or {}).get("finding_id", "")
        if not finding_id:
            return error_response(400, "VALIDATION_ERROR", "Missing finding_id", event)

        svc = _build_findings_service()
        deleted = svc.delete_finding(finding_id)
        if not deleted:
            return error_response(404, "NOT_FOUND", "Finding not found", event)
        return success_response({"deleted": True}, 200, event)
    except Exception as exc:
        logger.exception("Delete finding failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)
