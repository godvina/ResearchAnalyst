"""API Lambda handler for document annotations (Req 29).

Endpoints:
  POST /case-files/{id}/documents/{docId}/annotations — Create annotation
  GET  /case-files/{id}/documents/{docId}/annotations — List annotations
  GET  /case-files/{id}/evidence-board — Case-wide evidence board
  POST /case-files/{id}/documents/{docId}/auto-tag — AI auto-tag
"""
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_ann_svc = None


def _get_annotation_service():
    global _ann_svc
    if _ann_svc is None:
        from db.connection import ConnectionManager
        from services.annotation_service import AnnotationService
        import boto3
        from botocore.config import Config
        bedrock = boto3.client("bedrock-runtime", config=Config(read_timeout=120, retries={"max_attempts": 2}))
        _ann_svc = AnnotationService(aurora_cm=ConnectionManager(), bedrock_client=bedrock)
    return _ann_svc


def handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    params = event.get("pathParameters") or {}

    try:
        case_id = params.get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        svc = _get_annotation_service()

        # Evidence board
        if "evidence-board" in resource and method == "GET":
            tag = (event.get("queryStringParameters") or {}).get("tag")
            board = svc.get_evidence_board(case_id, tag)
            return success_response(board, 200, event)

        doc_id = params.get("docId", "")

        # Auto-tag
        if "auto-tag" in resource and method == "POST":
            # Stub — would call Bedrock to suggest tags
            return success_response({"suggestions": []}, 200, event)

        # Create annotation
        if method == "POST":
            body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
            result = svc.create_annotation(
                case_id, doc_id, body.get("user_id", "investigator"),
                body.get("char_start", 0), body.get("char_end", 0),
                body.get("highlighted_text", ""), body.get("tag_category", "custom"),
                body.get("note_text"), body.get("linked_entities"))
            return success_response(result, 201, event)

        # List annotations
        if method == "GET":
            annotations = svc.get_annotations(case_id, doc_id)
            return success_response({"annotations": annotations}, 200, event)

        return error_response(404, "NOT_FOUND", "Unknown endpoint", event)
    except Exception as e:
        logger.exception("Annotation handler failed")
        return error_response(500, "INTERNAL_ERROR", str(e), event)
