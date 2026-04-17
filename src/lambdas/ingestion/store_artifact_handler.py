"""Lambda handler for storing extraction artifacts to S3.

Stores the entity extraction JSON artifact for a document.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Store extraction result as a JSON artifact in S3.

    Expected event:
        {
            "case_id": "...",
            "document_id": "...",
            "entities": [...],
            "relationships": [...]
        }

    Returns:
        {
            "case_id": "...",
            "document_id": "...",
            "artifact_s3_key": "..."
        }
    """
    from storage.s3_helper import PrefixType, upload_file

    case_id = event["case_id"]
    document_id = event["document_id"]
    entities = event.get("entities", [])
    relationships = event.get("relationships", [])
    s3_bucket = os.environ.get("S3_BUCKET_NAME")

    logger.info("Storing extraction artifact for document %s in case %s", document_id, case_id)

    artifact = {
        "document_id": document_id,
        "case_file_id": case_id,
        "entities": entities,
        "relationships": relationships,
    }

    filename = f"{document_id}_extraction.json"
    s3_key = upload_file(
        case_id,
        PrefixType.EXTRACTIONS,
        filename,
        json.dumps(artifact),
        bucket=s3_bucket,
    )

    logger.info("Stored artifact at %s", s3_key)

    return {
        "case_id": case_id,
        "document_id": document_id,
        "artifact_s3_key": s3_key,
    }
