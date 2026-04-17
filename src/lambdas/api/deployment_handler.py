"""API Lambda handler for customer deployment wizard.

Endpoints:
    POST /deployment/validate         — validate wizard inputs
    POST /deployment/cost-estimate    — compute cost breakdown
    POST /deployment/sample-run       — start sample pipeline run
    GET  /deployment/sample-run/{id}  — get sample run results
    POST /deployment/generate-package — generate deployment ZIP
"""

import json
import logging
import re
import base64

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def validate_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        errors = []
        # Account ID: exactly 12 digits
        acct = body.get("aws_account_id", "")
        if not re.match(r"^\d{12}$", acct):
            errors.append("AWS account ID must be exactly 12 digits")
        # VPC CIDR
        cidr = body.get("vpc_cidr", "")
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$", cidr):
            errors.append("VPC CIDR must be in format like 10.0.0.0/16")
        # KMS ARN
        kms = body.get("kms_key_arn", "")
        if kms and not kms.startswith("arn:aws:kms:") and not kms.startswith("arn:aws-us-gov:kms:"):
            errors.append("KMS key ARN must start with arn:aws:kms: or arn:aws-us-gov:kms:")
        # Modules
        modules = body.get("modules", [])
        if not modules:
            errors.append("At least one module must be selected")
        if errors:
            return error_response(400, "VALIDATION_ERROR", "; ".join(errors), event)
        return success_response({"valid": True, "modules": modules}, 200, event)
    except Exception as exc:
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def cost_estimate_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        doc_count = int(body.get("document_count", 0))
        avg_size = float(body.get("avg_doc_size_mb", 1.0))
        modules = body.get("modules", ["investigator"])
        from services.cost_calculator import CostCalculator
        calc = CostCalculator()
        tier = calc.determine_tier(doc_count)
        cost = calc.calculate(tier, modules, doc_count, avg_size)
        return success_response(cost, 200, event)
    except Exception as exc:
        logger.exception("Cost estimate failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def sample_run_handler(event, context):
    from lambdas.api.response_helper import error_response, success_response
    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        documents = body.get("documents", [])
        if not documents or len(documents) > 5:
            return error_response(400, "VALIDATION_ERROR", "Upload 1-5 documents", event)
        # For now, return a mock result showing the pipeline would process these
        results = []
        for i, doc in enumerate(documents):
            results.append({
                "document_index": i + 1,
                "filename": doc.get("filename", f"document_{i+1}"),
                "status": "processed",
                "entities_found": 0,
                "relationships_found": 0,
                "classification": "pending",
            })
        return success_response({
            "run_id": "sample-" + str(hash(str(documents)))[-8:],
            "status": "completed",
            "results": results,
            "summary": {"total_entities": 0, "total_relationships": 0, "documents_processed": len(documents)},
        }, 200, event)
    except Exception as exc:
        logger.exception("Sample run failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def generate_package_handler(event, context):
    from lambdas.api.response_helper import error_response
    try:
        body = (json.loads(event.get("body")) if isinstance(event.get("body"), str) else (event.get("body") or {}))
        from services.deployment_generator import DeploymentGenerator
        from services.cost_calculator import CostCalculator
        calc = CostCalculator()
        doc_count = int(body.get("document_count", 0))
        tier = calc.determine_tier(doc_count)
        cost = calc.calculate(tier, body.get("modules", ["investigator"]), doc_count, float(body.get("avg_doc_size_mb", 1.0)))
        gen = DeploymentGenerator()
        zip_bytes = gen.generate_deployment_package_zip(body, {}, cost)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/zip",
                "Content-Disposition": "attachment; filename=deployment-package.zip",
                "Access-Control-Allow-Origin": "*",
            },
            "body": base64.b64encode(zip_bytes).decode("utf-8"),
            "isBase64Encoded": True,
        }
    except Exception as exc:
        logger.exception("Package generation failed")
        return error_response(500, "INTERNAL_ERROR", str(exc), event)


def dispatch_handler(event, context):
    from lambdas.api.response_helper import error_response
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    routes = {
        ("POST", "/deployment/validate"): validate_handler,
        ("POST", "/deployment/cost-estimate"): cost_estimate_handler,
        ("POST", "/deployment/sample-run"): sample_run_handler,
        ("POST", "/deployment/generate-package"): generate_package_handler,
    }
    handler = routes.get((method, resource))
    if handler:
        return handler(event, context)
    return error_response(404, "NOT_FOUND", f"Unknown route: {method} {resource}", event)
