"""IPS Worker Lambda handler.

Invoked by Step Functions for each phase of the IPS computation pipeline.
Dispatches to IPSWorker methods based on event.phase.

Phases:
    layer1_graph_topology  — Compute 4 graph topology sub-signals from Neptune
    layer2_prosecutorial   — Compute 5 prosecutorial evidence sub-signals
    anomaly_detection      — Run 6 anomaly detection algorithms
    layer3_ai_insight      — Send top 10 patterns to Bedrock
    store_results          — Compute final IPS and persist to Aurora
"""

import json
import logging
import os
import ssl
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")


def _neptune_query(query: str, timeout: int = 15) -> list:
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


def _get_graph_data(case_id: str) -> dict:
    """Fetch graph nodes and edges from Neptune for IPS computation."""
    label = f"Entity_{case_id}"
    esc_label = _escape(label)

    # Get nodes with degree
    q_nodes = (
        f"g.V().hasLabel('{esc_label}')"
        f".limit(500)"
        f".project('n','t','c','d')"
        f".by('canonical_name').by('entity_type').by('confidence').by(bothE().count())"
    )
    raw_nodes = _neptune_query(q_nodes)

    nodes = []
    for r in raw_nodes:
        if not isinstance(r, dict):
            continue
        d = r.get("d", 0)
        if isinstance(d, dict):
            d = d.get("@value", 0)
        nodes.append({
            "name": r.get("n", ""),
            "type": r.get("t", ""),
            "confidence": r.get("c", 0.5),
            "degree": int(d),
        })

    # Get edges
    q_edges = (
        f"g.V().hasLabel('{esc_label}').outE('RELATED_TO')"
        f".project('s','t','r','c')"
        f".by(outV().values('canonical_name'))"
        f".by(inV().values('canonical_name'))"
        f".by('relationship_type')"
        f".by('confidence')"
        f".limit(2000)"
    )
    raw_edges = _neptune_query(q_edges)

    edges = []
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        edges.append({
            "from": e.get("s", ""),
            "to": e.get("t", ""),
            "type": e.get("r", "related"),
            "confidence": e.get("c", 0.5),
        })

    return {"nodes": nodes, "edges": edges}


def _update_run_status(case_id: str, run_id: str, updates: dict):
    """Update ips_computation_runs table."""
    try:
        from db.connection import ConnectionManager
        cm = ConnectionManager()
        set_clauses = []
        values = []
        for k, v in updates.items():
            set_clauses.append(f"{k} = %s")
            values.append(v)
        values.append(run_id)
        sql = f"UPDATE ips_computation_runs SET {', '.join(set_clauses)} WHERE run_id = %s"
        with cm.cursor() as cur:
            cur.execute(sql, values)
        logger.info("Updated run %s: %s", run_id, updates)
    except Exception as exc:
        logger.warning("Failed to update run status: %s", str(exc)[:200])


def handler(event, context):
    """Dispatch to IPSWorker methods based on event.phase."""
    phase = event.get("phase", "")
    case_id = event.get("case_id", "")
    run_id = event.get("run_id", "")

    logger.info("IPS Worker: phase=%s case_id=%s run_id=%s", phase, case_id, run_id)

    if not case_id:
        return {"status": "error", "error": "Missing case_id"}

    from services.ips_engine import IPSWorker
    worker = IPSWorker()

    try:
        if phase == "layer1_graph_topology":
            return _phase_layer1(worker, case_id, run_id)
        elif phase == "layer2_prosecutorial":
            return _phase_layer2(worker, case_id, run_id, event)
        elif phase == "anomaly_detection":
            return _phase_anomaly(worker, case_id, run_id, event)
        elif phase == "layer3_ai_insight":
            return _phase_layer3(worker, case_id, run_id, event)
        elif phase == "store_results":
            return _phase_store(worker, case_id, run_id, event)
        elif phase == "typology_classification":
            return _phase_typology(case_id, run_id, event)
        else:
            return {"status": "error", "error": f"Unknown phase: {phase}"}
    except Exception as exc:
        logger.exception("IPS Worker phase %s failed", phase)
        if run_id:
            _update_run_status(case_id, run_id, {
                "status": "failed",
                "error_details": str(exc)[:500],
            })
        return {"status": "error", "error": str(exc)[:300]}


def _phase_layer1(worker, case_id, run_id):
    """Phase 1: Graph Topology signals from Neptune."""
    graph_data = _get_graph_data(case_id)
    scores = worker.compute_graph_topology(case_id, graph_data)

    if run_id:
        _update_run_status(case_id, run_id, {"layer1_completed": True})

    return {
        "status": "completed",
        "scores": scores,
        "graph_data_summary": {
            "node_count": len(graph_data.get("nodes", [])),
            "edge_count": len(graph_data.get("edges", [])),
        },
    }


def _phase_layer2(worker, case_id, run_id, event):
    """Phase 2: Prosecutorial Evidence signals."""
    graph_data = _get_graph_data(case_id)
    layer1 = event.get("layer1", {})
    layer1_scores = layer1.get("scores", {}) if isinstance(layer1, dict) else {}

    scores = worker.compute_prosecutorial(case_id, graph_data, layer1_scores)

    if run_id:
        _update_run_status(case_id, run_id, {"layer2_completed": True})

    return {"status": "completed", "scores": scores}


def _phase_anomaly(worker, case_id, run_id, event):
    """Phase 3: Run anomaly detection algorithms."""
    graph_data = _get_graph_data(case_id)

    try:
        from services.anomaly_detectors import (
            StructuringDetector, TemporalConvergenceDetector,
            GhostEntityDetector, AbsencePatternDetector,
            DecayPatternDetector, ProxyNetworkDetector,
        )
    except ImportError:
        logger.warning("Anomaly detectors not available")
        if run_id:
            _update_run_status(case_id, run_id, {"anomalies_completed": True})
        return {"status": "completed", "patterns": []}

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    all_patterns = []

    # Run each detector independently — continue on individual failures
    detectors = [
        ("structuring", StructuringDetector()),
        ("temporal_convergence", TemporalConvergenceDetector()),
        ("ghost_entity", GhostEntityDetector()),
        ("absence_pattern", AbsencePatternDetector()),
        ("decay_pattern", DecayPatternDetector()),
        ("proxy_network", ProxyNetworkDetector()),
    ]

    for det_type, detector in detectors:
        try:
            results = detector.detect(nodes, edges, case_id)
            for r in results:
                r["pattern_type"] = det_type
            all_patterns.extend(results)
            logger.info("Anomaly %s: found %d patterns", det_type, len(results))
        except Exception as exc:
            logger.warning("Anomaly detector %s failed: %s", det_type, str(exc)[:200])

    if run_id:
        _update_run_status(case_id, run_id, {"anomalies_completed": True})

    return {"status": "completed", "patterns": all_patterns}


def _phase_layer3(worker, case_id, run_id, event):
    """Phase 4: AI Insight from Bedrock."""
    import boto3
    from botocore.config import Config

    # Build top patterns from layer1 + layer2 scores
    layer1 = event.get("layer1", {})
    layer2 = event.get("layer2", {})
    anomalies = event.get("anomalies", {})

    layer1_scores = layer1.get("scores", {}) if isinstance(layer1, dict) else {}
    layer2_scores = layer2.get("scores", {}) if isinstance(layer2, dict) else {}
    anomaly_patterns = anomalies.get("patterns", []) if isinstance(anomalies, dict) else []

    # Build pattern list for Bedrock
    top_patterns = []
    for i, p in enumerate(anomaly_patterns[:10]):
        top_patterns.append({
            "index": i,
            "title": p.get("title", f"Pattern {i+1}"),
            "type": p.get("pattern_type", "unknown"),
            "persons": p.get("persons", []),
            "locations": p.get("locations", []),
        })

    try:
        bedrock = boto3.client(
            "bedrock-runtime",
            config=Config(read_timeout=60, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"}),
        )
        result = worker.compute_ai_insight(case_id, top_patterns, bedrock)
    except Exception as exc:
        logger.warning("Bedrock AI insight failed: %s", str(exc)[:200])
        result = {"scores": {}, "raw_response": "", "error": str(exc)[:200]}

    if run_id:
        _update_run_status(case_id, run_id, {"layer3_completed": True})

    return {"status": "completed", "scores": result.get("scores", {})}


def _phase_store(worker, case_id, run_id, event):
    """Phase 5: Compute final IPS and store results in Aurora."""
    from db.connection import ConnectionManager

    layer1 = event.get("layer1", {})
    layer2 = event.get("layer2", {})
    layer3 = event.get("layer3", {})
    anomalies = event.get("anomalies", {})

    l1_scores = layer1.get("scores", {}) if isinstance(layer1, dict) else {}
    l2_scores = layer2.get("scores", {}) if isinstance(layer2, dict) else {}
    l3_scores = layer3.get("scores", {}) if isinstance(layer3, dict) else {}
    anomaly_patterns = anomalies.get("patterns", []) if isinstance(anomalies, dict) else []

    l1_total = l1_scores.get("total", 0)
    l2_total = l2_scores.get("total", 0)

    # Determine if we have Layer 3
    has_layer3 = bool(l3_scores) and not l3_scores.get("error")
    l3_ai_scores = l3_scores.get("scores", {}) if has_layer3 else {}

    # Build patterns to store
    patterns_to_store = []

    # Add anomaly patterns
    for i, p in enumerate(anomaly_patterns):
        l3_score = l3_ai_scores.get(i, l3_ai_scores.get(str(i), 50))
        if has_layer3:
            ips = worker.compute_final_ips(l1_total, l2_total, float(l3_score))
            partial = False
        else:
            ips = worker.compute_partial_ips(l1_total, l2_total)
            partial = True

        evidence_gaps = worker.identify_evidence_gaps(
            l2_scores, p.get("persons", []), p.get("locations", [])
        )

        patterns_to_store.append({
            "pattern_index": i + 1,
            "pattern_type": p.get("pattern_type", "unknown"),
            "ips_total": round(ips, 2),
            "ips_partial": partial,
            "l1": l1_scores,
            "l2": l2_scores,
            "l3_ai_insight": float(l3_score) if has_layer3 else 0,
            "title": p.get("title", f"Pattern {i+1}"),
            "narrative": p.get("narrative", ""),
            "icon": p.get("icon", "📊"),
            "persons": p.get("persons", []),
            "locations": p.get("locations", []),
            "pattern_metadata": p.get("metadata", {}),
            "evidence_gaps": evidence_gaps,
            "is_facilitator": p.get("is_facilitator", False),
        })

    # Classify priorities
    all_scores = [p["ips_total"] for p in patterns_to_store]
    priorities = worker.classify_priority(all_scores)
    for i, p in enumerate(patterns_to_store):
        p["priority"] = priorities.get(i, "medium")

    # Sort by IPS descending
    patterns_to_store.sort(key=lambda x: x["ips_total"], reverse=True)

    # Store in Aurora
    cm = ConnectionManager()
    stored_count = 0
    try:
        with cm.cursor() as cur:
            # Delete old results for this case
            cur.execute("DELETE FROM case_ips_results WHERE case_file_id = %s", (case_id,))

            for p in patterns_to_store:
                cur.execute("""
                    INSERT INTO case_ips_results (
                        case_file_id, pattern_index, pattern_type,
                        ips_total, ips_partial,
                        l1_betweenness, l1_temporal_clustering, l1_cross_type_bridge, l1_isolation_anomaly, l1_total,
                        l2_the_act, l2_the_means, l2_the_network, l2_the_pattern, l2_the_gap, l2_total,
                        l3_ai_insight,
                        title, narrative, icon, priority,
                        persons, locations, pattern_metadata, evidence_gaps,
                        is_facilitator
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s
                    )
                """, (
                    case_id, p["pattern_index"], p["pattern_type"],
                    p["ips_total"], p["ips_partial"],
                    p["l1"].get("betweenness", 0), p["l1"].get("temporal_clustering", 0),
                    p["l1"].get("cross_type_bridge", 0), p["l1"].get("isolation_anomaly", 0),
                    p["l1"].get("total", 0),
                    p["l2"].get("the_act", 0), p["l2"].get("the_means", 0),
                    p["l2"].get("the_network", 0), p["l2"].get("the_pattern", 0),
                    p["l2"].get("the_gap", 0), p["l2"].get("total", 0),
                    p["l3_ai_insight"],
                    p["title"], p["narrative"], p["icon"], p["priority"],
                    json.dumps(p["persons"]), json.dumps(p["locations"]),
                    json.dumps(p["pattern_metadata"]),
                    json.dumps(p["evidence_gaps"]),
                    p["is_facilitator"],
                ))
                stored_count += 1

            # Update run status
            if run_id:
                cur.execute("""
                    UPDATE ips_computation_runs
                    SET status = 'completed', completed_at = now(), patterns_detected = %s
                    WHERE run_id = %s
                """, (stored_count, run_id))

        logger.info("Stored %d IPS patterns for case %s", stored_count, case_id)
    except Exception as exc:
        logger.exception("Failed to store IPS results")
        if run_id:
            _update_run_status(case_id, run_id, {
                "status": "failed",
                "error_details": str(exc)[:500],
            })
        raise

    return {"status": "completed", "patterns_stored": stored_count}


def _phase_typology(case_id, run_id, event):
    """Phase: Crime Typology Classification.

    Runs all registered typology modules against the case's entities and
    relationships. Stores results in case_typology_scores table.

    This phase can run independently (triggered via the /typology endpoint)
    or as part of the full IPS pipeline after store_results.
    """
    from db.connection import ConnectionManager
    from services.sex_trafficking_typology import SexTraffickingTypologyEngine

    cm = ConnectionManager()
    engine = SexTraffickingTypologyEngine(aurora_conn=cm)

    report = engine.analyze_case(case_id)

    # Get case name
    try:
        with cm.cursor() as cur:
            cur.execute("SELECT topic_name FROM case_files WHERE case_id = %s", (case_id,))
            row = cur.fetchone()
            if row:
                report.case_name = row[0]
    except Exception:
        pass

    # Store typology scores in Aurora
    stored = 0
    try:
        with cm.cursor() as cur:
            # Ensure table exists (idempotent)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS case_typology_scores (
                    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    case_file_id UUID NOT NULL,
                    typology_module VARCHAR(50) NOT NULL,
                    category_id VARCHAR(50) NOT NULL,
                    category_name VARCHAR(100) NOT NULL,
                    score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    confidence VARCHAR(10) NOT NULL DEFAULT 'low',
                    matched_flags JSONB DEFAULT '[]',
                    flag_details JSONB DEFAULT '[]',
                    evidence_summary TEXT DEFAULT '',
                    computed_at TIMESTAMPTZ DEFAULT now(),
                    UNIQUE(case_file_id, typology_module, category_id)
                )
            """)

            # Upsert scores for each category
            for s in report.scores:
                cur.execute("""
                    INSERT INTO case_typology_scores
                        (case_file_id, typology_module, category_id, category_name,
                         score, confidence, matched_flags, flag_details, evidence_summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (case_file_id, typology_module, category_id)
                    DO UPDATE SET
                        score = EXCLUDED.score,
                        confidence = EXCLUDED.confidence,
                        matched_flags = EXCLUDED.matched_flags,
                        flag_details = EXCLUDED.flag_details,
                        evidence_summary = EXCLUDED.evidence_summary,
                        computed_at = now()
                """, (
                    case_id,
                    "sex_trafficking",
                    s.category_id,
                    s.category_name,
                    s.score,
                    s.confidence,
                    json.dumps(s.matched_flags),
                    json.dumps(s.flag_details),
                    s.evidence_summary,
                ))
                stored += 1

        logger.info("Stored %d typology scores for case %s", stored, case_id)
    except Exception as exc:
        logger.exception("Failed to store typology scores")
        return {"status": "error", "error": str(exc)[:300]}

    return {
        "status": "completed",
        "scores_stored": stored,
        "overall_score": report.overall_score,
        "dominant_typology": report.dominant_typology,
        "flags_triggered": report.flags_triggered,
    }
