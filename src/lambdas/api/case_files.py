"""Consolidated API Lambda dispatcher.

All API routes (except /case-files/{id}/ingest) are routed through this
single Lambda to stay under the CloudFormation 500-resource limit.
Routing is based on event["path"] since API Gateway uses {proxy+} resources.
"""

import json
import logging
import os
from typing import Optional
import re
from datetime import datetime, timezone

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Pre-compiled path patterns for efficient routing
_UUID = r"[0-9a-f\-]+"


def _normalize_resource(event, path):
    """Reconstruct event['resource'] from the actual path for sub-dispatchers.

    When API Gateway uses {proxy+}, the resource field is generic (e.g.
    /case-files/{id}/{proxy+}). Sub-dispatchers expect specific resource
    templates like /case-files/{id}/patterns. This function converts the
    concrete path back to the template form.

    Also populates event['pathParameters'] with extracted IDs so that
    sub-handlers can use event['pathParameters']['id'] etc.
    """
    parts = path.strip("/").split("/")
    template_parts = []
    extracted_params = dict(event.get("pathParameters") or {})
    for i, part in enumerate(parts):
        if re.match(rf"^{_UUID}$", part):
            # Determine the right template variable based on context
            if i == 1 and parts[0] in ("case-files", "decisions", "matters", "documents"):
                template_parts.append("{id}")
                extracted_params["id"] = part
            elif i == 1 and parts[0] == "triage-queue":
                template_parts.append("{docId}")
                extracted_params["docId"] = part
            elif i == 2 and parts[0] == "admin" and parts[1] == "users":
                template_parts.append("{id}")
                extracted_params["id"] = part
            elif i == 2 and parts[0] == "portfolio" and parts[1] == "cases":
                template_parts.append("{id}")
                extracted_params["id"] = part
            elif i == 2 and parts[0] == "cross-case" and parts[1] == "graphs":
                template_parts.append("{id}")
                extracted_params["id"] = part
            elif i == 2 and parts[0] == "wizard" and parts[1] == "load-progress":
                template_parts.append("{id}")
                extracted_params["id"] = part
            elif i == 3 and parts[2] == "documents":
                template_parts.append("{doc_id}")
                extracted_params["doc_id"] = part
                extracted_params["docId"] = part
            elif i == 3 and parts[2] == "alerts":
                template_parts.append("{alert_id}")
                extracted_params["alert_id"] = part
            elif i == 3 and parts[2] == "theories":
                template_parts.append("{theory_id}")
                extracted_params["theory_id"] = part
            elif i == 3 and parts[2] == "persons-of-interest":
                template_parts.append("{pid}")
                extracted_params["pid"] = part
            elif i == 3 and parts[2] in ("sample-runs", "pipeline-runs"):
                template_parts.append("{run_id}")
                extracted_params["run_id"] = part
            elif i == 3 and parts[2] == "batch-loader" and parts[1] == "manifests":
                template_parts.append("{batch_id}")
                extracted_params["batch_id"] = part
            elif i == 4 and parts[3] == "versions":
                template_parts.append("{v}")
                extracted_params["v"] = part
            elif i == 5 and parts[4] == "steps":
                template_parts.append("{step}")
                extracted_params["step"] = part
            else:
                template_parts.append("{id}")
                extracted_params.setdefault("id", part)
        else:
            template_parts.append(part)

    event["resource"] = "/" + "/".join(template_parts)
    event["pathParameters"] = extracted_params

    # Handle non-UUID path parameters (e.g., /leads/{lead_id}/status)
    if len(parts) >= 2 and parts[0] == "leads" and parts[1] != "ingest":
        extracted_params["lead_id"] = parts[1]

    # Handle section_index for theory case-file section updates:
    # /case-files/{id}/theories/{tid}/case-file/sections/{idx}
    if (len(parts) == 7 and parts[0] == "case-files" and parts[2] == "theories"
            and parts[4] == "case-file" and parts[5] == "sections"):
        section_idx = parts[6]
        extracted_params["section_index"] = section_idx
        # Rewrite the resource template to use {section_index} placeholder
        event["resource"] = "/" + "/".join(template_parts[:6]) + "/{section_index}"


@with_access_control
def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and request path.

    Uses event['path'] for routing since API Gateway {proxy+} resources
    don't provide specific resource templates.
    """
    from lambdas.api.response_helper import CORS_HEADERS, error_response
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Handle async worker invocations (no HTTP context) — route directly
    # to batch_loader_handler before access control runs on sub-dispatchers
    if event.get("action") in ("process_batch", "extract_zip"):
        from lambdas.api.batch_loader_handler import dispatch_handler as bl_dispatch
        return bl_dispatch(event, context)

    # Handle async analysis invocations (no HTTP context)
    if event.get("action") == "async_analysis":
        from lambdas.api.investigator_analysis import async_analysis_handler
        return async_analysis_handler(event, context)

    # Handle Neptune → Aurora entity sync (no HTTP context)
    if event.get("action") == "sync_neptune_to_aurora":
        from lambdas.api.neptune_aurora_sync import handler as sync_handler
        return sync_handler(event, context)

    # Handle refresh_case_stats (direct invoke or POST body action)
    if event.get("action") == "refresh_case_stats":
        return _refresh_case_stats_handler(event, context)

    # Handle update_case_name (direct invoke)
    if event.get("action") == "update_case_name":
        return _update_case_name_handler(event, context)

    # Handle batch_insert_documents (direct invoke — HuggingFace/bulk text loader)
    if event.get("action") == "batch_insert_documents":
        return _batch_insert_documents_handler(event, context)

    # Handle embedding backfill (direct invoke)
    if event.get("action") == "backfill_embeddings_count":
        return _backfill_embeddings_count(event, context)
    if event.get("action") == "backfill_embeddings_batch":
        return _backfill_embeddings_batch(event, context)
    if event.get("action") == "backfill_entities_count":
        return _backfill_entities_count(event, context)
    if event.get("action") == "backfill_entities_batch":
        return _backfill_entities_batch(event, context)
    if event.get("action") == "cleanup_noise_entities":
        return _cleanup_noise_entities(event, context)
    if event.get("action") == "insert_entities":
        return _insert_entities_handler(event, context)
    if event.get("action") == "gremlin_query":
        return _gremlin_query_handler(event, context)
    if event.get("action") == "query_aurora_entities":
        return _query_aurora_entities(event, context)

    # Normalize: when using {proxy+}, sub-dispatchers expect event["resource"]
    # to contain the specific resource template. We reconstruct it from the path.
    _normalize_resource(event, path)

    # --- Pipeline Config routes ---
    if "/pipeline-config" in path or "/sample-runs" in path or "/pipeline-runs" in path:
        from lambdas.api.pipeline_config import dispatch_handler as pc_dispatch
        return pc_dispatch(event, context)

    # --- System default config ---
    if path.startswith("/system/"):
        from lambdas.api.pipeline_config import dispatch_handler as pc_dispatch
        return pc_dispatch(event, context)

    # --- Triage queue ---
    if path.startswith("/triage-queue"):
        from lambdas.api.pipeline_config import dispatch_handler as pc_dispatch
        return pc_dispatch(event, context)

    # --- Research Chat routes (must be before /chat catch-all) ---
    if "/research/chat" in path and "/case-files/" in path and method == "POST":
        from lambdas.api.research_chat import research_chat_handler
        return research_chat_handler(event, context)

    # --- Chat routes ---
    if "/chat" in path:
        from lambdas.api.chat import dispatch_handler as chat_dispatch
        return chat_dispatch(event, context)

    # --- Assessment routes ---
    if "/assessment" in path:
        from lambdas.api.assessment import dispatch_handler as assess_dispatch
        return assess_dispatch(event, context)

    # --- Wizard routes ---
    if path.startswith("/wizard/"):
        from lambdas.api.wizard import dispatch_handler as wiz_dispatch
        return wiz_dispatch(event, context)

    # --- Portfolio routes ---
    if path.startswith("/portfolio/"):
        from lambdas.api.portfolio import dispatch_handler as port_dispatch
        return port_dispatch(event, context)

    # --- Workbench routes ---
    if path.startswith("/workbench/"):
        from lambdas.api.workbench import dispatch_handler as wb_dispatch
        return wb_dispatch(event, context)

    # --- Deployment routes ---
    if path.startswith("/deployment/"):
        from lambdas.api.deployment_handler import dispatch_handler as dep_dispatch
        return dep_dispatch(event, context)

    # --- Batch Loader routes ---
    if path.startswith("/batch-loader/"):
        from lambdas.api.batch_loader_handler import dispatch_handler as bl_dispatch
        return bl_dispatch(event, context)

    # --- Organization & Matter routes ---
    if path.startswith("/organizations"):
        # Check if this is a matters sub-route: /organizations/{id}/matters
        if "/matters" in path:
            # Fix resource template — matters handler expects {org_id} not {id}
            params = event.get("pathParameters") or {}
            if "id" in params and "org_id" not in params:
                params["org_id"] = params["id"]
                event["pathParameters"] = params
            # Fix resource template
            event["resource"] = event.get("resource", "").replace("{id}/matters", "{org_id}/matters")
            from lambdas.api.matters import dispatch_handler as mat_dispatch
            return mat_dispatch(event, context)
        from lambdas.api.organizations import dispatch_handler as org_dispatch
        return org_dispatch(event, context)
    if path.startswith("/matters"):
        from lambdas.api.matters import dispatch_handler as mat_dispatch
        return mat_dispatch(event, context)

    # --- Ingest route (consolidated from ingestion Lambda) ---
    if path.endswith("/ingest") and "/case-files/" in path and method == "POST":
        from lambdas.api.ingestion import ingest_handler
        return ingest_handler(event, context)

    # --- Admin SQL migration (temporary) ---
    if path == "/admin/run-migration" and method == "POST":
        return _run_admin_migration(event, context)

    # --- Access Control Admin routes ---
    if path.startswith("/admin/"):
        from lambdas.api.access_control_admin import dispatch_handler as ac_dispatch
        return ac_dispatch(event, context)

    # --- Statutes ---
    if path == "/statutes" and method == "GET":
        from lambdas.api.statutes import dispatch_handler as stat_dispatch
        return stat_dispatch(event, context)

    # --- Security label routes ---
    if "/security-label" in path:
        from lambdas.api.access_control_admin import dispatch_handler as ac_dispatch
        return ac_dispatch(event, context)

    # --- Lead routes ---
    if path.startswith("/leads/"):
        from lambdas.api.leads import handle_ingest, handle_lead_status
        if path == "/leads/ingest" and method == "POST":
            return handle_ingest(event, context)
        if path.endswith("/status") and method == "GET":
            return handle_lead_status(event, context)

    # --- Matter lead metadata ---
    if path.endswith("/lead") and "/matters/" in path and method == "GET":
        from lambdas.api.leads import handle_matter_lead
        return handle_matter_lead(event, context)

    # --- Cross-case routes ---
    if path.startswith("/cross-case/"):
        from lambdas.api.cross_case import analyze_handler
        return analyze_handler(event, context)

    # --- Decisions routes ---
    if path.startswith("/decisions/"):
        from lambdas.api.decision_workflow import dispatch_handler as dw_dispatch
        return dw_dispatch(event, context)

    # --- Case file sub-resource routes (under /case-files/{id}/...) ---
    # These use event["resource"] when available, falling back to path matching
    resource = event.get("resource", "")

    # Top Patterns (must be before /patterns catch-all)
    if "/top-patterns" in path and "/case-files/" in path:
        from lambdas.api.patterns import top_patterns_handler
        # Extract pattern_index for evidence endpoint:
        # /case-files/{id}/top-patterns/{idx}/evidence
        tp_match = re.match(rf"^/case-files/{_UUID}/top-patterns/(\d+)/evidence$", path)
        if tp_match:
            params = event.get("pathParameters") or {}
            params["pattern_index"] = tp_match.group(1)
            event["pathParameters"] = params
        return top_patterns_handler(event, context)

    # Timeline (must be before /patterns catch-all)
    if "/timeline" in path and "/case-files/" in path:
        from lambdas.api.timeline_handler import dispatch_handler as tl_dispatch
        return tl_dispatch(event, context)

    # Patterns
    if resource == "/case-files/{id}/patterns" or "/patterns" in path:
        if method in ("POST", "GET"):
            from lambdas.api.patterns import discover_patterns_handler
            return discover_patterns_handler(event, context)

    # Search
    if resource == "/case-files/{id}/search" or (path.endswith("/search") and "/case-files/" in path):
        if method == "POST":
            from lambdas.api.search import search_handler
            return search_handler(event, context)

    # Drill-down
    if resource == "/case-files/{id}/drill-down" or (path.endswith("/drill-down") and "/case-files/" in path):
        if method == "POST":
            from lambdas.api.drill_down import drill_down_handler
            return drill_down_handler(event, context)

    # Pipeline status
    if resource == "/case-files/{id}/pipeline-status" or (path.endswith("/pipeline-status") and "/case-files/" in path):
        if method == "GET":
            from lambdas.api.pipeline_status import handler as status_handler
            return status_handler(event, context)

    # Entity Resolution
    if resource == "/case-files/{id}/entity-resolution" or (path.endswith("/entity-resolution") and "/case-files/" in path):
        if method == "POST":
            return entity_resolution_handler(event, context)

    # --- Theory-Driven Investigation routes ---
    if "/theories" in path and "/case-files/" in path:
        from lambdas.api.theory_handler import dispatch_handler as theory_dispatch
        return theory_dispatch(event, context)

    # Investigator AI-First routes
    if any(seg in path for seg in ("/investigator-analysis", "/investigative-leads", "/evidence-triage",
                                    "/ai-hypotheses", "/subpoena-recommendations", "/session-briefing",
                                    "/entity-neighborhood", "/geocode", "/map/",
                                    "/entity-leads", "/evidence-thread",
                                    "/discoveries", "/anomalies")):
        from lambdas.api.investigator_analysis import dispatch_handler as inv_dispatch
        return inv_dispatch(event, context)

    # Cross-case locations (top-level, not under /case-files/)
    if path == "/map/cross-case-locations" and method == "POST":
        from lambdas.api.investigator_analysis import cross_case_locations_handler
        return cross_case_locations_handler(event, context)

    # Network Discovery routes
    if any(seg in path for seg in ("/network-analysis", "/persons-of-interest", "/sub-cases", "/network-patterns")):
        from lambdas.api.network_discovery import dispatch_handler as net_dispatch
        return net_dispatch(event, context)

    # Document Images (must be before Document Assembly catch-all)
    if "/documents/" in path and path.endswith("/images") and "/case-files/" in path:
        if method == "GET":
            return document_images_handler(event, context)

    # Document Assembly routes
    if any(seg in path for seg in ("/documents/generate", "/documents/", "/discovery")):
        if "/case-files/" in path:
            from lambdas.api.document_assembly import dispatch_handler as doc_dispatch
            return doc_dispatch(event, context)

    # Decision Workflow / Prosecutor routes
    if any(seg in path for seg in ("/decisions", "/element-assessment", "/charging-memo",
                                    "/case-weaknesses", "/precedent-analysis")):
        if "/case-files/" in path:
            from lambdas.api.decision_workflow import dispatch_handler as dw_dispatch
            return dw_dispatch(event, context)

    # Question-Answer (progressive intelligence drilldown)
    if resource == "/case-files/{id}/question-answer" or (path.endswith("/question-answer") and "/case-files/" in path):
        if method == "POST":
            from lambdas.api.question_answer import question_answer_handler
            return question_answer_handler(event, context)

    # AI Investigative Search
    if path.endswith("/investigative-search") and "/case-files/" in path and method == "POST":
        from lambdas.api.investigative_search import investigative_search_handler
        return investigative_search_handler(event, context)

    # Lead Assessment
    if "/lead-assessment" in path and "/case-files/" in path:
        if method == "POST" and path.endswith("/lead-assessment"):
            from lambdas.api.investigative_search import lead_assessment_handler
            return lead_assessment_handler(event, context)

    # Investigation Findings (Research Notebook)
    if "/findings" in path and "/case-files/" in path:
        from lambdas.api import findings as findings_mod
        if method == "POST" and path.endswith("/findings"):
            return findings_mod.save_finding_handler(event, context)
        if method == "GET" and path.endswith("/findings"):
            return findings_mod.list_findings_handler(event, context)
        if method == "PUT" and "/findings/" in path:
            return findings_mod.update_finding_handler(event, context)
        if method == "DELETE" and "/findings/" in path:
            return findings_mod.delete_finding_handler(event, context)

    # --- OSINT Research routes ---
    if "/osint-research" in path and "/case-files/" in path:
        from lambdas.api.osint_handler import research_handler, list_cache_handler
        if method == "POST":
            return research_handler(event, context)
        elif method == "GET":
            return list_cache_handler(event, context)

    # Trawler / Alert routes
    if any(seg in path for seg in ("/trawl", "/alerts")):
        if "/case-files/" in path:
            from lambdas.api.trawl import dispatch_handler as trawl_dispatch
            return trawl_dispatch(event, context)

    # Entity Photos
    if path.endswith("/entity-photos") and "/case-files/" in path and method == "GET":
        return entity_photos_handler(event, context)

    # Image Evidence Gallery
    if path.endswith("/image-evidence") and "/case-files/" in path and method == "GET":
        return image_evidence_handler(event, context)

    # Video Evidence
    if path.endswith("/video-evidence") and "/case-files/" in path and method == "GET":
        return video_evidence_handler(event, context)

    # Evidence Analyze
    if path.endswith("/evidence-analyze") and "/case-files/" in path and method == "POST":
        return evidence_analyze_handler(event, context)

    # Refresh Case Stats (POST /case-files/{id}/refresh-stats)
    if path.endswith("/refresh-stats") and "/case-files/" in path and method == "POST":
        params = event.get("pathParameters") or {}
        return _refresh_case_stats_handler({"action": "refresh_case_stats", "case_id": params.get("id")}, context)

    # Archive
    if path.endswith("/archive") and "/case-files/" in path and method == "POST":
        return archive_case_file_handler(event, context)

    # Document download
    if "/documents/" in path and "/download" in path and "/case-files/" in path:
        return get_document_download_url_handler(event, context)

    # Case file CRUD (must be last — catch-all for /case-files and /case-files/{id})
    if path == "/case-files" and method == "POST":
        return create_case_file_handler(event, context)
    if path == "/case-files" and method == "GET":
        return list_case_files_handler(event, context)
    if re.match(rf"^/case-files/{_UUID}$", path):
        if method == "GET":
            return get_case_file_handler(event, context)
        if method == "DELETE":
            return delete_case_file_handler(event, context)

    return error_response(404, "NOT_FOUND", f"No handler for {method} {path}", event)


# ------------------------------------------------------------------
# ACTION: update_case_name
# ------------------------------------------------------------------

def _update_case_name_handler(event, context):
    """Update the topic_name and optionally search_tier of a case."""
    from lambdas.api.response_helper import error_response, success_response
    from db.connection import ConnectionManager

    case_id = event.get("case_id")
    new_name = event.get("new_name")
    new_tier = event.get("search_tier")  # optional: "standard" or "enterprise"
    if not case_id:
        return error_response(400, "MISSING_PARAM", "case_id is required", event)

    cm = ConnectionManager()
    try:
        with cm.cursor() as cur:
            if new_name:
                cur.execute("UPDATE case_files SET topic_name = %s WHERE case_id = %s", (new_name, case_id))
                try:
                    cur.execute("SAVEPOINT matters_rename")
                    cur.execute("UPDATE matters SET matter_name = %s WHERE matter_id = %s", (new_name, case_id))
                    cur.execute("RELEASE SAVEPOINT matters_rename")
                except Exception:
                    cur.execute("ROLLBACK TO SAVEPOINT matters_rename")
            if new_tier in ("standard", "enterprise"):
                cur.execute("UPDATE case_files SET search_tier = %s WHERE case_id = %s", (new_tier, case_id))
                try:
                    cur.execute("SAVEPOINT matters_tier")
                    cur.execute("UPDATE matters SET search_tier = %s WHERE matter_id = %s", (new_tier, case_id))
                    cur.execute("RELEASE SAVEPOINT matters_tier")
                except Exception:
                    cur.execute("ROLLBACK TO SAVEPOINT matters_tier")
    except Exception as exc:
        return error_response(500, "UPDATE_FAILED", str(exc)[:200], event)

    result = {"case_id": case_id}
    if new_name:
        result["new_name"] = new_name
    if new_tier:
        result["search_tier"] = new_tier
    return success_response(result, event=event)


# ------------------------------------------------------------------
# ACTION: refresh_case_stats
# ------------------------------------------------------------------

def _refresh_case_stats_handler(event, context):
    """Recalculate and persist document/entity/relationship counts for a case.

    Callable via:
      - Direct invoke: {"action": "refresh_case_stats", "case_id": "..."}
      - HTTP POST:     POST /case-files/{id}/refresh-stats
    """
    from lambdas.api.response_helper import error_response, success_response
    from db.connection import ConnectionManager

    case_id = event.get("case_id")
    if not case_id:
        return error_response(400, "MISSING_PARAM", "case_id is required", event)

    logger.info("refresh_case_stats: recalculating counts for case_id=%s", case_id)

    cm = ConnectionManager()
    document_count = 0
    entity_count = 0
    relationship_count = 0

    try:
        with cm.cursor() as cur:
            # Count documents
            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE case_file_id = %s",
                (case_id,),
            )
            row = cur.fetchone()
            document_count = row[0] if row else 0
            logger.info("refresh_case_stats: document_count=%d for case_id=%s", document_count, case_id)

            # Count entities
            cur.execute(
                "SELECT COUNT(*) FROM entities WHERE case_file_id = %s",
                (case_id,),
            )
            row = cur.fetchone()
            entity_count = row[0] if row else 0
            logger.info("refresh_case_stats: entity_count=%d for case_id=%s", entity_count, case_id)

            # Count relationships (table may not exist in older deployments)
            try:
                cur.execute("SAVEPOINT rel_check")
                cur.execute(
                    "SELECT COUNT(*) FROM relationships WHERE case_file_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                relationship_count = row[0] if row else 0
                cur.execute("RELEASE SAVEPOINT rel_check")
                logger.info("refresh_case_stats: relationship_count=%d for case_id=%s", relationship_count, case_id)
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT rel_check")
                logger.warning("refresh_case_stats: relationships table query failed (may not exist): %s", str(exc)[:200])
                relationship_count = 0

            # Update case_files table
            cur.execute(
                "UPDATE case_files SET document_count = %s, entity_count = %s, relationship_count = %s, last_activity = now() WHERE case_id = %s",
                (document_count, entity_count, relationship_count, case_id),
            )
            logger.info("refresh_case_stats: updated case_files for case_id=%s", case_id)

            # Also try updating matters table if it exists
            try:
                cur.execute("SAVEPOINT matters_update")
                cur.execute(
                    "UPDATE matters SET total_documents = %s, total_entities = %s, total_relationships = %s WHERE matter_id = %s",
                    (document_count, entity_count, relationship_count, case_id),
                )
                cur.execute("RELEASE SAVEPOINT matters_update")
                logger.info("refresh_case_stats: updated matters for case_id=%s", case_id)
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT matters_update")
                logger.warning("refresh_case_stats: matters table update failed (may not exist): %s", str(exc)[:200])

    except Exception as exc:
        logger.error("refresh_case_stats: failed for case_id=%s: %s", case_id, str(exc)[:500])
        return error_response(500, "REFRESH_FAILED", f"Failed to refresh case stats: {str(exc)[:200]}", event)

    result = {
        "case_id": case_id,
        "document_count": document_count,
        "entity_count": entity_count,
        "relationship_count": relationship_count,
    }
    logger.info("refresh_case_stats: complete — %s", result)
    return success_response(result, event=event)


# ------------------------------------------------------------------
# ACTION: batch_insert_documents
# ------------------------------------------------------------------

def _batch_insert_documents_handler(event, context):
    """Insert pre-processed text documents directly into Aurora.

    Bypasses Step Functions — used for bulk text ingestion from external
    sources (HuggingFace, Sifter Labs, etc.) where OCR/parse is not needed.

    Callable via direct invoke:
        {
            "action": "batch_insert_documents",
            "case_id": "...",
            "documents": [
                {"document_id": "...", "source_filename": "...", "raw_text": "...", "source_metadata": {...}},
                ...
            ],
            "skip_embeddings": false,
            "skip_entity_extraction": false
        }
    """
    import json as _json
    import uuid as _uuid
    from db.connection import ConnectionManager

    case_id = event.get("case_id")
    documents = event.get("documents", [])
    skip_embeddings = event.get("skip_embeddings", False)
    skip_extraction = event.get("skip_entity_extraction", False)

    if not case_id or not documents:
        return {"error": "case_id and documents are required"}

    logger.info("batch_insert_documents: %d docs for case %s", len(documents), case_id)

    cm = ConnectionManager()
    inserted = 0
    entities_extracted = 0

    try:
        with cm.cursor() as cur:
            for doc in documents:
                doc_id = doc.get("document_id", str(_uuid.uuid4()))
                raw_text = doc.get("raw_text", "")
                if not raw_text or not raw_text.strip():
                    continue

                source_filename = doc.get("source_filename", "")
                source_metadata = doc.get("source_metadata", {})

                # Check for duplicate by source_filename
                cur.execute(
                    "SELECT 1 FROM documents WHERE case_file_id = %s AND source_filename = %s LIMIT 1",
                    (case_id, source_filename),
                )
                if cur.fetchone():
                    continue  # skip duplicate

                cur.execute(
                    """INSERT INTO documents (document_id, case_file_id, source_filename, raw_text, source_metadata, indexed_at)
                       VALUES (%s, %s, %s, %s, %s, now())
                       ON CONFLICT (document_id) DO NOTHING""",
                    (doc_id, case_id, source_filename, raw_text, _json.dumps(source_metadata)),
                )
                inserted += 1

        logger.info("batch_insert_documents: inserted %d docs", inserted)

        # Generate embeddings if not skipped
        if not skip_embeddings and inserted > 0:
            try:
                _generate_embeddings_for_batch(cm, case_id, documents)
            except Exception as e:
                logger.warning("Embedding generation failed: %s", str(e)[:300])

        # Entity extraction if not skipped
        if not skip_extraction and inserted > 0:
            try:
                entities_extracted = _extract_entities_for_batch(cm, case_id, documents)
            except Exception as e:
                logger.warning("Entity extraction failed: %s", str(e)[:300])

    except Exception as exc:
        logger.error("batch_insert_documents failed: %s", str(exc)[:500])
        return {"error": str(exc)[:500], "documents_inserted": inserted}

    return {
        "documents_inserted": inserted,
        "entities_extracted": entities_extracted,
        "case_id": case_id,
    }


def _generate_embeddings_for_batch(cm, case_id, documents):
    """Generate and store Titan embeddings for inserted documents."""
    import boto3
    from botocore.config import Config

    bedrock_config = Config(
        read_timeout=120, connect_timeout=10,
        retries={"max_attempts": 2, "mode": "adaptive"},
    )
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    model_id = os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1")

    for doc in documents:
        raw_text = doc.get("raw_text", "")
        if not raw_text.strip():
            continue
        doc_id = doc.get("document_id")
        embed_text = raw_text[:20_000]

        try:
            import json as _json
            body = _json.dumps({"inputText": embed_text})
            resp = bedrock.invoke_model(
                modelId=model_id, contentType="application/json",
                accept="application/json", body=body,
            )
            resp_body = _json.loads(resp["body"].read())
            embedding = resp_body["embedding"]

            with cm.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET embedding = %s WHERE document_id = %s",
                    (str(embedding), doc_id),
                )
        except Exception as e:
            logger.warning("Embedding failed for %s: %s", doc_id, str(e)[:200])


def _extract_entities_for_batch(cm, case_id, documents):
    """Run Bedrock entity extraction on inserted documents."""
    import boto3
    import json as _json
    from botocore.config import Config

    bedrock_config = Config(
        read_timeout=120, connect_timeout=10,
        retries={"max_attempts": 2, "mode": "adaptive"},
    )
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    model_id = os.environ.get("BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    total_entities = 0
    for doc in documents:
        raw_text = doc.get("raw_text", "")
        if not raw_text.strip() or len(raw_text.strip()) < 50:
            continue
        doc_id = doc.get("document_id")

        # Truncate for extraction prompt
        text_for_extraction = raw_text[:8_000]

        prompt = f"""Extract named entities from this document. Return a JSON array of objects with "name", "type" (person/organization/location/date/financial/event), and "confidence" (0.0-1.0).

Document text:
{text_for_extraction}

Return ONLY a JSON array, no other text."""

        try:
            body = _json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            })
            resp = bedrock.invoke_model(
                modelId=model_id, contentType="application/json",
                accept="application/json", body=body,
            )
            resp_body = _json.loads(resp["body"].read())
            content = resp_body.get("content", [{}])[0].get("text", "[]")

            # Parse entities
            entities = _parse_entity_json(content)

            # Insert entities
            with cm.cursor() as cur:
                for ent in entities:
                    cur.execute(
                        """INSERT INTO entities (entity_id, case_file_id, document_id, canonical_name, entity_type, confidence)
                           VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)""",
                        (case_id, doc_id, ent.get("name", ""), ent.get("type", "unknown"),
                         float(ent.get("confidence", 0.5))),
                    )
                    total_entities += 1

        except Exception as e:
            logger.warning("Entity extraction failed for %s: %s", doc_id, str(e)[:200])

    return total_entities


def _parse_entity_json(text):
    """Parse entity JSON from Bedrock response, handling markdown fences."""
    import json as _json
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[cleaned.index("\n") + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    try:
        return _json.loads(cleaned)
    except Exception:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                return _json.loads(cleaned[start:end + 1])
            except Exception:
                pass
    return []


# ------------------------------------------------------------------
# ACTION: backfill_embeddings_count / backfill_embeddings_batch
# ------------------------------------------------------------------

def _backfill_embeddings_count(event, context):
    """Count docs with and without embeddings for a case."""
    from db.connection import ConnectionManager
    case_id = event.get("case_id")
    cm = ConnectionManager()
    try:
        with cm.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE case_file_id = %s AND embedding IS NULL AND raw_text IS NOT NULL AND LENGTH(raw_text) > 30",
                (case_id,),
            )
            missing = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE case_file_id = %s AND embedding IS NOT NULL",
                (case_id,),
            )
            has = cur.fetchone()[0]
        return {"missing_count": missing, "has_embedding_count": has, "case_id": case_id}
    except Exception as e:
        return {"error": str(e)[:500]}


def _backfill_embeddings_batch(event, context):
    """Generate embeddings for a batch of docs missing them."""
    import boto3 as _boto3
    import json as _json
    from botocore.config import Config
    from db.connection import ConnectionManager

    case_id = event.get("case_id")
    batch_size = event.get("batch_size", 50)
    cm = ConnectionManager()

    bedrock_config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"})
    bedrock = _boto3.client("bedrock-runtime", config=bedrock_config)
    model_id = "amazon.titan-embed-text-v1"  # Must match existing 1536-dim embeddings

    processed = 0
    errors = 0

    try:
        with cm.cursor() as cur:
            # Reset any aborted transaction
            try:
                cur.execute("SELECT 1")
            except Exception:
                cur.execute("ROLLBACK")

            # Get batch of docs needing embeddings
            cur.execute(
                """SELECT document_id, raw_text FROM documents
                   WHERE case_file_id = %s AND embedding IS NULL
                   AND raw_text IS NOT NULL AND LENGTH(raw_text) > 30
                   LIMIT %s""",
                (case_id, batch_size),
            )
            rows = cur.fetchall()

            for doc_id, raw_text in rows:
                embed_text = raw_text[:20_000]
                try:
                    body = _json.dumps({"inputText": embed_text})
                    resp = bedrock.invoke_model(
                        modelId=model_id, contentType="application/json",
                        accept="application/json", body=body,
                    )
                    resp_body = _json.loads(resp["body"].read())
                    embedding = resp_body["embedding"]

                    cur.execute(
                        "UPDATE documents SET embedding = %s WHERE document_id = %s",
                        (str(embedding), doc_id),
                    )
                    processed += 1
                except Exception as e:
                    errors += 1
                    logger.warning("Embed failed for %s: %s", doc_id, str(e)[:200])
                    # Reset transaction so next update works
                    try:
                        cur.execute("ROLLBACK")
                    except Exception:
                        pass

            # Count remaining
            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE case_file_id = %s AND embedding IS NULL AND raw_text IS NOT NULL AND LENGTH(raw_text) > 30",
                (case_id,),
            )
            remaining = cur.fetchone()[0]

        return {"processed": processed, "errors": errors, "remaining": remaining, "case_id": case_id}
    except Exception as e:
        return {"error": str(e)[:500], "processed": processed}


def _insert_entities_handler(event, context):
    """Insert entities directly into Aurora entities table."""
    from db.connection import ConnectionManager
    import json as _json
    case_id = event.get("case_id")
    entities = event.get("entities", [])
    cm = ConnectionManager()
    inserted = 0
    try:
        with cm.cursor() as cur:
            for ent in entities:
                try:
                    cur.execute(
                        """INSERT INTO entities (entity_id, case_file_id, canonical_name, entity_type, confidence)
                           VALUES (gen_random_uuid(), %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (case_id, ent.get("name", "")[:255], ent.get("type", "location"), float(ent.get("confidence", 0.9))),
                    )
                    inserted += 1
                except Exception:
                    pass
        return {"inserted": inserted, "case_id": case_id}
    except Exception as e:
        return {"error": str(e)[:500], "inserted": inserted}


def _gremlin_query_handler(event, context):
    """Execute a Gremlin query against Neptune."""
    import urllib.request
    import json as _json
    import ssl
    query = event.get("query", "")
    endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    port = os.environ.get("NEPTUNE_PORT", "8182")
    if not endpoint or not query:
        return {"error": "Missing endpoint or query"}
    try:
        url = f"https://{endpoint}:{port}/gremlin"
        data = _json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        timeout = int(event.get("timeout", 120))
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            result = _json.loads(resp.read().decode("utf-8"))
        raw = result.get("result", {}).get("data", "")
        max_len = int(event.get("max_result_len", 4000))
        return {"status": "ok", "result": str(raw)[:max_len]}
    except urllib.request.HTTPError as he:
        body = ""
        try:
            body = he.read().decode("utf-8")[:1000]
        except Exception:
            pass
        return {"error": f"HTTP Error {he.code}: {he.reason} | {body}"}
    except Exception as e:
        return {"error": str(e)[:500]}


def _query_aurora_entities(event, context):
    """Return distinct entities from Aurora for Neptune sync."""
    from db.connection import ConnectionManager
    case_id = event.get("case_id")
    limit = int(event.get("limit", 5000))
    offset = int(event.get("offset", 0))
    if not case_id:
        return {"error": "Missing case_id"}
    cm = ConnectionManager()
    try:
        with cm.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT canonical_name, entity_type, COUNT(*) as cnt
                   FROM entities WHERE case_file_id = %s
                   AND LENGTH(canonical_name) > 1
                   GROUP BY canonical_name, entity_type
                   ORDER BY cnt DESC
                   LIMIT %s OFFSET %s""",
                (case_id, limit, offset),
            )
            rows = cur.fetchall()
            entities = [{"name": r[0], "type": r[1], "count": r[2]} for r in rows]
            # Get total count
            cur.execute(
                """SELECT COUNT(DISTINCT (canonical_name, entity_type))
                   FROM entities WHERE case_file_id = %s AND LENGTH(canonical_name) > 1""",
                (case_id,),
            )
            total = cur.fetchone()[0]
        return {"entities": entities, "total": total, "offset": offset, "limit": limit}
    except Exception as e:
        return {"error": str(e)[:500]}


def _cleanup_noise_entities(event, context):
    """Delete OCR noise entities (placeholders, single chars, numbers-only)."""
    from db.connection import ConnectionManager
    case_id = event.get("case_id")
    cm = ConnectionManager()
    total = 0
    try:
        with cm.cursor() as cur:
            # Generic placeholders
            cur.execute(
                "DELETE FROM entities WHERE case_file_id = %s AND canonical_name IN "
                "('Doctor''s Name', 'Name', 'Relationship', 'Doctor', 'Address', "
                "'Phone Number', 'Email', 'Date', 'Number', 'Unknown', 'N/A', 'None', "
                "'null', '', 'EFTA', 'USG DUROCK', 'Document', 'Page', 'Case', 'File', "
                "'Defendant', 'Plaintiff', 'Court', 'Judge', 'Attorney')",
                (case_id,),
            )
            total += cur.rowcount
            # Single/double char entities
            cur.execute(
                "DELETE FROM entities WHERE case_file_id = %s AND LENGTH(canonical_name) <= 2",
                (case_id,),
            )
            total += cur.rowcount
            # Numbers-only
            cur.execute(
                "DELETE FROM entities WHERE case_file_id = %s AND canonical_name ~ '^[0-9\\-\\.\\s\\(\\)]+$'",
                (case_id,),
            )
            total += cur.rowcount
            # Placeholder patterns
            cur.execute(
                "DELETE FROM entities WHERE case_file_id = %s AND "
                "(canonical_name ILIKE '%%xxx%%' OR canonical_name ILIKE '%%000-000%%' "
                "OR canonical_name ILIKE 'page %%' OR canonical_name ILIKE '1-800%%')",
                (case_id,),
            )
            total += cur.rowcount
        return {"deleted": total, "case_id": case_id}
    except Exception as e:
        return {"error": str(e)[:500], "deleted": total}


def _backfill_entities_count(event, context):
    """Count docs with and without entities."""
    from db.connection import ConnectionManager
    case_id = event.get("case_id")
    cm = ConnectionManager()
    try:
        with cm.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM documents d
                   WHERE d.case_file_id = %s
                   AND NOT EXISTS (SELECT 1 FROM entities e WHERE e.document_id = d.document_id)
                   AND d.raw_text IS NOT NULL AND LENGTH(d.raw_text) > 50""",
                (case_id,),
            )
            missing = cur.fetchone()[0]
            cur.execute(
                """SELECT COUNT(DISTINCT document_id) FROM entities WHERE case_file_id = %s""",
                (case_id,),
            )
            has = cur.fetchone()[0]
        return {"missing_count": missing, "has_entities_count": has, "case_id": case_id}
    except Exception as e:
        return {"error": str(e)[:500]}


def _backfill_entities_batch(event, context):
    """Extract entities for a batch of docs missing them."""
    import boto3 as _boto3
    import json as _json
    from botocore.config import Config
    from db.connection import ConnectionManager

    case_id = event.get("case_id")
    batch_size = event.get("batch_size", 20)
    cm = ConnectionManager()

    bedrock_config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 2, "mode": "adaptive"})
    bedrock = _boto3.client("bedrock-runtime", config=bedrock_config)
    model_id = os.environ.get("BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    processed = 0
    entities_extracted = 0
    errors = 0

    try:
        with cm.cursor() as cur:
            try:
                cur.execute("SELECT 1")
            except Exception:
                cur.execute("ROLLBACK")

            cur.execute(
                """SELECT d.document_id, d.raw_text FROM documents d
                   WHERE d.case_file_id = %s
                   AND NOT EXISTS (SELECT 1 FROM entities e WHERE e.document_id = d.document_id)
                   AND d.raw_text IS NOT NULL AND LENGTH(d.raw_text) > 50
                   LIMIT %s""",
                (case_id, batch_size),
            )
            rows = cur.fetchall()

            for doc_id, raw_text in rows:
                text_for_extraction = raw_text[:8_000]
                prompt = f"""Extract named entities from this document. Return a JSON array of objects with "name", "type" (person/organization/location/date/financial/event), and "confidence" (0.0-1.0).

Document text:
{text_for_extraction}

Return ONLY a JSON array, no other text."""

                try:
                    body = _json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 2048,
                        "messages": [{"role": "user", "content": prompt}],
                    })
                    resp = bedrock.invoke_model(
                        modelId=model_id, contentType="application/json",
                        accept="application/json", body=body,
                    )
                    resp_body = _json.loads(resp["body"].read())
                    content = resp_body.get("content", [{}])[0].get("text", "[]")
                    entities = _parse_entity_json(content)

                    for ent in entities:
                        try:
                            cur.execute(
                                """INSERT INTO entities (entity_id, case_file_id, document_id, canonical_name, entity_type, confidence)
                                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
                                   ON CONFLICT DO NOTHING""",
                                (case_id, doc_id, ent.get("name", "")[:255], ent.get("type", "unknown"),
                                 float(ent.get("confidence", 0.5))),
                            )
                            entities_extracted += 1
                        except Exception:
                            pass

                    processed += 1
                except Exception as e:
                    errors += 1
                    logger.warning("Entity extraction failed for %s: %s", doc_id, str(e)[:200])
                    try:
                        cur.execute("ROLLBACK")
                    except Exception:
                        pass

            # Count remaining
            cur.execute(
                """SELECT COUNT(*) FROM documents d
                   WHERE d.case_file_id = %s
                   AND NOT EXISTS (SELECT 1 FROM entities e WHERE e.document_id = d.document_id)
                   AND d.raw_text IS NOT NULL AND LENGTH(d.raw_text) > 50""",
                (case_id,),
            )
            remaining = cur.fetchone()[0]

        return {"processed": processed, "entities_extracted": entities_extracted,
                "errors": errors, "remaining": remaining, "case_id": case_id}
    except Exception as e:
        return {"error": str(e)[:500], "processed": processed}


def _build_case_file_service():
    """Construct a CaseFileCompatService wrapping MatterService.

    Returns a backward-compatible service that delegates to MatterService,
    translating matter_id→case_id and matter_name→topic_name in responses.
    """
    from db.connection import ConnectionManager
    from services.case_file_compat_service import CaseFileCompatService
    from services.matter_service import MatterService

    aurora_cm = ConnectionManager()
    matter_service = MatterService(aurora_cm)
    default_org_id = os.environ.get("DEFAULT_ORG_ID", "")
    return CaseFileCompatService(matter_service, default_org_id)


# ------------------------------------------------------------------
# POST /case-files
# ------------------------------------------------------------------

def create_case_file_handler(event, context):
    """Create a new case file."""
    from lambdas.api.response_helper import error_response, success_response
    from models.case_file import SearchTier

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        topic_name = body.get("topic_name", "")
        description = body.get("description", "")

        if not topic_name or not description:
            missing = []
            if not topic_name:
                missing.append("topic_name")
            if not description:
                missing.append("description")
            return error_response(
                400, "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing)}", event,
            )

        # Validate search_tier if provided
        search_tier = body.get("search_tier", "standard")
        valid_tiers = [t.value for t in SearchTier]
        if search_tier not in valid_tiers:
            return error_response(
                400, "VALIDATION_ERROR",
                f"Invalid search_tier: '{search_tier}'. Allowed values: {valid_tiers}",
                event,
            )

        service = _build_case_file_service()
        case_file = service.create_case_file(
            topic_name=topic_name,
            description=description,
            parent_case_id=body.get("parent_case_id"),
            search_tier=search_tier,
        )

        return success_response(case_file.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create case file")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files
# ------------------------------------------------------------------

def list_case_files_handler(event, context):
    """List case files with optional filters."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        params = event.get("queryStringParameters") or {}

        kwargs = {}
        if "status" in params:
            kwargs["status"] = params["status"]
        if "topic_keyword" in params:
            kwargs["topic_keyword"] = params["topic_keyword"]
        if "date_from" in params:
            kwargs["date_from"] = datetime.fromisoformat(params["date_from"])
        if "date_to" in params:
            kwargs["date_to"] = datetime.fromisoformat(params["date_to"])
        if "entity_count_min" in params:
            kwargs["entity_count_min"] = int(params["entity_count_min"])
        if "entity_count_max" in params:
            kwargs["entity_count_max"] = int(params["entity_count_max"])

        service = _build_case_file_service()
        case_files = service.list_case_files(**kwargs)

        results = []
        for cf in case_files:
            data = cf.model_dump(mode="json")
            data["security_label"] = getattr(cf, "security_label", "restricted")
            results.append(data)

        return success_response(
            {"case_files": results},
            200, event,
        )

    except (ValueError, TypeError) as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to list case files")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}
# ------------------------------------------------------------------

def get_case_file_handler(event, context):
    """Get case file details by ID."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        service = _build_case_file_service()
        case_file = service.get_case_file(case_id)

        data = case_file.model_dump(mode="json")
        data["security_label"] = getattr(case_file, "security_label", "restricted")

        # Filter document data if user context is available
        user_ctx_dict = event.get("_user_context")
        if user_ctx_dict and data.get("documents"):
            from models.access_control import UserContext
            from services.access_control_service import AccessControlService
            user_ctx = UserContext(**user_ctx_dict)
            ac_service = AccessControlService()
            data["documents"] = ac_service.filter_documents(user_ctx, data["documents"])

        return success_response(data, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to get case file")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# DELETE /case-files/{id}
# ------------------------------------------------------------------

def delete_case_file_handler(event, context):
    """Delete a case file and all associated data."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        service = _build_case_file_service()
        service.delete_case_file(case_id)

        return success_response({"deleted": True, "case_id": case_id}, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to delete case file")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/archive
# ------------------------------------------------------------------

def archive_case_file_handler(event, context):
    """Archive a case file (retains all data)."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        service = _build_case_file_service()
        case_file = service.archive_case_file(case_id)

        return success_response(case_file.model_dump(mode="json"), 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to archive case file")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/documents/{docId}/download
# ------------------------------------------------------------------

def get_document_download_url_handler(event, context):
    """Generate a pre-signed S3 URL for downloading a case document."""
    import boto3
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        doc_id = (event.get("pathParameters") or {}).get("docId", "")
        if not case_id or not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID or document ID", event)

        bucket = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))
        if not bucket:
            return error_response(500, "CONFIG_ERROR", "S3 bucket not configured", event)

        s3 = boto3.client("s3")

        # Try to find the document in the case's raw prefix
        # Documents are stored as cases/{case_id}/raw/{filename}
        # The doc_id might be the document_id (UUID) or the filename
        # First try to look up the filename from Aurora
        filename = doc_id
        try:
            from db.connection import ConnectionManager
            cm = ConnectionManager()
            with cm.cursor() as cur:
                cur.execute(
                    "SELECT source_filename, s3_key FROM documents WHERE document_id = %s AND case_file_id = %s",
                    (doc_id, case_id),
                )
                row = cur.fetchone()
                if row:
                    filename = row[0] or doc_id
                    # If we have the s3_key directly, use it
                    if row[1]:
                        s3_key = row[1]
                    else:
                        s3_key = f"cases/{case_id}/raw/{filename}"
                else:
                    s3_key = f"cases/{case_id}/raw/{doc_id}"
        except Exception:
            s3_key = f"cases/{case_id}/raw/{doc_id}"

        # Generate pre-signed URL (valid for 15 minutes)
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=900,
        )

        return success_response({
            "download_url": url,
            "filename": filename,
            "s3_key": s3_key,
            "expires_in": 900,
        }, 200, event)

    except Exception as exc:
        logger.exception("Failed to generate download URL")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)

# ------------------------------------------------------------------
# POST /case-files/{id}/entity-resolution
# ------------------------------------------------------------------

def entity_photos_handler(event, context):
    """GET /case-files/{id}/entity-photos — presigned URLs for entity face photos."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        from services.entity_photo_service import EntityPhotoService
        service = EntityPhotoService()
        result = service.get_entity_photos(case_id)
        return success_response(result, 200, event)
    except Exception as exc:
        logger.exception("Failed to get entity photos")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def _parse_classification_param(raw_value: str) -> str:
    """Validate and return the classification query parameter.

    Valid values: photograph, document_page, redacted_text, blank, all.
    Returns 'photograph' for missing/invalid values.
    """
    valid = {"photograph", "document_page", "redacted_text", "blank", "all"}
    val = (raw_value or "").strip().lower()
    return val if val in valid else "photograph"


def load_classification_artifact(s3_client, bucket: str, case_id: str) -> Optional[list]:
    """Load image_classification.json from S3.

    Returns the list of classification entries, or None if the artifact
    does not exist or is malformed (backward-compat: caller treats None
    as 'no classification available').
    """
    try:
        key = f"cases/{case_id}/rekognition-artifacts/image_classification.json"
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(resp["Body"].read().decode())
        classifications = data.get("classifications", [])
        if not isinstance(classifications, list):
            return None
        return classifications
    except Exception:
        return None


def build_classification_lookup(classifications: list) -> dict:
    """Build a dict mapping s3_key → classification string."""
    lookup = {}
    for entry in classifications:
        s3_key = entry.get("s3_key", "")
        cls = entry.get("classification", "")
        if s3_key and cls:
            lookup[s3_key] = cls
    return lookup


def compute_classification_counts(classifications: list) -> dict:
    """Compute total counts per classification category.

    Returns dict like {"photograph": N, "document_page": N, "redacted_text": N, "blank": N}.
    """
    counts = {"photograph": 0, "document_page": 0, "redacted_text": 0, "blank": 0}
    for entry in classifications:
        cls = entry.get("classification", "")
        if cls in counts:
            counts[cls] += 1
    return counts


def filter_images_by_classification(
    images: list,
    classification_lookup: dict,
    classification_filter: str,
) -> list:
    """Filter image records by classification and annotate each with its classification.

    - Adds a 'classification' field to every image record.
    - When classification_filter is 'all', returns all images (no filtering).
    - Otherwise returns only images whose classification matches the filter.
    - Images not found in the lookup get classification 'unknown' and are
      excluded unless filter is 'all'.
    """
    result = []
    for img in images:
        s3_key = img.get("s3_key", "")
        cls = classification_lookup.get(s3_key, "unknown")
        img["classification"] = cls
        if classification_filter == "all" or cls == classification_filter:
            result.append(img)
    return result


def load_face_match_results(s3_client, bucket: str, case_id: str) -> Optional[dict]:
    """Load face_match_results.json from S3.

    Returns the parsed JSON dict, or None if the artifact does not exist
    or is malformed (backward-compat: caller treats None as 'no match data').
    """
    try:
        key = f"cases/{case_id}/rekognition-artifacts/face_match_results.json"
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(resp["Body"].read().decode())
        if not isinstance(data.get("matches"), list):
            return None
        return data
    except Exception:
        return None


def build_entity_match_lookup(match_results: Optional[dict]) -> dict:
    """Build a lookup from crop filename to entity name + similarity score.

    Returns dict like: {"abc123.jpg": {"entity_name": "John_Doe", "similarity": 95.2}, ...}
    """
    if not match_results:
        return {}
    lookup = {}
    for m in match_results.get("matches", []):
        crop = m.get("crop", "")
        entity = m.get("entity", "")
        similarity = m.get("similarity", 0.0)
        if crop and entity:
            lookup[crop] = {"entity_name": entity, "similarity": similarity}
    return lookup


def merge_entity_matches(images: list, match_lookup: dict) -> None:
    """Merge matched entity names into image records.

    For each image that has face data (a 'faces' list with crop keys),
    resolves entity names and similarity scores into a 'matched_entities' list.
    Images with no matched faces get an empty 'matched_entities' list.

    Mutates images in-place.
    """
    for img in images:
        matched_entities = []
        faces = img.get("faces", [])
        for face in faces:
            crop_key = face.get("crop_key", "")
            crop_filename = crop_key.split("/")[-1] if crop_key else ""
            match_info = match_lookup.get(crop_filename)
            if match_info:
                matched_entities.append({
                    "entity_name": match_info["entity_name"],
                    "similarity": match_info["similarity"],
                })
        img["matched_entities"] = matched_entities


def image_evidence_handler(event, context):
    """GET /case-files/{id}/image-evidence — paginated image gallery with labels and face crops.

    Query params:
        page (int, default 1)
        page_size (int, default 50, max 200)
        label_filter (str, optional) — filter images containing this label
        has_faces (bool, optional) — filter to images with detected faces
        classification (str, default 'photograph') — filter by image classification
    """
    import boto3
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        qsp = event.get("queryStringParameters") or {}
        page = max(1, int(qsp.get("page", "1")))
        page_size = min(200, max(1, int(qsp.get("page_size", "50"))))
        label_filter = qsp.get("label_filter", "").lower()
        has_faces = qsp.get("has_faces", "").lower() == "true"
        classification_filter = _parse_classification_param(qsp.get("classification", ""))

        bucket = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", "research-analyst-data-lake-974220725866"))
        s3 = boto3.client("s3")

        # Try to load batch labels details from S3
        labels_data = []
        try:
            details_key = f"cases/{case_id}/rekognition-artifacts/batch_labels_details.json"
            resp = s3.get_object(Bucket=bucket, Key=details_key)
            labels_data = json.loads(resp["Body"].read().decode())
        except Exception:
            pass

        # Try to load face crop metadata
        face_data = []
        try:
            face_key = f"cases/{case_id}/rekognition-artifacts/face_crop_metadata.json"
            resp = s3.get_object(Bucket=bucket, Key=face_key)
            face_data = json.loads(resp["Body"].read().decode())
        except Exception:
            pass

        # Load face match results via helper
        face_match_results = load_face_match_results(s3, bucket, case_id)
        entity_match_lookup = build_entity_match_lookup(face_match_results)
        # Build simple crop->entity map for face_by_source (backward compat)
        match_data = {crop: info["entity_name"] for crop, info in entity_match_lookup.items()}

        # Try to load labels summary
        summary = {}
        try:
            summary_key = f"cases/{case_id}/rekognition-artifacts/batch_labels_summary.json"
            resp = s3.get_object(Bucket=bucket, Key=summary_key)
            summary = json.loads(resp["Body"].read().decode())
        except Exception:
            pass

        # Try to load weapon AI descriptions (false positive detection)
        weapon_descriptions = {}
        try:
            weapon_key = f"cases/{case_id}/rekognition-artifacts/weapon_ai_descriptions.json"
            resp = s3.get_object(Bucket=bucket, Key=weapon_key)
            weapon_data = json.loads(resp["Body"].read().decode())
            for desc in weapon_data.get("descriptions", []):
                weapon_descriptions[desc.get("s3_key", "")] = {
                    "ai_description": desc.get("ai_description", ""),
                    "likely_false_positive": desc.get("likely_false_positive", False),
                }
        except Exception:
            pass

        # Build face lookup: source_s3_key -> list of face crops
        face_by_source = {}
        for face in face_data:
            src = face.get("source_s3_key", "")
            if src not in face_by_source:
                face_by_source[src] = []
            entity = match_data.get(face.get("crop_s3_key", "").split("/")[-1], face.get("entity_name", "unidentified"))
            face_by_source[src].append({
                "crop_key": face.get("crop_s3_key", ""),
                "entity_name": entity,
                "confidence": face.get("confidence", 0),
                "gender": face.get("gender", ""),
                "age_range": face.get("age_range", ""),
            })

        # Merge labels + faces into image records
        # If we have labels data, use that as the base
        if labels_data:
            images = []
            for item in labels_data:
                s3_key = item.get("s3_key", "")
                label_names = [l["name"].lower() for l in item.get("labels", [])]

                if label_filter and label_filter not in label_names:
                    continue

                faces = face_by_source.get(s3_key, [])
                if has_faces and not faces:
                    continue

                filename = s3_key.split("/")[-1] if s3_key else ""
                doc_id = filename.split("_page")[0] if "_page" in filename else ""

                weapon_info = weapon_descriptions.get(s3_key, {})
                images.append({
                    "s3_key": s3_key,
                    "filename": filename,
                    "source_document_id": doc_id,
                    "labels": item.get("labels", []),
                    "faces": faces,
                    "face_count": len(faces),
                    "ai_description": weapon_info.get("ai_description", ""),
                    "likely_false_positive": weapon_info.get("likely_false_positive", False),
                })
        else:
            # No labels data yet — just list extracted images from S3
            prefix = f"cases/{case_id}/extracted-images/"
            images = []
            paginator = s3.get_paginator("list_objects_v2")
            count = 0
            for pg in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in pg.get("Contents", []):
                    key = obj["Key"]
                    if not key.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue
                    filename = key.split("/")[-1]
                    doc_id = filename.split("_page")[0] if "_page" in filename else ""
                    faces = face_by_source.get(key, [])

                    if has_faces and not faces:
                        continue

                    images.append({
                        "s3_key": key,
                        "filename": filename,
                        "source_document_id": doc_id,
                        "labels": [],
                        "faces": faces,
                        "face_count": len(faces),
                    })
                    count += 1
                    if count >= 5000:  # Cap at 5000 for performance
                        break
                if count >= 5000:
                    break

        # --- Entity name merging ---
        merge_entity_matches(images, entity_match_lookup)

        # --- Classification filtering ---
        # Load classification artifact; None means not available
        classification_entries = load_classification_artifact(s3, bucket, case_id)
        classification_counts = {"photograph": 0, "document_page": 0, "redacted_text": 0, "blank": 0}

        if classification_entries is not None:
            classification_lookup = build_classification_lookup(classification_entries)
            classification_counts = compute_classification_counts(classification_entries)
            images = filter_images_by_classification(images, classification_lookup, classification_filter)
        else:
            # No classification artifact — annotate all images as 'unknown', no filtering
            for img in images:
                img["classification"] = "unknown"

        # Paginate
        total = len(images)
        start = (page - 1) * page_size
        end = start + page_size
        page_images = images[start:end]

        # Generate presigned URLs for the page images
        for img in page_images:
            try:
                img["presigned_url"] = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": img["s3_key"]},
                    ExpiresIn=3600,
                )
            except Exception:
                img["presigned_url"] = ""

        result = {
            "images": page_images,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "summary": {
                "label_counts": summary.get("label_counts", {}),
                "unique_labels": summary.get("unique_labels", 0),
                "images_with_labels": summary.get("images_processed", 0),
                "total_faces": len(face_data),
                "matched_faces": len(match_data),
                "classification_counts": classification_counts,
            },
        }
        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Failed to get image evidence")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def document_images_handler(event, context):
    """GET /case-files/{id}/documents/{doc_id}/images — presigned URLs for document images and face crops."""
    import boto3
    from lambdas.api.response_helper import error_response, success_response

    try:
        params = event.get("pathParameters") or {}
        case_id = params.get("id", "")
        doc_id = params.get("doc_id", params.get("docId", ""))

        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)
        if not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing document ID", event)

        bucket = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", "research-analyst-data-lake-974220725866"))
        if not bucket:
            return error_response(500, "CONFIG_ERROR", "S3 bucket not configured", event)

        s3 = boto3.client("s3")
        images = []

        # List extracted images matching this document ID
        extracted_prefix = f"cases/{case_id}/extracted-images/"
        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=extracted_prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    filename = key[len(extracted_prefix):]
                    # Match files starting with doc_id followed by _page
                    if filename.startswith(f"{doc_id}_page"):
                        try:
                            url = s3.generate_presigned_url(
                                "get_object",
                                Params={"Bucket": bucket, "Key": key},
                                ExpiresIn=3600,
                            )
                            images.append({
                                "url": url,
                                "type": "extracted_image",
                                "filename": filename,
                                "s3_key": key,
                            })
                        except Exception as e:
                            logger.warning("Failed to generate presigned URL for %s: %s", key, e)
        except Exception as e:
            logger.warning("Failed to list extracted images for doc %s: %s", doc_id, e)

        # Find face crops linked to this document via Neptune FACE_DETECTED_IN edges
        face_crop_keys = _get_face_crops_for_document(case_id, doc_id)

        for crop_key in face_crop_keys:
            try:
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": crop_key},
                    ExpiresIn=3600,
                )
                crop_filename = crop_key.rsplit("/", 1)[-1] if "/" in crop_key else crop_key
                images.append({
                    "url": url,
                    "type": "face_crop",
                    "filename": crop_filename,
                    "s3_key": crop_key,
                })
            except Exception as e:
                logger.warning("Failed to generate presigned URL for face crop %s: %s", crop_key, e)

        # Load image descriptions from S3 artifact
        desc_map = _load_image_descriptions_for_case(s3, bucket, case_id)

        # Enrich images with descriptions and rekognition labels
        for img in images:
            s3_key = img.get("s3_key", "")
            desc_info = desc_map.get(s3_key, {})
            img["description"] = desc_info.get("description") if desc_info else None
            img["rekognition_labels"] = desc_info.get("rekognition_labels", []) if desc_info else []

        return success_response({
            "document_id": doc_id,
            "images": images,
            "total_count": len(images),
        }, 200, event)

    except Exception as exc:
        logger.exception("Failed to get document images")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def _load_image_descriptions_for_case(s3_client, bucket: str, case_id: str) -> dict:
    """Load image descriptions from the most recent description artifact.

    Returns a dict mapping image S3 key to {description, rekognition_labels}.
    """
    desc_map = {}
    prefix = f"cases/{case_id}/image-description-artifacts/"
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        artifacts = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("_descriptions.json"):
                    artifacts.append(obj)

        if not artifacts:
            return desc_map

        # Use the most recent artifact
        artifacts.sort(key=lambda x: x.get("LastModified", ""), reverse=True)
        latest = artifacts[0]

        resp = s3_client.get_object(Bucket=bucket, Key=latest["Key"])
        artifact = json.loads(resp["Body"].read().decode("utf-8"))

        for desc in artifact.get("descriptions", []):
            s3_key = desc.get("image_s3_key", "")
            if s3_key:
                rek_ctx = desc.get("rekognition_context", {})
                desc_map[s3_key] = {
                    "description": desc.get("description", ""),
                    "rekognition_labels": rek_ctx.get("labels", []),
                }
    except Exception as e:
        logger.warning("Failed to load image descriptions for case %s: %s", case_id, str(e)[:200])

    return desc_map


def _get_face_crops_for_document(case_id: str, doc_id: str) -> list:
    """Query Neptune for face crops linked to a document via FACE_DETECTED_IN edges.

    Falls back to S3 filename convention matching if Neptune query fails.
    """
    import ssl
    import urllib.request
    import urllib.error

    neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")

    if not neptune_endpoint:
        return _get_face_crops_from_s3(case_id, doc_id)

    try:
        fc_label = f"FaceCrop_{case_id}"
        query = (
            f"g.V().hasLabel('{fc_label}')"
            f".has('source_document_id','{doc_id}')"
            f".values('crop_s3_key')"
        )
        url = f"https://{neptune_endpoint}:{neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result", {}).get("data", {})
            values = result.get("@value", [])
            if values:
                return [v for v in values if isinstance(v, str)]
    except Exception as e:
        logger.warning("Neptune face crop query failed, falling back to S3: %s", str(e)[:200])

    return _get_face_crops_from_s3(case_id, doc_id)


def _get_face_crops_from_s3(case_id: str, doc_id: str) -> list:
    """Fallback: find face crops by scanning S3 face-crops prefix for crops
    whose source images match the document ID."""
    import boto3

    bucket = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", "research-analyst-data-lake-974220725866"))
    s3 = boto3.client("s3")
    crop_keys = []

    # Load face_crop_metadata artifact if available
    try:
        artifact_key = f"cases/{case_id}/rekognition-artifacts/face_crop_metadata.json"
        resp = s3.get_object(Bucket=bucket, Key=artifact_key)
        metadata = json.loads(resp["Body"].read().decode("utf-8"))
        for entry in metadata:
            if entry.get("source_document_id") == doc_id:
                crop_key = entry.get("crop_s3_key", "")
                if crop_key:
                    crop_keys.append(crop_key)
    except Exception:
        pass

    return crop_keys


def entity_resolution_handler(event, context):
    """Trigger entity resolution for a case by invoking the ER Lambda async."""
    import boto3
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        execute = body.get("execute", False)

        lam = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        payload = {
            "case_id": case_id,
            "dry_run": not execute,
            "use_llm": True,
        }

        er_lambda = "ResearchAnalystStack-EntityResolutionLambda"
        resp = lam.invoke(
            FunctionName=er_lambda,
            InvocationType="Event" if execute else "RequestResponse",
            Payload=json.dumps(payload),
        )

        if execute:
            return success_response({
                "message": "Entity resolution triggered (async)",
                "case_id": case_id,
                "status": "running",
            }, 202, event)
        else:
            result = json.loads(resp["Payload"].read().decode())
            return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Failed to trigger entity resolution")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/evidence-analyze
# ------------------------------------------------------------------

def evidence_analyze_handler(event, context):
    """Analyze evidence using Bedrock AI and return investigative insights."""
    import boto3
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        evidence_type = body.get("evidence_type", "")
        filename = body.get("filename", "")
        s3_key = body.get("s3_key", "")
        labels = body.get("labels", [])
        faces = body.get("faces", [])
        source_document_id = body.get("source_document_id", "")
        case_context = body.get("case_context", "")

        if not evidence_type or not filename:
            missing = []
            if not evidence_type:
                missing.append("evidence_type")
            if not filename:
                missing.append("filename")
            return error_response(
                400, "VALIDATION_ERROR",
                f"Missing required fields: {', '.join(missing)}", event,
            )

        # Build prompt
        label_text = ", ".join(l.get("name", "") for l in labels) if labels else "none detected"
        face_text = ", ".join(
            f"{f.get('entity_name', 'Unknown')} ({f.get('confidence', 0):.1f}%)"
            for f in faces
        ) if faces else "none identified"

        prompt = (
            f"You are an investigative analyst. Analyze this {evidence_type} evidence item "
            f"from case '{case_context}'.\n\n"
            f"Filename: {filename}\n"
            f"Objects/labels detected: {label_text}\n"
            f"Persons identified: {face_text}\n"
            f"Source document: {source_document_id or 'unknown'}\n\n"
            f"Provide a brief investigative analysis (2-3 paragraphs) of what this evidence "
            f"shows and its potential significance to the investigation. Focus on actionable "
            f"insights and connections."
        )

        model_id = "anthropic.claude-3-haiku-20240307-v1:0"
        bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

        resp = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )

        result = json.loads(resp["body"].read().decode())
        analysis_text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                analysis_text += block.get("text", "")

        return success_response({
            "analysis": analysis_text,
            "evidence_type": evidence_type,
            "model_id": model_id,
        }, 200, event)

    except json.JSONDecodeError:
        return error_response(400, "VALIDATION_ERROR", "Invalid JSON body", event)
    except Exception as exc:
        logger.exception("Failed to analyze evidence")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/video-evidence
# ------------------------------------------------------------------

def video_evidence_handler(event, context):
    """List video evidence files with presigned URLs."""
    import boto3
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        bucket = os.environ.get(
            "S3_DATA_BUCKET",
            os.environ.get("S3_BUCKET_NAME", "research-analyst-data-lake-974220725866"),
        )
        s3 = boto3.client("s3")
        videos = []

        # Check cases/{case_id}/videos/ and cases/{case_id}/raw/ prefixes
        prefixes = [
            f"cases/{case_id}/videos/",
            f"cases/{case_id}/raw/",
        ]
        # Also check epstein_downloads/videos/ for Epstein cases
        prefixes.append("epstein_downloads/videos/")

        for prefix in prefixes:
            try:
                paginator = s3.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        lower_key = key.lower()
                        if not (lower_key.endswith(".mp4") or lower_key.endswith(".mov")):
                            continue
                        filename = key.rsplit("/", 1)[-1] if "/" in key else key
                        fmt = "mp4" if lower_key.endswith(".mp4") else "mov"
                        try:
                            url = s3.generate_presigned_url(
                                "get_object",
                                Params={"Bucket": bucket, "Key": key},
                                ExpiresIn=3600,
                            )
                        except Exception:
                            url = ""
                        videos.append({
                            "s3_key": key,
                            "filename": filename,
                            "format": fmt,
                            "presigned_url": url,
                            "size_bytes": obj.get("Size", 0),
                        })
            except Exception as e:
                logger.warning("Failed to list videos from prefix %s: %s", prefix, str(e)[:200])

        return success_response({
            "videos": videos,
            "total": len(videos),
        }, 200, event)

    except Exception as exc:
        logger.exception("Failed to get video evidence")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)

# ------------------------------------------------------------------
# Admin SQL migration (temporary helper)
# ------------------------------------------------------------------

def _run_admin_migration(event, context):
    """POST /admin/run-migration — run a predefined SQL migration."""
    from lambdas.api.response_helper import error_response, success_response
    import json as _json
    try:
        body = _(json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        migration_name = body.get("migration", "")

        from db.connection import ConnectionManager
        cm = ConnectionManager()

        if migration_name == "update_ai_insights":
            with cm.cursor() as cur:
                cur.execute("""
                    UPDATE trawler_alerts
                    SET ai_insight = 'Cross-case presence of ' || REPLACE(title, 'Cross-case overlap: ', '') || ' across multiple investigations strengthens the network analysis — this entity may be a key connector in the broader conspiracy.'
                    WHERE alert_type = 'cross_case_overlap' AND title LIKE 'Cross-case overlap:%%'
                """)
                count = cur.rowcount
            return success_response({"migration": migration_name, "rows_updated": count}, 200, event)
        else:
            return error_response(400, "VALIDATION_ERROR", f"Unknown migration: {migration_name}", event)
    except Exception as exc:
        logger.exception("Admin migration failed")
        return error_response(500, "INTERNAL_ERROR", str(exc)[:500], event)
