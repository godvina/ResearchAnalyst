"""Lambda handler for entity extraction step of the ingestion pipeline.

Receives parsed document data and delegates to EntityExtractionService.
Large documents are automatically chunked for full coverage.
"""

import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Extract entities and relationships from a parsed document.

    Expected event:
        {
            "case_id": "...",
            "document_id": "...",
            "raw_text": "..."
        }

    Returns:
        {
            "case_id": "...",
            "document_id": "...",
            "entities": [{...}, ...],
            "relationships": [{...}, ...]
        }
    """
    import boto3
    from botocore.config import Config

    from services.entity_extraction_service import EntityExtractionService

    case_id = event["case_id"]
    document_id = event["document_id"]
    raw_text = event["raw_text"]

    # Read extract config from effective_config (set by ResolveConfig step),
    # falling back to defaults for backward compatibility.
    extract_cfg = event.get("effective_config", {}).get("extract", {})
    llm_model_id = extract_cfg.get("llm_model_id")
    chunk_size_chars = extract_cfg.get("chunk_size_chars")
    confidence_threshold = extract_cfg.get("confidence_threshold")
    entity_types = extract_cfg.get("entity_types")

    text_len = len(raw_text)
    logger.info("Extracting entities from document %s for case %s (%d chars)",
                document_id, case_id, text_len)

    bedrock_config = Config(
        read_timeout=120,
        connect_timeout=10,
        retries={"max_attempts": 2, "mode": "adaptive"},
    )
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)

    # Pass effective_config overrides to the extraction service when available.
    kwargs = {}
    if llm_model_id:
        kwargs["model_id"] = llm_model_id
    extractor = EntityExtractionService(bedrock, **kwargs)

    entities = extractor.extract_entities(raw_text, document_id)
    relationships = extractor.extract_relationships(raw_text, entities, document_id)

    logger.info(
        "Extraction complete for doc %s: %d entities, %d relationships from %d chars",
        document_id, len(entities), len(relationships), text_len,
    )

    entity_dicts = [e.model_dump(mode="json") for e in entities]
    rel_dicts = [r.model_dump(mode="json") for r in relationships]

    # Persist entities and relationships to Aurora for SQL analytics,
    # cross-case queries, and entity-document provenance tracking.
    # This is additive — Neptune graph load happens separately downstream.
    try:
        from db.connection import ConnectionManager
        import json as _json

        cm = ConnectionManager()
        with cm.cursor() as cur:
            for e in entity_dicts:
                name = e.get("canonical_name", e.get("name", ""))
                etype = e.get("entity_type", e.get("type", "unknown"))
                conf = e.get("confidence", 0.5)
                occ = e.get("occurrence_count", e.get("occurrences", 1))
                if not name:
                    continue
                cur.execute(
                    """INSERT INTO entities (case_file_id, document_id, canonical_name, entity_type, confidence, occurrence_count, source_document_ids)
                       VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                       ON CONFLICT (case_file_id, canonical_name, entity_type)
                       DO UPDATE SET occurrence_count = entities.occurrence_count + EXCLUDED.occurrence_count,
                                     confidence = GREATEST(entities.confidence, EXCLUDED.confidence),
                                     source_document_ids = entities.source_document_ids || EXCLUDED.source_document_ids,
                                     updated_at = now()""",
                    (case_id, document_id, name, etype, conf, occ,
                     _json.dumps([document_id])),
                )
            for r in rel_dicts:
                src = r.get("source_entity", r.get("from", ""))
                tgt = r.get("target_entity", r.get("to", ""))
                rtype = r.get("relationship_type", r.get("type", "co-occurrence"))
                if isinstance(rtype, dict):
                    rtype = str(rtype.get("value", rtype))
                if not src or not tgt:
                    continue
                cur.execute(
                    """INSERT INTO relationships (case_file_id, source_entity, target_entity, relationship_type, confidence)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (case_file_id, source_entity, target_entity, relationship_type)
                       DO UPDATE SET occurrence_count = relationships.occurrence_count + 1""",
                    (case_id, src, tgt, rtype, r.get("confidence", 0.5)),
                )
        logger.info("Persisted %d entities, %d relationships to Aurora for doc %s",
                     len(entity_dicts), len(rel_dicts), document_id)
    except Exception as exc:
        logger.warning("Aurora entity persistence failed (non-fatal): %s", str(exc)[:200])

    return {
        "case_id": case_id,
        "document_id": document_id,
        "entities": entity_dicts,
        "relationships": rel_dicts,
    }
