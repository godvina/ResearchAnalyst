"""Lambda handler for pipeline status API — real-time pipeline ops dashboard.

GET /case-files/{id}/pipeline-status
Returns comprehensive pipeline metrics, AI health assessment, and step-level status.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Content-Type": "application/json",
}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return _err(400, "Missing case_id")

        import boto3
        from services.pipeline_status_service import PipelineStatusService

        s3 = boto3.client("s3")

        # Aurora connection is optional — may not have psycopg2 in this Lambda
        aurora_cm = None
        try:
            from db.connection import ConnectionManager
            aurora_cm = ConnectionManager()
        except Exception:
            logger.info("Aurora connection unavailable — using S3/Neptune only")

        svc = PipelineStatusService(
            s3_client=s3,
            aurora_cm=aurora_cm,
            neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
            neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
            opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT", ""),
        )
        result = svc.get_status(case_id)
        return {"statusCode": 200, "headers": CORS_HEADERS,
                "body": json.dumps(result, default=str)}
    except Exception as e:
        logger.exception("Pipeline status failed")
        return _err(500, str(e)[:300])


def _err(code, msg):
    return {"statusCode": code, "headers": CORS_HEADERS,
            "body": json.dumps({"error": msg})}
