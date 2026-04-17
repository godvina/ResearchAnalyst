"""Lambda handler for config resolution — first step in the Step Functions pipeline.

Receives a case_id, resolves the effective pipeline configuration by
deep-merging the system default with any case-level overrides, and returns
the effective_config JSON for downstream pipeline steps.
"""

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Resolve the effective pipeline config for a case.

    Expected event (only case_id is used — passed via ASL Parameters):
        {
            "case_id": "..."
        }

    Returns:
        The effective config dict (e.g. {"extract": {...}, "embed": {...}, ...}).
        The ASL's ResultPath places this at $.effective_config.
    """
    case_id = event["case_id"]

    from db.connection import ConnectionManager
    from services.config_resolution_service import ConfigResolutionService

    cm = ConnectionManager()
    service = ConfigResolutionService(cm)
    result = service.resolve_effective_config(case_id)

    # Return only the effective config JSON.
    # ResultPath in the ASL places this at $.effective_config,
    # so we must NOT wrap it — just return the config dict directly.
    return result.effective_json
