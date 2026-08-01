"""Re-score a case against the typology pattern library.

Triggers the score_typology Lambda for a specific case and module.
Use after indexing new signatures into OpenSearch.

Usage:
    python scripts/rescore_case_typology.py --case-id <CASE_ID> --module ancient_mysteries
    python scripts/rescore_case_typology.py --case-id d72b81fc --module ancient_mysteries --all-sub-categories

Environment:
    AWS_REGION - defaults to us-east-1
    LAMBDA_FUNCTION - score_typology Lambda name (auto-detected from stack)
"""

import argparse
import json
import logging
import os
import sys

import boto3

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Ancient Mysteries sub-category IDs (match the typology_id values)
ANCIENT_MYSTERIES_MODULES = [
    "advanced_ancient_technology",
    "global_grid_earth_energy",
    "lost_civilizations",
    "extraterrestrial_contact",
    "sacred_geometry_mathematics",
    "consciousness_nonphysical",
]

# Known case IDs
KNOWN_CASES = {
    "ancient_aliens": "d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7",
}


def find_lambda_function() -> str:
    """Find the score_typology Lambda function name from deployed stack."""
    client = boto3.client("lambda", region_name=AWS_REGION)
    paginator = client.get_paginator("list_functions")
    for page in paginator.paginate():
        for fn in page["Functions"]:
            if "score" in fn["FunctionName"].lower() and "typology" in fn["FunctionName"].lower():
                return fn["FunctionName"]
            # Also check the mega-lambda that routes internally
            if "research-analyst" in fn["FunctionName"].lower() and "pipeline" in fn["FunctionName"].lower():
                return fn["FunctionName"]
    return ""


def invoke_scoring(lambda_name: str, case_id: str, typology_module_id: str) -> dict:
    """Invoke the score_typology Lambda for a specific case + module."""
    client = boto3.client("lambda", region_name=AWS_REGION)

    payload = {
        "case_id": case_id,
        "typology_module_id": typology_module_id,
        "execution_id": f"rescore-{typology_module_id}-manual",
    }

    logger.info("Invoking %s for case=%s module=%s", lambda_name, case_id[:8], typology_module_id)

    resp = client.invoke(
        FunctionName=lambda_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )

    result = json.loads(resp["Payload"].read())
    return result


def main():
    parser = argparse.ArgumentParser(description="Re-score case against typology pattern library")
    parser.add_argument("--case-id", required=True, help="Case ID (full UUID or known alias like 'ancient_aliens')")
    parser.add_argument("--module", required=True, help="Typology module ID (e.g., ancient_mysteries, sex_trafficking)")
    parser.add_argument("--all-sub-categories", action="store_true", help="Score all sub-categories within the module")
    parser.add_argument("--lambda-name", default=None, help="Override Lambda function name")
    args = parser.parse_args()

    # Resolve case ID
    case_id = KNOWN_CASES.get(args.case_id, args.case_id)
    if len(case_id) < 36 and "-" not in case_id:
        # Try prefix match
        for alias, full_id in KNOWN_CASES.items():
            if full_id.startswith(case_id):
                case_id = full_id
                break

    logger.info("Case ID: %s", case_id)

    # Find Lambda
    lambda_name = args.lambda_name or find_lambda_function()
    if not lambda_name:
        logger.error("Could not find score_typology Lambda. Specify with --lambda-name")
        sys.exit(1)
    logger.info("Lambda: %s", lambda_name)

    # Determine what to score
    if args.module == "ancient_mysteries" and args.all_sub_categories:
        modules_to_score = ANCIENT_MYSTERIES_MODULES
    else:
        modules_to_score = [args.module]

    # Score each
    results = []
    for mod in modules_to_score:
        try:
            result = invoke_scoring(lambda_name, case_id, mod)
            results.append(result)
            score = result.get("overall_score", 0)
            strength = result.get("match_strength", "unknown")
            logger.info("  → %s: score=%.4f (%s)", mod, score, strength)
        except Exception as e:
            logger.error("  → %s: FAILED - %s", mod, str(e)[:200])

    # Summary
    logger.info("\n=== Scoring Summary ===")
    for r in results:
        mod = r.get("typology_module_id", "?")
        score = r.get("overall_score", 0)
        subs = r.get("sub_category_scores", [])
        logger.info("  %s: %.1f%% (%d sub-categories scored)", mod, score * 100, len(subs))


if __name__ == "__main__":
    main()
