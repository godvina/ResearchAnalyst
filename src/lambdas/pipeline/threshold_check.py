"""Threshold check Lambda — determines if a case requires pre-computation.

First step in the Typology Subgraph Pipeline state machine.
Checks entity count against threshold, determines incremental vs. full mode,
and returns the list of typology modules to process.

Input event:
    { "case_id": "uuid-string", "trigger_source": "ingestion"|"manual"|"incremental" }

Output:
    {
        "case_id": "...",
        "is_large_case": bool,
        "entity_count": int,
        "mode": "full"|"incremental"|"skip",
        "typology_modules": ["sex_trafficking", ...],
        "trigger_source": "..."
    }
"""

import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Lambda entry point."""
    from services.typology_pipeline_utils import (
        get_case_entity_count,
        get_stale_typologies,
        has_precomputed_results,
        is_pipeline_running,
    )
    from services.typology_query_definitions import ALL_TYPOLOGY_MODULES, CASE_ENTITY_THRESHOLD

    case_id = event.get("case_id", "")
    trigger_source = event.get("trigger_source", "manual")

    if not case_id:
        logger.error("Missing case_id in event")
        return {
            "case_id": "",
            "is_large_case": False,
            "entity_count": 0,
            "mode": "skip",
            "typology_modules": [],
            "trigger_source": trigger_source,
            "error": "Missing case_id",
        }

    # Check if pipeline is already running for this case
    if is_pipeline_running(case_id):
        logger.info("Pipeline already running for case %s — skipping", case_id)
        return {
            "case_id": case_id,
            "is_large_case": True,
            "entity_count": 0,
            "mode": "skip",
            "typology_modules": [],
            "trigger_source": trigger_source,
            "skip_reason": "pipeline_already_running",
        }

    entity_count = get_case_entity_count(case_id)
    is_large = entity_count >= CASE_ENTITY_THRESHOLD

    if not is_large:
        logger.info("Case %s has %d entities (< %d threshold) — skipping pipeline",
                    case_id, entity_count, CASE_ENTITY_THRESHOLD)
        return {
            "case_id": case_id,
            "is_large_case": False,
            "entity_count": entity_count,
            "mode": "skip",
            "typology_modules": [],
            "trigger_source": trigger_source,
        }

    # Determine mode: full vs incremental
    has_existing = has_precomputed_results(case_id)
    if has_existing:
        stale_modules = get_stale_typologies(case_id)
        if stale_modules:
            # If all modules are stale, do a full recompute
            if set(stale_modules) == set(ALL_TYPOLOGY_MODULES):
                mode = "full"
                modules_to_process = ALL_TYPOLOGY_MODULES
            else:
                mode = "incremental"
                modules_to_process = stale_modules
        else:
            # Existing results, nothing stale — only recompute if manual trigger
            if trigger_source == "manual":
                mode = "full"
                modules_to_process = ALL_TYPOLOGY_MODULES
            else:
                mode = "skip"
                modules_to_process = []
    else:
        # No existing results — full computation
        mode = "full"
        modules_to_process = ALL_TYPOLOGY_MODULES

    logger.info(
        "Case %s: entity_count=%d, mode=%s, modules=%d",
        case_id, entity_count, mode, len(modules_to_process),
    )

    return {
        "case_id": case_id,
        "is_large_case": True,
        "entity_count": entity_count,
        "mode": mode,
        "typology_modules": modules_to_process,
        "trigger_source": trigger_source,
    }
