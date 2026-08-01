"""API Lambda handler for antitrust pre-case intelligence.

Routes single HTTP requests to handler functions. No bulk processing,
no EC2 launches, no direct Bedrock calls (delegated to sub-services).

Endpoints:
    POST /pre-case/leads                        - submit new lead
    GET  /pre-case/leads                        - list leads with filters
    GET  /pre-case/leads/{lead_id}              - get lead detail
    POST /pre-case/leads/{lead_id}/classify     - trigger classification
    POST /pre-case/leads/{lead_id}/gather       - trigger OSINT gathering
    GET  /pre-case/leads/{lead_id}/assessment   - get assessment
    POST /pre-case/leads/{lead_id}/assess       - trigger assessment
    POST /pre-case/leads/{lead_id}/open-case    - promote to investigation
    PATCH /pre-case/leads/{lead_id}             - update lead
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
}


def _build_pre_case_intelligence_service():
    """Construct PreCaseIntelligenceService with all dependencies from env vars."""
    import boto3

    from db.connection import ConnectionManager
    from services.case_type_classifier import CaseTypeClassifier
    from services.osint_data_gatherer import OsintDataGatherer
    from services.prosecution_readiness_assessment import ProsecutionReadinessAssessment
    from services.pre_case_trawler import PreCaseTrawler
    from services.decision_workflow_service import DecisionWorkflowService
    from services.bulk_ingestion_service import BulkIngestionService
    from services.cross_case_pattern_detector import CrossCasePatternDetector
    from services.pre_case_intelligence_service import PreCaseIntelligenceService

    aurora_cm = ConnectionManager()
    bedrock = boto3.client("bedrock-runtime")
    neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")
    s3_bucket = os.environ.get("S3_BUCKET", "")

    s3_client = boto3.client("s3")
    redshift_client = boto3.client("redshift-data")

    case_type_classifier = CaseTypeClassifier(
        bedrock_client=bedrock,
        aurora_cm=aurora_cm,
    )

    osint_gatherer = OsintDataGatherer(
        aurora_cm=aurora_cm,
        redshift_client=redshift_client,
        neptune_endpoint=neptune_endpoint,
        neptune_port=neptune_port,
        s3_client=s3_client,
        s3_bucket=s3_bucket,
    )

    prosecution_assessment = ProsecutionReadinessAssessment(
        bedrock_client=bedrock,
        aurora_cm=aurora_cm,
    )

    decision_workflow_svc = DecisionWorkflowService(aurora_cm)

    bulk_ingestion_svc = BulkIngestionService(
        redshift_client=redshift_client,
        aurora_cm=aurora_cm,
        s3_client=s3_client,
    )

    cross_case_detector = CrossCasePatternDetector(
        redshift_client=redshift_client,
        aurora_cm=aurora_cm,
        bedrock_client=bedrock,
    )

    pre_case_trawler = None
    try:
        from services.trawler_service import TrawlerEngine

        trawler_engine = TrawlerEngine(aurora_cm=aurora_cm)
        pre_case_trawler = PreCaseTrawler(
            trawler_engine=trawler_engine,
            osint_gatherer=osint_gatherer,
            prosecution_assessment=prosecution_assessment,
            aurora_cm=aurora_cm,
        )
    except Exception as e:
        logger.warning(f"PreCaseTrawler not available: {e}")

    return PreCaseIntelligenceService(
        aurora_cm=aurora_cm,
        redshift_client=redshift_client,
        neptune_endpoint=neptune_endpoint,
        neptune_port=neptune_port,
        bedrock_client=bedrock,
        case_type_classifier=case_type_classifier,
        osint_gatherer=osint_gatherer,
        prosecution_assessment=prosecution_assessment,
        pre_case_trawler=pre_case_trawler,
        decision_workflow_svc=decision_workflow_svc,
        bulk_ingestion_svc=bulk_ingestion_svc,
        cross_case_detector=cross_case_detector,
    )


# ------------------------------------------------------------------
# POST /pre-case/leads
# ------------------------------------------------------------------

def submit_lead_handler(event, context):
    """Submit a new pre-case lead."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})

        if not body.get("title"):
            return error_response(400, "VALIDATION_ERROR", "Missing required field: title", event)

        if not body.get("source_type"):
            return error_response(400, "VALIDATION_ERROR", "Missing required field: source_type", event)

        svc = _build_pre_case_intelligence_service()
        result = svc.submit_lead(body)

        return success_response(result, 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to submit lead")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/leads
# ------------------------------------------------------------------

def list_leads_handler(event, context):
    """List pre-case leads with pagination and filtering."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        params = event.get("queryStringParameters") or {}

        filters = {}
        if params.get("case_type"):
            filters["case_type"] = params["case_type"]
        if params.get("status"):
            filters["status"] = params["status"]
        if params.get("priority"):
            filters["priority"] = params["priority"]
        if params.get("assigned_analyst"):
            filters["assigned_analyst"] = params["assigned_analyst"]
        if params.get("min_score"):
            filters["min_score"] = int(params["min_score"])
        if params.get("max_score"):
            filters["max_score"] = int(params["max_score"])

        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 50))

        svc = _build_pre_case_intelligence_service()
        result = svc.list_leads(filters=filters, page=page, page_size=page_size)

        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Failed to list leads")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/leads/{lead_id}
# ------------------------------------------------------------------

def get_lead_handler(event, context):
    """Get complete lead detail."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        svc = _build_pre_case_intelligence_service()
        result = svc.get_lead_detail(lead_id)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get lead detail")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/classify
# ------------------------------------------------------------------

def classify_lead_handler(event, context):
    """Trigger classification or reclassification of a lead."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})
        additional_context = body.get("additional_context", "")

        svc = _build_pre_case_intelligence_service()
        result = svc.classify_lead(lead_id, additional_context=additional_context)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to classify lead")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/gather
# ------------------------------------------------------------------

def gather_osint_handler(event, context):
    """Trigger OSINT data gathering for a lead."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})
        sources = body.get("sources")
        subjects = body.get("subjects")

        svc = _build_pre_case_intelligence_service()
        result = svc.gather_osint(lead_id, sources=sources, subjects=subjects)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to gather OSINT")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/leads/{lead_id}/assessment
# ------------------------------------------------------------------

def get_assessment_handler(event, context):
    """Get the current assessment for a lead."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        svc = _build_pre_case_intelligence_service()
        lead_detail = svc.get_lead_detail(lead_id)
        assessments = lead_detail.get("assessments", [])

        if not assessments:
            return error_response(404, "NOT_FOUND", f"No assessment found for lead {lead_id}", event)

        return success_response({"lead_id": lead_id, "assessment": assessments[0]}, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get assessment")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/assess
# ------------------------------------------------------------------

def trigger_assessment_handler(event, context):
    """Trigger a fresh prosecution readiness assessment."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        svc = _build_pre_case_intelligence_service()
        result = svc.assess_lead(lead_id)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to trigger assessment")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/open-case
# ------------------------------------------------------------------

def open_case_handler(event, context):
    """Promote a pre-case lead to a formal investigation."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})
        prosecutor_id = body.get("prosecutor_id", "")
        if not prosecutor_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: prosecutor_id", event)

        svc = _build_pre_case_intelligence_service()
        result = svc.promote_to_investigation(lead_id, prosecutor_id)

        return success_response(result, 201, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to open case")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PATCH /pre-case/leads/{lead_id}
# ------------------------------------------------------------------

def update_lead_handler(event, context):
    """Update lead priority, analyst, frequency, or status."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})
        if not body:
            return error_response(400, "VALIDATION_ERROR", "Request body is empty", event)

        svc = _build_pre_case_intelligence_service()
        result = svc.update_lead(lead_id, body)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to update lead")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/backlog
# ------------------------------------------------------------------

def get_backlog_handler(event, context):
    """Return ranked case backlog with computed scores."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        params = event.get("queryStringParameters") or {}

        filters = {}
        if params.get("case_type"):
            filters["case_type"] = params["case_type"]
        if params.get("priority"):
            filters["priority"] = params["priority"]
        if params.get("min_score"):
            filters["min_score"] = float(params["min_score"])

        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 25))

        from db.connection import ConnectionManager
        from services.backlog_scoring_service import BacklogScoringService
        from services.policy_priority_service import PolicyPriorityService

        aurora_cm = ConnectionManager()
        policy_svc = PolicyPriorityService(aurora_cm)
        backlog_svc = BacklogScoringService(aurora_cm, policy_provider=policy_svc)

        result = backlog_svc.get_ranked_backlog(filters=filters, page=page, page_size=page_size)

        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("Failed to get backlog")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/run-pipeline
# ------------------------------------------------------------------

def run_pipeline_handler(event, context):
    """Trigger full pipeline execution (classify → gather → assess)."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        svc = _build_pre_case_intelligence_service()
        result = svc.run_pipeline(lead_id)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to run pipeline")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/leads/{lead_id}/pipeline-status
# ------------------------------------------------------------------

def get_pipeline_status_handler(event, context):
    """Get current pipeline execution status."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        svc = _build_pre_case_intelligence_service()
        result = svc.get_pipeline_status(lead_id)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get pipeline status")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/policy-priorities
# ------------------------------------------------------------------

def get_policy_priorities_handler(event, context):
    """Return all active (non-expired) policy directives."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        from db.connection import ConnectionManager
        from services.policy_priority_service import PolicyPriorityService

        aurora_cm = ConnectionManager()
        policy_svc = PolicyPriorityService(aurora_cm)
        policies = policy_svc.get_active_policies()

        return success_response({"policies": policies, "count": len(policies)}, 200, event)

    except Exception as exc:
        logger.exception("Failed to get policy priorities")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/policy-priorities
# ------------------------------------------------------------------

def create_policy_priority_handler(event, context):
    """Create or update a policy priority directive."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})

        if not body.get("directive_title"):
            return error_response(400, "VALIDATION_ERROR", "Missing required field: directive_title", event)
        if not body.get("source"):
            return error_response(400, "VALIDATION_ERROR", "Missing required field: source", event)
        if not body.get("effective_date"):
            return error_response(400, "VALIDATION_ERROR", "Missing required field: effective_date", event)
        if not body.get("boost_multiplier"):
            return error_response(400, "VALIDATION_ERROR", "Missing required field: boost_multiplier", event)

        from db.connection import ConnectionManager
        from services.policy_priority_service import PolicyPriorityService

        aurora_cm = ConnectionManager()
        policy_svc = PolicyPriorityService(aurora_cm)
        result = policy_svc.create_or_update_policy(body)

        return success_response(result, 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create policy priority")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/generate-brief
# ------------------------------------------------------------------

def generate_brief_handler(event, context):
    """Generate an AI investigative intelligence brief for a lead."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        # Fetch full lead detail
        svc = _build_pre_case_intelligence_service()
        lead_detail = svc.get_lead_detail(lead_id)

        # Extract components for the brief service
        lead_data = lead_detail.get("lead", {})
        osint_data = lead_detail.get("osint_data", [])
        classifications = lead_detail.get("classifications", [])
        assessments = lead_detail.get("assessments", [])

        classification = classifications[0] if classifications else None
        assessment = assessments[0] if assessments else None

        # Generate the brief
        import boto3
        from services.investigative_brief_service import InvestigativeBriefService

        bedrock = boto3.client("bedrock-runtime")
        brief_svc = InvestigativeBriefService(bedrock_client=bedrock)
        brief = brief_svc.generate_brief(
            lead_data=lead_data,
            osint_data=osint_data,
            classification=classification,
            assessment=assessment,
        )

        return success_response({"lead_id": lead_id, "brief": brief}, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to generate brief")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/leads/{lead_id}/findings
# ------------------------------------------------------------------

def get_findings_handler(event, context):
    """Return paginated findings with signal scores for a lead."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        params = event.get("queryStringParameters") or {}
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 25))

        sms = _build_signal_mining_service()
        result = sms.get_findings(lead_id, page=page, page_size=page_size)

        return success_response(result.to_dict(), 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get findings")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/findings/{finding_id}/drill-down
# ------------------------------------------------------------------

def drill_down_handler(event, context):
    """Trigger a drill-down cycle for a specific finding."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        path_params = event.get("pathParameters") or {}
        lead_id = path_params.get("lead_id", "")
        finding_id = path_params.get("finding_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)
        if not finding_id:
            return error_response(400, "VALIDATION_ERROR", "Missing finding_id", event)

        sms = _build_signal_mining_service()
        result = sms.trigger_drill_down(lead_id, finding_id)

        return success_response(result.to_dict(), 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to execute drill-down")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /pre-case/leads/{lead_id}/investigate
# ------------------------------------------------------------------

def investigate_handler(event, context):
    """Accept a natural language directive and return findings."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})
        directive = body.get("directive", "")
        if not directive:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: directive", event)

        sms = _build_signal_mining_service()
        result = sms.execute_search(lead_id, directive)

        return success_response(result.to_dict(), 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to execute investigation directive")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /pre-case/leads/{lead_id}/iov-taxonomy
# ------------------------------------------------------------------

def get_iov_taxonomy_handler(event, context):
    """Return the IoV hierarchy for the lead's classified case type."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        # Get case_type from lead
        svc = _build_pre_case_intelligence_service()
        lead_detail = svc.get_lead_detail(lead_id)
        lead = lead_detail.get("lead", {})
        case_type = lead.get("case_type")

        if not case_type:
            return error_response(422, "VALIDATION_ERROR", "Lead has no classified case_type", event)

        import boto3
        from services.iov_taxonomy_service import IovTaxonomyService

        s3_client = boto3.client("s3")
        s3_bucket = os.environ.get("S3_BUCKET", "research-analyst-data-lake-974220725866")
        iov_svc = IovTaxonomyService(s3_client=s3_client, s3_bucket=s3_bucket)
        hierarchy = iov_svc.load_taxonomy(case_type)

        return success_response({
            "lead_id": lead_id,
            "case_type": hierarchy.case_type,
            "version": hierarchy.version,
            "categories": hierarchy.categories,
        }, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get IoV taxonomy")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PATCH /pre-case/leads/{lead_id}/monitoring
# ------------------------------------------------------------------

def update_monitoring_handler(event, context):
    """Update monitoring configuration (enabled, frequency)."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        lead_id = (event.get("pathParameters") or {}).get("lead_id", "")
        if not lead_id:
            return error_response(400, "VALIDATION_ERROR", "Missing lead_id", event)

        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else (event.get("body") or {})

        from db.connection import ConnectionManager

        aurora_cm = ConnectionManager()
        enabled = body.get("enabled")
        frequency = body.get("frequency", "weekly")

        # Upsert signal_mining_monitoring
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        freq_days = {"daily": 1, "weekly": 7, "monthly": 30}
        next_scan = now + timedelta(days=freq_days.get(frequency, 7)) if enabled else None

        with aurora_cm.cursor() as cur:
            cur.execute(
                """
                INSERT INTO signal_mining_monitoring
                    (lead_id, enabled, frequency, next_scan_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (lead_id) DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    frequency = EXCLUDED.frequency,
                    next_scan_at = EXCLUDED.next_scan_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (lead_id, enabled, frequency, next_scan, now, now),
            )

        return success_response({
            "lead_id": lead_id,
            "enabled": enabled,
            "frequency": frequency,
            "next_scan_at": next_scan.isoformat() if next_scan else None,
        }, 200, event)

    except Exception as exc:
        logger.exception("Failed to update monitoring config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# Signal Mining Service Builder
# ------------------------------------------------------------------

def _build_signal_mining_service():
    """Construct SignalMiningService with all dependencies."""
    import boto3

    from db.connection import ConnectionManager
    from services.iov_taxonomy_service import IovTaxonomyService
    from services.signal_scorer import SignalScorer
    from services.drill_down_engine import DrillDownEngine
    from services.investigator_search_service import InvestigatorSearchService
    from services.signal_mining_service import SignalMiningService
    from services.osint_data_gatherer import OsintDataGatherer

    aurora_cm = ConnectionManager()
    bedrock = boto3.client("bedrock-runtime")
    s3_client = boto3.client("s3")
    s3_bucket = os.environ.get("S3_BUCKET", "research-analyst-data-lake-974220725866")
    neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
    neptune_port = os.environ.get("NEPTUNE_PORT", "8182")
    redshift_client = boto3.client("redshift-data")

    iov_taxonomy_service = IovTaxonomyService(s3_client=s3_client, s3_bucket=s3_bucket)
    signal_scorer = SignalScorer()

    osint_gatherer = OsintDataGatherer(
        aurora_cm=aurora_cm,
        redshift_client=redshift_client,
        neptune_endpoint=neptune_endpoint,
        neptune_port=neptune_port,
        s3_client=s3_client,
        s3_bucket=s3_bucket,
    )

    drill_down_engine = DrillDownEngine(
        bedrock_client=bedrock,
        osint_gatherer=osint_gatherer,
        signal_scorer=signal_scorer,
        iov_taxonomy_service=iov_taxonomy_service,
    )

    investigator_search_service = InvestigatorSearchService(
        bedrock_client=bedrock,
        osint_gatherer=osint_gatherer,
        signal_scorer=signal_scorer,
        iov_taxonomy_service=iov_taxonomy_service,
    )

    return SignalMiningService(
        aurora_cm=aurora_cm,
        iov_taxonomy_service=iov_taxonomy_service,
        signal_scorer=signal_scorer,
        drill_down_engine=drill_down_engine,
        investigator_search_service=investigator_search_service,
    )


# ------------------------------------------------------------------
# Dispatch handler (Lambda entry point)
# ------------------------------------------------------------------

def dispatch_handler(event, context):
    """Route by HTTP method + resource path."""
    from lambdas.api.response_helper import error_response

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    routes = {
        ("POST", "/pre-case/leads"): submit_lead_handler,
        ("GET", "/pre-case/leads"): list_leads_handler,
        ("GET", "/pre-case/leads/{lead_id}"): get_lead_handler,
        ("POST", "/pre-case/leads/{lead_id}/classify"): classify_lead_handler,
        ("POST", "/pre-case/leads/{lead_id}/gather"): gather_osint_handler,
        ("GET", "/pre-case/leads/{lead_id}/assessment"): get_assessment_handler,
        ("POST", "/pre-case/leads/{lead_id}/assess"): trigger_assessment_handler,
        ("POST", "/pre-case/leads/{lead_id}/open-case"): open_case_handler,
        ("PATCH", "/pre-case/leads/{lead_id}"): update_lead_handler,
        ("GET", "/pre-case/backlog"): get_backlog_handler,
        ("POST", "/pre-case/leads/{lead_id}/run-pipeline"): run_pipeline_handler,
        ("GET", "/pre-case/leads/{lead_id}/pipeline-status"): get_pipeline_status_handler,
        ("POST", "/pre-case/leads/{lead_id}/generate-brief"): generate_brief_handler,
        ("GET", "/pre-case/policy-priorities"): get_policy_priorities_handler,
        ("POST", "/pre-case/policy-priorities"): create_policy_priority_handler,
        # Signal Mining routes
        ("GET", "/pre-case/leads/{lead_id}/findings"): get_findings_handler,
        ("POST", "/pre-case/leads/{lead_id}/findings/{finding_id}/drill-down"): drill_down_handler,
        ("POST", "/pre-case/leads/{lead_id}/investigate"): investigate_handler,
        ("GET", "/pre-case/leads/{lead_id}/iov-taxonomy"): get_iov_taxonomy_handler,
        ("PATCH", "/pre-case/leads/{lead_id}/monitoring"): update_monitoring_handler,
    }

    handler = routes.get((method, resource))
    if handler:
        return handler(event, context)

    return error_response(404, "NOT_FOUND", f"Unknown route: {method} {resource}", event)
