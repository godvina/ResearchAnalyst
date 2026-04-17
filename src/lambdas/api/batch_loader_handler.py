"""API Lambda handler for Batch Loader UI endpoints.

Endpoints:
    GET    /batch-loader/discover                — preview unprocessed files + cost estimate
    POST   /batch-loader/start                   — start async batch processing
    GET    /batch-loader/status                   — get current batch progress
    GET    /batch-loader/manifests                — list batch manifests
    GET    /batch-loader/manifests/{batch_id}     — get specific manifest
    GET    /batch-loader/quarantine               — get quarantine list + summary
    GET    /batch-loader/history                  — get batch history + cumulative stats
    GET    /batch-loader/sources                  — list source bucket prefixes + zip metadata
    POST   /batch-loader/extract                  — start async zip extraction
    GET    /batch-loader/extract-status            — poll extraction job progress
    GET    /batch-loader/pipeline-summary          — pipeline stage counts for dashboard

Also handles async self-invocation for long-running batch processing when
event contains action == "process_batch" or action == "extract_zip".
"""

import json
import logging
import math
import os
import time
import urllib.request
import urllib.error
from dataclasses import asdict
from datetime import datetime, timezone

import boto3

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Default config values
DEFAULT_CASE_ID = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
DEFAULT_BATCH_SIZE = 5000
DEFAULT_SUB_BATCH_SIZE = 50
DEFAULT_SOURCE_PREFIXES = ["pdfs/", "bw-documents/"]
DEFAULT_OCR_THRESHOLD = 50
DEFAULT_BLANK_THRESHOLD = 10
DEFAULT_DATA_LAKE_BUCKET = "research-analyst-data-lake-974220725866"
DEFAULT_SOURCE_BUCKET = "doj-cases-974220725866-us-east-1"
DEFAULT_API_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
DEFAULT_FAILURE_THRESHOLD = 0.10


@with_access_control
def dispatch_handler(event, context):
    """Route requests based on HTTP method and resource path."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Check for async worker invocations (not from API Gateway)
    if event.get("action") == "process_batch":
        return async_process_batch(event, context)
    if event.get("action") == "extract_zip":
        return async_extract_zip(event, context)

    # --- Batch loader endpoints ---
    if resource == "/batch-loader/discover" and method == "GET":
        return handle_discover(event, context)
    if resource == "/batch-loader/start" and method == "POST":
        return handle_start(event, context)
    if resource == "/batch-loader/status" and method == "GET":
        return handle_status(event, context)
    if resource == "/batch-loader/manifests" and method == "GET":
        return handle_list_manifests(event, context)
    if resource == "/batch-loader/manifests/{batch_id}" and method == "GET":
        return handle_get_manifest(event, context)
    if resource == "/batch-loader/quarantine" and method == "GET":
        return handle_quarantine(event, context)
    if resource == "/batch-loader/history" and method == "GET":
        return handle_history(event, context)
    if resource == "/batch-loader/sources" and method == "GET":
        return handle_sources(event, context)
    if resource == "/batch-loader/extract" and method == "POST":
        return handle_extract(event, context)
    if resource == "/batch-loader/extract-status" and method == "GET":
        return handle_extract_status(event, context)
    if resource == "/batch-loader/pipeline-summary" and method == "GET":
        return handle_pipeline_summary(event, context)

    return error_response(404, "NOT_FOUND", f"No handler for {method} {resource}", event)


# ------------------------------------------------------------------
# Helper: build BatchLoaderState
# ------------------------------------------------------------------

def _build_state(case_id: str, s3_client=None):
    """Construct a BatchLoaderState for the given case."""
    from services.batch_loader_state import BatchLoaderState

    if s3_client is None:
        s3_client = boto3.client("s3")
    bucket = os.environ.get("DATA_LAKE_BUCKET", DEFAULT_DATA_LAKE_BUCKET)
    return BatchLoaderState(s3_client, bucket, case_id)


def _get_case_id(event):
    """Extract case_id from query string parameters."""
    params = event.get("queryStringParameters") or {}
    return params.get("case_id", "")


# ------------------------------------------------------------------
# GET /batch-loader/discover
# ------------------------------------------------------------------

def handle_discover(event, context):
    """Preview unprocessed files and cost estimate for a batch."""
    from lambdas.api.response_helper import error_response, success_response
    from batch_loader.config import BatchConfig
    from batch_loader.cost_estimator import CostEstimator
    from batch_loader.discovery import BatchDiscovery

    try:
        params = event.get("queryStringParameters") or {}
        case_id = params.get("case_id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required parameter: case_id", event)

        batch_size = int(params.get("batch_size", str(DEFAULT_BATCH_SIZE)))
        source_prefixes_str = params.get("source_prefixes", "pdfs/,bw-documents/")
        source_prefixes = [p.strip() for p in source_prefixes_str.split(",") if p.strip()]
        blank_page_rate_str = params.get("blank_page_rate")

        s3_client = boto3.client("s3")
        config = BatchConfig(
            case_id=case_id,
            batch_size=batch_size,
            source_prefixes=source_prefixes,
        )

        discovery = BatchDiscovery(config, s3_client)
        all_raw_keys = discovery.list_all_raw_keys()
        processed_keys = discovery.load_processed_keys()
        unprocessed = [k for k in all_raw_keys if k not in processed_keys]

        # Source prefix breakdown
        prefix_breakdown = {}
        for prefix in source_prefixes:
            prefix_breakdown[prefix] = sum(1 for k in unprocessed if k.startswith(prefix))

        total_unprocessed = len(unprocessed)
        actual_batch_size = min(batch_size, total_unprocessed)

        # Cost preview
        cost_preview = None
        gross_estimate = None
        net_estimate = None
        blank_page_rate = None
        component_breakdown = None

        if total_unprocessed > 0:
            estimator = CostEstimator(config)

            if blank_page_rate_str is not None:
                # Dual cost estimate mode
                blank_page_rate = float(blank_page_rate_str)
                dual = estimator.estimate_dual(actual_batch_size, blank_page_rate=blank_page_rate)
                gross_estimate = asdict(dual.gross)
                net_estimate = asdict(dual.net)
                blank_page_rate = dual.blank_page_rate
                component_breakdown = dual.component_breakdown
                cost_preview = gross_estimate  # backward compat
            else:
                estimate = estimator.estimate(actual_batch_size)
                cost_preview = asdict(estimate)

        response = {
            "total_unprocessed_count": total_unprocessed,
            "requested_batch_size": batch_size,
            "actual_batch_size": actual_batch_size,
            "source_prefix_breakdown": prefix_breakdown,
            "cost_preview": cost_preview,
        }

        # Add dual estimate fields when blank_page_rate was provided
        if gross_estimate is not None:
            response["gross_estimate"] = gross_estimate
            response["net_estimate"] = net_estimate
            response["blank_page_rate"] = blank_page_rate
            response["component_breakdown"] = component_breakdown

        # If no unprocessed files, include cumulative stats from progress
        if total_unprocessed == 0:
            state = _build_state(case_id, s3_client)
            progress = state.read_progress()
            if progress and "cumulative_stats" in progress:
                response["cumulative_stats"] = progress["cumulative_stats"]

        return success_response(response, 200, event)

    except Exception as exc:
        logger.exception("Failed in handle_discover")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /batch-loader/start
# ------------------------------------------------------------------

def handle_start(event, context):
    """Start a new batch processing session."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        case_id = body.get("case_id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required field: case_id", event)

        batch_size = body.get("batch_size", DEFAULT_BATCH_SIZE)
        sub_batch_size = body.get("sub_batch_size", DEFAULT_SUB_BATCH_SIZE)
        source_prefixes = body.get("source_prefixes", DEFAULT_SOURCE_PREFIXES)
        enable_entity_resolution = body.get("enable_entity_resolution", True)
        ocr_threshold = body.get("ocr_threshold", DEFAULT_OCR_THRESHOLD)
        blank_threshold = body.get("blank_threshold", DEFAULT_BLANK_THRESHOLD)
        security_label = body.get("security_label")  # Optional: sets security_label_override on ingested documents

        # Validate params
        if not isinstance(batch_size, int) or batch_size <= 0:
            return error_response(400, "VALIDATION_ERROR", "batch_size must be a positive integer", event)
        if not isinstance(sub_batch_size, int) or sub_batch_size < 1 or sub_batch_size > 200:
            return error_response(400, "VALIDATION_ERROR", "sub_batch_size must be an integer between 1 and 200", event)
        if not source_prefixes or not isinstance(source_prefixes, list) or len(source_prefixes) == 0:
            return error_response(400, "VALIDATION_ERROR", "source_prefixes must be a non-empty list", event)
        if security_label is not None:
            valid_labels = {"public", "restricted", "confidential", "top_secret"}
            if str(security_label).lower() not in valid_labels:
                return error_response(400, "VALIDATION_ERROR", f"Invalid security_label: '{security_label}'. Allowed: {sorted(valid_labels)}", event)
            security_label = str(security_label).lower()

        s3_client = boto3.client("s3")
        data_lake_bucket = os.environ.get("S3_DATA_BUCKET",
                           os.environ.get("S3_BUCKET_NAME", DEFAULT_DATA_LAKE_BUCKET))

        # Fast check: just HEAD the progress file to see if a batch is running
        progress_key = f"batch-progress/{case_id}/batch_progress.json"
        try:
            resp = s3_client.get_object(Bucket=data_lake_bucket, Key=progress_key)
            existing = json.loads(resp["Body"].read().decode("utf-8"))
            status = existing.get("status", "")
            if status not in ("completed", "failed", "paused", ""):
                return error_response(
                    409, "BATCH_IN_PROGRESS",
                    f"Batch {existing.get('batch_id', '?')} is already running (status: {status})",
                    event,
                )
        except s3_client.exceptions.NoSuchKey:
            pass  # No progress file = no batch running
        except Exception:
            pass  # If we can't read it, proceed anyway

        # Use timestamp-based batch ID (fast, no S3 pagination)
        now = datetime.now(timezone.utc)
        batch_id = f"batch_{now.strftime('%Y%m%d_%H%M%S')}"

        initial_progress = {
            "batch_id": batch_id,
            "case_id": case_id,
            "status": "discovery",
            "current_phase": "discovery",
            "phase_progress": {"items_completed": 0, "items_total": 0},
            "overall_progress": {"files_processed": 0, "batch_size": batch_size},
            "config": {
                "batch_size": batch_size,
                "sub_batch_size": sub_batch_size,
                "source_prefixes": source_prefixes,
                "enable_entity_resolution": enable_entity_resolution,
                "ocr_threshold": ocr_threshold,
                "blank_threshold": blank_threshold,
            },
            "per_phase_stats": {
                "discovery": None,
                "extraction": None,
                "filtering": None,
                "ingesting": None,
                "polling_sfn": None,
                "entity_resolution": None,
            },
            "cumulative_stats": None,
            "error_reason": None,
            "started_at": now.isoformat(),
            "last_updated": now.isoformat(),
        }

        # Write progress directly to S3 (fast, no _build_state overhead)
        s3_client.put_object(
            Bucket=data_lake_bucket,
            Key=progress_key,
            Body=json.dumps(initial_progress, default=str).encode("utf-8"),
            ContentType="application/json",
        )

        # Invoke self asynchronously
        lambda_client = boto3.client("lambda")
        async_payload = {
            "action": "process_batch",
            "case_id": case_id,
            "batch_id": batch_id,
            "batch_size": batch_size,
            "sub_batch_size": sub_batch_size,
            "source_prefixes": source_prefixes,
            "enable_entity_resolution": enable_entity_resolution,
            "ocr_threshold": ocr_threshold,
            "blank_threshold": blank_threshold,
            "security_label": security_label,
        }

        function_name = getattr(context, "function_name", os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "batch_loader_handler"))
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(async_payload).encode(),
        )

        return success_response(
            {"batch_id": batch_id, "status": "discovery", "message": "Batch processing started"},
            202, event,
        )

    except json.JSONDecodeError:
        from lambdas.api.response_helper import error_response as err_resp
        return err_resp(400, "VALIDATION_ERROR", "Invalid JSON in request body", event)
    except Exception as exc:
        logger.exception("Failed in handle_start")
        from lambdas.api.response_helper import error_response as err_resp
        return err_resp(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/status
# ------------------------------------------------------------------

def handle_status(event, context):
    """Return current batch progress from S3."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = _get_case_id(event)
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required parameter: case_id", event)

        state = _build_state(case_id)
        progress = state.read_progress()
        if progress is None:
            return error_response(404, "NOT_FOUND", f"No batch progress found for case {case_id}", event)

        # Compute elapsed time
        started_at = progress.get("started_at")
        if started_at:
            try:
                start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
                progress["elapsed_time_seconds"] = int(elapsed)
            except (ValueError, TypeError):
                progress["elapsed_time_seconds"] = 0
        else:
            progress["elapsed_time_seconds"] = 0

        return success_response(progress, 200, event)

    except Exception as exc:
        logger.exception("Failed in handle_status")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/manifests
# ------------------------------------------------------------------

def handle_list_manifests(event, context):
    """List all batch manifests with summary stats."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = _get_case_id(event)
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required parameter: case_id", event)

        state = _build_state(case_id)
        manifests = state.list_manifests()

        return success_response({"manifests": manifests}, 200, event)

    except Exception as exc:
        logger.exception("Failed in handle_list_manifests")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/manifests/{batch_id}
# ------------------------------------------------------------------

def handle_get_manifest(event, context):
    """Get a specific batch manifest by batch_id."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = _get_case_id(event)
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required parameter: case_id", event)

        path_params = event.get("pathParameters") or {}
        batch_id = path_params.get("batch_id", "")
        if not batch_id:
            return error_response(400, "VALIDATION_ERROR", "Missing path parameter: batch_id", event)

        state = _build_state(case_id)
        manifest = state.read_manifest(batch_id)
        if manifest is None:
            return error_response(404, "NOT_FOUND", f"Manifest not found for batch {batch_id}", event)

        return success_response(manifest, 200, event)

    except Exception as exc:
        logger.exception("Failed in handle_get_manifest")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/quarantine
# ------------------------------------------------------------------

def handle_quarantine(event, context):
    """Return quarantine list with summary."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = _get_case_id(event)
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required parameter: case_id", event)

        state = _build_state(case_id)
        entries = state.read_quarantine()

        # Compute summary
        total = len(entries)
        by_reason = {}
        most_recent = None

        for entry in entries:
            reason = entry.get("reason", "unknown")
            # Categorize reason
            if "extraction" in reason.lower() or "pypdf" in reason.lower() or "textract" in reason.lower():
                category = "extraction_failed"
            elif "timeout" in reason.lower():
                category = "timeout"
            else:
                category = "pipeline_failed"
            by_reason[category] = by_reason.get(category, 0) + 1

            failed_at = entry.get("failed_at")
            if failed_at and (most_recent is None or failed_at > most_recent):
                most_recent = failed_at

        summary = {
            "total_quarantined": total,
            "by_reason": by_reason,
            "most_recent": most_recent,
        }

        return success_response(
            {"quarantined_files": entries, "summary": summary},
            200, event,
        )

    except Exception as exc:
        logger.exception("Failed in handle_quarantine")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/history
# ------------------------------------------------------------------

def handle_history(event, context):
    """Return batch history from ledger + cumulative stats."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        case_id = _get_case_id(event)
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required parameter: case_id", event)

        state = _build_state(case_id)
        ledger = state.read_ledger()

        # Extract loads for this case
        case_data = ledger.get("cases", {}).get(case_id, {})
        loads = case_data.get("loads", [])

        # Sort reverse-chronological
        batches = sorted(loads, key=lambda x: x.get("timestamp", ""), reverse=True)

        # Compute cumulative stats from progress file
        progress = state.read_progress()
        cumulative_stats = None
        if progress and "cumulative_stats" in progress:
            cumulative_stats = progress["cumulative_stats"]
        else:
            # Compute from loads
            total_processed = sum(l.get("docs_sent_to_pipeline", 0) for l in loads)
            total_blanks = sum(l.get("blanks_skipped", 0) for l in loads)
            total_cost = sum(l.get("cost_actual", 0) for l in loads)
            cumulative_stats = {
                "total_processed": total_processed,
                "total_blanks_filtered": total_blanks,
                "total_estimated_cost": total_cost,
            }

        return success_response(
            {"batches": batches, "cumulative_stats": cumulative_stats},
            200, event,
        )

    except Exception as exc:
        logger.exception("Failed in handle_history")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/sources
# ------------------------------------------------------------------

def handle_sources(event, context):
    """List all prefixes in source bucket with metadata and zip info."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        from services.source_browser_service import SourceBrowserService

        s3_client = boto3.client("s3")
        source_bucket = os.environ.get("S3_SOURCE_BUCKET", DEFAULT_SOURCE_BUCKET)
        data_lake_bucket = os.environ.get("S3_DATA_BUCKET",
                           os.environ.get("S3_BUCKET_NAME", DEFAULT_DATA_LAKE_BUCKET))

        browser = SourceBrowserService(s3_client, source_bucket, data_lake_bucket)

        prefixes = browser.list_prefixes()
        extraction_records = browser.get_extraction_records()
        summary = browser.get_summary(prefixes)

        # Build response with per-zip metadata and already_extracted status
        prefix_list = []
        for p in prefixes:
            zip_details = []
            for zf in p.zip_files:
                meta = browser.get_zip_metadata(zf.key)
                already_extracted = zf.key in extraction_records
                record = extraction_records.get(zf.key, {})
                zip_details.append({
                    "key": zf.key,
                    "size_bytes": zf.size_bytes,
                    "estimated_file_count": meta.total_entries,
                    "pdf_entries": meta.pdf_entries,
                    "already_extracted": already_extracted,
                    "extraction_job_id": record.get("job_id"),
                    "filenames_preview": meta.filenames[:20],
                })
            prefix_list.append({
                "prefix": p.prefix,
                "total_objects": p.total_objects,
                "total_size_bytes": p.total_size_bytes,
                "pdf_count": p.pdf_count,
                "zip_count": p.zip_count,
                "zip_files": zip_details,
            })

        response = {
            "prefixes": prefix_list,
            "summary": {
                "total_files": summary.total_files,
                "total_extracted_pdfs": summary.total_extracted_pdfs,
                "already_processed": summary.already_processed,
                "remaining_unprocessed": summary.remaining_unprocessed,
            },
        }

        return success_response(response, 200, event)

    except Exception as exc:
        error_code = "S3_ERROR" if "ClientError" in type(exc).__name__ else "INTERNAL_ERROR"
        status = 503 if error_code == "S3_ERROR" else 500
        logger.exception("Failed in handle_sources")
        from lambdas.api.response_helper import error_response as err_resp
        return err_resp(status, error_code, str(exc), event)


# ------------------------------------------------------------------
# POST /batch-loader/extract
# ------------------------------------------------------------------

def handle_extract(event, context):
    """Start async zip extraction job."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        from services.zip_extractor_service import ZipExtractorService

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        zip_keys = body.get("zip_keys", [])
        if not zip_keys or not isinstance(zip_keys, list):
            return error_response(400, "VALIDATION_ERROR", "Missing or invalid zip_keys list", event)

        s3_client = boto3.client("s3")
        source_bucket = os.environ.get("S3_SOURCE_BUCKET", DEFAULT_SOURCE_BUCKET)
        data_lake_bucket = os.environ.get("S3_DATA_BUCKET",
                           os.environ.get("S3_BUCKET_NAME", DEFAULT_DATA_LAKE_BUCKET))

        # Generate unique job ID
        now = datetime.now(timezone.utc)
        job_id = f"ext_{now.strftime('%Y%m%d_%H%M%S')}_{int(now.timestamp()) % 10000}"

        extractor = ZipExtractorService(s3_client, source_bucket, data_lake_bucket)
        extractor.start_extraction(zip_keys, job_id)

        # Invoke self asynchronously for the actual extraction work
        lambda_client = boto3.client("lambda")
        async_payload = {
            "action": "extract_zip",
            "job_id": job_id,
            "zip_keys": zip_keys,
        }

        function_name = getattr(context, "function_name",
                                os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "batch_loader_handler"))
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(async_payload).encode(),
        )

        return success_response(
            {"job_id": job_id, "status": "pending", "zip_keys": zip_keys},
            202, event,
        )

    except json.JSONDecodeError:
        from lambdas.api.response_helper import error_response as err_resp
        return err_resp(400, "VALIDATION_ERROR", "Invalid JSON in request body", event)
    except Exception as exc:
        logger.exception("Failed in handle_extract")
        from lambdas.api.response_helper import error_response as err_resp
        return err_resp(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/extract-status
# ------------------------------------------------------------------

def handle_extract_status(event, context):
    """Poll extraction job progress."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        from services.zip_extractor_service import ZipExtractorService

        params = event.get("queryStringParameters") or {}
        job_id = params.get("job_id", "")
        if not job_id:
            return error_response(400, "VALIDATION_ERROR", "Missing required parameter: job_id", event)

        s3_client = boto3.client("s3")
        source_bucket = os.environ.get("S3_SOURCE_BUCKET", DEFAULT_SOURCE_BUCKET)
        data_lake_bucket = os.environ.get("S3_DATA_BUCKET",
                           os.environ.get("S3_BUCKET_NAME", DEFAULT_DATA_LAKE_BUCKET))

        extractor = ZipExtractorService(s3_client, source_bucket, data_lake_bucket)
        progress = extractor.read_progress(job_id)

        if progress is None:
            return error_response(404, "NOT_FOUND", f"No extraction job found: {job_id}", event)

        return success_response(progress, 200, event)

    except Exception as exc:
        logger.exception("Failed in handle_extract_status")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# GET /batch-loader/pipeline-summary
# ------------------------------------------------------------------

def handle_pipeline_summary(event, context):
    """Return pipeline stage counts for the dashboard."""
    from lambdas.api.response_helper import error_response, success_response

    try:
        s3_client = boto3.client("s3")
        source_bucket = os.environ.get("S3_SOURCE_BUCKET", DEFAULT_SOURCE_BUCKET)
        data_lake_bucket = os.environ.get("S3_DATA_BUCKET",
                           os.environ.get("S3_BUCKET_NAME", DEFAULT_DATA_LAKE_BUCKET))

        # Count zip archives in source bucket
        zip_count = 0
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=source_bucket, Prefix=""):
                for obj in page.get("Contents", []):
                    if obj["Key"].lower().endswith(".zip"):
                        zip_count += 1
        except Exception as exc:
            logger.warning("Failed to count zips in source bucket: %s", exc)

        # Count extracted PDFs in selected prefixes
        extracted_pdfs = 0
        selected_prefixes = DEFAULT_SOURCE_PREFIXES
        try:
            for prefix in selected_prefixes:
                for page in paginator.paginate(Bucket=source_bucket, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        if obj["Key"].lower().endswith(".pdf"):
                            extracted_pdfs += 1
        except Exception as exc:
            logger.warning("Failed to count PDFs: %s", exc)

        # Count blank-filtered and ingested from batch manifests
        blank_filtered = 0
        ingested = 0
        try:
            for page in paginator.paginate(Bucket=data_lake_bucket, Prefix="batch-manifests/"):
                for obj in page.get("Contents", []):
                    if not obj["Key"].endswith(".json"):
                        continue
                    try:
                        resp = s3_client.get_object(Bucket=data_lake_bucket, Key=obj["Key"])
                        manifest = json.loads(resp["Body"].read().decode("utf-8"))
                        for f in manifest.get("files", []):
                            if f.get("blank_filtered"):
                                blank_filtered += 1
                            if f.get("pipeline_status") == "succeeded":
                                ingested += 1
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("Failed to read manifests for pipeline summary: %s", exc)

        # Check for active batch
        active_batch = None
        try:
            # Check all case progress files
            for page in paginator.paginate(Bucket=data_lake_bucket, Prefix="batch-progress/"):
                for obj in page.get("Contents", []):
                    if not obj["Key"].endswith("batch_progress.json"):
                        continue
                    try:
                        resp = s3_client.get_object(Bucket=data_lake_bucket, Key=obj["Key"])
                        progress = json.loads(resp["Body"].read().decode("utf-8"))
                        status = progress.get("status", "")
                        if status not in ("completed", "failed", ""):
                            active_batch = {
                                "batch_id": progress.get("batch_id"),
                                "status": status,
                                "case_id": progress.get("case_id"),
                            }
                            break
                    except Exception:
                        pass
                if active_batch:
                    break
        except Exception as exc:
            logger.warning("Failed to check active batch: %s", exc)

        response = {
            "stages": {
                "zip_archives": {"count": zip_count, "label": "Source Archives"},
                "extracted_pdfs": {"count": extracted_pdfs, "label": "Raw PDFs"},
                "blank_filtered": {"count": blank_filtered, "label": "Blank Filtered"},
                "ingested": {"count": ingested, "label": "Ingested"},
            },
            "selected_prefixes": selected_prefixes,
            "active_batch": active_batch,
        }

        return success_response(response, 200, event)

    except Exception as exc:
        logger.exception("Failed in handle_pipeline_summary")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# Async worker: extract_zip
# ------------------------------------------------------------------

def async_extract_zip(event, context):
    """Long-running zip extraction worker invoked asynchronously.

    Extracts PDFs from zip archives in the source bucket. Handles Lambda
    timeout by saving resume point and re-invoking self.
    """
    from services.zip_extractor_service import ZipExtractorService

    job_id = event.get("job_id", "")
    zip_keys = event.get("zip_keys", [])
    start_index = event.get("start_index", 0)
    current_zip_idx = event.get("current_zip_idx", 0)

    s3_client = boto3.client("s3")
    source_bucket = os.environ.get("S3_SOURCE_BUCKET", DEFAULT_SOURCE_BUCKET)
    data_lake_bucket = os.environ.get("S3_DATA_BUCKET",
                       os.environ.get("S3_BUCKET_NAME", DEFAULT_DATA_LAKE_BUCKET))

    extractor = ZipExtractorService(s3_client, source_bucket, data_lake_bucket)

    try:
        for idx in range(current_zip_idx, len(zip_keys)):
            zip_key = zip_keys[idx]
            resume_from = start_index if idx == current_zip_idx else 0

            remaining_ms = None
            if hasattr(context, "get_remaining_time_in_millis"):
                remaining_ms = context.get_remaining_time_in_millis()

            result = extractor.extract_zip(
                zip_key=zip_key,
                job_id=job_id,
                start_index=resume_from,
                remaining_ms=remaining_ms,
            )

            if result.get("status") == "timeout":
                # Re-invoke self to continue extraction
                lambda_client = boto3.client("lambda")
                async_payload = {
                    "action": "extract_zip",
                    "job_id": job_id,
                    "zip_keys": zip_keys,
                    "start_index": result.get("resume_index", 0),
                    "current_zip_idx": idx,
                }
                function_name = getattr(context, "function_name",
                                        os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "batch_loader_handler"))
                lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType="Event",
                    Payload=json.dumps(async_payload).encode(),
                )
                logger.info("Extraction timeout for %s, re-invoked at index %d",
                            zip_key, result.get("resume_index", 0))
                return {"statusCode": 200, "body": f"Extraction chunked for {zip_key}"}

            # Write completion record for this zip
            if result.get("status") == "completed":
                extractor.write_completion_record(job_id, zip_key, result)

        logger.info("Extraction job %s completed for all zips", job_id)
        return {"statusCode": 200, "body": f"Extraction job {job_id} completed"}

    except Exception as exc:
        logger.exception("Extraction job %s failed", job_id)
        # Try to update progress to failed
        try:
            progress = extractor.read_progress(job_id)
            if progress:
                progress["status"] = "failed"
                progress["errors"] = progress.get("errors", []) + [{"file": "worker", "error": str(exc)}]
                from services.zip_extractor_service import _utcnow_iso
                progress["last_updated"] = _utcnow_iso()
                s3_client.put_object(
                    Bucket=data_lake_bucket,
                    Key=f"extract-jobs/{job_id}/progress.json",
                    Body=json.dumps(progress, default=str).encode("utf-8"),
                    ContentType="application/json",
                )
        except Exception:
            logger.exception("Failed to update extraction progress to failed state")
        return {"statusCode": 500, "body": f"Extraction job {job_id} failed: {exc}"}


# ------------------------------------------------------------------
# Async worker: process_batch
# ------------------------------------------------------------------

def async_process_batch(event, context):
    """Long-running batch worker invoked asynchronously via Lambda Event invocation.

    Phases: discovery → extraction → filtering → ingestion → SFN polling →
    entity resolution → complete.

    Updates S3 progress after each phase. Writes manifest, updates quarantine,
    and appends ledger entry on completion.
    """
    from batch_loader.config import BatchConfig
    from batch_loader.cost_estimator import CostEstimator
    from batch_loader.discovery import BatchDiscovery
    from batch_loader.extractor import TextExtractor
    from batch_loader.filter import BlankFilter
    from batch_loader.ingestion import PipelineIngestion
    from batch_loader.manifest import BatchManifest, FileEntry
    from batch_loader.quarantine import check_failure_threshold
    from services.batch_loader_state import BatchLoaderState

    case_id = event.get("case_id", DEFAULT_CASE_ID)
    batch_id = event.get("batch_id", "batch_001")
    batch_size = event.get("batch_size", DEFAULT_BATCH_SIZE)
    sub_batch_size = event.get("sub_batch_size", DEFAULT_SUB_BATCH_SIZE)
    source_prefixes = event.get("source_prefixes", DEFAULT_SOURCE_PREFIXES)
    enable_entity_resolution = event.get("enable_entity_resolution", True)
    ocr_threshold = event.get("ocr_threshold", DEFAULT_OCR_THRESHOLD)
    blank_threshold = event.get("blank_threshold", DEFAULT_BLANK_THRESHOLD)

    s3_client = boto3.client("s3")
    data_lake_bucket = os.environ.get("DATA_LAKE_BUCKET", DEFAULT_DATA_LAKE_BUCKET)
    source_bucket = os.environ.get("SOURCE_BUCKET", DEFAULT_SOURCE_BUCKET)
    api_url = os.environ.get("API_URL", DEFAULT_API_URL)

    config = BatchConfig(
        case_id=case_id,
        batch_size=batch_size,
        sub_batch_size=sub_batch_size,
        source_prefixes=source_prefixes,
        ocr_threshold=ocr_threshold,
        blank_threshold=blank_threshold,
        source_bucket=source_bucket,
        data_lake_bucket=data_lake_bucket,
        api_url=api_url,
    )

    state = BatchLoaderState(s3_client, data_lake_bucket, case_id)

    # Read current progress
    progress = state.read_progress()
    if progress is None:
        logger.error("No progress file found for batch %s", batch_id)
        return {"statusCode": 500, "body": "No progress file found"}

    batch_number = int(batch_id.split("_")[-1])

    def update_progress(**kwargs):
        """Update progress fields and write to S3."""
        for k, v in kwargs.items():
            progress[k] = v
        progress["last_updated"] = datetime.now(timezone.utc).isoformat()
        state.write_progress(progress)

    try:
        # ---- Phase 1: Discovery ----
        logger.info("Phase 1: Discovery for batch %s", batch_id)
        phase_start = time.time()

        discovery = BatchDiscovery(config, s3_client)
        batch_keys = discovery.discover_batch()
        actual_batch_size = len(batch_keys)

        update_progress(
            status="extracting",
            current_phase="extracting",
            phase_progress={"items_completed": 0, "items_total": actual_batch_size},
            overall_progress={"files_processed": 0, "batch_size": actual_batch_size},
            per_phase_stats={
                **progress.get("per_phase_stats", {}),
                "discovery": {
                    "files_found": actual_batch_size,
                    "duration_seconds": round(time.time() - phase_start, 1),
                },
            },
        )

        if actual_batch_size == 0:
            update_progress(status="completed", current_phase="completed")
            return {"statusCode": 200, "body": "No files to process"}

        # ---- Phase 2: Extraction ----
        logger.info("Phase 2: Extraction — %d files", actual_batch_size)
        phase_start = time.time()

        textract_client = boto3.client("textract", region_name="us-east-1")
        extractor = TextExtractor(config, s3_client, textract_client)

        extraction_results = []
        method_counts = {"pypdf2": 0, "textract": 0, "failed": 0, "cached": 0}

        for i, s3_key in enumerate(batch_keys):
            result = extractor.extract(s3_key, batch_id)
            extraction_results.append(result)
            method_counts[result.method] = method_counts.get(result.method, 0) + 1

            # Update progress every 100 files
            if (i + 1) % 100 == 0 or i == actual_batch_size - 1:
                update_progress(
                    phase_progress={"items_completed": i + 1, "items_total": actual_batch_size},
                    per_phase_stats={
                        **progress.get("per_phase_stats", {}),
                        "extraction": {
                            **method_counts,
                            "duration_seconds": round(time.time() - phase_start, 1),
                        },
                    },
                )

        extraction_duration = round(time.time() - phase_start, 1)
        update_progress(
            per_phase_stats={
                **progress.get("per_phase_stats", {}),
                "extraction": {**method_counts, "duration_seconds": extraction_duration},
            },
        )

        # Check failure threshold after extraction
        if check_failure_threshold(method_counts["failed"], actual_batch_size, DEFAULT_FAILURE_THRESHOLD):
            update_progress(
                status="paused",
                error_reason=f"Extraction failure rate exceeded threshold: {method_counts['failed']}/{actual_batch_size}",
            )
            return {"statusCode": 200, "body": "Paused due to high failure rate"}

        # ---- Phase 3: Filtering ----
        logger.info("Phase 3: Filtering")
        phase_start = time.time()
        update_progress(status="filtering", current_phase="filtering")

        blank_filter = BlankFilter(config)
        filter_results = [blank_filter.filter(er) for er in extraction_results]

        blank_count = sum(1 for fr in filter_results if fr.is_blank)
        non_blank_count = actual_batch_size - blank_count

        update_progress(
            per_phase_stats={
                **progress.get("per_phase_stats", {}),
                "filtering": {
                    "blank_count": blank_count,
                    "non_blank_count": non_blank_count,
                    "duration_seconds": round(time.time() - phase_start, 1),
                },
            },
        )

        # Build non-blank documents for ingestion
        non_blank_docs = []
        for er, fr in zip(extraction_results, filter_results):
            if not fr.is_blank and er.method != "failed":
                filename = os.path.basename(er.s3_key)
                non_blank_docs.append((filename, er.text))

        # ---- Phase 4: Ingestion ----
        logger.info("Phase 4: Ingestion — %d non-blank docs", len(non_blank_docs))
        phase_start = time.time()
        total_sub_batches = math.ceil(len(non_blank_docs) / sub_batch_size) if non_blank_docs else 0

        update_progress(
            status="ingesting",
            current_phase="ingesting",
            phase_progress={"items_completed": 0, "items_total": len(non_blank_docs)},
            per_phase_stats={
                **progress.get("per_phase_stats", {}),
                "ingesting": {
                    "sub_batches_sent": 0,
                    "sub_batches_total": total_sub_batches,
                    "duration_seconds": None,
                },
            },
        )

        ingestion = PipelineIngestion(config)
        execution_arns = ingestion.send_sub_batches(non_blank_docs)

        update_progress(
            per_phase_stats={
                **progress.get("per_phase_stats", {}),
                "ingesting": {
                    "sub_batches_sent": total_sub_batches,
                    "sub_batches_total": total_sub_batches,
                    "duration_seconds": round(time.time() - phase_start, 1),
                },
            },
        )

        # ---- Phase 5: SFN Polling ----
        logger.info("Phase 5: SFN Polling — %d executions", len(execution_arns))
        phase_start = time.time()
        update_progress(
            status="polling_sfn",
            current_phase="polling_sfn",
            per_phase_stats={
                **progress.get("per_phase_stats", {}),
                "polling_sfn": {
                    "executions_total": len(execution_arns),
                    "succeeded": 0,
                    "failed": 0,
                    "running": len(execution_arns),
                },
            },
        )

        sfn_statuses = ingestion.poll_executions(execution_arns)
        sfn_succeeded = sum(1 for s in sfn_statuses.values() if s == "SUCCEEDED")
        sfn_failed = sum(1 for s in sfn_statuses.values() if s in ("FAILED", "TIMED_OUT", "ABORTED"))

        update_progress(
            per_phase_stats={
                **progress.get("per_phase_stats", {}),
                "polling_sfn": {
                    "executions_total": len(execution_arns),
                    "succeeded": sfn_succeeded,
                    "failed": sfn_failed,
                    "running": 0,
                    "duration_seconds": round(time.time() - phase_start, 1),
                },
            },
        )

        # ---- Phase 6: Entity Resolution ----
        er_result = {}
        if enable_entity_resolution and non_blank_docs:
            logger.info("Phase 6: Entity Resolution")
            update_progress(status="entity_resolution", current_phase="entity_resolution")

            try:
                er_url = f"{api_url}/case-files/{case_id}/entity-resolution"
                er_body = json.dumps({"mode": "no-llm"}).encode()
                req = urllib.request.Request(er_url, data=er_body, method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=600) as resp:
                    er_result = json.loads(resp.read().decode())
            except Exception as exc:
                logger.error("Entity resolution failed: %s", exc)
                er_result = {"error": str(exc)}

            update_progress(
                per_phase_stats={
                    **progress.get("per_phase_stats", {}),
                    "entity_resolution": er_result,
                },
            )

        # ---- Write manifest ----
        logger.info("Writing batch manifest")
        manifest_mgr = BatchManifest(config, s3_client)
        manifest_data = manifest_mgr.create(batch_number, source_prefixes)

        # Build a lookup for extraction results and filter results
        extraction_by_key = {er.s3_key: er for er in extraction_results}
        filter_by_key = {fr.s3_key: fr for fr in filter_results}

        # Map execution ARNs to documents (simplified — assign sequentially)
        for s3_key in batch_keys:
            er = extraction_by_key.get(s3_key)
            fr = filter_by_key.get(s3_key)

            if er is None:
                continue

            if er.method == "failed":
                pipeline_status = "quarantined"
            elif fr and fr.is_blank:
                pipeline_status = "blank_filtered"
            else:
                pipeline_status = "sent"

            entry = FileEntry(
                s3_key=s3_key,
                file_size_bytes=0,
                extraction_method=er.method,
                extracted_char_count=er.char_count,
                blank_filtered=fr.is_blank if fr else False,
                pipeline_status=pipeline_status,
                error_message=er.error,
            )
            manifest_mgr.add_file(manifest_data, entry)

        manifest_mgr.save(manifest_data)

        # ---- Update quarantine ----
        failed_keys = [er for er in extraction_results if er.method == "failed"]
        if failed_keys:
            existing_quarantine = state.read_quarantine()
            existing_q_keys = {e.get("s3_key") for e in existing_quarantine}
            for er in failed_keys:
                if er.s3_key not in existing_q_keys:
                    existing_quarantine.append({
                        "s3_key": er.s3_key,
                        "reason": f"extraction_failed: {er.error or 'unknown'}",
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                        "retry_count": config.max_retries,
                        "batch_number": batch_number,
                    })
            state.write_quarantine(existing_quarantine)

        # ---- Append ledger entry ----
        cost_estimator = CostEstimator(config)
        cost_estimate = cost_estimator.estimate(len(non_blank_docs))

        ledger_entry = {
            "load_id": batch_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_files_total": actual_batch_size,
            "blanks_skipped": blank_count,
            "docs_sent_to_pipeline": len(non_blank_docs),
            "sfn_executions": len(execution_arns),
            "sfn_succeeded": sfn_succeeded,
            "sfn_failed": sfn_failed,
            "textract_ocr_count": method_counts.get("textract", 0),
            "extraction_method_breakdown": method_counts,
            "entity_resolution_result": er_result,
            "cost_actual": cost_estimate.total_estimated,
            "notes": f"Batch {batch_number}. {blank_count / actual_batch_size * 100:.0f}% blank rate." if actual_batch_size > 0 else f"Batch {batch_number}.",
        }
        state.append_ledger_entry(ledger_entry)

        # ---- Mark completed ----
        update_progress(
            status="completed",
            current_phase="completed",
            overall_progress={"files_processed": actual_batch_size, "batch_size": actual_batch_size},
        )

        logger.info("Batch %s completed successfully", batch_id)
        return {"statusCode": 200, "body": f"Batch {batch_id} completed"}

    except Exception as exc:
        logger.exception("Batch %s failed with unhandled error", batch_id)
        try:
            update_progress(
                status="failed",
                error_reason=str(exc),
            )
        except Exception:
            logger.exception("Failed to update progress to failed state")
        return {"statusCode": 500, "body": f"Batch {batch_id} failed: {exc}"}
