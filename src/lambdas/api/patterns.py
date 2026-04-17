"""API Lambda handlers for pattern discovery.

Endpoints:
    POST /case-files/{id}/patterns — trigger pattern discovery or neighbor query
    GET  /case-files/{id}/patterns — get pattern reports for a case file
"""

import json
import logging
import os
import ssl
import urllib.request

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")


def _neptune_query(query: str) -> list:
    """Execute a Gremlin query via Neptune HTTP API."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result", {}).get("data", {})
            if isinstance(result, dict) and "@value" in result:
                return _parse_gs(result["@value"])
            return result if isinstance(result, list) else [result] if result else []
    except Exception as e:
        logger.error("Neptune query error: %s", str(e)[:200])
        return []


def _parse_gs(items):
    out = []
    for item in items:
        out.append(_parse_gs_val(item))
    return out


def _parse_gs_val(val):
    if not isinstance(val, dict):
        return val
    gt = val.get("@type", "")
    gv = val.get("@value")
    if gt == "g:Map" and isinstance(gv, list):
        d = {}
        for i in range(0, len(gv) - 1, 2):
            d[_parse_gs_val(gv[i])] = _parse_gs_val(gv[i + 1])
        return d
    if gt in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
        return gv
    if gt == "g:List" and isinstance(gv, list):
        return [_parse_gs_val(v) for v in gv]
    if "@value" in val:
        return _parse_gs_val(gv)
    return val


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _build_pattern_service():
    """Construct a PatternDiscoveryService with dependencies from environment."""
    import boto3
    from botocore.config import Config

    from db.connection import ConnectionManager
    from services.pattern_discovery_service import PatternDiscoveryService

    aurora_cm = ConnectionManager()
    bedrock_config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"})
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    return PatternDiscoveryService(None, aurora_cm, bedrock)


# ------------------------------------------------------------------
# POST /case-files/{id}/patterns
# ------------------------------------------------------------------

def _generate_entity_intelligence(case_id: str, entity_name: str, entity_type: str,
                                    neighbors: list, doc_excerpts: list, event: dict) -> dict:
    """Call Bedrock to generate an AI investigative analysis for an entity."""
    import boto3
    from botocore.config import Config as BotoConfig
    from lambdas.api.response_helper import success_response

    bedrock = boto3.client("bedrock-runtime", config=BotoConfig(
        read_timeout=60, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"}
    ))

    # Build connection summary for the prompt
    conn_lines = []
    for n in neighbors[:20]:
        ntype = n.get("type", "unknown").replace("_", " ")
        conn_lines.append(f"- {n.get('name', '?')} ({ntype})")
    connections_text = "\n".join(conn_lines) if conn_lines else "No direct connections found."

    # Build document excerpt summary
    doc_lines = []
    for d in doc_excerpts[:5]:
        doc_lines.append(f"Document: {d.get('filename', 'unknown')}\nExcerpt: {d.get('excerpt', '')[:300]}")
    docs_text = "\n\n".join(doc_lines) if doc_lines else "No document references found."

    prompt = f"""You are a senior investigative analyst at the U.S. Department of Justice, Antitrust Division. 
You are analyzing an entity from a case knowledge graph. Provide a concise, actionable intelligence assessment.

ENTITY: {entity_name}
TYPE: {entity_type.replace('_', ' ')}
DIRECT CONNECTIONS ({len(neighbors)}):
{connections_text}

DOCUMENT REFERENCES ({len(doc_excerpts)}):
{docs_text}

Provide your analysis in this exact JSON format:
{{
  "connection_intelligence": "2-3 sentences explaining WHY these entities are connected and what pattern this suggests. Focus on what an investigator needs to know.",
  "risk_assessment": "1-2 sentences on whether this entity is a hub (central connector), bridge (links separate clusters), or peripheral. What does this mean for the investigation?",
  "hidden_patterns": "1-2 sentences identifying any non-obvious patterns — unusual connection types, entities that shouldn't be connected, gaps in the network.",
  "investigative_questions": [
    {{"question": "Specific question 1 an investigator should pursue based on these connections", "quick_answer": "One-sentence answer (max 150 chars) directly addressing the question using graph and document context."}},
    {{"question": "Specific question 2 targeting a gap or anomaly in the evidence", "quick_answer": "One-sentence answer (max 150 chars) directly addressing the question."}},
    {{"question": "Specific question 3 about a relationship that needs verification", "quick_answer": "One-sentence answer (max 150 chars) directly addressing the question."}}
  ],
  "recommended_actions": [
    "Concrete action 1 (e.g., subpoena specific records, interview specific person)",
    "Concrete action 2",
    "Concrete action 3"
  ],
  "priority": "high|medium|low — based on connection density and investigative significance"
}}

Be specific to THIS entity and THESE connections. Do not give generic advice. Think like a prosecutor building a case."""

    try:
        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }),
        )
        resp_body = json.loads(resp["body"].read().decode("utf-8"))
        text = resp_body.get("content", [{}])[0].get("text", "{}")

        # Parse JSON from response (handle markdown fences)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        analysis = json.loads(text)
        # Normalize investigative_questions to object format with fallback for plain strings
        raw_questions = analysis.get("investigative_questions", [])
        normalized_questions = []
        for q in raw_questions:
            if isinstance(q, dict) and "question" in q:
                # Ensure quick_answer exists and is within 150 chars
                qa = q.get("quick_answer", "")
                if not isinstance(qa, str):
                    qa = ""
                normalized_questions.append({
                    "question": q["question"],
                    "quick_answer": qa[:150],
                })
            elif isinstance(q, str):
                # Fallback: wrap plain string as object with empty quick_answer
                normalized_questions.append({
                    "question": q,
                    "quick_answer": "",
                })
        analysis["investigative_questions"] = normalized_questions
    except json.JSONDecodeError:
        analysis = {
            "connection_intelligence": "AI analysis could not be parsed. Review connections manually.",
            "risk_assessment": "Unable to assess.",
            "hidden_patterns": "Unable to detect.",
            "investigative_questions": [{"question": "Review entity connections in the knowledge graph", "quick_answer": ""}],
            "recommended_actions": ["Manually review document references"],
            "priority": "medium",
        }
    except Exception as e:
        logger.error("Bedrock entity intelligence failed: %s", str(e)[:200])
        analysis = {
            "connection_intelligence": f"AI analysis unavailable: {str(e)[:100]}",
            "risk_assessment": "Unable to assess.",
            "hidden_patterns": "Unable to detect.",
            "investigative_questions": [{"question": "Review entity connections manually", "quick_answer": ""}],
            "recommended_actions": ["Check Bedrock connectivity"],
            "priority": "medium",
        }

    return success_response({"entity_name": entity_name, "analysis": analysis}, 200, event)


@with_access_control
def discover_patterns_handler(event, context):
    """Trigger pattern discovery or return 2-hop neighbors for an entity."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        raw_body = event.get("body")
        body = json.loads(raw_body) if isinstance(raw_body, str) else (raw_body or {})
        entity_name = body.get("entity_name")
        graph_mode = body.get("graph", False)
        ai_analysis = body.get("ai_analysis", False)

        # AI entity intelligence analysis
        if entity_name and ai_analysis:
            neighbors = body.get("neighbors", [])
            doc_excerpts = body.get("doc_excerpts", [])
            entity_type = body.get("entity_type", "unknown")
            return _generate_entity_intelligence(
                case_id, entity_name, entity_type, neighbors, doc_excerpts, event
            )

        # If entity_name provided, return 2-hop neighbors from Neptune
        if entity_name:
            return _get_neighbors(case_id, entity_name, event)

        # If graph mode, return top entities with their edges
        if graph_mode:
            return _get_graph(case_id, event)

        # AI Travel Intelligence — analyze travel patterns from graph data
        travel_intel = body.get("travel_intelligence", False)
        if travel_intel:
            return _analyze_travel_intelligence(case_id, event)

        service = _build_pattern_service()
        report = service.generate_pattern_report(case_id)

        return success_response(report.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to discover patterns")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def _get_graph(case_id: str, event: dict) -> dict:
    """Return top entities and their edges from Neptune for graph visualization."""
    from lambdas.api.response_helper import success_response

    label = f"Entity_{case_id}"
    esc_label = _escape(label)

    # Query locations separately to ensure ALL are included (they may be low-degree)
    # Limit to 200 and compute degree — this avoids timeout on large graphs
    q_locations = (
        f"g.V().hasLabel('{esc_label}')"
        f".has('entity_type','location')"
        f".limit(200)"
        f".project('n','t','c','d')"
        f".by('canonical_name').by('entity_type').by('confidence').by(bothE().count())"
    )
    raw_locs = _neptune_query(q_locations)
    logger.info("Location query returned %d nodes", len(raw_locs))

    # Query top non-location entities by traversal (limit 200)
    q_nodes = (
        f"g.V().hasLabel('{esc_label}')"
        f".has('entity_type',within('person','organization','event','theme','civilization','artifact'))"
        f".limit(200)"
        f".project('n','t','c','d')"
        f".by('canonical_name').by('entity_type').by('confidence').by(bothE().count())"
    )
    raw_nodes = _neptune_query(q_nodes)
    logger.info("Non-location query returned %d nodes", len(raw_nodes))

    # Parse all nodes
    node_list = []
    seen_names = set()
    for r in (raw_locs + raw_nodes):
        if not isinstance(r, dict):
            continue
        name = r.get("n", "")
        if name in seen_names:
            continue
        seen_names.add(name)
        d = r.get("d", 0)
        if isinstance(d, dict):
            d = d.get("@value", 0)
        node_list.append({
            "name": name,
            "type": r.get("t", ""),
            "confidence": r.get("c", 0.5),
            "degree": int(d),
        })
    node_list.sort(key=lambda x: x["degree"], reverse=True)
    # Filter OCR noise from location nodes before sending to frontend
    import re
    def _is_valid_location(name: str) -> bool:
        """Filter out OCR noise entities typed as location."""
        if not name or len(name) < 2:
            return False
        # Too short (single chars, abbreviations under 2 chars)
        stripped = name.strip()
        if len(stripped) < 2:
            return False
        # Numbers-only or mostly numbers
        alpha_count = sum(1 for c in stripped if c.isalpha())
        if alpha_count < 2:
            return False
        # Excessive special characters (OCR garbage)
        special = sum(1 for c in stripped if not c.isalnum() and c not in " .,'-/()")
        if len(stripped) > 0 and special / len(stripped) > 0.3:
            return False
        # Known noise patterns
        noise_patterns = [
            r'^EFTA\d', r'^\d{3,}$', r'^[A-Z]{1,2}$', r'^page\s', r'^1-800',
            r'[•§†‡¶]', r'^\W+$', r'^t\'tt', r'^KO E P S',
        ]
        for pat in noise_patterns:
            if re.search(pat, stripped, re.IGNORECASE):
                return False
        return True

    location_nodes = [n for n in node_list if n["type"] == "location" and _is_valid_location(n["name"])]
    other_nodes = [n for n in node_list if n["type"] != "location"]
    # Cap locations at 60 to avoid overwhelming the geocoder; keep top by degree
    location_nodes = location_nodes[:60]
    max_others = max(60 - len(location_nodes), 20)
    top_nodes = location_nodes + other_nodes[:max_others]
    top_names = {n["name"] for n in top_nodes}

    # Get edges between top nodes
    edges = []
    if top_names:
        q_edges = (
            f"g.V().hasLabel('{esc_label}').outE('RELATED_TO')"
            f".project('s','t','r','c')"
            f".by(outV().values('canonical_name'))"
            f".by(inV().values('canonical_name'))"
            f".by('relationship_type')"
            f".by('confidence')"
            f".limit(500)"
        )
        raw_edges = _neptune_query(q_edges)
        logger.info("Graph edge query returned %d edges", len(raw_edges))
        for e in raw_edges:
            if not isinstance(e, dict):
                continue
            src = e.get("s", "")
            tgt = e.get("t", "")
            if src in top_names and tgt in top_names:
                edges.append({
                    "from": src, "to": tgt,
                    "type": e.get("r", "related"),
                    "confidence": e.get("c", 0.5),
                })

    return success_response({
        "nodes": top_nodes,
        "edges": edges,
        "total_nodes": len(node_list),
        "total_edges_sampled": len(edges),
    }, 200, event)


def _get_neighbors(case_id: str, entity_name: str, event: dict) -> dict:
    """Query Neptune for 2-hop neighbors of an entity."""
    from lambdas.api.response_helper import success_response

    label = f"Entity_{case_id}"
    esc_name = _escape(entity_name)
    esc_label = _escape(label)

    # Level 1: direct neighbors
    q1 = (
        f"g.V().hasLabel('{esc_label}').has('canonical_name','{esc_name}')"
        f".both('RELATED_TO').hasLabel('{esc_label}')"
        f".project('name','type').by('canonical_name').by('entity_type').limit(20)"
    )
    level1 = _neptune_query(q1)
    level1_names = [n.get("name", "") for n in level1 if isinstance(n, dict)]

    # Level 2: neighbors of neighbors
    level2 = []
    level2_edges = []
    for l1_name in level1_names[:10]:
        q2 = (
            f"g.V().hasLabel('{esc_label}').has('canonical_name','{_escape(l1_name)}')"
            f".both('RELATED_TO').hasLabel('{esc_label}')"
            f".project('name','type').by('canonical_name').by('entity_type').limit(10)"
        )
        l2_results = _neptune_query(q2)
        for r in l2_results:
            if isinstance(r, dict):
                n = r.get("name", "")
                if n and n != entity_name and n != l1_name:
                    level2.append(r)
                    level2_edges.append({"from": l1_name, "to": n})

    # Build response
    nodes = [{"name": entity_name, "type": "root", "level": 0}]
    edges = []

    for n in level1:
        if isinstance(n, dict):
            nodes.append({"name": n.get("name", ""), "type": n.get("type", ""), "level": 1})
            edges.append({"from": entity_name, "to": n.get("name", "")})

    seen_l2 = set()
    for n in level2:
        if isinstance(n, dict):
            name = n.get("name", "")
            if name not in seen_l2:
                seen_l2.add(name)
                nodes.append({"name": name, "type": n.get("type", ""), "level": 2})
    edges.extend(level2_edges)

    return success_response({
        "entity_name": entity_name,
        "nodes": nodes,
        "edges": edges,
        "level1_count": len(level1),
        "level2_count": len(seen_l2),
    }, 200, event)


# ------------------------------------------------------------------
# GET /case-files/{id}/patterns
# ------------------------------------------------------------------

@with_access_control
def get_patterns_handler(event, context):
    """Get stored pattern reports for a case file."""
    from db.connection import ConnectionManager
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        aurora_cm = ConnectionManager()
        with aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT report_id, case_file_id, patterns,
                       graph_patterns_count, vector_patterns_count,
                       combined_count, created_at
                FROM pattern_reports
                WHERE case_file_id = %s
                ORDER BY created_at DESC
                """,
                (case_id,),
            )
            rows = cur.fetchall()

        reports = []
        for row in rows:
            reports.append({
                "report_id": str(row[0]),
                "case_file_id": str(row[1]),
                "patterns": json.loads(row[2]) if isinstance(row[2], str) else row[2],
                "graph_patterns_count": row[3],
                "vector_patterns_count": row[4],
                "combined_count": row[5],
                "created_at": str(row[6]),
            })

        return success_response({"reports": reports}, 200, event)

    except Exception as exc:
        logger.exception("Failed to get pattern reports")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/top-patterns
# GET /case-files/{id}/top-patterns/{pattern_index}/evidence
# ------------------------------------------------------------------

@with_access_control
def top_patterns_handler(event, context):
    """Handle Top 5 investigative patterns and evidence bundle requests."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        pattern_index = (event.get("pathParameters") or {}).get("pattern_index")

        if pattern_index is not None:
            # GET /case-files/{id}/top-patterns/{pattern_index}/evidence
            try:
                idx = int(pattern_index)
            except (ValueError, TypeError):
                return error_response(400, "VALIDATION_ERROR", "Pattern index must be between 1 and 5.", event)

            if idx < 1 or idx > 5:
                return error_response(400, "VALIDATION_ERROR", "Pattern index must be between 1 and 5.", event)

            service = _build_pattern_service()
            report = service.discover_top_patterns(case_id)
            patterns = report.get("patterns", [])

            if idx > len(patterns):
                return error_response(404, "NOT_FOUND", f"Pattern {idx} not found. Only {len(patterns)} patterns available.", event)

            target_pattern = patterns[idx - 1]
            raw = target_pattern.get("raw_pattern", target_pattern)
            bundle = service.get_evidence_bundle(case_id, raw)
            return success_response(bundle, 200, event)

        else:
            # GET /case-files/{id}/top-patterns
            service = _build_pattern_service()
            report = service.discover_top_patterns(case_id)
            return success_response(report, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to handle top patterns request")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/patterns  { "travel_intelligence": true }
# AI Travel Route Intelligence
# ------------------------------------------------------------------

def _analyze_travel_intelligence(case_id: str, event: dict) -> dict:
    """Analyze travel patterns from Neptune graph and generate AI insights.

    Computes:
    1. Person→location edge frequencies (corridors)
    2. Hub locations (convergence points)
    3. Outlier destinations
    4. Feeds to Bedrock for narrative intelligence
    """
    import re
    import boto3
    from lambdas.api.response_helper import success_response, error_response

    label = f"Entity_{case_id}"
    esc_label = _escape(label)

    # --- Step 1: Get all person→location edges with frequencies ---
    q_travel = (
        f"g.V().hasLabel('{esc_label}').has('entity_type','person')"
        f".as('p').outE('RELATED_TO').inV().has('entity_type','location').as('l')"
        f".select('p','l').by('canonical_name').by('canonical_name')"
        f".limit(2000)"
    )
    raw_travel = _neptune_query(q_travel)
    logger.info("Travel query returned %d edges", len(raw_travel))

    # Build person→location frequency map
    person_locs = {}  # person -> {location: count}
    loc_persons = {}  # location -> set(persons)
    all_locations = set()

    for r in raw_travel:
        if not isinstance(r, dict):
            continue
        person = r.get("p", "")
        location = r.get("l", "")
        if not person or not location:
            continue
        # Filter noise locations
        if len(location) < 3 or not any(c.isalpha() for c in location):
            continue
        special = sum(1 for c in location if not c.isalnum() and c not in " .,'-/()")
        if len(location) > 0 and special / len(location) > 0.3:
            continue

        if person not in person_locs:
            person_locs[person] = {}
        person_locs[person][location] = person_locs[person].get(location, 0) + 1

        if location not in loc_persons:
            loc_persons[location] = set()
        loc_persons[location].add(person)
        all_locations.add(location)

    if not person_locs:
        return success_response({
            "insights": [],
            "corridors": [],
            "hubs": [],
            "outliers": [],
            "summary": "No travel data found for this case.",
        }, 200, event)

    # --- Step 2: Compute corridors (high-frequency routes) ---
    corridors = []
    for person, locs in sorted(person_locs.items(), key=lambda x: sum(x[1].values()), reverse=True)[:10]:
        sorted_locs = sorted(locs.items(), key=lambda x: x[1], reverse=True)
        top_locs = sorted_locs[:5]
        total_trips = sum(locs.values())
        if total_trips >= 2:
            corridors.append({
                "person": person,
                "total_connections": total_trips,
                "top_locations": [{"name": loc, "frequency": freq} for loc, freq in top_locs],
                "unique_destinations": len(locs),
            })

    # --- Step 3: Identify hub locations (convergence points) ---
    hubs = []
    for loc, persons in sorted(loc_persons.items(), key=lambda x: len(x[1]), reverse=True):
        if len(persons) >= 2:
            hubs.append({
                "location": loc,
                "persons": sorted(persons),
                "person_count": len(persons),
            })

    # --- Step 4: Identify outlier destinations ---
    outliers = []
    for person, locs in person_locs.items():
        total = sum(locs.values())
        if total < 3:
            continue
        avg_freq = total / len(locs)
        for loc, freq in locs.items():
            # Outlier: visited only once AND location has only this person
            if freq == 1 and len(loc_persons.get(loc, set())) <= 1:
                outliers.append({
                    "person": person,
                    "location": loc,
                    "frequency": freq,
                    "person_avg_frequency": round(avg_freq, 1),
                    "reason": f"Single visit by {person} — no other subjects visited this location",
                })
    outliers = sorted(outliers, key=lambda x: x["person_avg_frequency"], reverse=True)[:10]

    # --- Step 5: Bedrock AI narrative ---
    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        model_id = os.environ.get("BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

        # Build compact data summary for the prompt
        corridor_summary = ""
        for c in corridors[:8]:
            top_locs_str = ", ".join(
                l["name"] + " (" + str(l["frequency"]) + "x)"
                for l in c["top_locations"][:3]
            )
            corridor_summary += (
                f"- {c['person']}: {c['total_connections']} connections across "
                f"{c['unique_destinations']} destinations. Top: {top_locs_str}\n"
            )
        hub_summary = "\n".join([
            f"- {h['location']}: {h['person_count']} persons ({', '.join(h['persons'][:4])})"
            for h in hubs[:8]
        ])
        outlier_summary = "\n".join([
            f"- {o['person']} → {o['location']} (1 visit, avg {o['person_avg_frequency']}x elsewhere)"
            for o in outliers[:6]
        ])

        prompt = f"""You are a senior investigative intelligence analyst. Analyze these travel patterns and produce investigative leads.

TRAVEL DATA:
{corridor_summary or 'No corridors.'}

CONVERGENCE POINTS (multiple subjects at same location):
{hub_summary or 'None.'}

OUTLIER DESTINATIONS (unusual single visits):
{outlier_summary or 'None.'}

Generate exactly 6 investigative lead cards as a JSON array. Each card tells a story an investigator needs to hear. Mix these types:
- ROUTINE CORRIDORS: "Epstein flew NYC↔Palm Beach 230 times between 2001-2005. This is the primary shuttle route — subpoena flight manifests for passenger lists on this corridor."
- OUTLIER ALERTS: "Single trip to Marrakesh stands out against the NYC/Paris/Palm Beach pattern. Cross-reference with known associates in Morocco."
- CONVERGENCE WARNINGS: "Paris is the only international city where Epstein, Maxwell, AND Groff all appear. Investigate what meetings or events drew all three."
- INVESTIGATIVE LEADS: "Larry Visoski (pilot) appears at every major hub — Teterboro, Islip, PBI. His flight logs would map the complete travel network."

Each JSON object must have:
- "icon": emoji (🔁 routine, ⚠️ outlier, 👥 convergence, 🔍 lead, ✈️ corridor, 🚨 alert)
- "title": punchy 4-7 word headline
- "narrative": 2-3 sentences. First sentence states the finding. Second explains WHY it matters for the investigation. Third suggests a specific action.
- "type": "routine", "outlier", "convergence", or "lead"
- "locations": array of specific location names from the data above (MUST match exactly)
- "persons": array of specific person names from the data above (MUST match exactly)
- "priority": "high", "medium", or "low"

Write like a briefing for a prosecutor — direct, specific, actionable. No hedging. Use actual numbers from the data.

Return ONLY the JSON array."""

        bedrock_body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        })

        resp = bedrock.invoke_model(modelId=model_id, body=bedrock_body)
        resp_body = json.loads(resp["body"].read().decode())
        ai_text = resp_body.get("content", [{}])[0].get("text", "[]")
        logger.info("Bedrock travel intel response length: %d", len(ai_text))

        # Parse JSON from response
        insights = []
        try:
            insights = json.loads(ai_text)
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', ai_text, re.DOTALL)
            if match:
                try:
                    insights = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning("Failed to parse Bedrock travel intel JSON: %s", ai_text[:300])

        if not isinstance(insights, list):
            insights = []
        logger.info("Parsed %d travel insights from Bedrock", len(insights))

    except Exception as e:
        logger.warning("Bedrock travel intelligence failed: %s", str(e)[:300])
        insights = []

    # Fallback: generate insights from raw data if Bedrock returned none
    if not insights:
        logger.info("Generating fallback insights from raw travel data")
        for c in corridors[:3]:
            top_locs = [l["name"] + " (" + str(l["frequency"]) + "x)" for l in c["top_locations"][:3]]
            insights.append({
                "icon": "✈️",
                "title": c["person"] + " Primary Corridor",
                "narrative": c["person"] + " has " + str(c["total_connections"]) + " travel connections across " + str(c["unique_destinations"]) + " destinations. Top routes: " + ", ".join(top_locs) + ". Subpoena flight manifests and passenger lists for these routes.",
                "type": "routine",
                "locations": [l["name"] for l in c["top_locations"][:5]],
                "persons": [c["person"]],
                "priority": "high",
            })
        for h in hubs[:2]:
            insights.append({
                "icon": "👥",
                "title": h["location"] + " Convergence Point",
                "narrative": str(h["person_count"]) + " subjects converge at " + h["location"] + ": " + ", ".join(h["persons"][:4]) + ". This location may be a coordination hub — investigate meetings and events.",
                "type": "convergence",
                "locations": [h["location"]],
                "persons": h["persons"][:4],
                "priority": "high" if h["person_count"] >= 5 else "medium",
            })
        for o in outliers[:1]:
            insights.append({
                "icon": "⚠️",
                "title": "Outlier: " + o["person"] + " → " + o["location"],
                "narrative": o["person"] + " visited " + o["location"] + " only once — this stands out against the typical travel pattern. Cross-reference with known associates at this location.",
                "type": "outlier",
                "locations": [o["location"]],
                "persons": [o["person"]],
                "priority": "medium",
            })

    return success_response({
        "insights": insights[:6],
        "corridors": corridors[:10],
        "hubs": hubs[:10],
        "outliers": outliers[:10],
        "stats": {
            "total_persons": len(person_locs),
            "total_locations": len(all_locations),
            "total_connections": sum(sum(v.values()) for v in person_locs.values()),
            "corridor_count": len(corridors),
            "hub_count": len(hubs),
            "outlier_count": len(outliers),
        },
    }, 200, event)
