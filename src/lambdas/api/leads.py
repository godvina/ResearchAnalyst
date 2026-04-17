"""API handlers for lead ingestion endpoints.

Thin handlers dispatched from case_files.py mega-dispatcher.
All business logic lives in LeadIngestionService.
"""

import json
import logging
import os

from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_service():
    """Construct LeadIngestionService with dependencies."""
    from db.connection import ConnectionManager
    from services.collection_service import CollectionService
    from services.lead_ingestion_service import LeadIngestionService
    from services.matter_service import MatterService

    cm = ConnectionManager()
    return LeadIngestionService(cm, MatterService(cm), CollectionService(cm))


def handle_ingest(event, context):
    """POST /leads/ingest — validate and ingest a lead JSON payload."""
    from services.lead_ingestion_service import ConflictError

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        service = _build_service()
        result = service.ingest_lead(body)
        return success_response(result, 202, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except ConflictError as exc:
        return error_response(409, "CONFLICT", str(exc), event)
    except Exception as exc:
        logger.exception("Lead ingestion failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def handle_lead_status(event, context):
    """GET /leads/{lead_id}/status — return lead processing status."""
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        service = _build_service()
        status = service.get_lead_status(lead_id)
        if not status:
            return error_response(404, "NOT_FOUND", f"Lead not found: {lead_id}", event)

        return success_response(status, 200, event)

    except Exception as exc:
        logger.exception("Failed to get lead status")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def handle_matter_lead(event, context):
    """GET /matters/{id}/lead — return lead metadata for a matter."""
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        matter_id = (event.get("pathParameters") or {}).get("id", "")
        if not matter_id:
            return error_response(400, "VALIDATION_ERROR", "Missing matter ID", event)

        service = _build_service()
        metadata = service.get_lead_metadata(matter_id)
        if not metadata:
            return error_response(404, "NOT_FOUND", f"No lead metadata for matter: {matter_id}", event)

        return success_response({"matter_id": matter_id, "lead_metadata": metadata}, 200, event)

    except Exception as exc:
        logger.exception("Failed to get lead metadata")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
