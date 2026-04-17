"""Sync Neptune entities to Aurora entities table.

Invoked directly (not via API Gateway) to read all entities from Neptune
for a given case and upsert them into the Aurora entities table.

This bridges the gap where Neptune has graph data (from Rekognition/visual
pipeline) but Aurora entities table is empty (entity extraction skipped).

Usage (via scripts/sync_neptune_to_aurora.py):
    Invoke this Lambda with:
    {
        "action": "sync_neptune_to_aurora",
        "case_id": "ed0b6c27-..."
    }
"""
import json
import logging
import os
import ssl
import urllib.request

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")


def _gremlin(query: str, timeout: int = 60) -> list:
    """Execute a Gremlin query against Neptune and return results."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("result", {}).get("data", {}).get("@value", [])


def _unwrap(val):
    """Unwrap Neptune GraphSON @value wrappers."""
    if isinstance(val, dict):
        if val.get("@type") == "g:Map" and "@value" in val:
            items = val["@value"]
            return {_unwrap(items[i]): _unwrap(items[i + 1]) for i in range(0, len(items), 2)}
        if "@value" in val:
            return _unwrap(val["@value"])
        return {k: _unwrap(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_unwrap(v) for v in val]
    return val


def handler(event, context):
    """Sync Neptune entities to Aurora for a given case."""
    case_id = event.get("case_id")
    if not case_id:
        return {"error": "case_id required"}

    if not NEPTUNE_ENDPOINT:
        return {"error": "NEPTUNE_ENDPOINT not configured"}

    label = f"Entity_{case_id}"
    logger.info("Syncing Neptune entities (label=%s) to Aurora", label)

    # 1. Query all entities from Neptune
    query = (
        f"g.V().hasLabel('{label}')"
        f".project('name','type','confidence','count')"
        f".by('canonical_name')"
        f".by('entity_type')"
        f".by(coalesce(values('confidence'), constant(0.5)))"
        f".by(coalesce(values('occurrence_count'), constant(1)))"
    )

    try:
        raw = _gremlin(query, timeout=120)
        entities = [_unwrap(r) for r in raw]
    except Exception as exc:
        logger.error("Neptune query failed: %s", str(exc)[:500])
        return {"error": f"Neptune query failed: {str(exc)[:200]}"}

    logger.info("Found %d entities in Neptune for case %s", len(entities), case_id)

    if not entities:
        return {"case_id": case_id, "neptune_entities": 0, "aurora_upserted": 0}

    # 2. Upsert into Aurora entities table
    from db.connection import ConnectionManager
    cm = ConnectionManager()
    upserted = 0
    errors = 0

    with cm.cursor() as cur:
        for e in entities:
            name = e.get("name", "")
            etype = e.get("type", "unknown")
            conf = float(e.get("confidence", 0.5))
            occ = int(e.get("count", 1))

            if not name or len(name) < 2:
                continue

            try:
                cur.execute(
                    """INSERT INTO entities
                       (case_file_id, canonical_name, entity_type, confidence,
                        occurrence_count, source_document_ids)
                       VALUES (%s, %s, %s, %s, %s, '[]'::jsonb)
                       ON CONFLICT (case_file_id, canonical_name, entity_type)
                       DO UPDATE SET
                           occurrence_count = GREATEST(entities.occurrence_count, EXCLUDED.occurrence_count),
                           confidence = GREATEST(entities.confidence, EXCLUDED.confidence),
                           updated_at = now()""",
                    (case_id, name, etype, conf, occ),
                )
                upserted += 1
            except Exception as exc:
                errors += 1
                if errors <= 5:
                    logger.warning("Upsert failed for '%s': %s", name, str(exc)[:200])

        # 3. Update entity_count on case_files
        cur.execute(
            "UPDATE case_files SET entity_count = %s, last_activity = now() WHERE case_id = %s",
            (upserted, case_id),
        )

    logger.info("Sync complete: %d Neptune entities, %d upserted, %d errors",
                len(entities), upserted, errors)

    return {
        "case_id": case_id,
        "neptune_entities": len(entities),
        "aurora_upserted": upserted,
        "errors": errors,
    }
