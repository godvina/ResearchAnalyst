"""API Lambda handler for hypothesis testing (Req 27).

Endpoints:
  POST /case-files/{id}/hypothesis/evaluate — Evaluate a hypothesis
  GET  /case-files/{id}/hypotheses — List saved hypotheses
"""
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_hyp_svc = None


def _get_hypothesis_service():
    global _hyp_svc
    if _hyp_svc is None:
        from db.connection import ConnectionManager
        from services.hypothesis_testing_service import HypothesisTestingService
        import boto3
        from botocore.config import Config
        bedrock = boto3.client("bedrock-runtime", config=Config(read_timeout=120, retries={"max_attempts": 2}))
        _hyp_svc = HypothesisTestingService(aurora_cm=ConnectionManager(), bedrock_client=bedrock)
    return _hyp_svc


def handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        if method == "POST" and "evaluate" in resource:
            body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
            hypothesis = body.get("hypothesis", "")
            if not hypothesis:
                return error_response(400, "VALIDATION_ERROR", "Missing hypothesis text", event)
            svc = _get_hypothesis_service()
            result = svc.evaluate(case_id, hypothesis, body.get("created_by", "investigator"))
            return success_response(result, 200, event)

        if method == "GET":
            return success_response({"hypotheses": []}, 200, event)

        return error_response(404, "NOT_FOUND", "Unknown endpoint", event)
    except Exception as e:
        logger.exception("Hypothesis handler failed")
        return error_response(500, "INTERNAL_ERROR", str(e), event)
