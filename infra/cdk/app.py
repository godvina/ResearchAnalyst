#!/usr/bin/env python3
"""CDK app entry point for the Research Analyst Platform."""

import os
import sys

# Add infra/cdk to path for construct imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aws_cdk as cdk

from config_loader import ConfigLoader
from stacks.research_analyst_stack import ResearchAnalystStack

app = cdk.App()

# Read config path from CDK context, env var, or default
config_path = app.node.try_get_context("config") or os.environ.get("DEPLOY_CONFIG") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "deployment-configs", "default.json",
)

# Load and validate config
loader = ConfigLoader(config_path)
config = loader.load()

ResearchAnalystStack(
    app,
    "ResearchAnalystStack",
    config=config,
    description="Research Analyst Platform — config-driven multi-environment deployment",
    env=cdk.Environment(
        account=config["account"],
        region=config["region"],
    ),
)

app.synth()

# --- Post-process: fix circular dependency in CloudFormation template ---
import json
import glob

for tpl_path in glob.glob(os.path.join("cdk.out", "*.template.json")):
    with open(tpl_path, encoding="utf-8") as f:
        tpl = json.load(f)
    modified = False
    for logical_id, resource in tpl.get("Resources", {}).items():
        rtype = resource.get("Type", "")
        if rtype == "AWS::ApiGateway::Deployment" and "DependsOn" in resource:
            del resource["DependsOn"]
            modified = True
        if rtype == "AWS::Lambda::Function" and "DependsOn" in resource:
            deps = resource["DependsOn"]
            if isinstance(deps, list):
                new_deps = [d for d in deps if "DefaultPolicy" not in d]
                if len(new_deps) != len(deps):
                    resource["DependsOn"] = new_deps if new_deps else None
                    if resource["DependsOn"] is None:
                        del resource["DependsOn"]
                    modified = True
    if modified:
        with open(tpl_path, "w", encoding="utf-8") as f:
            json.dump(tpl, f, indent=1)
