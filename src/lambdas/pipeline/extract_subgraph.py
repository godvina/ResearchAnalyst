"""Extract subgraph Lambda — runs typology-specific Neptune queries.

Called per typology module (11× via Map state, 3 concurrent). Extracts
entities and relationships matching the typology's sub-category patterns.

Input event:
    {
        "case_id": "uuid-string",
        "typology_module_id": "sex_trafficking",
        "execution_id": "uuid-string"
    }

Output:
    {
        "case_id": "...",
        "typology_module_id": "...",
        "sub_categories": [
            {
                "id": "financial_control",
                "entities": [{"name": "...", "type": "..."}],
                "edges": [{"src": "...", "tgt": "...", "type": "...", "weight": 1}],
                "entity_count": 42,
                "edge_count": 87
            },
            ...
        ],
        "extract_duration_ms": 12345,
        "execution_id": "..."
    }
"""

import json
import logging
import os
import ssl
import time
import urllib.request

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
QUERY_TIMEOUT = 290  # seconds — just under Lambda 300s limit


def _gremlin_query(query: str, timeout: int = QUERY_TIMEOUT) -> list:
    """Execute a Gremlin query via Neptune HTTP API."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result", {}).get("data", {})
            if isinstance(result, dict) and "@value" in result:
                return _parse_graphson(result["@value"])
            if isinstance(result, list):
                return _parse_graphson(result)
            return [result] if result else []
    except Exception as e:
        logger.error("Neptune query error (timeout=%ds): %s", timeout, str(e)[:200])
        return []


def _parse_graphson(items: list) -> list:
    """Parse GraphSON typed values into plain Python objects."""
    result = []
    for item in items:
        result.append(_parse_graphson_value(item))
    return result


def _parse_graphson_value(val):
    """Recursively parse a single GraphSON value."""
    if not isinstance(val, dict):
        return val
    gtype = val.get("@type", "")
    gval = val.get("@value")
    if gtype == "g:Map" and isinstance(gval, list):
        d = {}
        for i in range(0, len(gval) - 1, 2):
            d[_parse_graphson_value(gval[i])] = _parse_graphson_value(gval[i + 1])
        return d
    if gtype in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
        return gval
    if gtype == "g:List" and isinstance(gval, list):
        return [_parse_graphson_value(v) for v in gval]
    if "@value" in val:
        return _parse_graphson_value(gval)
    return val


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _extract_sub_category(case_id: str, sub_cat_id: str, sub_cat_def: dict) -> dict:
    """Extract subgraph for a single sub-category using its query template."""
    label = f"Entity_{_escape(case_id)}"
    query_template = sub_cat_def["query_template"]
    query = query_template.replace("{label}", label)

    logger.info("Extracting sub_category=%s, query_length=%d", sub_cat_id, len(query))

    start = time.monotonic()
    results = _gremlin_query(query, timeout=min(QUERY_TIMEOUT, 60))
    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Parse results into entities and edges
    entities = {}  # name -> type
    edges = []

    for r in results:
        if not isinstance(r, dict):
            continue
        src = r.get("src", "")
        tgt = r.get("tgt", "")
        rel_type = r.get("type", "related")
        weight = r.get("weight", 1)
        if isinstance(weight, dict):
            weight = weight.get("@value", 1)

        if src:
            entities[src] = entities.get(src, "unknown")
        if tgt:
            entities[tgt] = entities.get(tgt, "unknown")
        if src and tgt:
            edges.append({"src": src, "tgt": tgt, "type": rel_type, "weight": int(weight)})

    # Also try to get entity types for the extracted entities
    if entities:
        try:
            names_sample = list(entities.keys())[:100]
            name_predicates = ",".join(f"'{_escape(n)}'" for n in names_sample)
            type_query = (
                f"g.V().hasLabel('Entity_{_escape(case_id)}')"
                f".has('canonical_name', within({name_predicates}))"
                f".project('name','type')"
                f".by('canonical_name').by('entity_type')"
            )
            type_results = _gremlin_query(type_query, timeout=15)
            for tr in type_results:
                if isinstance(tr, dict) and tr.get("name") and tr.get("type"):
                    entities[tr["name"]] = tr["type"]
        except Exception:
            pass  # Types are best-effort

    entity_list = [{"name": name, "type": etype} for name, etype in entities.items()]

    logger.info(
        "Sub-category %s: %d entities, %d edges, %dms",
        sub_cat_id, len(entity_list), len(edges), elapsed_ms,
    )

    return {
        "id": sub_cat_id,
        "entities": entity_list[:10],  # Only top 10 for key_entities storage
        "edges": [],                   # Edges stored in Aurora, not passed through SFN
        "entity_count": len(entity_list),
        "edge_count": len(edges),
        "extract_ms": elapsed_ms,
    }


def handler(event, context):
    """Lambda entry point."""
    from services.typology_query_definitions import get_queries_for_module

    case_id = event.get("case_id", "")
    typology_module_id = event.get("typology_module_id", "")
    execution_id = event.get("execution_id", "")

    if not case_id or not typology_module_id:
        logger.error("Missing case_id or typology_module_id")
        return {"error": "Missing required fields", "case_id": case_id}

    logger.info("Starting extraction: case=%s, typology=%s", case_id, typology_module_id)
    start_time = time.monotonic()

    try:
        sub_category_defs = get_queries_for_module(typology_module_id)
    except KeyError as e:
        logger.error("Unknown typology module: %s", typology_module_id)
        return {"error": str(e), "case_id": case_id}

    sub_categories = []
    for sub_cat_id, sub_cat_def in sub_category_defs.items():
        try:
            result = _extract_sub_category(case_id, sub_cat_id, sub_cat_def)
            sub_categories.append(result)
        except Exception as exc:
            logger.error("Sub-category %s extraction failed: %s", sub_cat_id, str(exc)[:200])
            sub_categories.append({
                "id": sub_cat_id,
                "entities": [],
                "edges": [],
                "entity_count": 0,
                "edge_count": 0,
                "error": str(exc)[:200],
            })

    total_ms = int((time.monotonic() - start_time) * 1000)
    total_entities = sum(sc["entity_count"] for sc in sub_categories)
    total_edges = sum(sc["edge_count"] for sc in sub_categories)
    logger.info(
        "Extraction complete: case=%s, typology=%s, %d sub-categories, %d entities, %d edges, %dms total",
        case_id, typology_module_id, len(sub_categories), total_entities, total_edges, total_ms,
    )

    # Write key_entities to Aurora (pattern: data goes to DB, only IDs through Step Functions)
    try:
        from db.connection import ConnectionManager
        cm = ConnectionManager()
        with cm.cursor() as cur:
            for sc in sub_categories:
                key_ents = json.dumps([e.get("name", "") for e in sc.get("entities", [])[:10]])
                subgraph_summary = json.dumps({
                    "entity_count": sc["entity_count"],
                    "edge_count": sc["edge_count"],
                })
                cur.execute("""
                    INSERT INTO typology_precomputed_results
                        (case_id, typology_module_id, sub_category_id, overall_score,
                         match_strength, key_entities, subgraph_summary, is_stale, computed_at)
                    VALUES (%s, %s, %s, 0.0, 'weak', %s, %s, FALSE, NOW())
                    ON CONFLICT (case_id, typology_module_id, sub_category_id) DO UPDATE SET
                        key_entities = EXCLUDED.key_entities,
                        subgraph_summary = EXCLUDED.subgraph_summary,
                        is_stale = FALSE,
                        computed_at = NOW()
                """, (case_id, typology_module_id, sc["id"], key_ents, subgraph_summary))
        logger.info("Wrote extraction results to Aurora for %s/%s", case_id, typology_module_id)
    except Exception as db_exc:
        logger.error("Aurora write failed: %s", str(db_exc)[:300])

    # Return ONLY small reference data (Step Functions 256KB limit - Issue 56)
    return {
        "case_id": case_id,
        "typology_module_id": typology_module_id,
        "total_entities": total_entities,
        "total_edges": total_edges,
        "extract_duration_ms": total_ms,
        "execution_id": execution_id,
    }
