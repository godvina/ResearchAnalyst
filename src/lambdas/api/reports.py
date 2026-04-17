"""API Lambda handler for report generation (Req 26).

Endpoints:
  POST /case-files/{id}/reports/generate — Generate a report
  GET  /case-files/{id}/reports — List previous reports
"""
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_report_svc = None


def _get_report_service():
    global _report_svc
    if _report_svc is None:
        from db.connection import ConnectionManager
        from services.report_generation_service import ReportGenerationService
        import boto3
        from botocore.config import Config
        bedrock = boto3.client("bedrock-runtime", config=Config(read_timeout=120, retries={"max_attempts": 2}))
        _report_svc = ReportGenerationService(aurora_cm=ConnectionManager(), bedrock_client=bedrock)
    return _report_svc


def handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        if method == "POST" and "generate" in resource:
            body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
            report_type = body.get("report_type", "case_summary")
            entity_name = body.get("entity_name")
            created_by = body.get("created_by", "investigator")
            svc = _get_report_service()
            # Note: generate_report is async but Lambda is sync — call synchronously
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                svc.generate_report(case_id, report_type, entity_name, created_by))
            return success_response(result, 200, event)

        if method == "GET":
            # List previous reports (stub — returns empty for now)
            return success_response({"reports": []}, 200, event)

        return error_response(404, "NOT_FOUND", "Unknown endpoint", event)
    except ValueError as e:
        return error_response(400, "VALIDATION_ERROR", str(e), event)
    except Exception as e:
        logger.exception("Report handler failed")
        return error_response(500, "INTERNAL_ERROR", str(e), event)
