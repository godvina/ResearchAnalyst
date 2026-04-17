"""API handlers for Intelligence Trawler & Alerts.

Endpoints:
    POST   /case-files/{id}/trawl                          — run trawl scan
    GET    /case-files/{id}/trawl/briefing                 — intelligence brief
    GET    /case-files/{id}/alerts                         — list alerts
    PATCH  /case-files/{id}/alerts/{alert_id}              — update alert
    POST   /case-files/{id}/alerts/{alert_id}/investigate  — investigate alert
    GET    /case-files/{id}/trawl/history                  — scan history
    PUT    /case-files/{id}/trawl-config                   — save config
    GET    /case-files/{id}/trawl-config                   — load config
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_UUID = r"[0-9a-f\-]+"


# ------------------------------------------------------------------
# Service builders (lazy imports to keep cold-start fast)
# ------------------------------------------------------------------

def _build_trawler_engine():
    """Construct a TrawlerEngine with all injected dependencies.

    Skips PatternDiscoveryService to avoid Bedrock calls that exceed
    the API Gateway 29s timeout.  Graph scan + doc scan + cross-case
    scan are the high-value phases for alert generation.
    """
    import boto3
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.trawler_engine import TrawlerEngine

    aurora_cm = ConnectionManager()
    neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_cm = NeptuneConnectionManager(endpoint=neptune_ep)
    bedrock = boto3.client("bedrock-runtime")

    # Use a stub pattern service that returns empty patterns (avoids Bedrock)
    class _StubPatternService:
        def discover_top_patterns(self, case_id):
            return {"patterns": []}
    pattern_svc = _StubPatternService()

    # Use a stub cross-case service (avoids slow Neptune cross-case queries)
    class _StubCrossCaseService:
        def find_cross_case_entities(self, case_id, **kwargs):
            return []
        def scan_for_overlaps(self, case_id, **kwargs):
            return []
    cross_case_svc = _StubCrossCaseService()

    # Optional dependencies
    research_agent = None
    search_service = None
    try:
        from services.ai_research_agent import AIResearchAgent
        research_agent = AIResearchAgent()
    except Exception:
        pass
    try:
        from services.investigative_search_service import InvestigativeSearchService
        search_service = InvestigativeSearchService(aurora_cm)
    except Exception:
        pass

    return TrawlerEngine(
        aurora_cm=aurora_cm,
        pattern_service=pattern_svc,
        cross_case_service=cross_case_svc,
        research_agent=research_agent,
        search_service=search_service,
        neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT", ""),
        neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
        bedrock_client=bedrock,
    )


def _build_alert_store():
    """Construct a TrawlerAlertStore."""
    from db.connection import ConnectionManager
    from services.trawler_alert_store import TrawlerAlertStore
    return TrawlerAlertStore(ConnectionManager())


# ------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------

def dispatch_handler(event, context):
    """Route trawl/alert requests based on path and method."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response

    method = event.get("httpMethod", "")
    path = event.get("path", "")

    # CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Extract case_id from path: /case-files/{case_id}/...
    case_match = re.match(rf"^/case-files/({_UUID})/", path)
    if not case_match:
        return error_response(404, "NOT_FOUND", "Missing case_id in path", event)
    case_id = case_match.group(1)

    # Inject case_id into pathParameters for handlers
    params = event.get("pathParameters") or {}
    params["id"] = case_id
    event["pathParameters"] = params

    # --- Route: POST /case-files/{id}/trawl ---
    if re.match(rf"^/case-files/{_UUID}/trawl$", path) and method == "POST":
        return run_trawl_handler(event, context)

    # --- Route: GET /case-files/{id}/trawl/briefing ---
    if re.match(rf"^/case-files/{_UUID}/trawl/briefing$", path) and method == "GET":
        return trawl_briefing_handler(event, context)

    # --- Route: GET /case-files/{id}/trawl/impact ---
    if re.match(rf"^/case-files/{_UUID}/trawl/impact$", path) and method == "GET":
        return trawl_impact_handler(event, context)

    # --- Route: GET /case-files/{id}/trawl/evolution ---
    if re.match(rf"^/case-files/{_UUID}/trawl/evolution$", path) and method == "GET":
        return trawl_evolution_handler(event, context)

    # --- Route: GET /case-files/{id}/trawl/history ---
    if re.match(rf"^/case-files/{_UUID}/trawl/history$", path) and method == "GET":
        return scan_history_handler(event, context)

    # --- Route: PUT/GET /case-files/{id}/trawl-config ---
    if re.match(rf"^/case-files/{_UUID}/trawl-config$", path):
        if method == "PUT":
            return trawl_config_handler(event, context)
        if method == "GET":
            return trawl_config_handler(event, context)

    # --- Route: POST /case-files/{id}/alerts/{alert_id}/investigate ---
    alert_investigate_match = re.match(
        rf"^/case-files/{_UUID}/alerts/({_UUID})/investigate$", path
    )
    if alert_investigate_match and method == "POST":
        params["alert_id"] = alert_investigate_match.group(1)
        event["pathParameters"] = params
        return investigate_alert_handler(event, context)

    # --- Route: PATCH /case-files/{id}/alerts/{alert_id} ---
    alert_id_match = re.match(rf"^/case-files/{_UUID}/alerts/({_UUID})$", path)
    if alert_id_match and method == "PATCH":
        params["alert_id"] = alert_id_match.group(1)
        event["pathParameters"] = params
        return update_alert_handler(event, context)

    # --- Route: GET /case-files/{id}/alerts ---
    if re.match(rf"^/case-files/{_UUID}/alerts$", path) and method == "GET":
        return list_alerts_handler(event, context)

    return error_response(404, "NOT_FOUND", f"No trawl handler for {method} {path}", event)


# ------------------------------------------------------------------
# POST /case-files/{id}/trawl
# ------------------------------------------------------------------

def run_trawl_handler(event, context):
    """Trigger a trawl scan for the case. Returns scan summary."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(404, "NOT_FOUND", "Missing case_id", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        targeted_doc_ids = body.get("targeted_doc_ids")

        engine = _build_trawler_engine()
        # Override scan budget to fit within API Gateway 29s timeout.
        # Graph scan + doc scan typically complete in 5-10s.
        # Pattern comparison calls Bedrock (30s+) so it gets skipped by budget.
        import services.trawler_engine as _te
        _te.FULL_SCAN_BUDGET = 18
        _te.TARGETED_SCAN_BUDGET = 10
        summary = engine.run_scan(case_id=case_id, targeted_doc_ids=targeted_doc_ids)

        # Store indicator snapshot for impact tracking
        try:
            snapshot = _compute_indicator_snapshot(case_id)
            if snapshot and summary.get("scan_id"):
                from db.connection import ConnectionManager
                cm = ConnectionManager()
                with cm.cursor() as cur:
                    cur.execute(
                        """UPDATE trawl_scans SET indicator_snapshot = %s::jsonb
                           WHERE scan_id = %s""",
                        (json.dumps(snapshot), summary["scan_id"]),
                    )
        except Exception as snap_exc:
            logger.warning("Failed to store indicator snapshot: %s", str(snap_exc)[:200])

        return success_response(summary, 200, event)
    except Exception as exc:
        logger.exception("run_trawl_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


# ------------------------------------------------------------------
# GET /case-files/{id}/alerts
# ------------------------------------------------------------------

def list_alerts_handler(event, context):
    """List alerts for a case with optional filters."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(404, "NOT_FOUND", "Missing case_id", event)

        params = event.get("queryStringParameters") or {}
        kwargs = {"case_id": case_id}

        if "alert_type" in params:
            kwargs["alert_type"] = params["alert_type"]
        if "severity" in params:
            kwargs["severity"] = params["severity"]
        if "source_type" in params:
            kwargs["source_type"] = params["source_type"]
        if "is_read" in params:
            kwargs["is_read"] = params["is_read"].lower() == "true"
        if "is_dismissed" in params:
            kwargs["is_dismissed"] = params["is_dismissed"].lower() == "true"
        if "limit" in params:
            kwargs["limit"] = min(int(params["limit"]), 100)

        store = _build_alert_store()
        alerts = store.list_alerts(**kwargs)
        return success_response({"alerts": alerts, "total": len(alerts)}, 200, event)
    except Exception as exc:
        logger.exception("list_alerts_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


# ------------------------------------------------------------------
# PATCH /case-files/{id}/alerts/{alert_id}
# ------------------------------------------------------------------

def update_alert_handler(event, context):
    """Update is_read / is_dismissed on an alert."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        alert_id = (event.get("pathParameters") or {}).get("alert_id", "")
        if not alert_id:
            return error_response(404, "NOT_FOUND", "Missing alert_id", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        is_read = body.get("is_read")
        is_dismissed = body.get("is_dismissed")

        store = _build_alert_store()
        result = store.update_alert(
            alert_id=alert_id,
            is_read=is_read,
            is_dismissed=is_dismissed,
        )
        if not result:
            return error_response(404, "NOT_FOUND", f"Alert not found: {alert_id}", event)
        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("update_alert_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


# ------------------------------------------------------------------
# POST /case-files/{id}/alerts/{alert_id}/investigate
# ------------------------------------------------------------------

def investigate_alert_handler(event, context):
    """Mark alert as read and return entity_names + evidence_refs for drill-down."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        alert_id = (event.get("pathParameters") or {}).get("alert_id", "")
        if not alert_id:
            return error_response(404, "NOT_FOUND", "Missing alert_id", event)

        store = _build_alert_store()

        # Mark as read
        store.update_alert(alert_id=alert_id, is_read=True)

        # Fetch full alert
        alert = store.get_alert(alert_id)
        if not alert:
            return error_response(404, "NOT_FOUND", f"Alert not found: {alert_id}", event)

        return success_response({
            "alert_id": alert["alert_id"],
            "alert_type": alert["alert_type"],
            "title": alert["title"],
            "entity_names": alert.get("entity_names", []),
            "evidence_refs": alert.get("evidence_refs", []),
        }, 200, event)
    except Exception as exc:
        logger.exception("investigate_alert_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


# ------------------------------------------------------------------
# GET /case-files/{id}/trawl/history
# ------------------------------------------------------------------

def scan_history_handler(event, context):
    """Return recent scan history for the case."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(404, "NOT_FOUND", "Missing case_id", event)

        params = event.get("queryStringParameters") or {}
        limit = min(int(params.get("limit", 50)), 100)

        store = _build_alert_store()
        scans = store.list_scan_history(case_id=case_id, limit=limit)
        return success_response({"scans": scans, "total": len(scans)}, 200, event)
    except Exception as exc:
        logger.exception("scan_history_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


# ------------------------------------------------------------------
# PUT/GET /case-files/{id}/trawl-config
# ------------------------------------------------------------------

def trawl_config_handler(event, context):
    """Save (PUT) or load (GET) per-case trawl configuration."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(404, "NOT_FOUND", "Missing case_id", event)

        method = event.get("httpMethod", "")
        engine = _build_trawler_engine()

        if method == "PUT":
            body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
            result = engine.save_trawl_config(case_id, body)
            return success_response(result, 200, event)
        else:
            # GET
            config = engine.get_trawl_config(case_id)
            return success_response(config, 200, event)
    except Exception as exc:
        logger.exception("trawl_config_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


# ------------------------------------------------------------------
# Indicator snapshot helper
# ------------------------------------------------------------------

def _compute_indicator_snapshot(case_id: str) -> dict:
    """Compute current Command Center indicator scores for snapshot storage."""
    try:
        from services.command_center_engine import CommandCenterEngine
        from db.connection import ConnectionManager
        import boto3

        aurora_cm = ConnectionManager()
        neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
        neptune_port = os.environ.get("NEPTUNE_PORT", "8182")
        bedrock = boto3.client("bedrock-runtime")

        # Lightweight stubs for services not needed for indicator computation
        class _StubAssessment:
            def get_assessment(self, cid):
                return {"evidence_coverage": {}}
        class _StubWeakness:
            def analyze_weaknesses(self, cid):
                return []
        class _StubInvestigator:
            def get_investigative_leads(self, cid):
                return []

        engine = CommandCenterEngine(
            aurora_cm=aurora_cm,
            bedrock_client=bedrock,
            neptune_endpoint=neptune_ep,
            neptune_port=neptune_port,
            case_assessment_svc=_StubAssessment(),
            case_weakness_svc=_StubWeakness(),
            investigator_engine=_StubInvestigator(),
        )

        graph_case_id = os.environ.get("GRAPH_CASE_ID", "7f05e8d5-4492-4f19-8894-25367606db96")
        data = engine.compute(case_id, bypass_cache=True, graph_case_id=graph_case_id)
        snapshot = {"viability_score": data.get("viability_score", 0)}
        for ind in data.get("indicators", []):
            snapshot[ind["key"]] = ind["score"]
        return snapshot
    except Exception as e:
        logger.warning("_compute_indicator_snapshot failed: %s", str(e)[:300])
        return {}


# ------------------------------------------------------------------
# GET /case-files/{id}/trawl/briefing
# ------------------------------------------------------------------

def trawl_briefing_handler(event, context):
    """Generate an intelligence brief for the case — AI or deterministic fallback."""
    from lambdas.api.response_helper import error_response, success_response
    from datetime import datetime, timezone
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(404, "NOT_FOUND", "Missing case_id", event)

        store = _build_alert_store()

        # Load scan history for impact data (reuse impact logic)
        scans = store.list_scan_history(case_id=case_id, limit=2)
        if len(scans) < 1:
            return error_response(404, "NOT_FOUND", "No scans found for case", event)

        after_scan = scans[0]
        after_snap = after_scan.get("indicator_snapshot") or {}
        before_snap = scans[1].get("indicator_snapshot") or {} if len(scans) >= 2 else {}

        # Load non-dismissed alerts
        alerts = store.list_alerts(case_id, is_dismissed=False)
        alert_count = len(alerts)

        # Compute top 5 entities by frequency
        entity_freq = {}
        for a in alerts:
            for name in (a.get("entity_names") or []):
                entity_freq[name] = entity_freq.get(name, 0) + 1
        top_entities = sorted(entity_freq, key=entity_freq.get, reverse=True)[:5]

        # Build indicator deltas
        indicator_keys = [
            "signal_strength", "corroboration_depth", "network_density",
            "temporal_coherence", "prosecution_readiness",
        ]
        indicator_deltas = {}
        for k in indicator_keys:
            indicator_deltas[k] = {
                "before": before_snap.get(k, 0),
                "after": after_snap.get(k, 0),
            }

        v_before = before_snap.get("viability_score", 0)
        v_after = after_snap.get("viability_score", 0)

        # Attempt Bedrock Claude Haiku with 3-second timeout
        brief_text = None
        source = "fallback"
        try:
            brief_text = _invoke_bedrock_brief(
                alert_count, top_entities, indicator_deltas, v_before, v_after
            )
            if brief_text:
                source = "ai"
        except Exception as bedrock_exc:
            logger.info("Bedrock brief failed (using fallback): %s", str(bedrock_exc)[:200])

        # Fallback brief
        if not brief_text:
            delta_dir = "up" if v_after > v_before else ("down" if v_after < v_before else "unchanged")
            strongest = max(indicator_keys, key=lambda k: after_snap.get(k, 0))
            strongest_label = strongest.replace("_", " ").title()
            strongest_score = after_snap.get(strongest, 0)
            top_3 = ", ".join(top_entities[:3]) if top_entities else "none identified"
            brief_text = (
                f"{alert_count} new findings detected. "
                f"Top entities: {top_3}. "
                f"Viability moved from {v_before} to {v_after} ({delta_dir}). "
                f"{strongest_label} is the strongest signal at {strongest_score}/100."
            )
            source = "fallback"

        return success_response({
            "brief_text": brief_text,
            "top_entities": top_entities,
            "indicator_deltas": indicator_deltas,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "viability_before": v_before,
            "viability_after": v_after,
            "alert_count": alert_count,
            "completed_at": after_scan.get("completed_at"),
        }, 200, event)
    except Exception as exc:
        logger.exception("trawl_briefing_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


def _invoke_bedrock_brief(alert_count, top_entities, indicator_deltas, v_before, v_after):
    """Invoke Claude Haiku with 3s timeout. Returns brief text or None."""
    import boto3
    from botocore.config import Config as BotoConfig

    client = boto3.client(
        "bedrock-runtime",
        config=BotoConfig(
            read_timeout=3,
            connect_timeout=2,
            retries={"max_attempts": 0},
        ),
    )

    entities_str = ", ".join(top_entities) if top_entities else "none"
    deltas_parts = []
    for k, v in indicator_deltas.items():
        label = k.replace("_", " ").title()
        deltas_parts.append(f"{label}: {v['before']}→{v['after']}")

    prompt = (
        "You are a senior intelligence analyst. Write a 3-4 sentence briefing for an investigator.\n"
        f"Alert count: {alert_count}. Top entities: {entities_str}.\n"
        f"Indicator changes: {'; '.join(deltas_parts)}.\n"
        f"Viability score: {v_before} → {v_after}.\n"
        "Cover: what changed since the last scan, which entities matter most, and the recommended next action.\n"
        "Be concise and actionable. Do not use bullet points."
    )

    response = client.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )

    result = json.loads(response["body"].read())
    content = result.get("content", [])
    if content and len(content) > 0:
        return content[0].get("text", "").strip()
    return None


# ------------------------------------------------------------------
# GET /case-files/{id}/trawl/impact
# ------------------------------------------------------------------

def trawl_impact_handler(event, context):
    """Compare indicator snapshots between the two most recent scans."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(404, "NOT_FOUND", "Missing case_id", event)

        store = _build_alert_store()
        scans = store.list_scan_history(case_id=case_id, limit=2)

        if len(scans) < 1:
            return success_response({"impact": None, "message": "No scans found"}, 200, event)

        after_scan = scans[0]
        after_snap = after_scan.get("indicator_snapshot") or {}
        before_snap = scans[1].get("indicator_snapshot") or {} if len(scans) >= 2 else {}

        deltas = {}
        summary_parts = []
        for key in after_snap:
            if key == "viability_score":
                continue
            after_val = after_snap.get(key, 0)
            before_val = before_snap.get(key, 0)
            delta = after_val - before_val
            if delta != 0:
                deltas[key] = delta

        # Build summary string
        v_before = before_snap.get("viability_score", 0)
        v_after = after_snap.get("viability_score", 0)
        v_delta = v_after - v_before
        if v_delta != 0:
            summary_parts.append(f"Viability: {v_before}→{v_after} ({'+' if v_delta > 0 else ''}{v_delta})")

        for key, delta in deltas.items():
            label = key.replace("_", " ").title()
            before_val = before_snap.get(key, 0)
            after_val = after_snap.get(key, 0)
            summary_parts.append(f"{label}: {before_val}→{after_val} ({'+' if delta > 0 else ''}{delta})")

        alerts_gen = after_scan.get("alerts_generated", 0)
        summary = f"{alerts_gen} alerts generated. " + ". ".join(summary_parts) if summary_parts else f"{alerts_gen} alerts generated."

        return success_response({
            "before": before_snap,
            "after": after_snap,
            "deltas": deltas,
            "viability_delta": v_delta,
            "alerts_generated": alerts_gen,
            "summary": summary,
            "scan_id": after_scan.get("scan_id"),
            "completed_at": after_scan.get("completed_at"),
        }, 200, event)
    except Exception as exc:
        logger.exception("trawl_impact_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)


# ------------------------------------------------------------------
# GET /case-files/{id}/trawl/evolution
# ------------------------------------------------------------------

def trawl_evolution_handler(event, context):
    """Return chronological evolution events for the case."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(404, "NOT_FOUND", "Missing case_id", event)

        store = _build_alert_store()
        scans = store.list_scan_history(case_id=case_id, limit=100)

        # Reverse to chronological order (oldest first)
        scans.reverse()

        events = []
        # Add case creation as first event
        from db.connection import ConnectionManager
        try:
            cm = ConnectionManager()
            with cm.cursor() as cur:
                cur.execute(
                    "SELECT created_at FROM case_files WHERE case_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    events.append({
                        "event_type": "case_created",
                        "timestamp": row[0].isoformat(),
                        "alerts_generated": 0,
                        "indicator_snapshot": {},
                        "scan_status": "completed",
                    })
        except Exception:
            pass

        for s in scans:
            events.append({
                "event_type": "trawl_scan",
                "timestamp": s.get("started_at", ""),
                "completed_at": s.get("completed_at"),
                "alerts_generated": s.get("alerts_generated", 0),
                "indicator_snapshot": s.get("indicator_snapshot", {}),
                "scan_status": s.get("scan_status", "unknown"),
                "scan_id": s.get("scan_id"),
                "scan_type": s.get("scan_type", "full"),
            })

        return success_response({"events": events, "total": len(events)}, 200, event)
    except Exception as exc:
        logger.exception("trawl_evolution_handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)
