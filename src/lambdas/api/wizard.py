"""API Lambda handlers for the Pipeline Configuration Wizard.

Endpoints:
    POST /wizard/generate-config     — generate Pipeline_Config from answers
    POST /wizard/estimate-cost       — generate cost estimate
    POST /wizard/create-case         — create case with generated config
    GET  /wizard/templates           — list available config templates
    POST /wizard/export-summary      — generate shareable HTML summary
    POST /wizard/save-progress       — save partial wizard state
    GET  /wizard/load-progress/{id}  — load saved wizard state
"""

import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _build_wizard_service():
    """Construct WizardService with dependencies."""
    import boto3

    from db.connection import ConnectionManager
    from services.cost_estimation_service import CostEstimationService
    from services.wizard_service import WizardService

    aurora_cm = ConnectionManager()
    bedrock_client = boto3.client("bedrock-runtime")
    cost_svc = CostEstimationService()
    return WizardService(aurora_cm, bedrock_client, cost_svc), aurora_cm


def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if resource == "/wizard/generate-config" and method == "POST":
        return generate_config_handler(event, context)
    if resource == "/wizard/estimate-cost" and method == "POST":
        return estimate_cost_handler(event, context)
    if resource == "/wizard/create-case" and method == "POST":
        return create_case_handler(event, context)
    if resource == "/wizard/templates" and method == "GET":
        return list_templates_handler(event, context)
    if resource == "/wizard/export-summary" and method == "POST":
        return export_summary_handler(event, context)
    if resource == "/wizard/save-progress" and method == "POST":
        return save_progress_handler(event, context)
    if resource == "/wizard/load-progress/{id}" and method == "GET":
        return load_progress_handler(event, context)
    if resource == "/wizard/generate-deployment" and method == "POST":
        return generate_deployment_handler(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# POST /wizard/generate-config
# ------------------------------------------------------------------

def generate_config_handler(event, context):
    """Generate a Pipeline_Config from wizard answers."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        answers = body.get("answers", {})
        if not answers:
            return error_response(400, "VALIDATION_ERROR", "Missing 'answers' in request body", event)

        svc, _ = _build_wizard_service()
        config = svc.generate_config(answers)
        return success_response({"config": config}, 200, event)

    except Exception as exc:
        logger.exception("generate_config failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /wizard/estimate-cost
# ------------------------------------------------------------------

def estimate_cost_handler(event, context):
    """Generate a cost estimate from answers and config."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        answers = body.get("answers", {})
        config = body.get("config", {})
        if not answers:
            return error_response(400, "VALIDATION_ERROR", "Missing 'answers' in request body", event)

        svc, _ = _build_wizard_service()
        estimate = svc.estimate_cost(answers, config)
        return success_response({"estimate": estimate}, 200, event)

    except Exception as exc:
        logger.exception("estimate_cost failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /wizard/create-case
# ------------------------------------------------------------------

def create_case_handler(event, context):
    """Create a new case with the generated pipeline config."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        case_name = body.get("case_name", "").strip()
        config = body.get("config", {})
        answers = body.get("answers", {})
        created_by = body.get("created_by", "wizard")

        if not case_name:
            return error_response(400, "VALIDATION_ERROR", "Missing 'case_name'", event)

        _, aurora_cm = _build_wizard_service()

        # Create case file
        with aurora_cm.cursor() as cur:
            cur.execute(
                """
                INSERT INTO case_files (topic_name, status, case_category, created_by)
                VALUES (%s, 'created', %s, %s)
                RETURNING case_id
                """,
                (case_name, answers.get("investigation_type", "general"), created_by),
            )
            case_id = str(cur.fetchone()[0])

            # Apply pipeline config
            if config:
                from services.config_validation_service import ConfigValidationService
                validator = ConfigValidationService()
                errors = validator.validate(config)
                if errors:
                    return error_response(
                        400, "VALIDATION_ERROR",
                        f"Config validation failed: {[e.field_path for e in errors]}",
                        event,
                    )
                cur.execute(
                    """
                    INSERT INTO pipeline_configs (case_id, version, config_json, created_by, is_active)
                    VALUES (%s, 1, %s, %s, TRUE)
                    """,
                    (case_id, json.dumps(config), created_by),
                )

        return success_response({"case_id": case_id, "case_name": case_name}, 201, event)

    except Exception as exc:
        logger.exception("create_case failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /wizard/templates
# ------------------------------------------------------------------

def list_templates_handler(event, context):
    """List available config templates."""
    from lambdas.api.response_helper import success_response
    from services.config_validation_service import CONFIG_TEMPLATES

    templates = [
        {"name": name, "config": cfg}
        for name, cfg in CONFIG_TEMPLATES.items()
    ]
    return success_response({"templates": templates}, 200, event)


# ------------------------------------------------------------------
# POST /wizard/export-summary
# ------------------------------------------------------------------

def export_summary_handler(event, context):
    """Generate a shareable HTML summary."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        answers = body.get("answers", {})
        config = body.get("config", {})
        cost = body.get("cost", {})

        svc, _ = _build_wizard_service()
        html = svc.generate_summary(answers, config, cost)
        return success_response({"html": html}, 200, event)

    except Exception as exc:
        logger.exception("export_summary failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /wizard/save-progress
# ------------------------------------------------------------------

def save_progress_handler(event, context):
    """Save partial wizard state."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        progress_id = body.get("progress_id")
        answers = body.get("answers", {})

        svc, _ = _build_wizard_service()
        pid = svc.save_progress(progress_id, answers)
        return success_response({"progress_id": pid}, 200, event)

    except Exception as exc:
        logger.exception("save_progress failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /wizard/load-progress/{id}
# ------------------------------------------------------------------

def load_progress_handler(event, context):
    """Load saved wizard state."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        progress_id = (event.get("pathParameters") or {}).get("id", "")
        if not progress_id:
            return error_response(400, "VALIDATION_ERROR", "Missing progress ID", event)

        svc, _ = _build_wizard_service()
        answers = svc.load_progress(progress_id)
        return success_response({"progress_id": progress_id, "answers": answers}, 200, event)

    except ValueError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("load_progress failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /wizard/generate-deployment
# ------------------------------------------------------------------

def generate_deployment_handler(event, context):
    """Generate a one-click deployment package from wizard answers."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        answers = body.get("answers", {})
        config = body.get("config", {})
        cost_estimate = body.get("cost_estimate", {})

        if not answers:
            return error_response(400, "VALIDATION_ERROR", "Missing 'answers' in request body", event)
        if not config:
            return error_response(400, "VALIDATION_ERROR", "Missing 'config' in request body", event)

        from services.deployment_generator import DeploymentGenerator

        generator = DeploymentGenerator()
        bundle = generator.generate_bundle(answers, config, cost_estimate)

        return success_response({
            "cfn_template": bundle["cfn_template"],
            "deployment_guide": bundle["deployment_guide"],
            "pipeline_config": bundle["pipeline_config"],
            "cost_estimate": bundle["cost_estimate"],
            "bundle_contents": bundle["bundle_contents"],
        }, 200, event)

    except FileNotFoundError as exc:
        logger.exception("generate_deployment failed — template not found")
        return error_response(500, "TEMPLATE_NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("generate_deployment failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
