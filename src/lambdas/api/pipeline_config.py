"""API Lambda handlers for Pipeline Configuration endpoints.

Endpoints:
    GET    /case-files/{id}/pipeline-config                          — get effective config
    PUT    /case-files/{id}/pipeline-config                          — update config
    GET    /case-files/{id}/pipeline-config/versions                  — list versions
    GET    /case-files/{id}/pipeline-config/versions/{v}              — get specific version
    POST   /case-files/{id}/pipeline-config/rollback                  — rollback to version
    POST   /case-files/{id}/pipeline-config/export                    — export active config
    POST   /case-files/{id}/pipeline-config/import                    — import config
    POST   /case-files/{id}/pipeline-config/template                  — apply template
    POST   /case-files/{id}/sample-runs                               — start sample run
    GET    /case-files/{id}/sample-runs                               — list sample runs
    GET    /case-files/{id}/sample-runs/{run_id}                      — get sample run
    POST   /case-files/{id}/sample-runs/compare                       — compare two runs
    GET    /case-files/{id}/pipeline-runs                              — list pipeline runs
    GET    /case-files/{id}/pipeline-runs/{run_id}                     — get run metrics
    GET    /case-files/{id}/pipeline-runs/{run_id}/steps/{step}        — get step details
    GET    /system/default-config                                      — get system default
    PUT    /system/default-config                                      — update system default
    POST   /system/default-config/export                               — export system default
    POST   /system/default-config/import                               — import system default
    GET    /triage-queue                                               — list triage queue
    POST   /triage-queue/{docId}/assign                                — assign from triage
    POST   /triage-queue/{docId}/create-case                           — create case from triage
"""

import json
import logging
import os
from datetime import datetime, timezone

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@with_access_control
def dispatch_handler(event, context):
    """Route to the correct handler based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # --- Pipeline config endpoints ---
    if resource == "/case-files/{id}/pipeline-config" and method == "GET":
        return get_effective_config(event, context)
    if resource == "/case-files/{id}/pipeline-config" and method == "PUT":
        return update_config(event, context)
    if resource == "/case-files/{id}/pipeline-config/versions" and method == "GET":
        return list_versions(event, context)
    if resource == "/case-files/{id}/pipeline-config/versions/{v}" and method == "GET":
        return get_version(event, context)
    if resource == "/case-files/{id}/pipeline-config/rollback" and method == "POST":
        return rollback(event, context)
    if resource == "/case-files/{id}/pipeline-config/export" and method == "POST":
        return export_config(event, context)
    if resource == "/case-files/{id}/pipeline-config/import" and method == "POST":
        return import_config(event, context)
    if resource == "/case-files/{id}/pipeline-config/template" and method == "POST":
        return apply_template(event, context)

    # --- Sample run endpoints ---
    if resource == "/case-files/{id}/sample-runs" and method == "POST":
        return start_sample_run(event, context)
    if resource == "/case-files/{id}/sample-runs" and method == "GET":
        return list_sample_runs(event, context)
    if resource == "/case-files/{id}/sample-runs/{run_id}" and method == "GET":
        return get_sample_run(event, context)
    if resource == "/case-files/{id}/sample-runs/compare" and method == "POST":
        return compare_runs(event, context)

    # --- Pipeline run endpoints ---
    if resource == "/case-files/{id}/pipeline-runs" and method == "GET":
        return list_pipeline_runs(event, context)
    if resource == "/case-files/{id}/pipeline-runs/{run_id}" and method == "GET":
        return get_run_metrics(event, context)
    if resource == "/case-files/{id}/pipeline-runs/{run_id}/steps/{step}" and method == "GET":
        return get_step_details(event, context)

    # --- Triage queue endpoints ---
    if resource == "/triage-queue" and method == "GET":
        return get_triage_queue(event, context)
    if resource == "/triage-queue/{docId}/assign" and method == "POST":
        return assign_from_triage(event, context)
    if resource == "/triage-queue/{docId}/create-case" and method == "POST":
        return create_case_from_triage(event, context)

    # --- Pipeline status endpoint ---
    if resource == "/case-files/{id}/pipeline-status" and method == "GET":
        from lambdas.api.pipeline_status import handler as status_handler
        return status_handler(event, context)

    # --- System default config endpoints ---
    if resource == "/system/default-config" and method == "GET":
        return get_system_default(event, context)
    if resource == "/system/default-config" and method == "PUT":
        return update_system_default(event, context)
    if resource == "/system/default-config/export" and method == "POST":
        return export_system_default(event, context)
    if resource == "/system/default-config/import" and method == "POST":
        return import_system_default(event, context)

    from lambdas.api.response_helper import error_response
    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# Service construction helpers
# ------------------------------------------------------------------

def _build_config_services():
    """Construct PipelineConfigService with all dependencies."""
    from db.connection import ConnectionManager
    from services.config_resolution_service import ConfigResolutionService
    from services.config_validation_service import ConfigValidationService
    from services.pipeline_config_service import PipelineConfigService

    aurora_cm = ConnectionManager()
    validator = ConfigValidationService()
    resolution = ConfigResolutionService(aurora_cm)
    config_svc = PipelineConfigService(aurora_cm, validator, resolution)
    return config_svc, resolution, aurora_cm


def _build_sample_run_service():
    """Construct SampleRunService with dependencies."""
    import boto3
    from db.connection import ConnectionManager
    from services.config_resolution_service import ConfigResolutionService
    from services.sample_run_service import SampleRunService

    aurora_cm = ConnectionManager()
    sf_client = boto3.client("stepfunctions")
    resolution = ConfigResolutionService(aurora_cm)
    return SampleRunService(aurora_cm, sf_client, resolution)


def _build_monitoring_service():
    """Construct PipelineMonitoringService with dependencies."""
    from db.connection import ConnectionManager
    from services.pipeline_monitoring_service import PipelineMonitoringService

    aurora_cm = ConnectionManager()
    return PipelineMonitoringService(aurora_cm)


def _build_resolution_service():
    """Construct ConfigResolutionService."""
    from db.connection import ConnectionManager
    from services.config_resolution_service import ConfigResolutionService

    aurora_cm = ConnectionManager()
    return ConfigResolutionService(aurora_cm)


# ------------------------------------------------------------------
# GET /case-files/{id}/pipeline-config
# ------------------------------------------------------------------

def get_effective_config(event, context):
    """Return the computed Effective_Config for a case with origin annotations."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        resolution = _build_resolution_service()
        effective = resolution.resolve_effective_config(case_id)

        return success_response(effective.model_dump(mode="json"), 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get effective config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /case-files/{id}/pipeline-config
# ------------------------------------------------------------------

def update_config(event, context):
    """Create or update the pipeline config for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        config_json = body.get("config_json")
        if config_json is None:
            return error_response(400, "VALIDATION_ERROR", "Missing config_json in request body", event)

        created_by = body.get("created_by", "api")

        config_svc, _, _ = _build_config_services()
        version = config_svc.create_or_update_config(case_id, config_json, created_by)

        return success_response(version.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to update config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/pipeline-config/versions
# ------------------------------------------------------------------

def list_versions(event, context):
    """List all config versions for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        config_svc, _, _ = _build_config_services()
        versions = config_svc.list_versions(case_id)

        return success_response(
            {"versions": [v.model_dump(mode="json") for v in versions]},
            200, event,
        )

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to list versions")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/pipeline-config/versions/{v}
# ------------------------------------------------------------------

def get_version(event, context):
    """Get a specific config version for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        version_str = (event.get("pathParameters") or {}).get("v", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)
        if not version_str:
            return error_response(400, "VALIDATION_ERROR", "Missing version number", event)

        try:
            version_num = int(version_str)
        except (ValueError, TypeError):
            return error_response(400, "VALIDATION_ERROR", f"Invalid version number: {version_str}", event)

        config_svc, _, _ = _build_config_services()
        version = config_svc.get_version(case_id, version_num)

        return success_response(version.model_dump(mode="json"), 200, event)

    except ValueError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get version")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/pipeline-config/rollback
# ------------------------------------------------------------------

def rollback(event, context):
    """Rollback to a previous config version."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        target_version = body.get("target_version")
        if target_version is None:
            return error_response(400, "VALIDATION_ERROR", "Missing target_version in request body", event)

        try:
            target_version = int(target_version)
        except (ValueError, TypeError):
            return error_response(400, "VALIDATION_ERROR", f"Invalid target_version: {target_version}", event)

        created_by = body.get("created_by", "api")

        config_svc, _, _ = _build_config_services()
        version = config_svc.rollback_to_version(case_id, target_version, created_by)

        return success_response(version.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to rollback config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/pipeline-config/export
# ------------------------------------------------------------------

def export_config(event, context):
    """Export the active config for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        config_svc, _, _ = _build_config_services()
        export_doc = config_svc.export_config(case_id)

        return success_response(export_doc, 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to export config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/pipeline-config/import
# ------------------------------------------------------------------

def import_config(event, context):
    """Import a config into a case, creating a new version."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        created_by = body.get("created_by", "api")

        config_svc, _, _ = _build_config_services()
        version = config_svc.import_config(case_id, body, created_by)

        return success_response(version.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to import config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/pipeline-config/template
# ------------------------------------------------------------------

def apply_template(event, context):
    """Apply a named config template to a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        template_name = body.get("template_name")
        if not template_name:
            return error_response(400, "VALIDATION_ERROR", "Missing template_name in request body", event)

        created_by = body.get("created_by", "api")

        config_svc, _, _ = _build_config_services()
        version = config_svc.apply_template(case_id, template_name, created_by)

        return success_response(version.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to apply template")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/sample-runs
# ------------------------------------------------------------------

def start_sample_run(event, context):
    """Start a sample pipeline run for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        document_ids = body.get("document_ids")
        if not document_ids or not isinstance(document_ids, list):
            return error_response(400, "VALIDATION_ERROR", "Missing or invalid document_ids list", event)

        created_by = body.get("created_by", "api")

        svc = _build_sample_run_service()
        run = svc.start_sample_run(case_id, document_ids, created_by)

        return success_response(run.model_dump(mode="json"), 201, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to start sample run")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/sample-runs
# ------------------------------------------------------------------

def list_sample_runs(event, context):
    """List all sample runs for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        svc = _build_sample_run_service()
        runs = svc.list_sample_runs(case_id)

        return success_response(
            {"sample_runs": [r.model_dump(mode="json") for r in runs]},
            200, event,
        )

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to list sample runs")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/sample-runs/{run_id}
# ------------------------------------------------------------------

def get_sample_run(event, context):
    """Get details of a specific sample run."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        run_id = (event.get("pathParameters") or {}).get("run_id", "")
        if not run_id:
            return error_response(400, "VALIDATION_ERROR", "Missing run_id", event)

        svc = _build_sample_run_service()
        run = svc.get_sample_run(run_id)

        return success_response(run.model_dump(mode="json"), 200, event)

    except ValueError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get sample run")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/sample-runs/compare
# ------------------------------------------------------------------

def compare_runs(event, context):
    """Compare two sample run snapshots."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        run_id_a = body.get("run_id_a")
        run_id_b = body.get("run_id_b")
        if not run_id_a or not run_id_b:
            return error_response(400, "VALIDATION_ERROR", "Missing run_id_a or run_id_b", event)

        svc = _build_sample_run_service()
        comparison = svc.compare_runs(run_id_a, run_id_b)

        return success_response(comparison.model_dump(mode="json"), 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to compare runs")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/pipeline-runs
# ------------------------------------------------------------------

def list_pipeline_runs(event, context):
    """List pipeline runs for a case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        params = event.get("queryStringParameters") or {}
        limit = int(params.get("limit", "20"))

        svc = _build_monitoring_service()
        runs = svc.list_runs(case_id, limit=limit)

        return success_response(
            {"pipeline_runs": [r.model_dump(mode="json") for r in runs]},
            200, event,
        )

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to list pipeline runs")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/pipeline-runs/{run_id}
# ------------------------------------------------------------------

def get_run_metrics(event, context):
    """Get metrics for a specific pipeline run."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        run_id = (event.get("pathParameters") or {}).get("run_id", "")
        if not run_id:
            return error_response(400, "VALIDATION_ERROR", "Missing run_id", event)

        svc = _build_monitoring_service()
        metrics = svc.get_run_metrics(run_id)

        return success_response(metrics.model_dump(mode="json"), 200, event)

    except ValueError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get run metrics")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /case-files/{id}/pipeline-runs/{run_id}/steps/{step}
# ------------------------------------------------------------------

def get_step_details(event, context):
    """Get per-step drill-down details for a pipeline run."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        run_id = (event.get("pathParameters") or {}).get("run_id", "")
        step_name = (event.get("pathParameters") or {}).get("step", "")
        if not run_id:
            return error_response(400, "VALIDATION_ERROR", "Missing run_id", event)
        if not step_name:
            return error_response(400, "VALIDATION_ERROR", "Missing step name", event)

        svc = _build_monitoring_service()
        detail = svc.get_step_details(run_id, step_name)

        return success_response(detail.model_dump(mode="json"), 200, event)

    except ValueError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get step details")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /system/default-config
# ------------------------------------------------------------------

def get_system_default(event, context):
    """Get the active system default config."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        resolution = _build_resolution_service()
        config_json = resolution.get_system_default()

        return success_response({"config_json": config_json}, 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get system default config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# PUT /system/default-config
# ------------------------------------------------------------------

def update_system_default(event, context):
    """Update the system default config, creating a new version."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        config_json = body.get("config_json")
        if config_json is None:
            return error_response(400, "VALIDATION_ERROR", "Missing config_json in request body", event)

        created_by = body.get("created_by", "api")

        from db.connection import ConnectionManager
        from services.config_validation_service import ConfigValidationService

        validator = ConfigValidationService()
        errors = validator.validate(config_json)
        if errors:
            return error_response(
                400, "VALIDATION_ERROR",
                f"Config validation failed: {[{'field': e.field_path, 'reason': e.reason} for e in errors]}",
                event,
            )

        aurora_cm = ConnectionManager()
        with aurora_cm.cursor() as cur:
            # Get current max version
            cur.execute("SELECT COALESCE(MAX(version), 0) FROM system_default_config")
            max_version = cur.fetchone()[0]
            new_version = max_version + 1

            # Deactivate previous active version
            cur.execute("UPDATE system_default_config SET is_active = FALSE WHERE is_active = TRUE")

            # Insert new version
            cur.execute(
                """
                INSERT INTO system_default_config (version, config_json, created_by, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING config_id, created_at
                """,
                (new_version, json.dumps(config_json), created_by),
            )
            row = cur.fetchone()

        return success_response(
            {"config_id": str(row[0]), "version": new_version, "created_at": str(row[1])},
            201, event,
        )

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to update system default config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /system/default-config/export
# ------------------------------------------------------------------

def export_system_default(event, context):
    """Export the active system default config."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        from db.connection import ConnectionManager

        aurora_cm = ConnectionManager()
        with aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT config_json, version, created_at
                FROM system_default_config
                WHERE is_active = TRUE
                """
            )
            row = cur.fetchone()

        if row is None:
            return error_response(404, "NOT_FOUND", "No active system default config found", event)

        config_json = row[0] if isinstance(row[0], dict) else json.loads(row[0])

        export_doc = {
            "metadata": {
                "source": "system_default",
                "config_version": row[1],
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "config_json": config_json,
        }

        return success_response(export_doc, 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to export system default config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /system/default-config/import
# ------------------------------------------------------------------

def import_system_default(event, context):
    """Import a system default config from a JSON document."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        config_json = body.get("config_json")
        if config_json is None:
            return error_response(400, "VALIDATION_ERROR", "Missing config_json in request body", event)

        created_by = body.get("created_by", "api")

        from db.connection import ConnectionManager
        from services.config_validation_service import ConfigValidationService

        validator = ConfigValidationService()
        errors = validator.validate(config_json)
        if errors:
            return error_response(
                400, "VALIDATION_ERROR",
                f"Config validation failed: {[{'field': e.field_path, 'reason': e.reason} for e in errors]}",
                event,
            )

        aurora_cm = ConnectionManager()
        with aurora_cm.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(version), 0) FROM system_default_config")
            max_version = cur.fetchone()[0]
            new_version = max_version + 1

            cur.execute("UPDATE system_default_config SET is_active = FALSE WHERE is_active = TRUE")

            cur.execute(
                """
                INSERT INTO system_default_config (version, config_json, created_by, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING config_id, created_at
                """,
                (new_version, json.dumps(config_json), created_by),
            )
            row = cur.fetchone()

        return success_response(
            {"config_id": str(row[0]), "version": new_version, "created_at": str(row[1])},
            201, event,
        )

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to import system default config")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# Service construction helper – Document Classification
# ------------------------------------------------------------------

def _build_classification_service():
    """Construct DocumentClassificationService with dependencies."""
    from db.connection import ConnectionManager
    from services.document_classification_service import DocumentClassificationService

    aurora_cm = ConnectionManager()
    return DocumentClassificationService(aurora_cm)


# ------------------------------------------------------------------
# GET /triage-queue
# ------------------------------------------------------------------

def get_triage_queue(event, context):
    """List documents in the triage queue with optional filters."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        params = event.get("queryStringParameters") or {}
        limit = int(params.get("limit", "50"))
        offset = int(params.get("offset", "0"))
        status = params.get("status", "pending")

        svc = _build_classification_service()
        items = svc.get_triage_queue(limit=limit, offset=offset, status=status)

        return success_response({"items": items, "limit": limit, "offset": offset}, 200, event)

    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to get triage queue")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /triage-queue/{docId}/assign
# ------------------------------------------------------------------

def assign_from_triage(event, context):
    """Assign a triaged document to an existing case."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        doc_id = (event.get("pathParameters") or {}).get("docId", "")
        if not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing document ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        case_id = body.get("case_id")
        assigned_by = body.get("assigned_by")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case_id in request body", event)
        if not assigned_by:
            return error_response(400, "VALIDATION_ERROR", "Missing assigned_by in request body", event)

        svc = _build_classification_service()
        result = svc.assign_from_triage(doc_id, case_id, assigned_by)

        return success_response(result, 200, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to assign from triage")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /triage-queue/{docId}/create-case
# ------------------------------------------------------------------

def create_case_from_triage(event, context):
    """Create a new case from a triaged document."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        doc_id = (event.get("pathParameters") or {}).get("docId", "")
        if not doc_id:
            return error_response(400, "VALIDATION_ERROR", "Missing document ID", event)

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        case_name = body.get("case_name")
        created_by = body.get("created_by")
        if not case_name:
            return error_response(400, "VALIDATION_ERROR", "Missing case_name in request body", event)
        if not created_by:
            return error_response(400, "VALIDATION_ERROR", "Missing created_by in request body", event)

        svc = _build_classification_service()
        result = svc.create_case_from_triage(doc_id, case_name, created_by)

        return success_response(result, 201, event)

    except KeyError as exc:
        return error_response(404, "NOT_FOUND", str(exc), event)
    except ValueError as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), event)
    except Exception as exc:
        logger.exception("Failed to create case from triage")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)
