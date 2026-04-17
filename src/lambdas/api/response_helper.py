"""Shared helpers for building consistent API Gateway Lambda proxy responses.

Every API handler returns responses through these helpers so that status codes,
JSON serialisation, error codes, and request IDs are uniform across the API.
"""

import json
import uuid
from typing import Any


def _request_id(event: dict) -> str:
    """Extract or generate a request ID for traceability."""
    ctx = event.get("requestContext") or {}
    return ctx.get("requestId", str(uuid.uuid4()))


CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS",
}


def success_response(body: Any, status_code: int = 200, event: dict | None = None) -> dict:
    """Build a successful API Gateway proxy response."""
    payload = body
    if isinstance(body, dict):
        payload = {**body, "requestId": _request_id(event or {})}
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(payload, default=str),
    }


def error_response(
    status_code: int,
    error_code: str,
    message: str,
    event: dict | None = None,
) -> dict:
    """Build a structured error API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(
            {
                "error": {
                    "code": error_code,
                    "message": message,
                },
                "requestId": _request_id(event or {}),
            },
            default=str,
        ),
    }
