"""API Lambda handlers for investigative timeline reconstruction.

Endpoints:
    POST /case-files/{id}/timeline          — reconstruct timeline with clustering and gap analysis
    POST /case-files/{id}/timeline/ai-analysis — generate AI temporal pattern analysis
"""

import json
import logging
import re

from services.access_control_middleware import with_access_control

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


_cached_timeline_service = None

def _build_timeline_service():
    """Construct a TimelineService with dependencies from environment. Cached for reuse."""
    global _cached_timeline_service
    if _cached_timeline_service is not None:
        return _cached_timeline_service
    import boto3
    from botocore.config import Config

    from db.connection import ConnectionManager
    from services.timeline_service import TimelineService

    aurora_cm = ConnectionManager()
    bedrock_config = Config(
        read_timeout=120,
        connect_timeout=10,
        retries={"max_attempts": 2, "mode": "adaptive"},
    )
    bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
    _cached_timeline_service = TimelineService(None, aurora_cm, bedrock)
    return _cached_timeline_service



# ------------------------------------------------------------------
# POST /case-files/{id}/timeline
# ------------------------------------------------------------------


def timeline_handler(event, context):
    """Reconstruct timeline with clustering and gap analysis."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        if not _UUID_RE.match(case_id):
            return error_response(
                400, "VALIDATION_ERROR", "Invalid case file ID format — expected UUID", event
            )

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))

        # Parse and validate clustering_window_hours (default 48)
        raw_window = body.get("clustering_window_hours", 48)
        try:
            clustering_window_hours = int(raw_window)
            if clustering_window_hours < 0:
                raise ValueError("negative")
        except (ValueError, TypeError):
            return error_response(
                400,
                "VALIDATION_ERROR",
                "clustering_window_hours must be a non-negative integer",
                event,
            )

        # Parse and validate gap_threshold_days (default 30)
        raw_gap = body.get("gap_threshold_days", 30)
        try:
            gap_threshold_days = int(raw_gap)
            if gap_threshold_days <= 0:
                raise ValueError("non-positive")
        except (ValueError, TypeError):
            return error_response(
                400,
                "VALIDATION_ERROR",
                "gap_threshold_days must be a positive integer",
                event,
            )

        # Parse and validate noise_cutoff_year (optional)
        noise_cutoff_year = None
        raw_cutoff = body.get("noise_cutoff_year")
        if raw_cutoff is not None:
            try:
                noise_cutoff_year = int(raw_cutoff)
            except (ValueError, TypeError):
                return error_response(
                    400,
                    "VALIDATION_ERROR",
                    "noise_cutoff_year must be an integer",
                    event,
                )
            import datetime as _dt
            current_year = _dt.datetime.now(_dt.timezone.utc).year
            if noise_cutoff_year > current_year:
                return error_response(
                    400,
                    "VALIDATION_ERROR",
                    "noise_cutoff_year cannot be in the future",
                    event,
                )

        service = _build_timeline_service()
        result = service.reconstruct_timeline(
            case_id,
            clustering_window_hours=clustering_window_hours,
            gap_threshold_days=gap_threshold_days,
            skip_snippets=body.get("skip_snippets", True),
            noise_cutoff_year=noise_cutoff_year,
        )
        return success_response(result, 200, event)

    except KeyError:
        return error_response(404, "NOT_FOUND", f"Case file not found: {case_id}", event)
    except Exception as exc:
        logger.exception("Failed to reconstruct timeline")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


# ------------------------------------------------------------------
# POST /case-files/{id}/timeline/ai-analysis
# ------------------------------------------------------------------


def ai_analysis_handler(event, context):
    """Generate AI temporal pattern analysis for a timeline."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        case_id = (event.get("pathParameters") or {}).get("id", "")
        if not case_id:
            return error_response(400, "VALIDATION_ERROR", "Missing case file ID", event)

        if not _UUID_RE.match(case_id):
            return error_response(
                400, "VALIDATION_ERROR", "Invalid case file ID format — expected UUID", event
            )

        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        events = body.get("events", [])
        gaps = body.get("gaps", [])

        service = _build_timeline_service()
        result = service.generate_ai_analysis(case_id, events, gaps)
        return success_response(result, 200, event)

    except Exception as exc:
        logger.exception("AI timeline analysis failed")
        return error_response(500, "AI_ANALYSIS_ERROR", str(exc), event)


# ------------------------------------------------------------------
# Dispatch handler (entry point from case_files.py)
# ------------------------------------------------------------------


@with_access_control
def dispatch_handler(event, context):
    """Route timeline requests to the correct handler."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response

    method = event.get("httpMethod", "")
    path = event.get("path", "")

    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    if "/ai-analysis" in path:
        return ai_analysis_handler(event, context)

    if "/timeline" in path:
        return timeline_handler(event, context)

    return error_response(404, "NOT_FOUND", f"No handler for {method} {path}", event)
