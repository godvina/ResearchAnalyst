"""Lambda handler for AI image description pipeline step.

Downloads extracted images from S3, sends them to Bedrock Claude's vision API
with an investigative-focused prompt, and returns natural language descriptions.
Descriptions are indexed in the search backend, stored as S3 artifacts, and
passed to the graph loader for Neptune integration.
"""

import base64
import json
import logging
import os
import time
import uuid

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
_DEFAULT_EMBEDDING_MODEL = "amazon.titan-embed-text-v1"

# Media type mapping for Claude vision API
_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


def _get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def _get_bedrock_client():
    config = Config(
        read_timeout=120,
        connect_timeout=10,
        retries={"max_attempts": 2, "mode": "adaptive"},
    )
    return boto3.client("bedrock-runtime", region_name=AWS_REGION, config=config)


def _load_rekognition_artifact(s3_client, s3_bucket: str, artifact_key: str) -> dict:
    """Load the full Rekognition results artifact from S3."""
    try:
        resp = s3_client.get_object(Bucket=s3_bucket, Key=artifact_key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except Exception as e:
        logger.error("Failed to load Rekognition artifact %s: %s", artifact_key, str(e)[:200])
        return {}


def _build_image_rekognition_map(rek_artifact: dict, min_confidence: float = 0.7) -> dict:
    """Map each image S3 key to its Rekognition face count and labels.

    Returns dict: s3_key -> {face_count, labels_with_confidence, source_document_id}
    """
    image_map = {}
    for result in rek_artifact.get("results", []):
        s3_key = result.get("s3_key", "")
        if not s3_key:
            continue

        face_count = len(result.get("faces", []))
        labels_with_conf = []
        for label in result.get("labels", []):
            name = label.get("name", "")
            conf = label.get("confidence", 0)
            if name:
                labels_with_conf.append({"name": name, "confidence": conf})

        # Parse source_document_id from filename
        filename = s3_key.rsplit("/", 1)[-1] if "/" in s3_key else s3_key
        source_doc_id = filename.split("_page")[0] if "_page" in filename else "unknown"

        image_map[s3_key] = {
            "face_count": face_count,
            "labels_with_confidence": labels_with_conf,
            "source_document_id": source_doc_id,
        }

    return image_map


def _load_case_entities(s3_client, s3_bucket: str, case_id: str) -> list[str]:
    """Load known entity names for the case from extraction artifacts."""
    entity_names = set()
    prefix = f"cases/{case_id}/extractions/"
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=s3_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Size"] < 50:
                    continue
                try:
                    resp = s3_client.get_object(Bucket=s3_bucket, Key=obj["Key"])
                    artifact = json.loads(resp["Body"].read().decode("utf-8"))
                    for ent in artifact.get("entities", []):
                        name = ent.get("canonical_name", ent.get("name", ""))
                        if name:
                            entity_names.add(name)
                except Exception:
                    continue
    except Exception as e:
        logger.warning("Failed to load case entities: %s", str(e)[:200])

    # Also load from Rekognition entities
    rek_prefix = f"cases/{case_id}/rekognition-artifacts/"
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=s3_bucket, Prefix=rek_prefix):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith("_rekognition.json"):
                    continue
                try:
                    resp = s3_client.get_object(Bucket=s3_bucket, Key=obj["Key"])
                    artifact = json.loads(resp["Body"].read().decode("utf-8"))
                    for ent in artifact.get("entities", []):
                        name = ent.get("canonical_name", "")
                        if name:
                            entity_names.add(name)
                except Exception:
                    continue
    except Exception as e:
        logger.warning("Failed to load Rekognition entities: %s", str(e)[:200])

    return list(entity_names)


def _describe_image(
    s3_client, bedrock_client, s3_bucket: str, image_key: str,
    rek_context: dict, config: dict,
) -> dict | None:
    """Download image, call Bedrock Claude vision API, return description dict.

    Returns None on failure (logged, not raised).
    """
    from services.image_description_service import (
        build_investigative_prompt, get_system_prompt, parse_bedrock_response,
    )

    model_id = config.get("model_id", _DEFAULT_MODEL_ID) or _DEFAULT_MODEL_ID
    max_tokens = config.get("max_tokens_per_image", 1024)
    custom_prompt = config.get("custom_prompt")

    start_ms = time.time()

    # Download image from S3
    try:
        resp = s3_client.get_object(Bucket=s3_bucket, Key=image_key)
        image_bytes = resp["Body"].read()
    except Exception as e:
        logger.warning("Failed to download image %s: %s", image_key, str(e)[:200])
        return None

    # Skip images > 20MB (Claude limit)
    if len(image_bytes) > 20 * 1024 * 1024:
        logger.warning("Image %s too large (%d bytes), skipping", image_key, len(image_bytes))
        return None

    # Determine media type
    ext = "." + image_key.lower().rsplit(".", 1)[-1] if "." in image_key else ".jpg"
    media_type = _MEDIA_TYPES.get(ext, "image/jpeg")

    # Base64 encode
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Build prompt
    prompt_text = build_investigative_prompt(rek_context, custom_prompt)
    system_prompt = get_system_prompt()

    # Call Bedrock
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": prompt_text,
                },
            ],
        }],
    }

    try:
        response = bedrock_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body),
        )
        response_body = json.loads(response["body"].read())
    except Exception as e:
        logger.warning("Bedrock invoke_model failed for %s: %s", image_key, str(e)[:200])
        return None

    duration_ms = int((time.time() - start_ms) * 1000)

    description_text = parse_bedrock_response(response_body)
    usage = response_body.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    return {
        "image_s3_key": image_key,
        "description": description_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "model_id": model_id,
    }


def _generate_embedding(bedrock_client, text: str, model_id: str = _DEFAULT_EMBEDDING_MODEL) -> list | None:
    """Generate a vector embedding for description text."""
    try:
        embed_text = text[:25_000] if len(text) > 25_000 else text
        body = json.dumps({"inputText": embed_text})
        response = bedrock_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        response_body = json.loads(response["body"].read())
        return response_body.get("embedding")
    except Exception as e:
        logger.warning("Embedding generation failed: %s", str(e)[:200])
        return None


def _index_description(case_id: str, doc_id: str, image_key: str,
                       description: str, embedding: list | None,
                       labels: list[str], source_type: str = "image_description"):
    """Index a description in the search backend."""
    try:
        from services.backend_factory import BackendFactory
        from services.aurora_pgvector_backend import AuroraPgvectorBackend
        from services.search_backend import IndexDocumentRequest
        from db.connection import ConnectionManager

        aurora_cm = ConnectionManager()
        aurora_backend = AuroraPgvectorBackend(aurora_cm)

        opensearch_backend = None
        os_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
        if os_endpoint:
            from services.opensearch_serverless_backend import OpenSearchServerlessBackend
            opensearch_backend = OpenSearchServerlessBackend(collection_endpoint=os_endpoint)

        factory = BackendFactory(aurora_backend=aurora_backend, opensearch_backend=opensearch_backend)

        # Determine search tier
        search_tier = "standard"
        try:
            from services.case_file_service import CaseFileService
            from db.neptune import NeptuneConnectionManager
            neptune_cm = NeptuneConnectionManager(endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""))
            svc = CaseFileService(aurora_cm, neptune_cm)
            case_file = svc.get_case_file(case_id)
            tier = case_file.search_tier
            search_tier = tier.value if hasattr(tier, "value") else str(tier)
        except Exception:
            pass

        backend = factory.get_backend(search_tier)

        index_req = IndexDocumentRequest(
            document_id=f"imgdesc_{doc_id}_{image_key.rsplit('/', 1)[-1]}",
            case_file_id=case_id,
            text=description,
            embedding=embedding or [],
            metadata={
                "source_type": source_type,
                "image_s3_key": image_key,
                "rekognition_labels": labels,
            },
        )
        backend.index_documents(case_id, [index_req])
        logger.info("Indexed image description for %s", image_key)
    except Exception as e:
        logger.warning("Failed to index description for %s: %s", image_key, str(e)[:200])


def handler(event, context):
    """Process images for a case using Bedrock Claude vision API.

    Event format:
        {
            "case_id": "...",
            "rekognition_result": {
                "case_id": "...",
                "status": "...",
                "artifact_key": "...",
            },
            "effective_config": {
                "image_description": {
                    "enabled": true,
                    "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
                    ...
                }
            }
        }

    Returns:
        {
            "case_id": "...",
            "status": "completed" | "skipped" | "batch_submitted",
            "descriptions": [...],
            "images_evaluated": int,
            "images_described": int,
            "images_skipped": int,
            "artifact_key": "...",
            "batch_job_id": str | None,
        }
    """
    from services.image_description_service import (
        apply_trigger_filter, extract_mentioned_entities,
        build_description_artifact, get_artifact_s3_key,
    )

    case_id = event.get("case_id", "")
    config = event.get("effective_config", {}).get("image_description", {})
    rek_result = event.get("rekognition_result", {})

    # Check if enabled
    if not config.get("enabled", False):
        logger.info("Image description disabled for case %s, skipping", case_id)
        return {"case_id": case_id, "status": "skipped", "descriptions": [],
                "images_evaluated": 0, "images_described": 0, "images_skipped": 0,
                "artifact_key": None, "batch_job_id": None}

    s3_bucket = S3_BUCKET
    if not s3_bucket:
        logger.error("S3_DATA_BUCKET not configured")
        return {"case_id": case_id, "status": "skipped", "descriptions": [],
                "images_evaluated": 0, "images_described": 0, "images_skipped": 0,
                "artifact_key": None, "batch_job_id": None}

    s3 = _get_s3_client()
    bedrock = _get_bedrock_client()

    # Load Rekognition artifact
    artifact_key = rek_result.get("artifact_key", "")
    rek_artifact = {}
    if artifact_key:
        rek_artifact = _load_rekognition_artifact(s3, s3_bucket, artifact_key)

    # Build image-to-Rekognition map
    image_rek_map = _build_image_rekognition_map(rek_artifact, config.get("min_rekognition_confidence", 0.7))
    images_evaluated = len(image_rek_map)

    # Apply trigger filter
    selected = apply_trigger_filter(image_rek_map, config)
    images_skipped = images_evaluated - len(selected)

    logger.info(
        "Trigger filter: %d evaluated, %d selected, %d skipped",
        images_evaluated, len(selected), images_skipped,
    )
    for item in selected:
        logger.info("Selected: %s (reason=%s, faces=%d, labels=%d)",
                     item["s3_key"], item["reason"], item["face_count"], len(item["labels"]))

    if not selected:
        logger.info("No images selected for description, returning skipped")
        return {"case_id": case_id, "status": "completed", "descriptions": [],
                "images_evaluated": images_evaluated, "images_described": 0,
                "images_skipped": images_skipped, "artifact_key": None, "batch_job_id": None}

    # Check for batch inference mode
    use_batch = config.get("use_batch_inference", False)
    if use_batch:
        return _handle_batch_inference(s3, s3_bucket, case_id, selected, image_rek_map, config,
                                       images_evaluated, images_skipped)

    # Load case entities for mention extraction
    case_entities = _load_case_entities(s3, s3_bucket, case_id)

    # Get embedding model from effective config
    embed_cfg = event.get("effective_config", {}).get("embed", {})
    embed_model_id = embed_cfg.get("embedding_model_id", _DEFAULT_EMBEDDING_MODEL)

    model_id = config.get("model_id", _DEFAULT_MODEL_ID) or _DEFAULT_MODEL_ID
    run_id = uuid.uuid4().hex[:12]
    descriptions = []

    for item in selected:
        image_key = item["s3_key"]
        rek_data = image_rek_map.get(image_key, {})
        source_doc_id = rek_data.get("source_document_id", "unknown")

        rek_context = {
            "face_count": item["face_count"],
            "labels": item["labels"],
        }

        result = _describe_image(s3, bedrock, s3_bucket, image_key, rek_context, config)
        if result is None:
            continue

        # Extract entity mentions
        mentioned = extract_mentioned_entities(result["description"], case_entities)

        # Generate embedding
        embedding = _generate_embedding(bedrock, result["description"], embed_model_id)

        # Index in search backend
        _index_description(
            case_id, source_doc_id, image_key,
            result["description"], embedding, item["labels"],
        )

        desc_entry = {
            "image_s3_key": image_key,
            "source_document_id": source_doc_id,
            "description": result["description"],
            "rekognition_context": rek_context,
            "mentioned_entities": mentioned,
            "model_id": result["model_id"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "duration_ms": result["duration_ms"],
        }
        descriptions.append(desc_entry)

    # Build and store artifact
    artifact = build_description_artifact(
        case_id, run_id, model_id, descriptions, images_evaluated, images_skipped,
    )
    artifact_s3_key = get_artifact_s3_key(case_id, run_id)

    try:
        s3.put_object(
            Bucket=s3_bucket,
            Key=artifact_s3_key,
            Body=json.dumps(artifact, default=str).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Stored description artifact: %s", artifact_s3_key)
    except Exception as e:
        logger.error("Failed to store artifact: %s", str(e)[:200])
        artifact_s3_key = None

    logger.info(
        "Image description complete: %d described, %d skipped, %d evaluated",
        len(descriptions), images_skipped, images_evaluated,
    )

    return {
        "case_id": case_id,
        "status": "completed",
        "descriptions": descriptions,
        "images_evaluated": images_evaluated,
        "images_described": len(descriptions),
        "images_skipped": images_skipped,
        "artifact_key": artifact_s3_key,
        "batch_job_id": None,
    }


def _handle_batch_inference(s3_client, s3_bucket: str, case_id: str,
                            selected: list[dict], image_rek_map: dict,
                            config: dict, images_evaluated: int,
                            images_skipped: int) -> dict:
    """Prepare and submit a Bedrock Batch Inference job.

    Falls back to real-time invocation on submission failure.
    """
    from services.image_description_service import (
        build_investigative_prompt, get_system_prompt, get_artifact_s3_key,
    )

    model_id = config.get("model_id", _DEFAULT_MODEL_ID) or _DEFAULT_MODEL_ID
    max_tokens = config.get("max_tokens_per_image", 1024)
    custom_prompt = config.get("custom_prompt")
    run_id = uuid.uuid4().hex[:12]

    # Build JSONL batch input
    jsonl_lines = []
    for item in selected:
        image_key = item["s3_key"]
        rek_context = {
            "face_count": item["face_count"],
            "labels": item["labels"],
        }
        prompt_text = build_investigative_prompt(rek_context, custom_prompt)
        system_prompt = get_system_prompt()

        # For batch, we reference S3 image location instead of base64
        record = {
            "recordId": image_key,
            "modelInput": {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"[Image from S3: {image_key}]\n\n{prompt_text}",
                        },
                    ],
                }],
            },
        }
        jsonl_lines.append(json.dumps(record))

    jsonl_content = "\n".join(jsonl_lines)
    jsonl_key = f"cases/{case_id}/image-description-artifacts/{run_id}_batch_input.jsonl"

    try:
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=jsonl_key,
            Body=jsonl_content.encode("utf-8"),
            ContentType="application/jsonl",
        )
        logger.info("Stored batch input JSONL: %s (%d records)", jsonl_key, len(jsonl_lines))
    except Exception as e:
        logger.error("Failed to store batch JSONL: %s", str(e)[:200])
        # Fall back to real-time
        logger.warning("Batch JSONL upload failed, falling back to real-time invocation")
        return _fallback_to_realtime(s3_client, s3_bucket, case_id, selected, image_rek_map,
                                     config, images_evaluated, images_skipped)

    # Submit batch inference job
    try:
        bedrock = boto3.client("bedrock", region_name=AWS_REGION)
        input_config = {
            "s3InputDataConfig": {
                "s3Uri": f"s3://{s3_bucket}/{jsonl_key}",
            },
        }
        output_config = {
            "s3OutputDataConfig": {
                "s3Uri": f"s3://{s3_bucket}/cases/{case_id}/image-description-artifacts/{run_id}_batch_output/",
            },
        }
        iam_role = os.environ.get("BEDROCK_BATCH_ROLE_ARN", "")
        if not iam_role:
            raise ValueError("BEDROCK_BATCH_ROLE_ARN not configured")

        response = bedrock.create_model_invocation_job(
            jobName=f"img-desc-{case_id[:8]}-{run_id}",
            modelId=model_id,
            roleArn=iam_role,
            inputDataConfig=input_config,
            outputDataConfig=output_config,
        )
        batch_job_id = response.get("jobArn", "")
        logger.info("Submitted batch inference job: %s", batch_job_id)

        return {
            "case_id": case_id,
            "status": "batch_submitted",
            "descriptions": [],
            "images_evaluated": images_evaluated,
            "images_described": 0,
            "images_skipped": images_skipped,
            "artifact_key": jsonl_key,
            "batch_job_id": batch_job_id,
        }
    except Exception as e:
        logger.warning("Batch inference submission failed: %s. Falling back to real-time.", str(e)[:200])
        return _fallback_to_realtime(s3_client, s3_bucket, case_id, selected, image_rek_map,
                                     config, images_evaluated, images_skipped)


def _fallback_to_realtime(s3_client, s3_bucket: str, case_id: str,
                          selected: list[dict], image_rek_map: dict,
                          config: dict, images_evaluated: int,
                          images_skipped: int) -> dict:
    """Fall back to real-time invocation when batch fails."""
    from services.image_description_service import (
        extract_mentioned_entities, build_description_artifact, get_artifact_s3_key,
    )

    logger.warning("Falling back to real-time invocation for up to %d images",
                    config.get("max_images_per_run", 50))

    bedrock = _get_bedrock_client()
    model_id = config.get("model_id", _DEFAULT_MODEL_ID) or _DEFAULT_MODEL_ID
    run_id = uuid.uuid4().hex[:12]
    case_entities = _load_case_entities(s3_client, s3_bucket, case_id)
    descriptions = []

    max_images = config.get("max_images_per_run", 50)
    for item in selected[:max_images]:
        image_key = item["s3_key"]
        rek_data = image_rek_map.get(image_key, {})
        source_doc_id = rek_data.get("source_document_id", "unknown")
        rek_context = {"face_count": item["face_count"], "labels": item["labels"]}

        result = _describe_image(s3_client, bedrock, s3_bucket, image_key, rek_context, config)
        if result is None:
            continue

        mentioned = extract_mentioned_entities(result["description"], case_entities)

        desc_entry = {
            "image_s3_key": image_key,
            "source_document_id": source_doc_id,
            "description": result["description"],
            "rekognition_context": rek_context,
            "mentioned_entities": mentioned,
            "model_id": result["model_id"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "duration_ms": result["duration_ms"],
        }
        descriptions.append(desc_entry)

    artifact = build_description_artifact(
        case_id, run_id, model_id, descriptions, images_evaluated, images_skipped,
    )
    artifact_s3_key = get_artifact_s3_key(case_id, run_id)

    try:
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=artifact_s3_key,
            Body=json.dumps(artifact, default=str).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as e:
        logger.error("Failed to store fallback artifact: %s", str(e)[:200])
        artifact_s3_key = None

    return {
        "case_id": case_id,
        "status": "completed",
        "descriptions": descriptions,
        "images_evaluated": images_evaluated,
        "images_described": len(descriptions),
        "images_skipped": images_skipped,
        "artifact_key": artifact_s3_key,
        "batch_job_id": None,
    }
