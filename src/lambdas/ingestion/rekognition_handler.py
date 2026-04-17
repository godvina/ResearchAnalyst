"""Lambda handler for Rekognition image/video analysis pipeline step.

Processes image files (JPEG, PNG, TIFF) and video files (MP4, MOV) from a
case's S3 prefix using Amazon Rekognition APIs. Detects faces, labels, text,
and optionally matches faces against watchlist collections. Converts detections
to entity format for the graph loader and stores results as JSON artifacts in S3.

Also supports importing pre-processed Rekognition JSON from
s3://bucket/cases/{case_id}/rekognition-output/.
"""

import json
import logging
import os
import re
import time
import uuid

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Feature flag: when "false", Rekognition processing is skipped
_REKOGNITION_ENABLED = os.environ.get("REKOGNITION_ENABLED", "true") == "true"

S3_BUCKET = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}

# Investigative object labels worth tracking as entities
# Organized by investigative category for criminal/trafficking cases
INVESTIGATIVE_LABELS = {
    # Weapons & contraband
    "weapon", "gun", "knife", "firearm", "handgun", "rifle",
    # Drugs & substances
    "drug", "pill", "syringe", "alcohol", "bottle", "wine",
    # Financial instruments
    "currency", "money", "cash", "credit card", "check", "receipt",
    # Vehicles & transport
    "car", "vehicle", "boat", "yacht", "airplane", "helicopter",
    "limousine", "motorcycle", "bicycle", "taxi", "bus",
    # Electronics & surveillance
    "phone", "cell phone", "computer", "laptop", "tablet", "camera",
    "monitor", "television", "headphones",
    # Documents & identity
    "passport", "document", "letter", "envelope", "book", "newspaper",
    "sign", "license plate", "badge", "id card",
    # Luggage & containers
    "suitcase", "bag", "backpack", "briefcase", "box", "package",
    "handbag", "purse",
    # Valuables & luxury
    "jewelry", "watch", "ring", "necklace", "sunglasses", "hat",
    # Locations & settings (contextual for trafficking cases)
    "swimming pool", "pool", "hot tub", "bedroom", "bed", "hotel",
    "resort", "mansion", "building", "house", "apartment",
    "island", "beach", "pier", "dock", "marina", "airport",
    "gate", "fence", "security camera",
    # People & clothing context
    "uniform", "suit", "dress", "swimwear", "bikini", "lingerie",
    "mask", "costume", "wig",
    # Furniture & interior (scene context)
    "couch", "sofa", "chair", "table", "desk", "safe",
    # Food & hospitality (event context + cross-case patterns)
    "food", "dining table", "wine glass", "champagne",
    "pizza", "restaurant", "bar", "nightclub", "cafe",
    # Symbols, art & decor (cross-case pattern indicators)
    "painting", "poster", "mural", "statue", "sculpture",
    "flag", "banner", "symbol", "logo", "tattoo", "graffiti",
    # Infrastructure & concealment
    "tunnel", "basement", "staircase", "elevator", "corridor",
    "door", "window", "lock", "key", "chain", "rope", "tape",
    "handcuffs", "restraint",
    # Nature & outdoor (location context)
    "palm tree", "garden", "forest", "mountain",
}

MIN_PERSON_NAME_LENGTH = 3
NOISE_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "is", "it", "this", "that", "with", "from", "by", "as", "be", "was",
    "are", "were", "been", "have", "has", "had", "do", "does", "did",
}


def _get_rekognition_client():
    """Return a boto3 Rekognition client."""
    return boto3.client("rekognition", region_name=AWS_REGION)


def _get_s3_client():
    """Return a boto3 S3 client."""
    return boto3.client("s3", region_name=AWS_REGION)


def _is_quality_person(name: str) -> bool:
    """Filter out OCR noise from person entity names."""
    if not name or len(name) < MIN_PERSON_NAME_LENGTH:
        return False
    if name.lower() in NOISE_WORDS:
        return False
    if name.replace(" ", "").replace("-", "").isdigit():
        return False
    words = name.split()
    if len(words) == 1 and len(name) < 4:
        return False
    alpha_ratio = sum(1 for c in name if c.isalpha()) / max(len(name), 1)
    if alpha_ratio < 0.5:
        return False
    return True


def _parse_source_document_id(filename: str) -> str:
    """Parse the source document ID from an extracted image filename.

    Expected pattern: {document_id}_page{N}_img{M}.{ext}
    Splits on '_page' and returns everything before the first occurrence.

    Returns:
        The source document_id, or "unknown" if the filename doesn't match.
    """
    if "_page" in filename:
        return filename.split("_page")[0]
    logger.warning("Extracted image filename does not match expected pattern: %s", filename)
    return "unknown"


def _list_extracted_images(s3_client, s3_bucket: str, case_id: str) -> list:
    """List image files under the case's extracted-images/ S3 prefix.

    Returns a list of dicts with s3_key, type, size, and source_document_id.
    """
    prefix = f"cases/{case_id}/extracted-images/"
    extracted = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            lower_key = key.lower()
            ext = "." + lower_key.rsplit(".", 1)[-1] if "." in lower_key else ""
            if ext in IMAGE_EXTENSIONS:
                filename = key[len(prefix):]
                source_doc_id = _parse_source_document_id(filename)
                extracted.append({
                    "s3_key": key,
                    "type": "image",
                    "size": obj["Size"],
                    "source_document_id": source_doc_id,
                })

    logger.info("Found %d extracted images for case %s", len(extracted), case_id)
    return extracted


def _list_media_files(s3_client, s3_bucket: str, case_id: str) -> list:
    """List image and video files under the case's S3 prefix."""
    prefix = f"cases/{case_id}/"
    media_files = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            lower_key = key.lower()
            ext = "." + lower_key.rsplit(".", 1)[-1] if "." in lower_key else ""
            if ext in IMAGE_EXTENSIONS:
                media_files.append({"s3_key": key, "type": "image", "size": obj["Size"]})
            elif ext in VIDEO_EXTENSIONS:
                media_files.append({"s3_key": key, "type": "video", "size": obj["Size"]})

    logger.info("Found %d media files for case %s", len(media_files), case_id)
    return media_files


def _process_image(s3_bucket: str, s3_key: str, config: dict) -> dict:
    """Run Rekognition detect_faces, detect_labels, detect_text on an image.

    Returns a dict with faces, labels, and text detections.
    """
    rek = _get_rekognition_client()
    image_ref = {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
    min_face_conf = config.get("min_face_confidence", 0.8) * 100
    min_obj_conf = config.get("min_object_confidence", 0.7) * 100
    result = {"s3_key": s3_key, "type": "image", "faces": [], "labels": [], "text": []}

    # Detect faces
    try:
        face_resp = rek.detect_faces(
            Image=image_ref,
            Attributes=["ALL"],
        )
        for face in face_resp.get("FaceDetails", []):
            confidence = face.get("Confidence", 0)
            if confidence >= min_face_conf:
                result["faces"].append({
                    "confidence": round(confidence / 100, 4),
                    "bounding_box": face.get("BoundingBox", {}),
                    "age_range": face.get("AgeRange", {}),
                    "gender": face.get("Gender", {}),
                    "emotions": face.get("Emotions", []),
                })
    except Exception as e:
        logger.warning("detect_faces failed for %s: %s", s3_key, str(e)[:200])

    # Detect labels (objects/scenes)
    try:
        label_resp = rek.detect_labels(
            Image=image_ref,
            MinConfidence=min_obj_conf,
        )
        for label in label_resp.get("Labels", []):
            result["labels"].append({
                "name": label.get("Name", ""),
                "confidence": round(label.get("Confidence", 0) / 100, 4),
                "parents": [p.get("Name", "") for p in label.get("Parents", [])],
                "instances": label.get("Instances", []),
            })
    except Exception as e:
        logger.warning("detect_labels failed for %s: %s", s3_key, str(e)[:200])

    # Detect text (OCR)
    if config.get("detect_text", True):
        try:
            text_resp = rek.detect_text(Image=image_ref)
            for text_item in text_resp.get("TextDetections", []):
                if text_item.get("Type") == "LINE":
                    result["text"].append({
                        "detected_text": text_item.get("DetectedText", ""),
                        "confidence": round(text_item.get("Confidence", 0) / 100, 4),
                        "bounding_box": text_item.get("Geometry", {}).get("BoundingBox", {}),
                    })
        except Exception as e:
            logger.warning("detect_text failed for %s: %s", s3_key, str(e)[:200])

    # Watchlist face comparison (if configured)
    watchlist_id = config.get("watchlist_collection_id")
    if watchlist_id:
        try:
            search_resp = rek.search_faces_by_image(
                CollectionId=watchlist_id,
                Image=image_ref,
                FaceMatchThreshold=min_face_conf,
                MaxFaces=10,
            )
            matches = []
            for match in search_resp.get("FaceMatches", []):
                face_record = match.get("Face", {})
                matches.append({
                    "face_id": face_record.get("FaceId", ""),
                    "external_image_id": face_record.get("ExternalImageId", ""),
                    "similarity": round(match.get("Similarity", 0) / 100, 4),
                })
            if matches:
                result["watchlist_matches"] = matches
        except Exception as e:
            logger.warning("search_faces_by_image failed for %s: %s", s3_key, str(e)[:200])

    return result


def _process_video(s3_bucket: str, s3_key: str, config: dict) -> dict:
    """Start async Rekognition video analysis jobs and poll for completion.

    Starts label detection and face detection jobs, then polls until complete.
    Returns a dict with labels and faces from the video.
    """
    rek = _get_rekognition_client()
    video_ref = {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
    min_face_conf = config.get("min_face_confidence", 0.8) * 100
    min_obj_conf = config.get("min_object_confidence", 0.7) * 100
    result = {"s3_key": s3_key, "type": "video", "labels": [], "faces": []}

    # Start label detection
    label_job_id = None
    try:
        label_resp = rek.start_label_detection(
            Video=video_ref,
            MinConfidence=min_obj_conf,
        )
        label_job_id = label_resp.get("JobId")
        logger.info("Started label detection job %s for %s", label_job_id, s3_key)
    except Exception as e:
        logger.warning("start_label_detection failed for %s: %s", s3_key, str(e)[:200])

    # Start face detection
    face_job_id = None
    try:
        face_resp = rek.start_face_detection(
            Video=video_ref,
            FaceAttributes="ALL",
        )
        face_job_id = face_resp.get("JobId")
        logger.info("Started face detection job %s for %s", face_job_id, s3_key)
    except Exception as e:
        logger.warning("start_face_detection failed for %s: %s", s3_key, str(e)[:200])

    # Poll label detection
    if label_job_id:
        result["labels"] = _poll_video_labels(rek, label_job_id, min_obj_conf)

    # Poll face detection
    if face_job_id:
        result["faces"] = _poll_video_faces(rek, face_job_id, min_face_conf)

    return result


def _poll_video_labels(rek, job_id: str, min_confidence: float, max_wait: int = 600) -> list:
    """Poll get_label_detection until complete, return labels."""
    labels_map = {}  # name -> best confidence
    start = time.time()

    while time.time() - start < max_wait:
        try:
            resp = rek.get_label_detection(JobId=job_id, SortBy="TIMESTAMP")
            status = resp.get("JobStatus", "")
            if status == "SUCCEEDED":
                for item in resp.get("Labels", []):
                    label = item.get("Label", {})
                    name = label.get("Name", "")
                    conf = label.get("Confidence", 0)
                    if name and conf >= min_confidence:
                        if name not in labels_map or conf > labels_map[name]:
                            labels_map[name] = conf
                break
            if status == "FAILED":
                logger.error("Label detection job %s failed", job_id)
                break
        except Exception as e:
            logger.warning("Poll label detection error: %s", str(e)[:200])
        time.sleep(10)

    return [
        {"name": name, "confidence": round(conf / 100, 4)}
        for name, conf in labels_map.items()
    ]


def _poll_video_faces(rek, job_id: str, min_confidence: float, max_wait: int = 600) -> list:
    """Poll get_face_detection until complete, return face detections."""
    faces = []
    start = time.time()

    while time.time() - start < max_wait:
        try:
            resp = rek.get_face_detection(JobId=job_id)
            status = resp.get("JobStatus", "")
            if status == "SUCCEEDED":
                for item in resp.get("Faces", []):
                    face = item.get("Face", {})
                    confidence = face.get("Confidence", 0)
                    if confidence >= min_confidence:
                        faces.append({
                            "confidence": round(confidence / 100, 4),
                            "timestamp_ms": item.get("Timestamp", 0),
                            "bounding_box": face.get("BoundingBox", {}),
                            "age_range": face.get("AgeRange", {}),
                            "gender": face.get("Gender", {}),
                            "emotions": face.get("Emotions", []),
                        })
                break
            if status == "FAILED":
                logger.error("Face detection job %s failed", job_id)
                break
        except Exception as e:
            logger.warning("Poll face detection error: %s", str(e)[:200])
        time.sleep(10)

    return faces


def _process_video_faces_only(s3_bucket: str, s3_key: str, config: dict) -> dict:
    """Run only face detection on video — no label detection. Cheaper mode."""
    rek = _get_rekognition_client()
    video_ref = {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
    min_face_conf = config.get("min_face_confidence", 0.8) * 100
    result = {"s3_key": s3_key, "type": "video", "labels": [], "faces": []}

    face_job_id = None
    try:
        face_resp = rek.start_face_detection(Video=video_ref, FaceAttributes="ALL")
        face_job_id = face_resp.get("JobId")
        logger.info("Started faces-only job %s for %s", face_job_id, s3_key)
    except Exception as e:
        logger.warning("start_face_detection failed for %s: %s", s3_key, str(e)[:200])

    if face_job_id:
        result["faces"] = _poll_video_faces(rek, face_job_id, min_face_conf)

    return result


def _get_flagged_videos(case_id: str) -> set:
    """Query Aurora for videos flagged for analysis by an investigator."""
    try:
        from db.connection import ConnectionManager
        cm = ConnectionManager()
        with cm.cursor() as cur:
            cur.execute(
                """
                SELECT s3_key FROM documents
                WHERE case_file_id = %s
                  AND (tags @> '["flagged_for_video_analysis"]'::jsonb
                       OR source_filename LIKE '%%.mp4'
                       OR source_filename LIKE '%%.mov')
                  AND EXISTS (
                      SELECT 1 FROM investigator_findings f
                      WHERE f.case_id = %s
                        AND f.finding_type = 'video_flag'
                        AND f.document_refs @> ARRAY[documents.document_id::text]
                  )
                """,
                (case_id, case_id),
            )
            return {row[0] for row in cur.fetchall() if row[0]}
    except Exception as e:
        logger.warning("Failed to get flagged videos: %s", str(e)[:200])
        return set()


def _results_to_entities(results: list, config: dict) -> list:
    """Convert Rekognition detections to entity format for graph loader.

    Creates person entities for face/watchlist matches, object entities for
    significant detections (weapons, drugs, vehicles, currency, electronics),
    and phone_number entities from detected text.
    """
    entities = {}  # canonical_name -> entity dict
    min_obj_conf = config.get("min_object_confidence", 0.7)

    for result in results:
        s3_key = result.get("s3_key", "")

        # Person entities from watchlist matches
        for match in result.get("watchlist_matches", []):
            name = match.get("external_image_id", "")
            if _is_quality_person(name):
                if name in entities:
                    entities[name]["occurrence_count"] += 1
                    entities[name]["confidence"] = max(
                        entities[name]["confidence"], match.get("similarity", 0.8)
                    )
                else:
                    entities[name] = {
                        "canonical_name": name,
                        "entity_type": "person",
                        "confidence": match.get("similarity", 0.8),
                        "occurrence_count": 1,
                        "source": "rekognition_watchlist",
                        "source_files": [s3_key],
                    }

        # Person entities from face detections (anonymous faces)
        for i, face in enumerate(result.get("faces", [])):
            confidence = face.get("confidence", 0)
            gender_val = face.get("gender", {})
            gender = gender_val.get("Value", "Unknown") if isinstance(gender_val, dict) else "Unknown"
            age_range = face.get("age_range", {})
            age_low = age_range.get("Low", 0) if isinstance(age_range, dict) else 0
            age_high = age_range.get("High", 0) if isinstance(age_range, dict) else 0
            face_label = f"Unidentified Face ({gender}, ~{age_low}-{age_high})"
            # Group similar anonymous faces by gender+age bucket
            bucket_key = f"face_{gender}_{age_low // 10 * 10}_{age_high // 10 * 10}"
            if bucket_key in entities:
                entities[bucket_key]["occurrence_count"] += 1
                entities[bucket_key]["confidence"] = max(
                    entities[bucket_key]["confidence"], confidence
                )
            else:
                entities[bucket_key] = {
                    "canonical_name": face_label,
                    "entity_type": "person",
                    "confidence": confidence,
                    "occurrence_count": 1,
                    "source": "rekognition_face",
                    "source_files": [s3_key],
                }

        # Object/artifact entities from labels
        for label in result.get("labels", []):
            label_name = label.get("name", "")
            label_conf = label.get("confidence", 0)
            if label_name.lower() in INVESTIGATIVE_LABELS and label_conf >= min_obj_conf:
                if label_name in entities:
                    entities[label_name]["occurrence_count"] += 1
                    entities[label_name]["confidence"] = max(
                        entities[label_name]["confidence"], label_conf
                    )
                else:
                    entities[label_name] = {
                        "canonical_name": label_name,
                        "entity_type": "artifact",
                        "confidence": label_conf,
                        "occurrence_count": 1,
                        "source": "rekognition_label",
                        "source_files": [s3_key],
                    }

        # Phone numbers from detected text
        for text_item in result.get("text", []):
            detected = text_item.get("detected_text", "")
            if detected and len(detected) > 5:
                phone_match = re.search(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", detected)
                if phone_match:
                    phone = phone_match.group()
                    if phone in entities:
                        entities[phone]["occurrence_count"] += 1
                    else:
                        entities[phone] = {
                            "canonical_name": phone,
                            "entity_type": "phone_number",
                            "confidence": text_item.get("confidence", 0.8),
                            "occurrence_count": 1,
                            "source": "rekognition_text",
                            "source_files": [s3_key],
                        }

    return list(entities.values())


def _import_existing_results(s3_bucket: str, case_id: str) -> list:
    """Import pre-processed Rekognition JSON from S3.

    Reads from s3://bucket/cases/{case_id}/rekognition-output/ and converts
    existing Rekognition results into the standard result format.
    """
    s3 = _get_s3_client()
    prefix = f"cases/{case_id}/rekognition-output/"
    results = []
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Size"] < 100:
                continue
            try:
                body = s3.get_object(Bucket=s3_bucket, Key=obj["Key"])["Body"].read().decode()
                data = json.loads(body)
                result = {
                    "s3_key": obj["Key"],
                    "type": "imported",
                    "faces": [],
                    "labels": [],
                    "text": [],
                    "watchlist_matches": [],
                }

                # Convert celebrities to watchlist-style matches
                for celeb in data.get("celebrities", []):
                    name = celeb.get("Name", celeb.get("name", ""))
                    if name and _is_quality_person(name):
                        conf = celeb.get("MatchConfidence", celeb.get("confidence", 90))
                        result["watchlist_matches"].append({
                            "external_image_id": name,
                            "similarity": round(conf / 100, 4) if conf > 1 else conf,
                        })

                # Convert labels
                for label in data.get("labels", []):
                    lname = label.get("Name", label.get("name", ""))
                    conf = label.get("Confidence", label.get("confidence", 80))
                    if lname:
                        result["labels"].append({
                            "name": lname,
                            "confidence": round(conf / 100, 4) if conf > 1 else conf,
                        })

                # Convert text detections
                for text_item in data.get("text", []):
                    detected = text_item.get("DetectedText", text_item.get("text", ""))
                    conf = text_item.get("Confidence", text_item.get("confidence", 80))
                    if detected:
                        result["text"].append({
                            "detected_text": detected,
                            "confidence": round(conf / 100, 4) if conf > 1 else conf,
                        })

                # Convert face detections from personEntities
                for person in data.get("personEntities", []):
                    if _is_quality_person(person):
                        result["watchlist_matches"].append({
                            "external_image_id": person.strip(),
                            "similarity": 0.7,
                        })

                results.append(result)
            except Exception as e:
                logger.warning("Failed to import %s: %s", obj["Key"], str(e)[:200])

    logger.info("Imported %d pre-processed Rekognition results for case %s", len(results), case_id)
    return results


def _store_results_artifact(s3_bucket: str, case_id: str, results: list, entities: list) -> str:
    """Store Rekognition results as a JSON artifact in S3."""
    s3 = _get_s3_client()
    artifact = {
        "case_id": case_id,
        "media_processed": len(results),
        "entity_count": len(entities),
        "results": results,
        "entities": entities,
    }
    artifact_key = f"cases/{case_id}/rekognition-artifacts/{uuid.uuid4().hex[:12]}_rekognition.json"
    s3.put_object(
        Bucket=s3_bucket,
        Key=artifact_key,
        Body=json.dumps(artifact, default=str).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Stored Rekognition artifact: %s", artifact_key)
    return artifact_key


def _build_face_crop_metadata(results: list, extracted_images: list) -> list:
    """Build face_crop_metadata from Rekognition results for the graph loader.

    For each face detection with confidence >= 0.90, creates a metadata entry
    linking the face crop to its source image and document. Uses the extracted
    images list to resolve source_document_id from filenames.

    Returns a list of dicts, each with: crop_s3_key, source_s3_key,
    source_document_id, bounding_box, confidence, entity_name.
    """
    import hashlib

    # Build lookup: s3_key -> source_document_id from extracted images
    key_to_doc_id = {}
    for img in extracted_images:
        key_to_doc_id[img["s3_key"]] = img.get("source_document_id", "unknown")

    # Build lookup: s3_key -> list of entity names from watchlist matches
    key_entity_map = {}
    for result in results:
        s3_key = result.get("s3_key", "")
        for match in result.get("watchlist_matches", []):
            name = match.get("external_image_id", "")
            if name:
                key_entity_map.setdefault(s3_key, []).append(name)

    metadata = []
    for result in results:
        s3_key = result.get("s3_key", "")
        source_doc_id = key_to_doc_id.get(s3_key, "unknown")

        for face in result.get("faces", []):
            confidence = face.get("confidence", 0)
            if confidence < 0.90:
                continue

            bounding_box = face.get("bounding_box", {})
            if not bounding_box:
                continue

            # Compute crop hash (same algorithm as FaceCropService)
            left = bounding_box.get("Left", 0.0)
            top = bounding_box.get("Top", 0.0)
            width = bounding_box.get("Width", 0.0)
            height = bounding_box.get("Height", 0.0)
            raw = f"{s3_key}:{left}:{top}:{width}:{height}"
            crop_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

            entity_names = key_entity_map.get(s3_key, ["unidentified"])

            for entity_name in entity_names:
                # Derive case_id from s3_key: cases/{case_id}/...
                parts = s3_key.split("/")
                case_id = parts[1] if len(parts) > 1 else "unknown"
                crop_s3_key = f"cases/{case_id}/face-crops/{entity_name}/{crop_hash}.jpg"

                metadata.append({
                    "crop_s3_key": crop_s3_key,
                    "source_s3_key": s3_key,
                    "source_document_id": source_doc_id,
                    "bounding_box": {
                        "Left": left,
                        "Top": top,
                        "Width": width,
                        "Height": height,
                    },
                    "confidence": confidence,
                    "entity_name": entity_name,
                })

    logger.info("Built %d face_crop_metadata entries", len(metadata))
    return metadata


def _store_face_crop_metadata_artifact(s3_bucket: str, case_id: str, metadata: list) -> str:
    """Store face_crop_metadata as a JSON artifact in S3 for the graph loader."""
    s3 = _get_s3_client()
    artifact_key = f"cases/{case_id}/rekognition-artifacts/face_crop_metadata.json"
    s3.put_object(
        Bucket=s3_bucket,
        Key=artifact_key,
        Body=json.dumps(metadata, default=str).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Stored face_crop_metadata artifact: %s (%d entries)", artifact_key, len(metadata))
    return artifact_key


def handler(event, context):
    """Process images/video for a case using Amazon Rekognition.

    Event format:
        {
            "case_id": "...",
            "effective_config": {"rekognition": {"enabled": true, ...}},
        }

    Returns:
        {
            "case_id": "...",
            "status": "completed" | "skipped",
            "entities": [...],
            "media_processed": int,
            "artifact_key": "...",
        }
    """
    case_id = event["case_id"]

    # Check environment-level feature flag first
    if not _REKOGNITION_ENABLED:
        logger.info("Rekognition disabled via REKOGNITION_ENABLED env var for case %s", case_id)
        return {
            "case_id": case_id,
            "status": "skipped",
            "reason": "rekognition_disabled",
            "labels": [],
            "faces": [],
            "entities": [],
            "source": "disabled",
        }

    config = event.get("effective_config", {}).get("rekognition", {})
    document_ids = event.get("document_ids", [])

    if not config.get("enabled", False):
        logger.info("Rekognition disabled for case %s, skipping", case_id)
        return {"case_id": case_id, "status": "skipped", "reason": "rekognition_disabled"}

    s3_bucket = S3_BUCKET
    if not s3_bucket:
        logger.error("S3_DATA_BUCKET not configured")
        return {"case_id": case_id, "status": "error", "reason": "s3_bucket_not_configured"}

    s3 = _get_s3_client()

    # Check for pre-processed Rekognition output first
    imported_results = _import_existing_results(s3_bucket, case_id)

    # List and process media files (uploaded + extracted from PDFs)
    media_files = _list_media_files(s3, s3_bucket, case_id)
    extracted_images = _list_extracted_images(s3, s3_bucket, case_id)

    # Filter to only images from the current batch's documents (if document_ids provided)
    if document_ids:
        doc_id_set = set(document_ids)
        extracted_images = [
            img for img in extracted_images
            if img.get("source_document_id", "unknown") in doc_id_set
        ]
        # Also filter media_files to only those from current batch docs
        media_files = [
            f for f in media_files
            if any(f["s3_key"].split("/")[-1].startswith(did) for did in doc_id_set)
        ]
        logger.info(
            "Filtered to %d extracted images and %d media files for %d document IDs",
            len(extracted_images), len(media_files), len(document_ids),
        )

    all_media = media_files + extracted_images
    extracted_image_count = len(extracted_images)
    results = list(imported_results)

    # Separate images and videos
    images = [f for f in all_media if f["type"] == "image"]
    videos = [f for f in all_media if f["type"] == "video"]
    video_mode = config.get("video_processing_mode", "skip")

    # Always process images
    for media_file in images:
        try:
            result = _process_image(s3_bucket, media_file["s3_key"], config)
            results.append(result)
        except Exception as e:
            logger.error("Failed to process image %s: %s", media_file["s3_key"], str(e)[:300])

    # Process videos based on video_processing_mode
    if video_mode == "skip":
        logger.info("Video processing mode: skip — ignoring %d video files", len(videos))
    elif video_mode == "faces_only":
        logger.info("Video processing mode: faces_only — processing %d videos for faces", len(videos))
        for media_file in videos:
            try:
                result = _process_video_faces_only(s3_bucket, media_file["s3_key"], config)
                results.append(result)
            except Exception as e:
                logger.error("Failed to process video %s: %s", media_file["s3_key"], str(e)[:300])
    elif video_mode == "targeted":
        flagged = _get_flagged_videos(case_id)
        targeted_videos = [v for v in videos if v["s3_key"] in flagged]
        logger.info("Video processing mode: targeted — %d/%d videos flagged", len(targeted_videos), len(videos))
        for media_file in targeted_videos:
            try:
                result = _process_video(s3_bucket, media_file["s3_key"], config)
                results.append(result)
            except Exception as e:
                logger.error("Failed to process video %s: %s", media_file["s3_key"], str(e)[:300])
    elif video_mode == "full":
        logger.info("Video processing mode: full — processing all %d videos", len(videos))
        for media_file in videos:
            try:
                result = _process_video(s3_bucket, media_file["s3_key"], config)
                results.append(result)
            except Exception as e:
                logger.error("Failed to process video %s: %s", media_file["s3_key"], str(e)[:300])

    # Convert all results to entities
    entities = _results_to_entities(results, config)
    logger.info("Extracted %d entities from %d media files for case %s",
                len(entities), len(results), case_id)

    # Build face_crop_metadata from results for graph loader
    face_crop_metadata = _build_face_crop_metadata(results, extracted_images)

    # Store results artifact in S3
    artifact_key = _store_results_artifact(s3_bucket, case_id, results, entities)

    # Store face_crop_metadata as a separate S3 artifact for the graph loader
    if face_crop_metadata:
        _store_face_crop_metadata_artifact(s3_bucket, case_id, face_crop_metadata)

    return {
        "case_id": case_id,
        "status": "completed",
        "entities": entities,
        "face_crop_metadata": face_crop_metadata,
        "media_processed": len(all_media),
        "imported_count": len(imported_results),
        "extracted_image_count": extracted_image_count,
        "artifact_key": artifact_key,
    }
