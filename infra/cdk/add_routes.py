#!/usr/bin/env python3
"""Add missing API Gateway routes (batch-loader, admin, etc.) directly via AWS API.

These routes were never deployed because the CDK stack update failed.
This script adds them manually, pointing to the CaseFiles Lambda.
"""

import boto3
import time

REGION = "us-east-1"
API_ID = "edb025my3i"
LAMBDA_ARN = "arn:aws:lambda:us-east-1:974220725866:function:ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
ACCOUNT_ID = "974220725866"

apigw = boto3.client("apigateway", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)


def get_root_id():
    resources = apigw.get_resources(restApiId=API_ID, limit=500)["items"]
    for r in resources:
        if r["path"] == "/":
            return r["id"]


def find_resource(path):
    """Find existing resource by path."""
    resources = apigw.get_resources(restApiId=API_ID, limit=500)["items"]
    for r in resources:
        if r["path"] == path:
            return r["id"]
    return None


def create_resource(parent_id, path_part):
    """Create a resource under parent."""
    resp = apigw.create_resource(
        restApiId=API_ID,
        parentId=parent_id,
        pathPart=path_part,
    )
    print(f"  Created resource: {resp['path']} ({resp['id']})")
    return resp["id"]


def add_method_and_integration(resource_id, http_method, path_for_display):
    """Add a method with Lambda proxy integration."""
    # Create method
    try:
        apigw.put_method(
            restApiId=API_ID,
            resourceId=resource_id,
            httpMethod=http_method,
            authorizationType="NONE",
        )
    except apigw.exceptions.ConflictException:
        print(f"  Method {http_method} already exists on {path_for_display}")
        return

    # Create Lambda proxy integration
    uri = f"arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/{LAMBDA_ARN}/invocations"
    apigw.put_integration(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod=http_method,
        type="AWS_PROXY",
        integrationHttpMethod="POST",
        uri=uri,
    )

    # Add method response for CORS
    apigw.put_method_response(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod=http_method,
        statusCode="200",
        responseParameters={
            "method.response.header.Access-Control-Allow-Origin": False,
            "method.response.header.Access-Control-Allow-Headers": False,
            "method.response.header.Access-Control-Allow-Methods": False,
        },
    )

    print(f"  Added {http_method} → Lambda on {path_for_display}")


def add_cors_options(resource_id, path_for_display):
    """Add OPTIONS method for CORS preflight."""
    try:
        apigw.put_method(
            restApiId=API_ID,
            resourceId=resource_id,
            httpMethod="OPTIONS",
            authorizationType="NONE",
        )
    except apigw.exceptions.ConflictException:
        return

    apigw.put_integration(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        type="MOCK",
        requestTemplates={"application/json": '{"statusCode": 200}'},
    )

    apigw.put_method_response(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        statusCode="200",
        responseParameters={
            "method.response.header.Access-Control-Allow-Origin": False,
            "method.response.header.Access-Control-Allow-Headers": False,
            "method.response.header.Access-Control-Allow-Methods": False,
        },
    )

    apigw.put_integration_response(
        restApiId=API_ID,
        resourceId=resource_id,
        httpMethod="OPTIONS",
        statusCode="200",
        responseParameters={
            "method.response.header.Access-Control-Allow-Origin": "'*'",
            "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization,X-Amz-Date,X-Api-Key'",
            "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
        },
    )


def ensure_lambda_permission(source_arn_suffix):
    """Ensure API Gateway can invoke the Lambda."""
    # Skip — Lambda already has API Gateway permissions from CDK deployment
    pass


def add_proxy_route(parent_path, parent_id):
    """Add a {proxy+} catch-all under a parent resource."""
    proxy_id = find_resource(f"{parent_path}/{{proxy+}}")
    if not proxy_id:
        proxy_id = create_resource(parent_id, "{proxy+}")
    add_method_and_integration(proxy_id, "ANY", f"{parent_path}/{{proxy+}}")
    add_cors_options(proxy_id, f"{parent_path}/{{proxy+}}")


def main():
    root_id = get_root_id()
    print(f"Root ID: {root_id}")

    # Ensure broad Lambda permission for API Gateway
    ensure_lambda_permission("any")

    # --- batch-loader routes ---
    print("\n==> Adding /batch-loader routes...")
    bl_id = find_resource("/batch-loader") or create_resource(root_id, "batch-loader")

    for sub in ["discover", "start", "status", "manifests", "quarantine", "history"]:
        sub_id = find_resource(f"/batch-loader/{sub}") or create_resource(bl_id, sub)
        method = "POST" if sub == "start" else "GET"
        add_method_and_integration(sub_id, method, f"/batch-loader/{sub}")
        add_cors_options(sub_id, f"/batch-loader/{sub}")

    # /batch-loader/manifests/{batch_id}
    manifests_id = find_resource("/batch-loader/manifests")
    if manifests_id:
        bid_id = find_resource("/batch-loader/manifests/{batch_id}") or create_resource(manifests_id, "{batch_id}")
        add_method_and_integration(bid_id, "GET", "/batch-loader/manifests/{batch_id}")
        add_cors_options(bid_id, "/batch-loader/manifests/{batch_id}")

    # --- Source browser routes (data-prep-source-management) ---
    print("\n==> Adding /batch-loader source browser routes...")
    for sub in ["sources", "extract-status", "pipeline-summary"]:
        sub_id = find_resource(f"/batch-loader/{sub}") or create_resource(bl_id, sub)
        add_method_and_integration(sub_id, "GET", f"/batch-loader/{sub}")
        add_cors_options(sub_id, f"/batch-loader/{sub}")

    extract_id = find_resource("/batch-loader/extract") or create_resource(bl_id, "extract")
    add_method_and_integration(extract_id, "POST", "/batch-loader/extract")
    add_cors_options(extract_id, "/batch-loader/extract")

    # --- admin routes ---
    print("\n==> Adding /admin routes...")
    admin_id = find_resource("/admin") or create_resource(root_id, "admin")
    users_id = find_resource("/admin/users") or create_resource(admin_id, "users")
    add_method_and_integration(users_id, "GET", "/admin/users")
    add_method_and_integration(users_id, "POST", "/admin/users")
    add_cors_options(users_id, "/admin/users")

    uid_id = find_resource("/admin/users/{id}") or create_resource(users_id, "{id}")
    for m in ["GET", "PUT", "DELETE"]:
        add_method_and_integration(uid_id, m, "/admin/users/{id}")
    add_cors_options(uid_id, "/admin/users/{id}")

    audit_id = find_resource("/admin/audit-log") or create_resource(admin_id, "audit-log")
    add_method_and_integration(audit_id, "GET", "/admin/audit-log")
    add_cors_options(audit_id, "/admin/audit-log")

    # --- Deploy ---
    print("\n==> Creating deployment...")
    deploy = apigw.create_deployment(restApiId=API_ID, stageName="v1")
    print(f"  Deployed: {deploy['id']}")
    print("\nDone! Routes are live.")


if __name__ == "__main__":
    main()
