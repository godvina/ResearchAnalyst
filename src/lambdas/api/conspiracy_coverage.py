"""API Handlers for Conspiracy Theory Taxonomy Coverage Monitoring.

Endpoints:
- GET /taxonomy/conspiracy/coverage — taxonomy coverage metrics
- GET /taxonomy/conspiracy/cross-theory-report — cross-theory connection analytics
- GET /taxonomy/conspiracy/processing-status — validation pipeline status for all theories
- POST /proof/evaluate — trigger proof engine evaluation for a finding
- GET /proof/{finding_id} — retrieve proof verdict for a finding
"""
import json
from datetime import datetime, timezone


def get_coverage_handler(event, context):
    """GET /taxonomy/conspiracy/coverage
    
    Returns taxonomy coverage metrics: domain counts, balance score,
    under-specified domains.
    """
    from src.services.conspiracy_taxonomy_service import ConspiracyTaxonomyService

    # Initialize service (connection_manager would be injected in production)
    service = ConspiracyTaxonomyService(connection_manager=None)

    try:
        report = service.get_coverage_report()
        response = {
            "total_domains": report.total_domains,
            "total_typologies": report.total_typologies,
            "total_methods": report.total_methods,
            "total_signatures": report.total_signatures,
            "total_precedent_cases": report.total_precedent_cases,
            "per_domain": report.per_domain,
            "balance_score": report.balance_score,
            "under_specified_domains": report.under_specified_domains,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        return _success_response(response)
    except Exception as e:
        return _error_response(500, f"Coverage report generation failed: {str(e)}")


def get_cross_theory_report_handler(event, context):
    """GET /taxonomy/conspiracy/cross-theory-report
    
    Returns cross-theory connection analytics: total connections,
    per-pair counts, most-connected signatures, theories with zero connections.
    """
    # In production, this would query Neptune for cross_connects edges
    # and Aurora for signature_matches across theories

    try:
        response = {
            "total_connections": 0,
            "connections_per_theory_pair": [],
            "most_connected_signatures": [],
            "theories_with_zero_connections": [
                "bermuda_triangle", "princess_diana", "flat_earth",
                "ufos_uaps", "jfk_assassination", "nine_eleven",
                "covid_lab_leak", "moon_landing", "vaccine_conspiracies",
                "new_world_order"
            ],
            "universal_confirmed_signatures": 0,
            "average_reproducibility_score": 0.0,
            "note": "Cross-theory detection runs after seeding and validation pipelines complete",
        }
        return _success_response(response)
    except Exception as e:
        return _error_response(500, f"Cross-theory report failed: {str(e)}")


def get_processing_status_handler(event, context):
    """GET /taxonomy/conspiracy/processing-status
    
    Returns validation pipeline status for all 10 theories.
    """
    from src.services.conspiracy_validation_pipeline import ConspiracyValidationPipeline

    pipeline = ConspiracyValidationPipeline(connection_manager=None)

    try:
        # Without DB, return the static processing order info
        status = {
            "processing_order": pipeline.PROCESSING_ORDER,
            "ungated_theories": pipeline.UNGATED_THEORIES,
            "current_status": [
                {"theory_name": t, "status": "pending"} for t in pipeline.PROCESSING_ORDER
            ] + [
                {"theory_name": t, "status": "pending"} for t in pipeline.UNGATED_THEORIES
            ],
            "next_theory_to_process": pipeline.PROCESSING_ORDER[0],
        }
        return _success_response(status)
    except Exception as e:
        return _error_response(500, f"Processing status failed: {str(e)}")


def evaluate_proof_handler(event, context):
    """POST /proof/evaluate
    
    Trigger proof engine evaluation for a finding.
    Body: {finding_id, standard_override (optional), evidence (optional)}
    """
    from src.services.proof_engine import ProofEngine

    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _error_response(400, "Invalid JSON body")

    finding_id = body.get('finding_id')
    if not finding_id:
        return _error_response(400, "finding_id is required")

    standard = body.get('standard_override', 'intelligence')  # Default for conspiracy tenant
    evidence = body.get('evidence', '')
    finding_data = body.get('finding_data', {})

    engine = ProofEngine(bedrock_client=None, connection_manager=None)

    try:
        verdict = engine.evaluate(
            finding_id=finding_id,
            finding_data=finding_data,
            evidence=evidence,
            standard_name=standard,
            tenant_id="conspiracy_theories"
        )
        return _success_response(verdict.to_dict())
    except Exception as e:
        return _error_response(500, f"Proof evaluation failed: {str(e)}")


def get_proof_handler(event, context):
    """GET /proof/{finding_id}
    
    Retrieve the most recent proof verdict for a finding.
    """
    finding_id = event.get('pathParameters', {}).get('finding_id')
    if not finding_id:
        return _error_response(400, "finding_id path parameter required")

    # In production, query Aurora proof_verdicts table
    response = {
        "finding_id": finding_id,
        "verdict": "INSUFFICIENT_EVIDENCE",
        "message": "No proof evaluation has been run for this finding yet. POST to /proof/evaluate to trigger.",
    }
    return _success_response(response)


# ============================================================
# RESPONSE HELPERS
# ============================================================

def _success_response(body: dict, status_code: int = 200) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def _error_response(status_code: int, message: str) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": message}),
    }
