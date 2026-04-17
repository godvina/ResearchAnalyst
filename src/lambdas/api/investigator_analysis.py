"""API Lambda handler for investigator AI-first analysis.

Endpoints:
    POST /case-files/{id}/investigator-analysis     — trigger AI analysis
    GET  /case-files/{id}/investigator-analysis      — get cached analysis
    GET  /case-files/{id}/investigative-leads        — ranked leads
    GET  /case-files/{id}/evidence-triage            — triage results
    GET  /case-files/{id}/ai-hypotheses              — hypotheses
    GET  /case-files/{id}/subpoena-recommendations   — subpoena recs
    GET  /case-files/{id}/session-briefing           — session briefing
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _parse_body(event):
    """Safely parse the request body, handling both string and dict formats."""
    raw = event.get("body")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def _build_engine():
    import boto3
    from botocore.config import Config
    from db.connection import ConnectionManager
    from services.investigator_ai_engine import InvestigatorAIEngine
    from services.decision_workflow_service import DecisionWorkflowService
    from services.case_assessment_service import CaseAssessmentService
    from services.hypothesis_testing_service import HypothesisTestingService
    from services.pattern_discovery_service import PatternDiscoveryService
    from db.neptune import NeptuneConnectionManager

    aurora_cm = ConnectionManager()
    bedrock_config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"})
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_cm = NeptuneConnectionManager(endpoint=neptune_ep)

    return InvestigatorAIEngine(
        aurora_cm=aurora_cm, bedrock_client=bedrock,
        neptune_endpoint=neptune_ep,
        neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
        opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT", ""),
        case_assessment_svc=CaseAssessmentService(aurora_cm, bedrock, neptune_ep),
        hypothesis_testing_svc=HypothesisTestingService(aurora_cm, bedrock),
        pattern_discovery_svc=PatternDiscoveryService(neptune_cm, aurora_cm, bedrock),
        decision_workflow_svc=DecisionWorkflowService(aurora_cm),
    )


def trigger_analysis(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        engine = _build_engine()
        result = engine.trigger_async_analysis(case_id)
        code = 202 if result.status == "processing" else 200
        return success_response(result.model_dump(mode="json"), code, event)
    except Exception as exc:
        logger.exception("Analysis trigger failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def _build_command_center_engine(aurora_cm, bedrock, neptune_ep, engine):
    """Build a CommandCenterEngine with existing dependencies."""
    from services.command_center_engine import CommandCenterEngine
    from services.case_assessment_service import CaseAssessmentService
    from services.case_weakness_service import CaseWeaknessService
    from db.neptune import NeptuneConnectionManager

    neptune_cm = NeptuneConnectionManager(endpoint=neptune_ep)
    case_assessment_svc = CaseAssessmentService(aurora_cm, bedrock, neptune_ep)
    case_weakness_svc = CaseWeaknessService(aurora_cm, neptune_cm, bedrock)

    return CommandCenterEngine(
        aurora_cm=aurora_cm,
        bedrock_client=bedrock,
        neptune_endpoint=neptune_ep,
        neptune_port=os.environ.get("NEPTUNE_PORT", "8182"),
        case_assessment_svc=case_assessment_svc,
        case_weakness_svc=case_weakness_svc,
        investigator_engine=engine,
    )


def get_analysis(event, context):
    from lambdas.api.response_helper import error_response, success_response
    import time
    t0 = time.time()
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        engine = _build_engine()
        result = engine.get_analysis_status(case_id)
        if not result:
            # No analysis yet — still try to return Command Center data
            response_data = {"status": "no_analysis", "case_id": case_id}
        else:
            response_data = result.model_dump(mode="json")

        # --- Command Center enhancement (time-budgeted) ---
        elapsed = time.time() - t0
        if elapsed < 10:  # Only attempt if we have >19s headroom before 29s API GW timeout
            try:
                params = event.get("queryStringParameters") or {}
                bypass_cache = params.get("bypass_cache", "").lower() == "true"

                # Reuse the engine's aurora_cm and bedrock if available
                aurora_cm = getattr(engine, '_aurora', None)
                bedrock = getattr(engine, '_bedrock', None)
                neptune_ep = getattr(engine, '_neptune_endpoint', os.environ.get("NEPTUNE_ENDPOINT", ""))

                if not aurora_cm or not bedrock:
                    from db.connection import ConnectionManager
                    import boto3
                    from botocore.config import Config
                    aurora_cm = aurora_cm or ConnectionManager()
                    bedrock_config = Config(read_timeout=12, connect_timeout=3, retries={"max_attempts": 1, "mode": "standard"})
                    bedrock = bedrock or boto3.client("bedrock-runtime", config=bedrock_config)

                cc_engine = _build_command_center_engine(aurora_cm, bedrock, neptune_ep, engine)
                # Resolve graph_case_id: combined cases use parent_case_id for Neptune
                graph_case_id = case_id
                try:
                    with aurora_cm.cursor() as cur:
                        cur.execute("SELECT parent_case_id FROM case_files WHERE case_id = %s", (case_id,))
                        row = cur.fetchone()
                        if row and row[0]:
                            graph_case_id = str(row[0])
                            logger.info("Resolved graph_case_id=%s from parent_case_id for case %s", graph_case_id, case_id)
                except Exception:
                    pass  # Fall back to case_id
                # Use Bedrock for strategic assessment — AI-written case narrative
                cc_data = cc_engine.compute(case_id, bypass_cache=bypass_cache, graph_case_id=graph_case_id)
                response_data["command_center"] = cc_data
            except Exception as cc_exc:
                logger.warning("CommandCenterEngine failed for %s (%.1fs elapsed): %s", case_id, time.time() - t0, str(cc_exc)[:300])
        else:
            logger.info("Skipping CommandCenter for %s — %.1fs already elapsed (cold start)", case_id, elapsed)

        return success_response(response_data, 200, event)
    except Exception as exc:
        logger.exception("Get analysis failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def get_leads(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        params = event.get("queryStringParameters") or {}
        min_score = int(params.get("min_score", 0))
        engine = _build_engine()
        leads = engine.get_investigative_leads(case_id, min_score=min_score)
        return success_response({"leads": [l.model_dump(mode="json") for l in leads]}, 200, event)
    except Exception as exc:
        logger.exception("Get leads failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def get_triage(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        params = event.get("queryStringParameters") or {}
        doc_type = params.get("doc_type")
        engine = _build_engine()
        results = engine.get_evidence_triage_results(case_id, doc_type=doc_type)
        return success_response({"triage_results": [r.model_dump(mode="json") for r in results]}, 200, event)
    except Exception as exc:
        logger.exception("Get triage failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def get_hypotheses(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        engine = _build_engine()
        cached = engine.get_cached_analysis(case_id)
        hyps = cached.hypotheses if cached else []
        return success_response({"hypotheses": [h.model_dump(mode="json") for h in hyps]}, 200, event)
    except Exception as exc:
        logger.exception("Get hypotheses failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def get_subpoenas(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        engine = _build_engine()
        cached = engine.get_cached_analysis(case_id)
        recs = cached.subpoena_recommendations if cached else []
        return success_response({"recommendations": [r.model_dump(mode="json") for r in recs]}, 200, event)
    except Exception as exc:
        logger.exception("Get subpoenas failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def get_session_briefing_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        engine = _build_engine()
        briefing = engine.get_session_briefing(case_id)
        return success_response(briefing.model_dump(mode="json"), 200, event)
    except Exception as exc:
        logger.exception("Session briefing failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def async_analysis_handler(event, context):
    """Entry point for async Lambda self-invoke. Not an API Gateway handler."""
    try:
        case_id = event.get("case_id", "")
        if not case_id:
            logger.error("async_analysis_handler: missing case_id")
            return {"status": "error", "error_message": "Missing case_id"}
        engine = _build_engine()
        return engine.run_async_analysis(case_id)
    except Exception as exc:
        logger.exception("async_analysis_handler failed")
        return {"status": "error", "error_message": str(exc)[:500]}


def entity_neighborhood_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        params = event.get("queryStringParameters") or {}
        entity_name = params.get("entity_name", "")
        if not entity_name:
            return error_response(400, "VALIDATION_ERROR", "Missing entity_name parameter", event)
        hops = int(params.get("hops", 2))
        if hops < 1 or hops > 3:
            return error_response(400, "VALIDATION_ERROR", "hops must be 1–3", event)
        engine = _build_engine()
        result = engine.get_entity_neighborhood(case_id, entity_name, hops)
        return success_response(result, 200, event)
    except ValueError:
        return error_response(400, "VALIDATION_ERROR", "hops must be an integer 1–3", event)
    except Exception as exc:
        logger.exception("Entity neighborhood failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ── Geospatial Evidence Map handlers ──────────────────────────────────


def geocode_handler(event, context):
    """POST /case-files/{id}/geocode — resolve location names to coordinates."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        body = _parse_body(event)
        locations = body.get("locations", [])
        if not isinstance(locations, list):
            return error_response(400, "VALIDATION_ERROR", "locations must be a list", event)

        from services.geocoding_service import GeocodingService
        svc = GeocodingService()
        result = svc.geocode(locations)

        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("Geocode handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def location_detail_handler(event, context):
    """POST /case-files/{id}/map/location-detail — drill-down data for a location."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        body = _parse_body(event)
        location_name = body.get("location_name", "").strip()
        if not location_name:
            return error_response(400, "VALIDATION_ERROR", "Missing location_name", event)

        engine = _build_engine()
        result = engine.get_location_detail(case_id, location_name)
        if result is None:
            return error_response(404, "LOCATION_NOT_FOUND",
                                  f"No location entity '{location_name}' in case", event)
        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("Location detail handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def ai_map_analysis_handler(event, context):
    """POST /case-files/{id}/map/ai-analysis — AI geographic insights."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)
        body = _parse_body(event)
        locations_data = body.get("locations", [])
        if not locations_data:
            return error_response(400, "VALIDATION_ERROR", "locations list is empty", event)

        engine = _build_engine()
        result = engine.analyze_geography(case_id, locations_data)
        return success_response({"analysis": result}, 200, event)
    except Exception as exc:
        err_str = str(exc).lower()
        if "timeout" in err_str or "timed out" in err_str:
            return error_response(504, "AI_ANALYSIS_TIMEOUT",
                                  "AI analysis timed out — please retry", event)
        if "throttl" in err_str or "rate" in err_str:
            return error_response(429, "AI_THROTTLED",
                                  "AI service throttled — please retry shortly", event)
        logger.exception("AI map analysis failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def cross_case_locations_handler(event, context):
    """POST /map/cross-case-locations — locations shared across cases."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        body = _parse_body(event)
        case_id = body.get("case_file_id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case_file_id", event)

        from db.connection import ConnectionManager
        from services.geocoding_service import GeocodingService
        aurora_cm = ConnectionManager()
        svc = GeocodingService()
        results = svc.cross_case_locations(case_id, aurora_cm)
        return success_response({
            "cross_case_locations": results,
            "total": len(results),
        }, 200, event)
    except Exception as exc:
        logger.exception("Cross-case locations failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def entity_leads_handler(event, context):
    """POST /case-files/{id}/entity-leads — generate investigation leads for an entity."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = _parse_body(event)
        entity_name = body.get("entity_name", "").strip() if body.get("entity_name") else ""
        if not entity_name:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: entity_name", event)

        entity_type = body.get("entity_type", "unknown") or "unknown"
        neighbors = body.get("neighbors") or []
        doc_excerpts = body.get("doc_excerpts") or []

        # Build dependencies
        import boto3
        from botocore.config import Config
        from db.connection import ConnectionManager
        from services.lead_generator_service import LeadGeneratorService

        aurora_cm = ConnectionManager()
        bedrock_config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"})
        bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
        neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
        neptune_port = os.environ.get("NEPTUNE_PORT", "8182")

        svc = LeadGeneratorService(
            aurora_cm=aurora_cm,
            bedrock_client=bedrock,
            neptune_endpoint=neptune_ep,
            neptune_port=neptune_port,
        )
        leads = svc.generate_leads(
            case_id=case_id,
            entity_name=entity_name,
            entity_type=entity_type,
            neighbors=neighbors,
            doc_excerpts=doc_excerpts,
        )
        return success_response({"leads": [lead.to_dict() for lead in leads]}, 200, event)
    except Exception as exc:
        logger.exception("Entity leads handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def evidence_thread_handler(event, context):
    """POST /case-files/{id}/evidence-thread — assemble evidence thread for a lead."""
    from dataclasses import asdict
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = _parse_body(event)
        required_fields = ["lead_id", "entity_names", "lead_type", "narrative"]
        missing = [f for f in required_fields if not body.get(f)]
        if missing:
            return error_response(
                400, "VALIDATION_ERROR",
                f"Missing required field(s): {', '.join(missing)}", event,
            )

        lead_id = body["lead_id"]
        entity_names = body["entity_names"]
        lead_type = body["lead_type"]
        narrative = body["narrative"]

        # Build dependencies
        from db.connection import ConnectionManager
        from services.evidence_assembler_service import EvidenceAssemblerService

        aurora_cm = ConnectionManager()
        neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
        neptune_port = os.environ.get("NEPTUNE_PORT", "8182")

        svc = EvidenceAssemblerService(
            aurora_cm=aurora_cm,
            neptune_endpoint=neptune_ep,
            neptune_port=neptune_port,
        )
        thread = svc.assemble_evidence(
            case_id=case_id,
            lead_id=lead_id,
            entity_names=entity_names,
            lead_type=lead_type,
            narrative=narrative,
        )
        return success_response(asdict(thread), 200, event)
    except Exception as exc:
        logger.exception("Evidence thread handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def _build_discovery_engine():
    """Construct a DiscoveryEngineService with all dependencies."""
    import boto3
    from botocore.config import Config
    from db.connection import ConnectionManager
    from db.neptune import NeptuneConnectionManager
    from services.discovery_engine_service import DiscoveryEngineService
    from services.pattern_discovery_service import PatternDiscoveryService
    from services.investigator_ai_engine import InvestigatorAIEngine

    aurora_cm = ConnectionManager()
    bedrock_config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"})
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")
    neptune_cm = NeptuneConnectionManager(endpoint=neptune_ep)

    pattern_svc = PatternDiscoveryService(neptune_cm, aurora_cm, bedrock)
    ai_engine = InvestigatorAIEngine(
        aurora_cm=aurora_cm, bedrock_client=bedrock,
        neptune_endpoint=neptune_ep, neptune_port=neptune_port,
        opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT", ""),
    )

    return DiscoveryEngineService(
        aurora_cm=aurora_cm,
        bedrock_client=bedrock,
        neptune_endpoint=neptune_ep,
        neptune_port=neptune_port,
        pattern_svc=pattern_svc,
        ai_engine=ai_engine,
    )


def _build_anomaly_service():
    """Construct an AnomalyDetectionService with all dependencies."""
    from db.connection import ConnectionManager
    from services.anomaly_detection_service import AnomalyDetectionService

    aurora_cm = ConnectionManager()
    neptune_ep = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")

    return AnomalyDetectionService(
        aurora_cm=aurora_cm,
        neptune_endpoint=neptune_ep,
        neptune_port=neptune_port,
    )


def discoveries_handler(event, context):
    """POST /case-files/{id}/discoveries — generate a batch of Did You Know discoveries."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = _parse_body(event)
        user_id = body.get("user_id", "investigator")
        model_id = body.get("model_id")

        svc = _build_discovery_engine()
        batch = svc.generate_discoveries(case_id=case_id, user_id=user_id, model_id=model_id)
        return success_response(batch.to_dict(), 200, event)
    except Exception as exc:
        logger.exception("Discoveries handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def discovery_feedback_handler(event, context):
    """POST /case-files/{id}/discoveries/feedback — submit thumbs-up/down feedback."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = _parse_body(event)
        required_fields = ["discovery_id", "rating", "discovery_type", "content_hash"]
        missing = [f for f in required_fields if f not in body]
        if missing:
            return error_response(
                400, "VALIDATION_ERROR",
                f"Missing required field(s): {', '.join(missing)}", event,
            )

        rating = body["rating"]
        if rating not in (1, -1):
            return error_response(400, "VALIDATION_ERROR", "rating must be 1 or -1", event)

        svc = _build_discovery_engine()
        result = svc.submit_feedback(
            case_id=case_id,
            user_id=body.get("user_id", "investigator"),
            discovery_id=body["discovery_id"],
            rating=rating,
            discovery_type=body["discovery_type"],
            content_hash=body["content_hash"],
        )
        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("Discovery feedback handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def anomalies_handler(event, context):
    """GET /case-files/{id}/anomalies — detect statistical anomalies for a case."""
    from lambdas.api.response_helper import error_response, success_response
    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        svc = _build_anomaly_service()
        report = svc.detect_anomalies(case_id)
        result = report.to_dict()

        # Limit response size to avoid Lambda 6MB payload limit
        if "anomalies" in result and len(result["anomalies"]) > 20:
            result["anomalies"] = result["anomalies"][:20]
            result["truncated"] = True
        # Trim entity lists within each anomaly
        for a in result.get("anomalies", []):
            if "entities" in a and len(a["entities"]) > 10:
                a["entities"] = a["entities"][:10]
            if "evidence" in a and len(a["evidence"]) > 5:
                a["evidence"] = a["evidence"][:5]

        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("Anomalies handler failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def dispatch_handler(event, context):
    from lambdas.api.response_helper import error_response
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    routes = {
        ("POST", "/case-files/{id}/investigator-analysis"): trigger_analysis,
        ("GET", "/case-files/{id}/investigator-analysis"): get_analysis,
        ("GET", "/case-files/{id}/investigative-leads"): get_leads,
        ("GET", "/case-files/{id}/evidence-triage"): get_triage,
        ("GET", "/case-files/{id}/ai-hypotheses"): get_hypotheses,
        ("GET", "/case-files/{id}/subpoena-recommendations"): get_subpoenas,
        ("GET", "/case-files/{id}/session-briefing"): get_session_briefing_handler,
        ("GET", "/case-files/{id}/entity-neighborhood"): entity_neighborhood_handler,
        ("POST", "/case-files/{id}/geocode"): geocode_handler,
        ("POST", "/case-files/{id}/map/location-detail"): location_detail_handler,
        ("POST", "/case-files/{id}/map/ai-analysis"): ai_map_analysis_handler,
        ("POST", "/map/cross-case-locations"): cross_case_locations_handler,
        ("POST", "/case-files/{id}/entity-leads"): entity_leads_handler,
        ("POST", "/case-files/{id}/evidence-thread"): evidence_thread_handler,
        ("POST", "/case-files/{id}/discoveries"): discoveries_handler,
        ("POST", "/case-files/{id}/discoveries/feedback"): discovery_feedback_handler,
        ("GET", "/case-files/{id}/anomalies"): anomalies_handler,
    }
    handler = routes.get((method, resource))
    if handler:
        return handler(event, context)
    return error_response(404, "NOT_FOUND", f"Unknown route: {method} {resource}", event)
