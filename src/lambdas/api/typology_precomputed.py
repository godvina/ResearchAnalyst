"""API handler for pre-computed typology results.

Endpoint: GET /case-files/{id}/typology-precomputed
Returns pre-computed typology scores and summary graph from Aurora.
No Neptune or Bedrock calls — sub-500ms response time.
"""

import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Serve pre-computed typology data from Aurora."""
    from db.connection import ConnectionManager
    from lambdas.api.response_helper import error_response, success_response

    case_id = (event.get("pathParameters") or {}).get("id", "")
    if not case_id:
        return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

    try:
        cm = ConnectionManager()

        # 1. Get typology summaries (one row per typology module)
        with cm.cursor() as cur:
            cur.execute("""
                SELECT typology_module_id, overall_typology_score, match_strength,
                       dominant_sub_category, flags_triggered, total_flags,
                       key_entities, narrative, is_stale, computed_at
                FROM typology_precomputed_summary
                WHERE case_id = %s
                ORDER BY overall_typology_score DESC
            """, (case_id,))
            summary_rows = cur.fetchall()

        if not summary_rows:
            return success_response({
                "precomputed": False,
                "reason": "no_results",
                "case_id": case_id,
            }, 200, event)

        typologies = []
        any_stale = False
        for row in summary_rows:
            is_stale = row[8] if row[8] is not None else False
            if is_stale:
                any_stale = True
            key_entities = row[6]
            if isinstance(key_entities, str):
                key_entities = json.loads(key_entities)
            typologies.append({
                "typology_module_id": row[0],
                "overall_score": float(row[1]) if row[1] else 0.0,
                "match_strength": row[2] or "weak",
                "dominant_sub_category": row[3],
                "flags_triggered": row[4] or 0,
                "total_flags": row[5] or 0,
                "key_entities": key_entities or [],
                "narrative": row[7],
                "is_stale": is_stale,
                "computed_at": str(row[9]) if row[9] else None,
            })

        # 2. Get sub-category details for all typologies
        with cm.cursor() as cur:
            cur.execute("""
                SELECT typology_module_id, sub_category_id, overall_score,
                       match_strength, cosine_similarity, key_entities, narrative
                FROM typology_precomputed_results
                WHERE case_id = %s
                ORDER BY typology_module_id, overall_score DESC
            """, (case_id,))
            detail_rows = cur.fetchall()

        sub_category_details = {}
        for row in detail_rows:
            module_id = row[0]
            if module_id not in sub_category_details:
                sub_category_details[module_id] = []
            key_ents = row[5]
            if isinstance(key_ents, str):
                key_ents = json.loads(key_ents)
            sub_category_details[module_id].append({
                "sub_category_id": row[1],
                "score": float(row[2]) if row[2] else 0.0,
                "match_strength": row[3] or "weak",
                "cosine_similarity": float(row[4]) if row[4] else 0.0,
                "key_entities": key_ents or [],
                "narrative": row[6],
            })

        # Attach sub-categories to each typology
        for t in typologies:
            t["sub_categories"] = sub_category_details.get(t["typology_module_id"], [])

        # 3. Get summary graph
        summary_graph = None
        with cm.cursor() as cur:
            cur.execute("""
                SELECT nodes, edges, hub_count, cross_typology_entities, is_stale
                FROM typology_summary_graph
                WHERE case_id = %s
            """, (case_id,))
            graph_row = cur.fetchone()

        if graph_row:
            nodes = graph_row[0] if isinstance(graph_row[0], list) else json.loads(graph_row[0] or "[]")
            edges = graph_row[1] if isinstance(graph_row[1], list) else json.loads(graph_row[1] or "[]")
            cross_ents = graph_row[3] if isinstance(graph_row[3], list) else json.loads(graph_row[3] or "[]")
            summary_graph = {
                "nodes": nodes,
                "edges": edges,
                "hub_count": graph_row[2] or 0,
                "cross_typology_entities": cross_ents,
                "is_stale": graph_row[4] if graph_row[4] is not None else False,
            }

        # 4. Get pipeline status
        pipeline_status = None
        with cm.cursor() as cur:
            cur.execute("""
                SELECT status, started_at, completed_at
                FROM pipeline_executions
                WHERE case_id = %s
                ORDER BY started_at DESC LIMIT 1
            """, (case_id,))
            pipe_row = cur.fetchone()
            if pipe_row:
                pipeline_status = {
                    "status": pipe_row[0],
                    "started_at": str(pipe_row[1]) if pipe_row[1] else None,
                    "completed_at": str(pipe_row[2]) if pipe_row[2] else None,
                }

        return success_response({
            "precomputed": True,
            "case_id": case_id,
            "typologies": typologies,
            "summary_graph": summary_graph,
            "any_stale": any_stale,
            "pipeline_status": pipeline_status,
        }, 200, event)

    except Exception as exc:
        logger.exception("Failed to load precomputed typology data")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
