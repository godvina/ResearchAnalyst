"""Build summary graph Lambda — cross-typology hub analysis.

Runs AFTER all typology scoring is complete. Reads precomputed results,
identifies hub entities (appear in 2+ typology modules), queries Neptune
for inter-hub edges, and stores a vis.js-compatible summary graph.

Input:  {"case_id": "uuid", "execution_id": "uuid"}
Output: {"case_id", "hub_count", "cross_typology_entities", "build_duration_ms"}
"""

import json
import logging
import os
import ssl
import time
import urllib.request
from collections import defaultdict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
MAX_HUBS = 50
CROSS_TYPOLOGY_THRESHOLD = 3  # entities in 3+ typologies get special highlighting


def _gremlin_query(query: str, timeout: int = 30) -> list:
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
        logger.error("Neptune query error: %s", str(e)[:200])
        return []


def _parse_graphson(items: list) -> list:
    """Parse GraphSON typed values into plain Python objects."""
    parsed = []
    for item in items:
        parsed.append(_parse_value(item))
    return parsed


def _parse_value(val):
    """Recursively parse a single GraphSON value."""
    if not isinstance(val, dict):
        return val
    gtype = val.get("@type", "")
    gval = val.get("@value")
    if gtype == "g:Map" and isinstance(gval, list):
        d = {}
        for i in range(0, len(gval) - 1, 2):
            d[_parse_value(gval[i])] = _parse_value(gval[i + 1])
        return d
    if gtype in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
        return gval
    if gtype == "g:List" and isinstance(gval, list):
        return [_parse_value(v) for v in gval]
    if "@value" in val:
        return _parse_value(gval)
    return val


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _load_precomputed_results(case_id: str) -> list[dict]:
    """Read all typology precomputed results for the case from Aurora."""
    from db.connection import connection_manager

    with connection_manager.cursor() as cur:
        cur.execute(
            "SELECT typology_module_id, sub_category_id, key_entities, match_strength "
            "FROM typology_precomputed_results WHERE case_id = %s",
            (case_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "typology_module_id": r[0],
            "sub_category_id": r[1],
            "key_entities": r[2],
            "match_strength": r[3],
        }
        for r in rows
    ]


def _build_hub_entities(results: list[dict]) -> list[dict]:
    """Find entities appearing in 2+ distinct typology modules. Return sorted hubs."""
    # entity_name -> {typology_module_id: max_match_strength}
    entity_map: dict[str, dict[str, str]] = defaultdict(dict)

    for row in results:
        typology_id = row["typology_module_id"]
        strength = row["match_strength"]
        key_entities_raw = row["key_entities"]

        # key_entities is JSONB — may already be parsed or a string
        if isinstance(key_entities_raw, str):
            try:
                entities = json.loads(key_entities_raw)
            except (json.JSONDecodeError, TypeError):
                continue
        elif isinstance(key_entities_raw, list):
            entities = key_entities_raw
        else:
            continue

        for entity_name in entities:
            if not entity_name or not isinstance(entity_name, str):
                continue
            existing = entity_map[entity_name].get(typology_id)
            # Keep strongest match per typology
            if existing is None or _strength_rank(strength) > _strength_rank(existing):
                entity_map[entity_name][typology_id] = strength

    # Filter to entities in 2+ typology modules, sort by participation count
    hubs = []
    for name, typologies in entity_map.items():
        if len(typologies) >= 2:
            hubs.append({
                "name": name,
                "typologies": [
                    {"id": tid, "match_strength": ms}
                    for tid, ms in typologies.items()
                ],
                "participation_count": len(typologies),
            })

    hubs.sort(key=lambda h: h["participation_count"], reverse=True)
    return hubs[:MAX_HUBS]


def _strength_rank(strength: str) -> int:
    return {"strong": 3, "moderate": 2, "weak": 1}.get(strength, 0)


def _query_inter_hub_edges(case_id: str, hub_names: list[str]) -> list[dict]:
    """Query Neptune for direct edges between hub entities (bounded)."""
    if not hub_names or not NEPTUNE_ENDPOINT:
        return []

    names_csv = ",".join(f"'{_escape(n)}'" for n in hub_names)
    label = f"Entity_{_escape(case_id)}"
    query = (
        f"g.V().hasLabel('{label}')"
        f".has('canonical_name', within({names_csv}))"
        f".outE().inV().hasLabel('{label}')"
        f".has('canonical_name', within({names_csv}))"
        f".path().by(valueMap('canonical_name','entity_type'))"
        f".by(valueMap('type')).by(valueMap('canonical_name','entity_type'))"
        f".limit(500)"
    )

    results = _gremlin_query(query, timeout=30)
    edges = []
    seen = set()
    for path in results:
        if not isinstance(path, list) or len(path) < 3:
            continue
        src_props = path[0] if isinstance(path[0], dict) else {}
        edge_props = path[1] if isinstance(path[1], dict) else {}
        tgt_props = path[2] if isinstance(path[2], dict) else {}

        src_name = _extract_prop(src_props, "canonical_name")
        tgt_name = _extract_prop(tgt_props, "canonical_name")
        edge_type = _extract_prop(edge_props, "type") or "related"

        if src_name and tgt_name:
            key = f"{src_name}|{tgt_name}|{edge_type}"
            if key not in seen:
                seen.add(key)
                edges.append({"from": src_name, "to": tgt_name, "type": edge_type})

    return edges


def _extract_prop(props: dict, key: str) -> str:
    """Extract a property value from Neptune valueMap format."""
    val = props.get(key, "")
    if isinstance(val, list):
        return val[0] if val else ""
    return str(val) if val else ""


def _store_summary_graph(case_id: str, execution_id: str, graph: dict):
    """Store the vis.js-compatible summary graph to Aurora."""
    from db.connection import connection_manager

    with connection_manager.cursor() as cur:
        cur.execute("""
            INSERT INTO typology_summary_graph (case_id, execution_id, graph_json, hub_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (case_id) DO UPDATE SET
                execution_id = EXCLUDED.execution_id,
                graph_json = EXCLUDED.graph_json,
                hub_count = EXCLUDED.hub_count,
                updated_at = NOW()
        """, (case_id, execution_id, json.dumps(graph), graph.get("hub_count", 0)))


def handler(event, context):
    """Lambda entry point — builds cross-typology summary graph."""
    case_id = event.get("case_id", "")
    execution_id = event.get("execution_id", "")

    if not case_id:
        return {"error": "Missing case_id"}

    logger.info("Building summary graph: case=%s", case_id)
    start = time.monotonic()

    # 1. Load all precomputed typology results
    results = _load_precomputed_results(case_id)
    logger.info("Loaded %d precomputed results for case=%s", len(results), case_id)

    if not results:
        return {"case_id": case_id, "hub_count": 0,
                "cross_typology_entities": [], "build_duration_ms": 0}

    # 2. Identify hub entities (in 2+ typology modules)
    hubs = _build_hub_entities(results)
    hub_names = [h["name"] for h in hubs]
    logger.info("Identified %d hub entities", len(hubs))

    # 3. Query Neptune for edges between hubs
    edges = _query_inter_hub_edges(case_id, hub_names)
    logger.info("Found %d inter-hub edges", len(edges))

    # 4. Build degree map from edges
    degree_map: dict[str, int] = defaultdict(int)
    for edge in edges:
        degree_map[edge["from"]] += 1
        degree_map[edge["to"]] += 1

    # 5. Assemble vis.js-compatible graph
    nodes = [
        {
            "name": h["name"],
            "type": "hub_entity",
            "typologies": h["typologies"],
            "degree": degree_map.get(h["name"], 0),
        }
        for h in hubs
    ]

    graph = {"nodes": nodes, "edges": edges, "hub_count": len(hubs)}

    # 6. Identify cross-typology entities (3+ typologies)
    cross_typology_entities = [
        h["name"] for h in hubs
        if h["participation_count"] >= CROSS_TYPOLOGY_THRESHOLD
    ]

    # 7. Store to Aurora
    try:
        _store_summary_graph(case_id, execution_id, graph)
    except Exception as e:
        logger.error("Failed to store summary graph: %s", str(e)[:300])

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info("Summary graph built: %d hubs, %d cross-typology, %dms",
                len(hubs), len(cross_typology_entities), duration_ms)

    return {
        "case_id": case_id,
        "hub_count": len(hubs),
        "cross_typology_entities": cross_typology_entities,
        "build_duration_ms": duration_ms,
    }
