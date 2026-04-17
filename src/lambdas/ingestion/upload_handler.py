"""Lambda handler for file upload step of the ingestion pipeline.

Receives a file upload event and delegates to IngestionService.upload_documents().
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_ingestion_service():
    """Construct an IngestionService with dependencies from environment."""
    import boto3

    from db.connection import ConnectionManager
    from services.case_file_service import CaseFileService
    from services.document_parser import DocumentParser
    from services.entity_extraction_service import EntityExtractionService
    from services.neptune_graph_loader import NeptuneGraphLoader
    from services.ingestion_service import IngestionService

    bedrock = boto3.client("bedrock-runtime")
    aurora_cm = ConnectionManager()
    neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    s3_bucket = os.environ.get("S3_BUCKET_NAME", "")
    iam_role_arn = os.environ.get("NEPTUNE_IAM_ROLE_ARN", "")

    return IngestionService(
        document_parser=DocumentParser(),
        entity_extraction_service=EntityExtractionService(bedrock),
        neptune_graph_loader=NeptuneGraphLoader(neptune_endpoint=neptune_endpoint, s3_bucket=s3_bucket),
        case_file_service=CaseFileService(aurora_cm),
        bedrock_client=bedrock,
        aurora_connection_manager=aurora_cm,
        s3_bucket=s3_bucket,
        iam_role_arn=iam_role_arn,
    )


def handler(event, context):
    """Upload raw files to S3 for a case file.

    Expected event:
        {
            "case_id": "...",
            "files": [{"filename": "...", "content_base64": "..."}]
        }

    Returns:
        {
            "case_id": "...",
            "document_ids": ["...", ...],
            "document_count": N
        }
    """
    case_id = event["case_id"]
    raw_files = event.get("files", [])
    security_label = event.get("security_label")  # Optional: sets security_label_override on documents

    logger.info("Uploading %d files for case %s", len(raw_files), case_id)

    import base64

    files = [
        (f["filename"], base64.b64decode(f["content_base64"]))
        for f in raw_files
    ]

    service = _build_ingestion_service()
    document_ids = service.upload_documents(case_id, files)

    # If security_label provided, set security_label_override on each document
    if security_label:
        _valid_labels = {"public", "restricted", "confidential", "top_secret"}
        if security_label.lower() in _valid_labels:
            try:
                from db.connection import ConnectionManager
                cm = ConnectionManager()
                with cm.cursor() as cur:
                    for doc_id in document_ids:
                        cur.execute(
                            "UPDATE documents SET security_label_override = %s WHERE document_id = %s",
                            (security_label.lower(), doc_id),
                        )
            except Exception as exc:
                logger.warning("Failed to set security_label_override: %s", exc)
        else:
            logger.warning("Invalid security_label '%s' ignored", security_label)

    logger.info("Uploaded %d documents for case %s", len(document_ids), case_id)

    result = {
        "case_id": case_id,
        "document_ids": document_ids,
        "document_count": len(document_ids),
    }
    if security_label:
        result["security_label"] = security_label.lower()

    return result
