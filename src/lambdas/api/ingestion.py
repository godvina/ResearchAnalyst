"""API Lambda handler for document ingestion.

Endpoint:
    POST /case-files/{id}/ingest — upload files to S3, then trigger Step Functions pipeline
"""

import base64
import json
import logging
import os
import uuid

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")


def ingest_handler(event, context):
    """Upload documents to S3 and trigger the Step Functions ingestion pipeline."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        raw_files = body.get("files", [])

        if not raw_files:
            return error_response(
                400, "VALIDATION_ERROR", "No files provided for ingestion", event,
            )

        # Upload files to S3 raw/ prefix
        s3 = boto3.client("s3")
        bucket = os.environ.get("S3_BUCKET_NAME", "")
        document_ids = []

        for f in raw_files:
            filename = f.get("filename", "")
            content_b64 = f.get("content_base64", "")
            if not filename or not content_b64:
                return error_response(
                    400, "VALIDATION_ERROR",
                    "Each file must have 'filename' and 'content_base64'", event,
                )
            doc_id = str(uuid.uuid4())
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "txt"
            key = f"cases/{case_id}/raw/{doc_id}.{ext}"
            s3.put_object(Bucket=bucket, Key=key, Body=base64.b64decode(content_b64))
            document_ids.append(doc_id)

        # Trigger Step Functions pipeline asynchronously
        sfn = boto3.client("stepfunctions")
        sfn_input = {
            "case_id": case_id,
            "sample_mode": False,
            "files": [{"filename": f.get("filename", ""), "content_base64": ""} for f in raw_files],
            "upload_result": {
                "document_ids": document_ids,
                "document_count": len(document_ids),
            },
        }

        execution = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"ingest-{case_id[:8]}-{uuid.uuid4().hex[:8]}",
            input=json.dumps(sfn_input),
        )

        # Mark theories stale when new evidence is ingested
        try:
            from services.theory_engine_service import TheoryEngineService
            from db.connection import ConnectionManager
            theory_svc = TheoryEngineService(aurora_cm=ConnectionManager(), bedrock_client=None, hypothesis_svc=None)
            theory_svc.mark_theories_stale(case_id)
        except Exception:
            pass  # Non-critical — don't fail ingestion if theory marking fails

        return success_response({
            "case_id": case_id,
            "documents_uploaded": len(document_ids),
            "document_ids": document_ids,
            "execution_arn": execution["executionArn"],
            "status": "processing",
        }, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to ingest documents")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
