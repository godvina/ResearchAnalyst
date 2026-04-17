"""Access control middleware decorator for Lambda handlers.

Provides a ``with_access_control`` decorator that:
- Resolves the caller's identity via ``AccessControlService``
- Injects the resolved ``UserContext`` into the event as ``event["_user_context"]``
- Respects the ``ACCESS_CONTROL_ENABLED`` kill-switch
- Supports a ``TRANSITION_PERIOD_ENABLED`` flag for graceful rollout
"""

import json
import logging
import os
from functools import wraps

from lambdas.api.response_helper import CORS_HEADERS
from models.access_control import SecurityLabel, UserContext

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------


def _is_enabled() -> bool:
    """Return True when access control is active (default: true)."""
    return os.environ.get("ACCESS_CONTROL_ENABLED", "true").lower() == "true"


def _transition_period() -> bool:
    """Return True when the transition period is active (default: false)."""
    return os.environ.get("TRANSITION_PERIOD_ENABLED", "false").lower() == "true"


def _default_restricted_user() -> UserContext:
    """Return a fallback UserContext with restricted clearance."""
    return UserContext(
        user_id="anonymous",
        username="anonymous",
        clearance_level=SecurityLabel.RESTRICTED,
        role="viewer",
        groups=[],
    )


def _build_access_control_service():
    """Construct an ``AccessControlService`` instance.

    Imported lazily so the module can be loaded without triggering
    heavy DB/provider initialisation at import time.
    """
    from services.access_control_service import AccessControlService

    return AccessControlService()


# ------------------------------------------------------------------
# Decorator
# ------------------------------------------------------------------


def with_access_control(handler_fn):
    """Decorator that resolves user context and injects it into the event.

    When ``ACCESS_CONTROL_ENABLED`` is ``"false"``, the original handler
    is called directly without any user resolution.

    When the user identity cannot be resolved:
    - If ``TRANSITION_PERIOD_ENABLED`` is ``"true"``, a default restricted
      ``UserContext`` is injected so the request can proceed.
    - Otherwise a **401 Unauthorized** response is returned immediately.
    """

    @wraps(handler_fn)
    def wrapper(event, context):
        # Pass through CORS preflight requests without access control
        if event.get("httpMethod") == "OPTIONS":
            return handler_fn(event, context)

        if not _is_enabled():
            return handler_fn(event, context)

        ac_service = _build_access_control_service()
        try:
            user_ctx = ac_service.resolve_user_context(event)
        except (KeyError, Exception) as exc:
            logger.warning("User identity resolution failed: %s", exc)
            if _transition_period():
                user_ctx = _default_restricted_user()
            else:
                return {
                    "statusCode": 401,
                    "headers": CORS_HEADERS,
                    "body": json.dumps(
                        {
                            "error": {
                                "code": "UNAUTHORIZED",
                                "message": "User identity could not be resolved",
                            }
                        }
                    ),
                }

        event["_user_context"] = user_ctx.model_dump()
        return handler_fn(event, context)

    return wrapper
