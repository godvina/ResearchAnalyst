#!/usr/bin/env python3
"""Deploy the Research Analyst stack with config-driven multi-environment support.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 19.2
"""

import argparse
import json
import os
import subprocess
import sys
import time

import boto3

STACK_NAME = "ResearchAnalystStack"
TEMPLATE_PATH = os.path.join("cdk.out", f"{STACK_NAME}.template.json")
ASSETS_FILE = os.path.join("cdk.out", f"{STACK_NAME}.assets.json")


def parse_args():
    parser = argparse.ArgumentParser(description="Deploy Research Analyst Platform")
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployment-configs", "default.json"),
        help="Path to deployment config JSON file",
    )
    return parser.parse_args()


def load_config(config_path):
    """Load and validate config before synth."""
    # Add infra/cdk to path for config_loader import
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config_loader import ConfigLoader, ConfigValidationError

    try:
        loader = ConfigLoader(config_path)
        return loader.load()
    except ConfigValidationError as e:
        print("Config validation failed:")
        for err in e.errors:
            print(f"  - {err}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        sys.exit(1)


def synth(config_path):
    """Run CDK synth with config context."""
    print(f"==> Synthesizing with config: {config_path}")
    result = subprocess.run(
        [sys.executable, "app.py"],
        capture_output=True, text=True,
        env={**os.environ, "CDK_CONTEXT_JSON": json.dumps({"config": config_path})},
    )
    if result.returncode != 0:
        print(f"Synth failed:\n{result.stderr}")
        sys.exit(1)
    print("==> Synth OK")


def publish_assets(config):
    """Publish CDK assets to the target account's staging bucket."""
    account = config["account"]
    region = config["region"]
    print(f"==> Publishing assets to {account}/{region}")

    if not os.path.exists(ASSETS_FILE):
        print("  No assets file found — skipping")
        return

    with open(ASSETS_FILE, encoding="utf-8") as f:
        assets = json.load(f)

    s3 = boto3.client("s3", region_name=region)

    for asset_id, asset in assets.get("files", {}).items():
        source = asset.get("source", {})
        destinations = asset.get("destinations", {})
        src_path = source.get("path", "")
        src_packaging = source.get("packaging", "file")

        for dest_key, dest in destinations.items():
            bucket = dest["bucketName"].replace("${AWS::AccountId}", account).replace("${AWS::Region}", region)
            obj_key = dest["objectKey"]

            try:
                s3.head_object(Bucket=bucket, Key=obj_key)
                print(f"  Asset {obj_key[:20]}... already exists")
                continue
            except s3.exceptions.ClientError:
                pass

            full_path = os.path.join("cdk.out", src_path)
            if src_packaging == "zip":
                import shutil
                zip_path = full_path + ".zip"
                if not os.path.exists(zip_path):
                    shutil.make_archive(full_path, "zip", full_path)
                full_path = zip_path

            if os.path.isfile(full_path):
                print(f"  Uploading {obj_key[:40]}... to s3://{bucket}")
                s3.upload_file(full_path, bucket, obj_key)
            else:
                print(f"  WARNING: Asset path not found: {full_path}")


def deploy(config):
    """Deploy via CloudFormation."""
    account = config["account"]
    region = config["region"]
    print(f"==> Deploying to {account}/{region}")

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template_body = f.read()

    if len(template_body) > 51200:
        print("  Template too large for inline, uploading to S3...")
        s3 = boto3.client("s3", region_name=region)
        bucket = f"cdk-hnb659fds-assets-{account}-{region}"
        key = f"templates/{STACK_NAME}-{int(time.time())}.json"
        s3.put_object(Bucket=bucket, Key=key, Body=template_body.encode("utf-8"))
        template_url = f"https://s3.amazonaws.com/{bucket}/{key}"
    else:
        template_url = None

    cfn = boto3.client("cloudformation", region_name=region)

    try:
        cfn.describe_stacks(StackName=STACK_NAME)
        action = "update"
    except cfn.exceptions.ClientError:
        action = "create"

    params = {
        "StackName": STACK_NAME,
        "Capabilities": ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"],
    }
    if template_url:
        params["TemplateURL"] = template_url
    else:
        params["TemplateBody"] = template_body

    try:
        if action == "update":
            cfn.update_stack(**params)
        else:
            cfn.create_stack(**params)
    except cfn.exceptions.ClientError as e:
        if "No updates are to be performed" in str(e):
            print("  No changes to deploy.")
            return
        raise

    print(f"  Waiting for {action} to complete...")
    waiter = cfn.get_waiter(f"stack_{action}_complete")
    try:
        waiter.wait(StackName=STACK_NAME, WaiterConfig={"Delay": 10, "MaxAttempts": 120})
        print(f"==> Stack {action} complete!")
    except Exception as e:
        print(f"==> Stack {action} FAILED: {e}")
        events = cfn.describe_stack_events(StackName=STACK_NAME)["StackEvents"][:10]
        for ev in events:
            status = ev.get("ResourceStatus", "")
            reason = ev.get("ResourceStatusReason", "")
            if "FAILED" in status or "ROLLBACK" in status:
                print(f"  {ev['LogicalResourceId']}: {status} - {reason}")
        sys.exit(1)


def print_summary(config):
    """Print post-deployment summary."""
    region = config["region"]
    cfn = boto3.client("cloudformation", region_name=region)
    try:
        resp = cfn.describe_stacks(StackName=STACK_NAME)
        outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    except Exception:
        outputs = {}

    print("\n" + "=" * 60)
    print(f"DEPLOYMENT SUMMARY — {config['environment_name']}")
    print("=" * 60)
    if "ApiGatewayUrl" in outputs:
        print(f"  API URL:     {outputs['ApiGatewayUrl']}")
    print(f"  S3 Bucket:   {outputs.get('DataBucketName', 'N/A')}")
    print(f"  Aurora:      {outputs.get('AuroraClusterEndpoint', 'N/A')}")
    if "NeptuneClusterEndpoint" in outputs:
        print(f"  Neptune:     {outputs['NeptuneClusterEndpoint']}")
    if "OpenSearchEndpoint" in outputs:
        print(f"  OpenSearch:  {outputs['OpenSearchEndpoint']}")
    print()
    print("NEXT STEPS:")
    print("  1. Run Aurora migrations")
    print("  2. Upload frontend to S3")
    print("  3. Load sample data (optional)")
    print("=" * 60)


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    synth(args.config)
    publish_assets(config)
    deploy(config)
    print_summary(config)
