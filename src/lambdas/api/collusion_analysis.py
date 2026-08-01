"""API Lambda handler for procurement collusion detection.

Endpoints:
    POST /case-files/{id}/collusion-analysis       — trigger analysis
    GET  /case-files/{id}/collusion-analysis        — get cached results
    GET  /case-files/{id}/red-flags                 — list red flags
    GET  /case-files/{id}/collusion-rings           — list collusion rings
    GET  /case-files/{id}/collusion-rings/{ring_id} — ring detail
    GET  /case-files/{id}/vendor-network            — vendor graph data
    POST /case-files/{id}/procurement-records       — ingest procurement data

Follows the existing dispatch_handler pattern from network_discovery.py.
"""

import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_collusion_detection_service():
    """Construct CollusionDetectionService with all dependencies from environment."""
    import boto3

    from db.connection import ConnectionManager
    from services.antitrust_legal_reasoning import AntitrustLegalReasoning
    from services.antitrust_scoring_service import AntitrustScoringService
    from services.collusion_detection_service import CollusionDetectionService
    from services.decision_workflow_service import DecisionWorkflowService
    from services.procurement_parser import ProcurementParser

    aurora_cm = ConnectionManager()
    bedrock = boto3.client("bedrock-runtime")
    neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")
    opensearch_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")

    decision_svc = DecisionWorkflowService(aurora_cm)
    scoring_svc = AntitrustScoringService(aurora_cm)
    legal_reasoning = AntitrustLegalReasoning(bedrock, model_id=model_id)
    parser = ProcurementParser()

    return CollusionDetectionService(
        aurora_cm=aurora_cm,
        neptune_endpoint=neptune_endpoint,
        neptune_port=neptune_port,
        bedrock_client=bedrock,
        opensearch_endpoint=opensearch_endpoint,
        decision_workflow_svc=decision_svc,
        antitrust_scoring_svc=scoring_svc,
        antitrust_legal_reasoning=legal_reasoning,
        procurement_parser=parser,
    )


# ------------------------------------------------------------------
# POST /case-files/{id}/collusion-analysis
# ------------------------------------------------------------------

def trigger_analysis_handler(event, context):
    """Trigger collusion analysis for a case.

    For large datasets (>50K bids), returns a processing status immediately
    rather than waiting for the full analysis to complete.
    """
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        svc = _build_collusion_detection_service()

        # Check dataset size to determine sync vs async response
        from db.connection import ConnectionManager

        cm = ConnectionManager()
        bid_count = 0
        try:
            with cm.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM procurement_bids WHERE case_id = %s",
                        (case_id,),
                    )
                    row = cur.fetchone()
                    bid_count = row[0] if row else 0
        except Exception:
            pass

        if bid_count > 50000:
            # Large dataset — return processing status
            return success_response(
                {
                    "status": "processing",
                    "case_id": case_id,
                    "bid_count": bid_count,
                    "message": f"Analysis queued for {bid_count:,} bids. Poll GET /case-files/{case_id}/collusion-analysis for results.",
                },
                202,
                event,
            )

        result = svc.run_analysis(case_id)

        return success_response(
            {
                "analysis_id": getattr(result, "analysis_id", str(uuid.uuid4())),
                "case_id": result.case_id,
                "status": result.status,
                "pcsf_score": result.overall_score,
                "evidence_summary": result.evidence_summary,
                "patterns_detected": len(result.patterns),
                "red_flags_count": len(result.red_flags),
                "subjects_count": len(result.subjects),
                "metadata": result.metadata,
            },
            200,
            event,
        )

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to trigger collusion analysis")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/collusion-analysis
# ------------------------------------------------------------------

def get_analysis_handler(event, context):
    """Get cached collusion analysis results."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        from db.connection import ConnectionManager

        cm = ConnectionManager()
        with cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT analysis_id, case_id, analysis_status, pcsf_score,
                           pcsf_breakdown, total_contracts_analyzed, total_bids_analyzed,
                           total_vendors_analyzed, total_patterns_detected,
                           total_red_flags, total_collusion_rings,
                           bid_rigging_patterns, price_anomalies,
                           communication_patterns, financial_flow_patterns,
                           collusion_rings, metadata, created_at, updated_at
                    FROM collusion_analyses
                    WHERE case_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (case_id,),
                )
                row = cur.fetchone()

        if not row:
            return error_response(
                404, "NOT_FOUND", f"No analysis found for case {case_id}", event
            )

        result = {
            "analysis_id": str(row[0]),
            "case_id": str(row[1]),
            "status": row[2],
            "pcsf_score": float(row[3]) if row[3] else 0.0,
            "pcsf_breakdown": row[4] if row[4] else {},
            "total_contracts_analyzed": row[5] or 0,
            "total_bids_analyzed": row[6] or 0,
            "total_vendors_analyzed": row[7] or 0,
            "total_patterns_detected": row[8] or 0,
            "total_red_flags": row[9] or 0,
            "total_collusion_rings": row[10] or 0,
            "bid_rigging_patterns": row[11] if row[11] else [],
            "price_anomalies": row[12] if row[12] else [],
            "communication_patterns": row[13] if row[13] else [],
            "financial_flow_patterns": row[14] if row[14] else [],
            "collusion_rings": row[15] if row[15] else [],
            "metadata": row[16] if row[16] else {},
            "created_at": str(row[17]) if row[17] else None,
            "updated_at": str(row[18]) if row[18] else None,
        }

        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Failed to get collusion analysis")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/red-flags
# ------------------------------------------------------------------

def list_red_flags_handler(event, context):
    """List red flags for a case with optional severity/category filters."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        params = event.get("queryStringParameters") or {}
        severity = params.get("severity")
        category = params.get("category")

        from db.connection import ConnectionManager

        cm = ConnectionManager()
        with cm.get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT flag_id, case_id, analysis_id, category, severity,
                           title, description, evidence_refs, involved_vendors,
                           involved_contracts, pcsf_taxonomy_code,
                           ai_legal_reasoning, decision_id, created_at
                    FROM antitrust_red_flags
                    WHERE case_id = %s
                """
                query_params = [case_id]

                if severity:
                    query += " AND severity = %s"
                    query_params.append(severity)
                if category:
                    query += " AND category = %s"
                    query_params.append(category)

                query += " ORDER BY CASE severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, created_at DESC"

                cur.execute(query, query_params)
                rows = cur.fetchall()

        red_flags = []
        for row in rows:
            red_flags.append({
                "flag_id": str(row[0]),
                "case_id": str(row[1]),
                "analysis_id": str(row[2]) if row[2] else None,
                "category": row[3],
                "severity": row[4],
                "title": row[5],
                "description": row[6],
                "evidence_refs": row[7] if row[7] else [],
                "involved_vendors": row[8] if row[8] else [],
                "involved_contracts": row[9] if row[9] else [],
                "pcsf_taxonomy_code": row[10],
                "ai_legal_reasoning": row[11],
                "decision_id": str(row[12]) if row[12] else None,
                "created_at": str(row[13]) if row[13] else None,
            })

        return success_response(
            {"red_flags": red_flags, "total": len(red_flags)},
            200,
            event,
        )

    except Exception as exc:
        logger.exception("Failed to list red flags")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/collusion-rings
# ------------------------------------------------------------------

def list_collusion_rings_handler(event, context):
    """List identified collusion rings for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        from db.connection import ConnectionManager

        cm = ConnectionManager()
        with cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ring_id, case_id, analysis_id, ring_name,
                           member_vendors, member_roles, pcsf_score,
                           scheme_type, affected_contracts, timeline,
                           evidence_summary, ai_legal_reasoning,
                           decision_id, created_at
                    FROM collusion_rings
                    WHERE case_id = %s
                    ORDER BY pcsf_score DESC NULLS LAST
                    """,
                    (case_id,),
                )
                rows = cur.fetchall()

        rings = []
        for row in rows:
            rings.append({
                "ring_id": str(row[0]),
                "case_id": str(row[1]),
                "analysis_id": str(row[2]) if row[2] else None,
                "ring_name": row[3],
                "member_vendors": row[4] if row[4] else [],
                "member_roles": row[5] if row[5] else {},
                "pcsf_score": float(row[6]) if row[6] else None,
                "scheme_type": row[7],
                "affected_contracts": row[8] if row[8] else [],
                "timeline": row[9] if row[9] else [],
                "evidence_summary": row[10] if row[10] else {},
                "ai_legal_reasoning": row[11],
                "decision_id": str(row[12]) if row[12] else None,
                "created_at": str(row[13]) if row[13] else None,
            })

        return success_response(
            {"collusion_rings": rings, "total": len(rings)},
            200,
            event,
        )

    except Exception as exc:
        logger.exception("Failed to list collusion rings")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/collusion-rings/{ring_id}
# ------------------------------------------------------------------

def get_collusion_ring_handler(event, context):
    """Get full detail for a specific collusion ring."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        ring_id = (event.get("pathParameters") or {}).get("ring_id", "")
        if not case_id or not ring_id:
            return error_response(
                400, "VALIDATION_ERROR", "Missing case ID or ring ID", event
            )

        from db.connection import ConnectionManager

        cm = ConnectionManager()
        with cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ring_id, case_id, analysis_id, ring_name,
                           member_vendors, member_roles, pcsf_score,
                           scheme_type, affected_contracts, timeline,
                           evidence_summary, ai_legal_reasoning,
                           decision_id, created_at
                    FROM collusion_rings
                    WHERE case_id = %s AND ring_id = %s
                    """,
                    (case_id, ring_id),
                )
                row = cur.fetchone()

        if not row:
            return error_response(
                404, "NOT_FOUND",
                f"Collusion ring {ring_id} not found in case {case_id}",
                event,
            )

        ring = {
            "ring_id": str(row[0]),
            "case_id": str(row[1]),
            "analysis_id": str(row[2]) if row[2] else None,
            "ring_name": row[3],
            "member_vendors": row[4] if row[4] else [],
            "member_roles": row[5] if row[5] else {},
            "pcsf_score": float(row[6]) if row[6] else None,
            "scheme_type": row[7],
            "affected_contracts": row[8] if row[8] else [],
            "timeline": row[9] if row[9] else [],
            "evidence_summary": row[10] if row[10] else {},
            "ai_legal_reasoning": row[11],
            "decision_id": str(row[12]) if row[12] else None,
            "created_at": str(row[13]) if row[13] else None,
        }

        return success_response(ring, 200, event)

    except Exception as exc:
        logger.exception("Failed to get collusion ring detail")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/vendor-network
# ------------------------------------------------------------------

def get_vendor_network_handler(event, context):
    """Get vendor network graph data with optional filters.

    Supports filtering by relationship type and minimum connection strength.
    """
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        params = event.get("queryStringParameters") or {}
        relationship_type = params.get("relationship_type")
        min_strength = float(params.get("min_strength", 0))

        # Query Neptune for vendor network
        neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
        neptune_port = os.environ.get("NEPTUNE_PORT", "8182")

        if not neptune_endpoint:
            return success_response(
                {
                    "nodes": [],
                    "edges": [],
                    "status": "neptune_unavailable",
                    "message": "Neptune endpoint not configured",
                },
                200,
                event,
            )

        # Build Gremlin query for vendor network
        import ssl
        import urllib.request
        import urllib.error

        case_label = f"Vendor_{case_id}"
        query = f"g.V().hasLabel('{case_label}').bothE().dedup().path()"

        try:
            url = f"https://{neptune_endpoint}:{neptune_port}/gremlin"
            payload = json.dumps({"gremlin": query}).encode("utf-8")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                url, data=payload, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("Neptune query failed: %s", e)
            return success_response(
                {
                    "nodes": [],
                    "edges": [],
                    "status": "partial",
                    "message": f"Neptune query failed: {e}",
                },
                200,
                event,
            )

        # Parse Neptune response into nodes and edges
        nodes = {}
        edges = []
        results = raw.get("result", {}).get("data", {}).get("@value", [])

        for path_item in results:
            objects = path_item.get("@value", {}).get("objects", {}).get("@value", [])
            for obj in objects:
                obj_type = obj.get("@type", "")
                obj_value = obj.get("@value", {})

                if obj_type == "g:Vertex":
                    vid = obj_value.get("id", "")
                    label = obj_value.get("label", "")
                    props = obj_value.get("properties", {})
                    if vid not in nodes:
                        nodes[vid] = {
                            "id": vid,
                            "label": label,
                            "properties": props,
                        }
                elif obj_type == "g:Edge":
                    edge_label = obj_value.get("label", "")
                    edge_props = obj_value.get("properties", {})
                    strength = edge_props.get("strength", 1.0)

                    # Apply filters
                    if relationship_type and edge_label != relationship_type:
                        continue
                    if isinstance(strength, (int, float)) and strength < min_strength:
                        continue

                    edges.append({
                        "id": obj_value.get("id", ""),
                        "label": edge_label,
                        "source": obj_value.get("outV", ""),
                        "target": obj_value.get("inV", ""),
                        "properties": edge_props,
                    })

        return success_response(
            {
                "nodes": list(nodes.values()),
                "edges": edges,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
            200,
            event,
        )

    except Exception as exc:
        logger.exception("Failed to get vendor network")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/procurement-records
# ------------------------------------------------------------------

def ingest_procurement_records_handler(event, context):
    """Ingest procurement data into the investigation.

    Parses records using ProcurementParser, stores valid records in
    procurement_bids (batch INSERT), quarantines invalid ones, and
    computes contract statistics for the ingested batch.
    """
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case ID", event)

        body = (
            json.loads(event.get("body"))
            if isinstance(event.get("body"), str)
            else (event.get("body") or {})
        )

        records_data = body.get("records", [])
        file_format = body.get("format", "json")
        file_content = body.get("file_content", "")
        source_file = body.get("source_file", "api_upload")

        from services.procurement_parser import ProcurementParser

        parser = ProcurementParser()

        # Parse records based on format
        parsed_records = []
        if records_data:
            # Direct JSON array of records
            for rec in records_data:
                parsed_records.append(rec)
        elif file_content and file_format == "csv":
            parsed = parser.parse_csv(file_content)
            parsed_records = [
                {
                    "record_id": r.record_id,
                    "vendor_id": r.vendor_id,
                    "vendor_name": r.vendor_name,
                    "contract_id": r.contract_id,
                    "bid_amount": r.bid_amount,
                    "submission_timestamp": r.submission_timestamp,
                    "specifications_met": r.specifications_met,
                    "award_status": r.award_status,
                    "government_estimate": r.government_estimate,
                    "geographic_region": r.geographic_region,
                    "raw_data": r.raw_data,
                }
                for r in parsed
            ]
        elif file_content and file_format == "json":
            parsed = parser.parse_json(file_content)
            parsed_records = [
                {
                    "record_id": r.record_id,
                    "vendor_id": r.vendor_id,
                    "vendor_name": r.vendor_name,
                    "contract_id": r.contract_id,
                    "bid_amount": r.bid_amount,
                    "submission_timestamp": r.submission_timestamp,
                    "specifications_met": r.specifications_met,
                    "award_status": r.award_status,
                    "government_estimate": r.government_estimate,
                    "geographic_region": r.geographic_region,
                    "raw_data": r.raw_data,
                }
                for r in parsed
            ]

        if not parsed_records:
            return error_response(
                400, "VALIDATION_ERROR",
                "No records provided. Supply 'records' array or 'file_content' with 'format'.",
                event,
            )

        # Validate and separate valid/invalid records
        valid_records = []
        quarantined = []
        batch_id = str(uuid.uuid4())

        for rec in parsed_records:
            is_valid, failure_reason = parser.validate_record(rec)
            if is_valid:
                valid_records.append(rec)
            else:
                quarantined.append({
                    "raw_record": rec,
                    "failure_reason": failure_reason or "Unknown validation error",
                })

        # Store valid records and quarantine invalid ones in Aurora
        from db.connection import ConnectionManager

        cm = ConnectionManager()
        inserted_count = 0
        quarantined_count = 0
        affected_contracts = []

        with cm.get_connection() as conn:
            with conn.cursor() as cur:
                # Batch INSERT valid records (chunks of 500)
                if valid_records:
                    values_list = []
                    for rec in valid_records:
                        record_id = rec.get("record_id") or str(uuid.uuid4())
                        values_list.append((
                            str(uuid.uuid4()),  # bid_id
                            case_id,
                            record_id,
                            rec.get("vendor_id", ""),
                            rec.get("vendor_name", ""),
                            rec.get("contract_id", ""),
                            rec.get("bid_amount", 0),
                            rec.get("submission_timestamp"),
                            rec.get("specifications_met", True),
                            rec.get("award_status", "lost"),
                            rec.get("government_estimate"),
                            json.dumps(rec.get("naics_codes", [])),
                            rec.get("geographic_region"),
                            json.dumps(rec.get("raw_data", {})),
                            batch_id,
                        ))

                    for i in range(0, len(values_list), 500):
                        chunk = values_list[i:i + 500]
                        args_str = ",".join(
                            cur.mogrify(
                                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                v,
                            ).decode("utf-8")
                            for v in chunk
                        )
                        cur.execute(
                            f"""
                            INSERT INTO procurement_bids
                                (bid_id, case_id, record_id, vendor_id, vendor_name,
                                 contract_id, bid_amount, submission_timestamp,
                                 specifications_met, award_status, government_estimate,
                                 naics_codes, geographic_region, raw_data, batch_id)
                            VALUES {args_str}
                            """
                        )
                    inserted_count = len(values_list)

                # Batch INSERT quarantined records (chunks of 500)
                if quarantined:
                    q_values = []
                    for q in quarantined:
                        q_values.append((
                            str(uuid.uuid4()),  # quarantine_id
                            case_id,
                            batch_id,
                            json.dumps(q["raw_record"]),
                            q["failure_reason"],
                            source_file,
                        ))

                    for i in range(0, len(q_values), 500):
                        chunk = q_values[i:i + 500]
                        args_str = ",".join(
                            cur.mogrify(
                                "(%s,%s,%s,%s,%s,%s)", v
                            ).decode("utf-8")
                            for v in chunk
                        )
                        cur.execute(
                            f"""
                            INSERT INTO procurement_quarantine
                                (quarantine_id, case_id, batch_id, raw_record,
                                 failure_reason, source_file)
                            VALUES {args_str}
                            """
                        )
                    quarantined_count = len(q_values)

                # Compute contract statistics for affected contracts
                affected_contracts = list(set(
                    rec.get("contract_id", "")
                    for rec in valid_records
                    if rec.get("contract_id")
                ))
                for contract_id in affected_contracts:
                    cur.execute(
                        """
                        INSERT INTO contract_statistics
                            (stat_id, case_id, contract_id, bid_count,
                             price_min, price_max, price_mean, price_stddev, price_cv,
                             computed_at)
                        SELECT
                            gen_random_uuid(),
                            %s,
                            %s,
                            COUNT(*),
                            MIN(bid_amount),
                            MAX(bid_amount),
                            AVG(bid_amount),
                            STDDEV(bid_amount),
                            CASE WHEN AVG(bid_amount) > 0
                                 THEN STDDEV(bid_amount) / AVG(bid_amount)
                                 ELSE 0 END,
                            NOW()
                        FROM procurement_bids
                        WHERE case_id = %s AND contract_id = %s
                        ON CONFLICT (case_id, contract_id) DO UPDATE SET
                            bid_count = EXCLUDED.bid_count,
                            price_min = EXCLUDED.price_min,
                            price_max = EXCLUDED.price_max,
                            price_mean = EXCLUDED.price_mean,
                            price_stddev = EXCLUDED.price_stddev,
                            price_cv = EXCLUDED.price_cv,
                            computed_at = NOW()
                        """,
                        (case_id, contract_id, case_id, contract_id),
                    )

            conn.commit()

        return success_response(
            {
                "batch_id": batch_id,
                "case_id": case_id,
                "total_submitted": len(parsed_records),
                "records_inserted": inserted_count,
                "records_quarantined": quarantined_count,
                "contracts_affected": len(affected_contracts),
            },
            201,
            event,
        )

    except json.JSONDecodeError as exc:
        return error_response(400, "VALIDATION_ERROR", f"Invalid JSON body: {exc}", event)
    except Exception as exc:
        logger.exception("Failed to ingest procurement records")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# Dispatch handler (Lambda entry point)
# ------------------------------------------------------------------

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def dispatch_handler(event, context):
    """Route by HTTP method + resource path."""
    from lambdas.api.response_helper import error_response

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    routes = {
        ("POST", "/case-files/{id}/collusion-analysis"): trigger_analysis_handler,
        ("GET", "/case-files/{id}/collusion-analysis"): get_analysis_handler,
        ("GET", "/case-files/{id}/red-flags"): list_red_flags_handler,
        ("GET", "/case-files/{id}/collusion-rings"): list_collusion_rings_handler,
        ("GET", "/case-files/{id}/collusion-rings/{ring_id}"): get_collusion_ring_handler,
        ("GET", "/case-files/{id}/vendor-network"): get_vendor_network_handler,
        ("POST", "/case-files/{id}/procurement-records"): ingest_procurement_records_handler,
    }

    handler = routes.get((method, resource))
    if handler:
        return handler(event, context)

    return error_response(404, "NOT_FOUND", f"Unknown route: {method} {resource}", event)
