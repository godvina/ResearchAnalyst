"""Intelligence Command Brief — prosecution-oriented synthesis for large cases.

Endpoint: GET /case-files/{id}/intelligence-brief
Returns a synthesized prosecution brief generated from precomputed typology
pipeline data. No Neptune queries. Sub-5s response (cached after first call).

Sections:
1. Prosecution Readiness Score (composite 0-100)
2. Hub Entities (cross-typology convergence points)
3. Strongest Thread (actionable prosecution path)
4. Vulnerability Map (defense attorney's attack surface)
5. Typology Threat Ranking (top patterns by evidence strength)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SYNTH_MODEL = os.environ.get("BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")


def handler(event, context):
    """Generate or serve cached Intelligence Command Brief."""
    from db.connection import ConnectionManager
    from lambdas.api.response_helper import error_response, success_response

    case_id = (event.get("pathParameters") or {}).get("id", "")
    if not case_id:
        return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

    cm = ConnectionManager()
    params = event.get("queryStringParameters") or {}
    bypass_cache = params.get("refresh", "").lower() == "true"

    # Check cache first (unless refresh requested)
    if not bypass_cache:
        try:
            with cm.cursor() as cur:
                cur.execute("""
                    SELECT brief_json, generated_at FROM intelligence_command_brief
                    WHERE case_id = %s AND generated_at > NOW() - INTERVAL '2 hours'
                """, (case_id,))
                cached = cur.fetchone()
                if cached:
                    brief = json.loads(cached[0]) if isinstance(cached[0], str) else cached[0]
                    brief["cached"] = True
                    brief["generated_at"] = str(cached[1])
                    return success_response(brief, 200, event)
        except Exception:
            pass  # Table may not exist yet — generate fresh

    # Gather precomputed data from Aurora
    try:
        data = _gather_precomputed_data(cm, case_id)
    except Exception as exc:
        logger.error("Failed to gather precomputed data: %s", str(exc)[:300])
        return error_response(404, "NO_DATA", "No precomputed data available for this case", event)

    if not data["typologies"]:
        return error_response(404, "NO_DATA", "No precomputed typology results for this case", event)

    # Generate synthesis via Bedrock
    t0 = time.time()
    try:
        brief = _synthesize_brief(data)
    except Exception as exc:
        logger.error("Bedrock synthesis failed: %s", str(exc)[:300])
        # Return a degraded brief with just the scores (no AI synthesis)
        brief = _build_degraded_brief(data)

    brief["generation_time_ms"] = int((time.time() - t0) * 1000)
    brief["case_id"] = case_id
    brief["entity_count"] = data["entity_count"]
    brief["generated_at"] = datetime.now(timezone.utc).isoformat()
    brief["cached"] = False

    # Cache the result
    try:
        _cache_brief(cm, case_id, brief)
    except Exception:
        pass  # Non-critical

    return success_response(brief, 200, event)


def _gather_precomputed_data(cm, case_id: str) -> dict:
    """Read all precomputed pipeline data from Aurora."""
    data = {"case_id": case_id, "typologies": [], "sub_categories": [],
            "summary_graph": None, "entity_count": 0}

    with cm.cursor() as cur:
        # Entity count
        cur.execute("SELECT entity_count FROM case_files WHERE case_id = %s", (case_id,))
        row = cur.fetchone()
        data["entity_count"] = int(row[0]) if row and row[0] else 0

        # Typology summaries
        cur.execute("""
            SELECT typology_module_id, overall_typology_score, match_strength,
                   dominant_sub_category, key_entities, is_stale
            FROM typology_precomputed_summary
            WHERE case_id = %s ORDER BY overall_typology_score DESC
        """, (case_id,))
        for row in cur.fetchall():
            key_ents = row[4] if isinstance(row[4], list) else json.loads(row[4] or "[]")
            data["typologies"].append({
                "module_id": row[0],
                "score": float(row[1]) if row[1] else 0.0,
                "match_strength": row[2] or "weak",
                "dominant_sub": row[3],
                "key_entities": key_ents,
                "is_stale": row[5] or False,
            })

        # Sub-category details
        cur.execute("""
            SELECT typology_module_id, sub_category_id, overall_score,
                   match_strength, cosine_similarity, key_entities, subgraph_summary
            FROM typology_precomputed_results
            WHERE case_id = %s ORDER BY overall_score DESC
        """, (case_id,))
        for row in cur.fetchall():
            key_ents = row[5] if isinstance(row[5], list) else json.loads(row[5] or "[]")
            summary = row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}")
            data["sub_categories"].append({
                "module_id": row[0],
                "sub_id": row[1],
                "score": float(row[2]) if row[2] else 0.0,
                "match_strength": row[3] or "weak",
                "cosine_similarity": float(row[4]) if row[4] else 0.0,
                "key_entities": key_ents,
                "entity_count": summary.get("entity_count", 0),
                "edge_count": summary.get("edge_count", 0),
            })

        # Summary graph (cross-typology)
        cur.execute("""
            SELECT nodes, edges, hub_count, cross_typology_entities
            FROM typology_summary_graph WHERE case_id = %s
        """, (case_id,))
        graph_row = cur.fetchone()
        if graph_row:
            nodes = graph_row[0] if isinstance(graph_row[0], list) else json.loads(graph_row[0] or "[]")
            edges = graph_row[1] if isinstance(graph_row[1], list) else json.loads(graph_row[1] or "[]")
            cross = graph_row[3] if isinstance(graph_row[3], list) else json.loads(graph_row[3] or "[]")
            data["summary_graph"] = {
                "nodes": nodes,
                "edges": edges,
                "hub_count": graph_row[2] or 0,
                "cross_typology_entities": cross,
            }

    return data


def _synthesize_brief(data: dict) -> dict:
    """Call Bedrock Claude Haiku to synthesize the prosecution brief."""
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    # Build structured context for the model
    typology_summary = "\n".join(
        f"- {t['module_id'].replace('_',' ').title()}: score={t['score']:.2f} ({t['match_strength']}), "
        f"key_entities={t['key_entities'][:5]}"
        for t in data["typologies"][:11]
    )

    # Find cross-typology hub entities
    hub_entities = []
    if data["summary_graph"] and data["summary_graph"]["cross_typology_entities"]:
        hub_entities = data["summary_graph"]["cross_typology_entities"][:10]

    # Top sub-categories by score
    top_subs = data["sub_categories"][:8]
    sub_detail = "\n".join(
        f"- {s['module_id']}/{s['sub_id']}: score={s['score']:.2f}, "
        f"cosine={s['cosine_similarity']:.2f}, entities={s['entity_count']}, edges={s['edge_count']}"
        for s in top_subs
    )

    # Entity count for scale context
    entity_count = data["entity_count"]

    prompt = f"""You are a senior intelligence analyst preparing a prosecution readiness brief for a complex multi-typology criminal case. This case has {entity_count:,} entities in its knowledge graph.

## Scored Typologies (11 crime patterns analyzed):
{typology_summary}

## Top Evidence Concentrations (sub-categories):
{sub_detail}

## Cross-Typology Hub Entities (appear in 3+ crime patterns):
{json.dumps(hub_entities[:10]) if hub_entities else "No cross-typology convergence data available yet."}

## Your Task:
Generate a prosecution-oriented intelligence brief with these exact sections. Be specific, cite entity names and typology connections where available. Write for a federal prosecutor reviewing this case.

Return ONLY valid JSON with this structure:
{{
  "prosecution_readiness_score": <0-100 integer>,
  "readiness_label": "<not_ready|building|strong|indictment_ready>",
  "bluf": "<2-3 sentence Bottom Line Up Front for the AUSA>",
  "strongest_thread": {{
    "typology": "<dominant crime pattern>",
    "summary": "<1 paragraph: what the evidence shows, who's connected, why it's prosecutable>",
    "next_action": "<specific investigative step to strengthen this thread>"
  }},
  "hub_entities": [
    {{"name": "<entity>", "role": "<role across typologies>", "typologies": ["<list>"], "significance": "<why this person/org matters>"}}
  ],
  "vulnerabilities": [
    {{"gap": "<what's missing>", "impact": "<how defense exploits it>", "remediation": "<how to fix>"}}
  ],
  "cross_typology_insight": "<1 paragraph on how the crime patterns connect — the anti-silo view>"
}}"""

    resp = bedrock.invoke_model(
        modelId=SYNTH_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    body = json.loads(resp["body"].read())
    text = body.get("content", [{}])[0].get("text", "")

    # Parse the JSON response
    # Handle cases where model wraps in markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    brief = json.loads(text.strip())

    # Add the raw typology scores for the frontend
    brief["typology_scores"] = [
        {"module_id": t["module_id"], "score": t["score"],
         "match_strength": t["match_strength"], "key_entities": t["key_entities"][:5]}
        for t in data["typologies"]
    ]

    # Add summary graph metadata
    if data["summary_graph"]:
        brief["graph_stats"] = {
            "hub_count": data["summary_graph"]["hub_count"],
            "node_count": len(data["summary_graph"]["nodes"]),
            "edge_count": len(data["summary_graph"]["edges"]),
        }

    return brief


def _build_degraded_brief(data: dict) -> dict:
    """Build a scores-only brief when Bedrock synthesis fails."""
    top = data["typologies"][0] if data["typologies"] else {}
    avg_score = sum(t["score"] for t in data["typologies"]) / len(data["typologies"]) if data["typologies"] else 0

    return {
        "prosecution_readiness_score": int(avg_score * 100),
        "readiness_label": "building" if avg_score > 0.5 else "not_ready",
        "bluf": f"Case contains {data['entity_count']:,} entities across {len(data['typologies'])} crime typologies. "
                f"Dominant pattern: {top.get('module_id', 'unknown').replace('_', ' ')}. AI synthesis unavailable.",
        "strongest_thread": {
            "typology": top.get("module_id", "unknown"),
            "summary": "Automated synthesis unavailable. Review typology scores below.",
            "next_action": "Run manual analysis on the dominant typology sub-categories.",
        },
        "hub_entities": [],
        "vulnerabilities": [],
        "cross_typology_insight": "Cross-typology analysis requires AI synthesis. Refresh to retry.",
        "typology_scores": [
            {"module_id": t["module_id"], "score": t["score"],
             "match_strength": t["match_strength"], "key_entities": t["key_entities"][:5]}
            for t in data["typologies"]
        ],
        "degraded": True,
    }


def _cache_brief(cm, case_id: str, brief: dict):
    """Store the generated brief in Aurora for fast retrieval."""
    with cm.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS intelligence_command_brief (
                case_id UUID PRIMARY KEY,
                brief_json JSONB NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            INSERT INTO intelligence_command_brief (case_id, brief_json, generated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (case_id) DO UPDATE SET
                brief_json = EXCLUDED.brief_json,
                generated_at = NOW()
        """, (case_id, json.dumps(brief)))
