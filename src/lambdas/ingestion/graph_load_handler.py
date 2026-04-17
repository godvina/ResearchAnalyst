"""Lambda handler for graph loading step of the ingestion pipeline.

Uses Neptune's bulk CSV loader for reliable loading of all entity types
and special characters. Falls back to Gremlin HTTP for small batches.
"""

import csv
import io
import json
import logging
import os
import ssl
import time
import urllib.request
import urllib.error
import uuid

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
S3_BUCKET = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))
IAM_ROLE_ARN = os.environ.get("NEPTUNE_IAM_ROLE_ARN", "")


def _loader_url():
    return f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/loader"


def _gremlin_http(query: str, timeout: int = 60) -> dict:
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        logger.error("Neptune HTTP %s: %s", e.code, body[:300])
        raise


def _escape(s: str) -> str:
    """Escape for Gremlin query strings."""
    return (s.replace("\\", "\\\\").replace("'", "\\'")
             .replace('"', '\\"').replace("\n", " ")
             .replace("\r", " ").replace("\t", " ").replace("\x00", ""))


def _load_from_s3(case_id: str, doc_results: list) -> list:
    """Load extraction artifacts from S3 for documents that don't have inline entities."""
    s3 = boto3.client("s3")
    results = []
    for doc in doc_results:
        if doc.get("status") != "success":
            results.append(doc)
            continue
        doc_id = doc.get("document_id", "")
        key = f"cases/{case_id}/extractions/{doc_id}_extraction.json"
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
            artifact = json.loads(resp["Body"].read().decode("utf-8"))
            results.append({
                "status": "success",
                "entities": artifact.get("entities", []),
                "relationships": artifact.get("relationships", []),
            })
        except Exception as exc:
            logger.warning("S3 artifact load failed for %s: %s", doc_id, str(exc)[:200])
            results.append(doc)
    loaded = len([r for r in results if r.get("entities")])
    logger.info("Loaded %d extraction artifacts from S3", loaded)
    return results


def _collect_entities_and_relationships(case_id, extraction_results):
    """Collect and deduplicate entities and relationships from extraction results."""
    entities = {}
    relationships = []
    for result in extraction_results:
        if result.get("status") != "success":
            continue
        for e in result.get("entities", []):
            name = e.get("canonical_name", e.get("name", ""))
            if not name:
                continue
            if name in entities:
                entities[name]["occurrence_count"] += e.get("occurrence_count", e.get("occurrences", 1))
            else:
                entities[name] = {
                    "canonical_name": name,
                    "entity_type": e.get("entity_type", e.get("type", "theme")),
                    "confidence": e.get("confidence", 0.5),
                    "occurrence_count": e.get("occurrence_count", e.get("occurrences", 1)),
                }
        for r in result.get("relationships", []):
            relationships.append(r)
    return entities, relationships


def _generate_and_upload_csv(case_id, entities, relationships):
    """Generate Neptune bulk load CSV files and upload to S3."""
    s3 = boto3.client("s3")
    label = f"Entity_{case_id}"
    batch_id = uuid.uuid4().hex[:12]

    # --- Nodes CSV ---
    nodes_buf = io.StringIO()
    writer = csv.writer(nodes_buf)
    writer.writerow(["~id", "~label", "entity_type:String", "canonical_name:String",
                      "confidence:Double", "occurrence_count:Int", "case_file_id:String"])
    for name, ent in entities.items():
        node_id = f"{case_id}_{ent['entity_type']}_{name}"
        writer.writerow([
            node_id, label, ent["entity_type"], name,
            ent["confidence"], ent["occurrence_count"], case_id,
        ])

    nodes_key = f"neptune-bulk-load/{case_id}/{batch_id}_nodes.csv"
    s3.put_object(Bucket=S3_BUCKET, Key=nodes_key, Body=nodes_buf.getvalue().encode("utf-8"))
    logger.info("Uploaded nodes CSV: %s (%d entities)", nodes_key, len(entities))

    # --- Edges CSV ---
    # Build node ID lookup
    node_ids = {}
    for name, ent in entities.items():
        node_ids[name] = f"{case_id}_{ent['entity_type']}_{name}"

    edges_buf = io.StringIO()
    writer = csv.writer(edges_buf)
    writer.writerow(["~id", "~from", "~to", "~label", "relationship_type:String",
                      "confidence:Double", "case_file_id:String"])

    seen_edges = set()
    edge_count = 0
    for rel in relationships:
        src = rel.get("source_entity", rel.get("from", ""))
        tgt = rel.get("target_entity", rel.get("to", ""))
        if not src or not tgt or src not in node_ids or tgt not in node_ids:
            continue
        key = (src, tgt)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        rel_type = rel.get("relationship_type", rel.get("type", "co-occurrence"))
        if isinstance(rel_type, dict):
            rel_type = rel_type.get("value", str(rel_type))
        edge_id = f"{case_id}_edge_{uuid.uuid4().hex[:8]}"
        writer.writerow([
            edge_id, node_ids[src], node_ids[tgt], "RELATED_TO",
            str(rel_type), rel.get("confidence", 0.5), case_id,
        ])
        edge_count += 1

    edges_key = f"neptune-bulk-load/{case_id}/{batch_id}_edges.csv"
    s3.put_object(Bucket=S3_BUCKET, Key=edges_key, Body=edges_buf.getvalue().encode("utf-8"))
    logger.info("Uploaded edges CSV: %s (%d edges)", edges_key, edge_count)

    return nodes_key, edges_key, len(entities), edge_count


def _trigger_bulk_load(s3_key):
    """Trigger Neptune bulk loader for a CSV file."""
    if not IAM_ROLE_ARN:
        logger.warning("NEPTUNE_IAM_ROLE_ARN not set, skipping bulk load")
        return None

    url = _loader_url()
    payload = json.dumps({
        "source": f"s3://{S3_BUCKET}/{s3_key}",
        "format": "csv",
        "iamRoleArn": IAM_ROLE_ARN,
        "region": os.environ.get("AWS_REGION", "us-east-1"),
        "failOnError": "FALSE",
        "parallelism": "MEDIUM",
        "updateSingleCardinalityProperties": "TRUE",
    }).encode("utf-8")

    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            load_id = body.get("payload", {}).get("loadId", "")
            logger.info("Bulk load started: %s for %s", load_id, s3_key)
            return load_id
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        logger.error("Bulk load trigger failed: %s %s", e.code, err_body[:300])
        return None


def _poll_bulk_load(load_id, max_wait=600):
    """Poll Neptune bulk loader until complete or timeout."""
    url = f"{_loader_url()}/{load_id}"
    ctx = ssl.create_default_context()
    start = time.time()

    while time.time() - start < max_wait:
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                status = body.get("payload", {}).get("overallStatus", {}).get("status", "")
                if status == "LOAD_COMPLETED":
                    logger.info("Bulk load %s completed", load_id)
                    return "LOAD_COMPLETED"
                if status in ("LOAD_FAILED", "LOAD_CANCELLED_BY_USER"):
                    errors = body.get("payload", {}).get("overallStatus", {}).get("errors", {})
                    logger.error("Bulk load %s failed: %s", load_id, json.dumps(errors)[:500])
                    return "LOAD_FAILED"
                logger.info("Bulk load %s status: %s", load_id, status)
        except Exception as e:
            logger.warning("Poll error: %s", str(e)[:200])
        time.sleep(10)

    logger.warning("Bulk load %s timed out after %ds", load_id, max_wait)
    return "TIMEOUT"


def _load_face_crop_metadata(case_id: str, event: dict) -> list:
    """Load face_crop_metadata from event or S3 artifact.

    The rekognition handler stores face_crop_metadata both in its return value
    (available if passed through the event) and as an S3 artifact at
    cases/{case_id}/rekognition-artifacts/face_crop_metadata.json.

    Returns a list of face crop metadata dicts.
    """
    # Try direct from event first
    metadata = event.get("face_crop_metadata", [])
    if metadata:
        logger.info("Loaded %d face_crop_metadata entries from event", len(metadata))
        return metadata

    # Try from rekognition_result in event
    rek_result = event.get("rekognition_result", {})
    metadata = rek_result.get("face_crop_metadata", [])
    if metadata:
        logger.info("Loaded %d face_crop_metadata entries from rekognition_result", len(metadata))
        return metadata

    # Fall back to S3 artifact
    if S3_BUCKET:
        s3 = boto3.client("s3")
        artifact_key = f"cases/{case_id}/rekognition-artifacts/face_crop_metadata.json"
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=artifact_key)
            metadata = json.loads(resp["Body"].read().decode("utf-8"))
            logger.info("Loaded %d face_crop_metadata entries from S3 artifact", len(metadata))
            return metadata
        except Exception as exc:
            logger.info("No face_crop_metadata artifact found in S3: %s", str(exc)[:100])

    return []


def _generate_face_crop_csv(case_id: str, face_crop_metadata: list, entities: dict) -> tuple:
    """Generate Neptune bulk load CSV for FaceCrop nodes and edges.

    Creates:
    - FaceCrop nodes with label FaceCrop_{case_id}
    - FACE_DETECTED_IN edges (FaceCrop → Document) when source_document_id != "unknown"
    - HAS_FACE_CANDIDATE edges (Person entity → FaceCrop) via document co-occurrence
    - HAS_FACE_MATCH edges (Person entity → FaceCrop) via watchlist match

    Returns (nodes_csv_key, edges_csv_key, node_count, edge_count).
    """
    s3 = boto3.client("s3")
    fc_label = f"FaceCrop_{case_id}"
    entity_label = f"Entity_{case_id}"
    batch_id = uuid.uuid4().hex[:12]

    # --- FaceCrop Nodes CSV ---
    nodes_buf = io.StringIO()
    writer = csv.writer(nodes_buf)
    writer.writerow([
        "~id", "~label", "crop_s3_key:String", "source_s3_key:String",
        "source_document_id:String", "confidence:Double",
        "case_file_id:String", "entity_name:String",
    ])

    # Track FaceCrop node IDs and doc associations for edge generation
    fc_node_ids = {}  # crop_s3_key -> node_id
    doc_to_face_crops = {}  # source_document_id -> list of crop_s3_keys
    entity_face_matches = []  # (entity_name, crop_s3_key, similarity)

    for entry in face_crop_metadata:
        crop_key = entry.get("crop_s3_key", "")
        if not crop_key or crop_key in fc_node_ids:
            continue

        source_doc_id = entry.get("source_document_id", "unknown")
        node_id = f"{case_id}_facecrop_{crop_key.split('/')[-1].replace('.jpg', '')}"
        fc_node_ids[crop_key] = node_id

        writer.writerow([
            node_id, fc_label, crop_key,
            entry.get("source_s3_key", ""),
            source_doc_id,
            entry.get("confidence", 0.0),
            case_id,
            entry.get("entity_name", "unidentified"),
        ])

        # Track document associations
        if source_doc_id != "unknown":
            doc_to_face_crops.setdefault(source_doc_id, []).append(crop_key)
        else:
            logger.warning("FaceCrop %s has unknown source_document_id, skipping FACE_DETECTED_IN edge", crop_key)

        # Track watchlist matches for HAS_FACE_MATCH edges
        entity_name = entry.get("entity_name", "unidentified")
        if entity_name != "unidentified":
            entity_face_matches.append((entity_name, crop_key, entry.get("confidence", 0.0)))

    node_count = len(fc_node_ids)
    nodes_key = f"neptune-bulk-load/{case_id}/{batch_id}_facecrop_nodes.csv"
    s3.put_object(Bucket=S3_BUCKET, Key=nodes_key, Body=nodes_buf.getvalue().encode("utf-8"))
    logger.info("Uploaded FaceCrop nodes CSV: %s (%d nodes)", nodes_key, node_count)

    # --- Edges CSV ---
    edges_buf = io.StringIO()
    writer = csv.writer(edges_buf)
    writer.writerow([
        "~id", "~from", "~to", "~label",
        "confidence:Double", "association_source:String",
        "similarity:Double", "case_file_id:String",
    ])

    edge_count = 0

    # FACE_DETECTED_IN edges: FaceCrop → Document node
    for doc_id, crop_keys in doc_to_face_crops.items():
        # Document node ID follows the entity naming convention
        doc_node_id = f"{case_id}_document_{doc_id}"
        for crop_key in crop_keys:
            fc_node_id = fc_node_ids.get(crop_key)
            if not fc_node_id:
                continue
            edge_id = f"{case_id}_fdi_{uuid.uuid4().hex[:8]}"
            # Find confidence for this crop
            conf = next(
                (e.get("confidence", 0.0) for e in face_crop_metadata if e.get("crop_s3_key") == crop_key),
                0.0,
            )
            writer.writerow([
                edge_id, fc_node_id, doc_node_id, "FACE_DETECTED_IN",
                conf, "", 0.0, case_id,
            ])
            edge_count += 1

    # HAS_FACE_CANDIDATE edges: Person entity → FaceCrop via document co-occurrence
    # For each document with face crops, find person entities from that document
    for doc_id, crop_keys in doc_to_face_crops.items():
        # Find person entities that share this document
        for ent_name, ent_data in entities.items():
            if ent_data.get("entity_type") != "person":
                continue
            # Person entities from the same case are candidates
            person_node_id = f"{case_id}_{ent_data['entity_type']}_{ent_name}"
            for crop_key in crop_keys:
                fc_node_id = fc_node_ids.get(crop_key)
                if not fc_node_id:
                    continue
                edge_id = f"{case_id}_hfc_{uuid.uuid4().hex[:8]}"
                writer.writerow([
                    edge_id, person_node_id, fc_node_id, "HAS_FACE_CANDIDATE",
                    0.0, "document_co_occurrence", 0.0, case_id,
                ])
                edge_count += 1

    # HAS_FACE_MATCH edges: Person entity → FaceCrop via watchlist match
    for entity_name, crop_key, similarity in entity_face_matches:
        # Find the entity in the entities dict
        if entity_name in entities:
            ent_data = entities[entity_name]
            person_node_id = f"{case_id}_{ent_data['entity_type']}_{entity_name}"
        else:
            # Entity might not be in the extraction results, create a reference anyway
            person_node_id = f"{case_id}_person_{entity_name}"

        fc_node_id = fc_node_ids.get(crop_key)
        if not fc_node_id:
            continue
        edge_id = f"{case_id}_hfm_{uuid.uuid4().hex[:8]}"
        writer.writerow([
            edge_id, person_node_id, fc_node_id, "HAS_FACE_MATCH",
            similarity, "watchlist_match", similarity, case_id,
        ])
        edge_count += 1

    edges_key = f"neptune-bulk-load/{case_id}/{batch_id}_facecrop_edges.csv"
    s3.put_object(Bucket=S3_BUCKET, Key=edges_key, Body=edges_buf.getvalue().encode("utf-8"))
    logger.info("Uploaded FaceCrop edges CSV: %s (%d edges)", edges_key, edge_count)

    return nodes_key, edges_key, node_count, edge_count


def _load_face_crops_via_gremlin(case_id: str, face_crop_metadata: list, entities: dict):
    """Load face crop nodes and edges via Gremlin HTTP (fallback path)."""
    fc_label = _escape(f"FaceCrop_{case_id}")
    entity_label = _escape(f"Entity_{case_id}")
    esc_case_id = _escape(case_id)
    node_count = 0
    edge_count = 0

    fc_node_ids = {}
    doc_to_face_crops = {}
    entity_face_matches = []

    # Create FaceCrop nodes
    for entry in face_crop_metadata:
        crop_key = entry.get("crop_s3_key", "")
        if not crop_key or crop_key in fc_node_ids:
            continue

        source_doc_id = entry.get("source_document_id", "unknown")
        entity_name = entry.get("entity_name", "unidentified")

        try:
            q = (
                f"g.addV('{fc_label}')"
                f".property('crop_s3_key','{_escape(crop_key)}')"
                f".property('source_s3_key','{_escape(entry.get('source_s3_key', ''))}')"
                f".property('source_document_id','{_escape(source_doc_id)}')"
                f".property('confidence',{entry.get('confidence', 0.0)})"
                f".property('case_file_id','{esc_case_id}')"
                f".property('entity_name','{_escape(entity_name)}')"
            )
            _gremlin_http(q)
            fc_node_ids[crop_key] = True
            node_count += 1
        except Exception as e:
            logger.warning("Gremlin addV FaceCrop failed for '%s': %s", crop_key[:50], str(e)[:200])
            continue

        if source_doc_id != "unknown":
            doc_to_face_crops.setdefault(source_doc_id, []).append(crop_key)
        else:
            logger.warning("FaceCrop %s has unknown source_document_id, skipping FACE_DETECTED_IN", crop_key)

        if entity_name != "unidentified":
            entity_face_matches.append((entity_name, crop_key, entry.get("confidence", 0.0)))

    # FACE_DETECTED_IN edges
    for doc_id, crop_keys in doc_to_face_crops.items():
        for crop_key in crop_keys:
            try:
                q = (
                    f"g.V().hasLabel('{fc_label}').has('crop_s3_key','{_escape(crop_key)}')"
                    f".addE('FACE_DETECTED_IN')"
                    f".to(__.V().hasLabel('{entity_label}').has('canonical_name','{_escape(doc_id)}'))"
                    f".property('case_file_id','{esc_case_id}')"
                )
                _gremlin_http(q, timeout=10)
                edge_count += 1
            except Exception:
                pass

    # HAS_FACE_CANDIDATE edges (person → FaceCrop via document co-occurrence)
    for doc_id, crop_keys in doc_to_face_crops.items():
        for ent_name, ent_data in entities.items():
            if ent_data.get("entity_type") != "person":
                continue
            for crop_key in crop_keys:
                try:
                    q = (
                        f"g.V().hasLabel('{entity_label}').has('canonical_name','{_escape(ent_name)}')"
                        f".addE('HAS_FACE_CANDIDATE')"
                        f".to(__.V().hasLabel('{fc_label}').has('crop_s3_key','{_escape(crop_key)}'))"
                        f".property('association_source','document_co_occurrence')"
                        f".property('case_file_id','{esc_case_id}')"
                    )
                    _gremlin_http(q, timeout=10)
                    edge_count += 1
                except Exception:
                    pass

    # HAS_FACE_MATCH edges (person → FaceCrop via watchlist match)
    for entity_name, crop_key, similarity in entity_face_matches:
        try:
            q = (
                f"g.V().hasLabel('{entity_label}').has('canonical_name','{_escape(entity_name)}')"
                f".addE('HAS_FACE_MATCH')"
                f".to(__.V().hasLabel('{fc_label}').has('crop_s3_key','{_escape(crop_key)}'))"
                f".property('association_source','watchlist_match')"
                f".property('similarity',{similarity})"
                f".property('case_file_id','{esc_case_id}')"
            )
            _gremlin_http(q, timeout=10)
            edge_count += 1
        except Exception:
            pass

    return node_count, edge_count


def _load_via_gremlin(case_id, entities, relationships):
    """Fallback: load via individual Gremlin HTTP queries when bulk loader isn't available."""
    label = _escape(f"Entity_{case_id}")
    esc_case_id = _escape(case_id)
    node_count = 0
    edge_count = 0

    for name, ent in entities.items():
        try:
            etype = _escape(ent["entity_type"])
            conf = ent["confidence"]
            occ = ent["occurrence_count"]
            q = (
                f"g.addV('{label}')"
                f".property('canonical_name','{_escape(name)}')"
                f".property('entity_type','{etype}')"
                f".property('confidence',{conf})"
                f".property('occurrence_count',{occ})"
                f".property('case_file_id','{esc_case_id}')"
            )
            _gremlin_http(q)
            node_count += 1
        except Exception as e:
            logger.warning("Gremlin addV failed for '%s': %s", name[:50], str(e)[:200])

    if node_count % 100 == 0 or node_count == len(entities):
        logger.info("Gremlin nodes: %d/%d", node_count, len(entities))

    # Edges
    seen = set()
    for rel in relationships:
        src = rel.get("source_entity", rel.get("from", ""))
        tgt = rel.get("target_entity", rel.get("to", ""))
        if not src or not tgt or src not in entities or tgt not in entities:
            continue
        if (src, tgt) in seen:
            continue
        seen.add((src, tgt))
        rel_type = rel.get("relationship_type", rel.get("type", "co-occurrence"))
        if isinstance(rel_type, dict):
            rel_type = rel_type.get("value", str(rel_type))
        try:
            q = (
                f"g.V().hasLabel('{label}').has('canonical_name','{_escape(src)}')"
                f".addE('RELATED_TO')"
                f".to(__.V().hasLabel('{label}').has('canonical_name','{_escape(tgt)}'))"
                f".property('relationship_type','{_escape(str(rel_type))}')"
                f".property('confidence',{rel.get('confidence', 0.5)})"
                f".property('case_file_id','{esc_case_id}')"
            )
            _gremlin_http(q, timeout=10)
            edge_count += 1
        except Exception:
            pass

    return node_count, edge_count


def _load_image_description_result(case_id: str, event: dict) -> dict:
    """Load image_description_result from event or S3 artifact.

    Returns the image_description_result dict, or empty dict if absent.
    """
    # Try direct from event
    id_result = event.get("image_description_result", {})
    if id_result and id_result.get("status") in ("completed", "batch_submitted"):
        logger.info("Loaded image_description_result from event (status=%s, %d descriptions)",
                     id_result.get("status"), len(id_result.get("descriptions", [])))
        return id_result

    # Try loading artifact from S3
    artifact_key = id_result.get("artifact_key", "") if id_result else ""
    if artifact_key and S3_BUCKET:
        s3 = boto3.client("s3")
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=artifact_key)
            artifact = json.loads(resp["Body"].read().decode("utf-8"))
            logger.info("Loaded image description artifact from S3: %s", artifact_key)
            return {
                "status": "completed",
                "descriptions": artifact.get("descriptions", []),
                "artifact_key": artifact_key,
            }
        except Exception as exc:
            logger.info("No image description artifact at key %s: %s", artifact_key, str(exc)[:100])

    # Fall back to listing the most recent artifact in S3
    if S3_BUCKET:
        s3 = boto3.client("s3")
        prefix = f"cases/{case_id}/image-description-artifacts/"
        try:
            paginator = s3.get_paginator("list_objects_v2")
            artifacts = []
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith("_descriptions.json"):
                        artifacts.append(obj)
            if artifacts:
                artifacts.sort(key=lambda x: x.get("LastModified", ""), reverse=True)
                latest_key = artifacts[0]["Key"]
                resp = s3.get_object(Bucket=S3_BUCKET, Key=latest_key)
                artifact = json.loads(resp["Body"].read().decode("utf-8"))
                logger.info("Loaded latest image description artifact: %s", latest_key)
                return {
                    "status": "completed",
                    "descriptions": artifact.get("descriptions", []),
                    "artifact_key": latest_key,
                }
        except Exception as exc:
            logger.info("No image description artifacts found for case %s: %s", case_id, str(exc)[:100])

    return {}


def _process_image_descriptions_gremlin(case_id: str, descriptions: list, entities: dict) -> tuple:
    """Set image_descriptions property on document nodes and create DESCRIBED_IN_IMAGE edges via Gremlin.

    Returns (properties_set, edges_created).
    """
    entity_label = _escape(f"Entity_{case_id}")
    esc_case_id = _escape(case_id)
    properties_set = 0
    edges_created = 0

    # Group descriptions by source_document_id
    doc_descriptions = {}
    for desc in descriptions:
        doc_id = desc.get("source_document_id", "unknown")
        if doc_id == "unknown":
            continue
        doc_descriptions.setdefault(doc_id, []).append(desc)

    # Set image_descriptions property on document nodes
    for doc_id, descs in doc_descriptions.items():
        concatenated = "\n\n".join(d.get("description", "") for d in descs if d.get("description"))
        if not concatenated:
            continue

        try:
            q = (
                f"g.V().hasLabel('{entity_label}')"
                f".has('canonical_name','{_escape(doc_id)}')"
                f".property('image_descriptions','{_escape(concatenated[:10000])}')"
            )
            _gremlin_http(q, timeout=15)
            properties_set += 1
        except Exception as e:
            logger.warning("Failed to set image_descriptions for doc %s: %s", doc_id, str(e)[:200])

    # Create DESCRIBED_IN_IMAGE edges from mentioned entities to document nodes
    for desc in descriptions:
        doc_id = desc.get("source_document_id", "unknown")
        if doc_id == "unknown":
            continue
        image_key = desc.get("image_s3_key", "")
        for entity_name in desc.get("mentioned_entities", []):
            if entity_name not in entities:
                continue
            try:
                q = (
                    f"g.V().hasLabel('{entity_label}')"
                    f".has('canonical_name','{_escape(entity_name)}')"
                    f".addE('DESCRIBED_IN_IMAGE')"
                    f".to(__.V().hasLabel('{entity_label}').has('canonical_name','{_escape(doc_id)}'))"
                    f".property('image_s3_key','{_escape(image_key)}')"
                    f".property('case_file_id','{esc_case_id}')"
                )
                _gremlin_http(q, timeout=10)
                edges_created += 1
            except Exception:
                pass

    return properties_set, edges_created


def _process_image_descriptions_csv(case_id: str, descriptions: list, entities: dict) -> tuple:
    """Generate and load CSV for image description edges.

    Returns (properties_set, edges_created).
    """
    # For properties, we still use Gremlin since Neptune bulk loader doesn't support property updates
    entity_label = _escape(f"Entity_{case_id}")
    properties_set = 0

    doc_descriptions = {}
    for desc in descriptions:
        doc_id = desc.get("source_document_id", "unknown")
        if doc_id == "unknown":
            continue
        doc_descriptions.setdefault(doc_id, []).append(desc)

    for doc_id, descs in doc_descriptions.items():
        concatenated = "\n\n".join(d.get("description", "") for d in descs if d.get("description"))
        if not concatenated:
            continue
        try:
            q = (
                f"g.V().hasLabel('{entity_label}')"
                f".has('canonical_name','{_escape(doc_id)}')"
                f".property('image_descriptions','{_escape(concatenated[:10000])}')"
            )
            _gremlin_http(q, timeout=15)
            properties_set += 1
        except Exception as e:
            logger.warning("Failed to set image_descriptions for doc %s: %s", doc_id, str(e)[:200])

    # Generate edges CSV for DESCRIBED_IN_IMAGE
    s3 = boto3.client("s3")
    label = f"Entity_{case_id}"
    batch_id = uuid.uuid4().hex[:12]

    edges_buf = io.StringIO()
    writer = csv.writer(edges_buf)
    writer.writerow(["~id", "~from", "~to", "~label", "image_s3_key:String", "case_file_id:String"])

    edge_count = 0
    for desc in descriptions:
        doc_id = desc.get("source_document_id", "unknown")
        if doc_id == "unknown":
            continue
        image_key = desc.get("image_s3_key", "")
        for entity_name in desc.get("mentioned_entities", []):
            if entity_name not in entities:
                continue
            ent_data = entities[entity_name]
            from_id = f"{case_id}_{ent_data['entity_type']}_{entity_name}"
            to_id = f"{case_id}_document_{doc_id}"
            edge_id = f"{case_id}_dii_{uuid.uuid4().hex[:8]}"
            writer.writerow([edge_id, from_id, to_id, "DESCRIBED_IN_IMAGE", image_key, case_id])
            edge_count += 1

    if edge_count > 0:
        edges_key = f"neptune-bulk-load/{case_id}/{batch_id}_imgdesc_edges.csv"
        s3.put_object(Bucket=S3_BUCKET, Key=edges_key, Body=edges_buf.getvalue().encode("utf-8"))
        logger.info("Uploaded image description edges CSV: %s (%d edges)", edges_key, edge_count)

        load_id = _trigger_bulk_load(edges_key)
        if load_id:
            _poll_bulk_load(load_id, max_wait=120)

    return properties_set, edge_count


def handler(event, context):
    case_id = event["case_id"]
    extraction_results = event.get("extraction_results", [])

    # Read graph_load config from effective_config (set by ResolveConfig step),
    # falling back to event-level / hardcoded defaults for backward compatibility.
    graph_load_cfg = event.get("effective_config", {}).get("graph_load", {})
    load_strategy = graph_load_cfg.get(
        "load_strategy",
        event.get("load_strategy", "gremlin"),
    )
    batch_size = graph_load_cfg.get("batch_size", event.get("batch_size", 0))

    logger.info("Loading graph for case %s, strategy=%s, docs=%d",
                case_id, load_strategy, len(extraction_results))

    if not NEPTUNE_ENDPOINT:
        return {"case_id": case_id, "status": "skipped", "node_count": 0, "edge_count": 0}

    # Load extraction artifacts from S3 if not inline
    has_entities = any(r.get("entities") for r in extraction_results if r.get("status") == "success")
    if not has_entities:
        extraction_results = _load_from_s3(case_id, extraction_results)

    entities, relationships = _collect_entities_and_relationships(case_id, extraction_results)
    logger.info("Collected %d unique entities, %d relationships", len(entities), len(relationships))

    if len(entities) == 0:
        return {"case_id": case_id, "load_strategy": load_strategy, "status": "completed",
                "node_count": 0, "edge_count": 0}

    # Load face crop metadata for graph edge creation
    face_crop_metadata = _load_face_crop_metadata(case_id, event)
    fc_node_count = 0
    fc_edge_count = 0

    # Try bulk CSV loader first (works for any entity names, handles special chars)
    if IAM_ROLE_ARN and S3_BUCKET:
        logger.info("Using Neptune bulk CSV loader")
        try:
            nodes_key, edges_key, node_count, edge_count = _generate_and_upload_csv(
                case_id, entities, relationships
            )

            # Load nodes
            nodes_load_id = _trigger_bulk_load(nodes_key)
            if nodes_load_id:
                nodes_status = _poll_bulk_load(nodes_load_id, max_wait=300)
                if nodes_status != "LOAD_COMPLETED":
                    logger.warning("Nodes bulk load status: %s, falling back to Gremlin", nodes_status)
                    node_count, edge_count = _load_via_gremlin(case_id, entities, relationships)
                    return {"case_id": case_id, "load_strategy": "gremlin-fallback",
                            "status": "completed", "node_count": node_count, "edge_count": edge_count}

                # Load edges
                edges_load_id = _trigger_bulk_load(edges_key)
                if edges_load_id:
                    edges_status = _poll_bulk_load(edges_load_id, max_wait=300)
                    logger.info("Edges bulk load status: %s", edges_status)

                # Load face crop nodes and edges if metadata exists
                if face_crop_metadata:
                    try:
                        fc_nodes_key, fc_edges_key, fc_node_count, fc_edge_count = _generate_face_crop_csv(
                            case_id, face_crop_metadata, entities
                        )
                        fc_nodes_load_id = _trigger_bulk_load(fc_nodes_key)
                        if fc_nodes_load_id:
                            fc_nodes_status = _poll_bulk_load(fc_nodes_load_id, max_wait=300)
                            if fc_nodes_status == "LOAD_COMPLETED":
                                fc_edges_load_id = _trigger_bulk_load(fc_edges_key)
                                if fc_edges_load_id:
                                    _poll_bulk_load(fc_edges_load_id, max_wait=300)
                        logger.info("FaceCrop graph load: %d nodes, %d edges", fc_node_count, fc_edge_count)
                    except Exception as e:
                        logger.error("FaceCrop bulk CSV load failed: %s", str(e)[:300])

                # Process image descriptions if available
                id_props = 0
                id_edges = 0
                id_result = _load_image_description_result(case_id, event)
                id_descriptions = id_result.get("descriptions", [])
                if id_descriptions:
                    try:
                        id_props, id_edges = _process_image_descriptions_csv(case_id, id_descriptions, entities)
                        logger.info("Image description graph load: %d properties, %d edges", id_props, id_edges)
                    except Exception as e:
                        logger.error("Image description CSV load failed: %s", str(e)[:300])

                return {"case_id": case_id, "load_strategy": "bulk",
                        "status": "completed", "node_count": node_count, "edge_count": edge_count,
                        "face_crop_nodes": fc_node_count, "face_crop_edges": fc_edge_count,
                        "image_desc_properties": id_props, "image_desc_edges": id_edges}
        except Exception as e:
            logger.error("Bulk CSV load failed: %s, falling back to Gremlin", str(e)[:300])

    # Fallback to Gremlin
    logger.info("Using Gremlin HTTP loader (fallback)")
    node_count, edge_count = _load_via_gremlin(case_id, entities, relationships)

    # Load face crop nodes and edges via Gremlin
    if face_crop_metadata:
        try:
            fc_node_count, fc_edge_count = _load_face_crops_via_gremlin(case_id, face_crop_metadata, entities)
            logger.info("FaceCrop Gremlin load: %d nodes, %d edges", fc_node_count, fc_edge_count)
        except Exception as e:
            logger.error("FaceCrop Gremlin load failed: %s", str(e)[:300])

    # Process image descriptions if available
    id_props = 0
    id_edges = 0
    id_result = _load_image_description_result(case_id, event)
    id_descriptions = id_result.get("descriptions", [])
    if id_descriptions:
        try:
            id_props, id_edges = _process_image_descriptions_gremlin(case_id, id_descriptions, entities)
            logger.info("Image description Gremlin load: %d properties, %d edges", id_props, id_edges)
        except Exception as e:
            logger.error("Image description Gremlin load failed: %s", str(e)[:300])

    logger.info("Graph load complete: %d nodes, %d edges", node_count, edge_count)
    return {"case_id": case_id, "load_strategy": load_strategy,
            "status": "completed", "node_count": node_count, "edge_count": edge_count,
            "face_crop_nodes": fc_node_count, "face_crop_edges": fc_edge_count,
            "image_desc_properties": id_props, "image_desc_edges": id_edges}
