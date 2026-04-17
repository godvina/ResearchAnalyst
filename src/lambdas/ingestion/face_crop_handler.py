"""Lambda handler for face cropping pipeline step.

Crops face bounding box regions from Rekognition detections, resizes to
100x100 JPEG thumbnails, and stores them in S3 for the investigation wall.
Runs after the RekognitionStep in the ingestion pipeline.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))


def handler(event, context):
    """Crop faces from Rekognition results.

    Event format (from Step Functions):
        {
            "case_id": "...",
            "rekognition_result": {
                "entities": [...],
                "artifact_key": "...",
                "status": "completed"
            },
            "effective_config": {...}
        }

    Returns:
        {
            "case_id": str,
            "status": "completed" | "skipped",
            "crops_created": int,
            "crops_from_extracted_images": int,
            "primary_thumbnails": dict
        }
    """
    case_id = event.get("case_id", "")
    effective_config = event.get("effective_config", {})
    rekognition_result = event.get("rekognition_result", {})

    # Check if face cropping is enabled (default: true)
    face_crop_config = effective_config.get("face_crop", {})
    if not face_crop_config.get("enabled", True):
        logger.info("Face cropping disabled for case %s, skipping", case_id)
        return {
            "case_id": case_id,
            "status": "skipped",
            "crops_created": 0,
            "crops_from_extracted_images": 0,
            "primary_thumbnails": {},
        }

    s3_bucket = S3_BUCKET
    if not s3_bucket:
        logger.error("S3_DATA_BUCKET not configured")
        return {
            "case_id": case_id,
            "status": "skipped",
            "crops_created": 0,
            "crops_from_extracted_images": 0,
            "primary_thumbnails": {},
        }

    # Load Rekognition results from the artifact in S3 if available
    rekognition_results = _load_rekognition_results(s3_bucket, rekognition_result)

    # If no face detections at all, skip
    if not _has_face_detections(rekognition_results):
        logger.info("No face detections found for case %s, skipping", case_id)
        return {
            "case_id": case_id,
            "status": "skipped",
            "crops_created": 0,
            "crops_from_extracted_images": 0,
            "primary_thumbnails": {},
        }

    # Instantiate FaceCropService and crop faces
    from services.face_crop_service import FaceCropService

    service = FaceCropService(s3_bucket=s3_bucket)
    result = service.crop_faces(case_id=case_id, rekognition_results=rekognition_results)

    logger.info(
        "Face cropping completed for case %s: %d crops created, %d from extracted images",
        case_id,
        result.get("crops_created", 0),
        result.get("crops_from_extracted_images", 0),
    )

    return {
        "case_id": case_id,
        "status": "completed",
        "crops_created": result.get("crops_created", 0),
        "crops_from_extracted_images": result.get("crops_from_extracted_images", 0),
        "primary_thumbnails": result.get("primary_thumbnails", {}),
    }


def _load_rekognition_results(s3_bucket: str, rekognition_result: dict) -> list:
    """Load full Rekognition results from the S3 artifact.

    The rekognition_result from Step Functions contains an artifact_key
    pointing to the full JSON results stored in S3.

    Returns:
        List of per-image Rekognition result dicts.
    """
    artifact_key = rekognition_result.get("artifact_key", "")
    if not artifact_key:
        logger.warning("No artifact_key in rekognition_result, using inline results")
        return []

    try:
        import boto3

        s3 = boto3.client("s3")
        resp = s3.get_object(Bucket=s3_bucket, Key=artifact_key)
        body = resp["Body"].read().decode("utf-8")
        artifact = json.loads(body)
        results = artifact.get("results", [])
        logger.info("Loaded %d Rekognition results from %s", len(results), artifact_key)
        return results
    except Exception as exc:
        logger.error("Failed to load Rekognition artifact %s: %s", artifact_key, str(exc)[:200])
        return []


def _has_face_detections(rekognition_results: list) -> bool:
    """Check if any Rekognition results contain face detections."""
    for result in rekognition_results:
        faces = result.get("faces", [])
        if faces:
            return True
    return False
