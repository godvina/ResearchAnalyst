"""One-Click Deployment Package Generator.

Generates a self-contained deployment bundle from wizard answers:
- Parameterized CloudFormation YAML template
- Lambda code zip (src/ directory)
- Markdown deployment guide with step-by-step instructions

The bundle enables zero-coding deployment: upload zip to S3, deploy CFN stack,
get a working system in 30-45 minutes.

Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7, 22.9, 22.10
"""

import io
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CFN_BASE_TEMPLATE = _PROJECT_ROOT / "infra" / "cfn" / "base_template.yaml"


class DeploymentGenerator:
    """Generates deployment bundles from wizard answers and pipeline config."""

    def generate_bundle(
        self, answers: dict, config: dict, cost_estimate: dict
    ) -> dict:
        """Orchestrate creation of the full deployment bundle.

        Returns:
            dict with keys:
                cfn_template   — rendered CloudFormation YAML string
                deployment_guide — markdown deployment instructions
                pipeline_config — the generated config JSON string
                cost_estimate   — the cost estimate JSON string
                bundle_contents — list of filenames in the bundle
        """
        cfn_template = self._render_cfn_template(answers, config)
        deployment_guide = self._generate_deployment_guide(answers, cost_estimate)

        bundle_contents = [
            "template.yaml",
            "lambda-code.zip",
            "DEPLOYMENT_GUIDE.md",
            "pipeline-config.json",
            "cost-estimate.json",
        ]

        return {
            "cfn_template": cfn_template,
            "deployment_guide": deployment_guide,
            "pipeline_config": json.dumps(config, indent=2),
            "cost_estimate": json.dumps(cost_estimate, indent=2),
            "bundle_contents": bundle_contents,
        }

    # ------------------------------------------------------------------
    # CloudFormation template rendering
    # ------------------------------------------------------------------

    def _render_cfn_template(self, answers: dict, config: dict) -> str:
        """Render CloudFormation YAML from base template with substitutions.

        Uses simple string replacement (no Jinja2 dependency) to inject
        wizard-derived values into the parameterized base template.
        """
        template_path = _CFN_BASE_TEMPLATE
        if not template_path.exists():
            raise FileNotFoundError(
                f"Base CloudFormation template not found at {template_path}"
            )

        template = template_path.read_text()

        # Derive sizing from wizard answers
        doc_count = answers.get("document_count", 0)
        volume_tb = answers.get("total_volume_tb", 0)
        concurrent_users = answers.get("concurrent_users", 10)

        # Neptune NCU sizing
        if doc_count > 500_000:
            min_ncu, max_ncu = 2.0, 16.0
        elif doc_count > 100_000:
            min_ncu, max_ncu = 1.0, 8.0
        else:
            min_ncu, max_ncu = 1.0, 4.0

        # Aurora ACU sizing
        if doc_count > 1_000_000:
            min_acu, max_acu = 2.0, 16.0
        elif doc_count > 100_000:
            min_acu, max_acu = 1.0, 8.0
        else:
            min_acu, max_acu = 0.5, 4.0

        # OpenSearch OCU sizing
        search_tier = config.get("embed", {}).get("search_tier", "standard")
        if search_tier == "enterprise":
            min_ocu = 4
        else:
            min_ocu = 2

        # Rekognition enabled?
        rek_enabled = config.get("rekognition", {}).get("enabled", False)

        # Region / GovCloud detection
        region = answers.get("aws_region", "us-east-1")
        is_govcloud = region.startswith("us-gov-")
        partition = "aws-us-gov" if is_govcloud else "aws"

        # Pipeline config as escaped JSON for CFN default
        config_json_escaped = json.dumps(config).replace("\\", "\\\\").replace('"', '\\"')

        # Perform substitutions
        replacements = {
            "{{MIN_NCU}}": str(min_ncu),
            "{{MAX_NCU}}": str(max_ncu),
            "{{MIN_ACU}}": str(min_acu),
            "{{MAX_ACU}}": str(max_acu),
            "{{MIN_OCU}}": str(min_ocu),
            "{{SEARCH_TIER}}": search_tier,
            "{{REKOGNITION_ENABLED}}": str(rek_enabled).lower(),
            "{{PARTITION}}": partition,
            "{{PIPELINE_CONFIG_DEFAULT}}": config_json_escaped,
            "{{GENERATED_TIMESTAMP}}": datetime.now(timezone.utc).isoformat(),
        }

        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)

        return template

    # ------------------------------------------------------------------
    # Lambda code packaging
    # ------------------------------------------------------------------

    def _package_lambda_code(self) -> bytes:
        """Zip the src/ directory into a Lambda deployment package.

        Returns the zip file contents as bytes.
        """
        src_dir = _PROJECT_ROOT / "src"
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(src_dir):
                for fname in files:
                    if fname.endswith((".py", ".json", ".yaml", ".html")):
                        full_path = Path(root) / fname
                        arc_name = full_path.relative_to(_PROJECT_ROOT)
                        zf.write(full_path, arc_name)

            # Include config/aws_pricing.json
            pricing_path = _PROJECT_ROOT / "config" / "aws_pricing.json"
            if pricing_path.exists():
                zf.write(pricing_path, "config/aws_pricing.json")

        return buf.getvalue()

    # ------------------------------------------------------------------
    # Deployment guide generation
    # ------------------------------------------------------------------

    def _generate_deployment_guide(self, answers: dict, cost: dict) -> str:
        """Generate markdown deployment instructions."""
        region = answers.get("aws_region", "us-east-1")
        is_govcloud = region.startswith("us-gov-")
        inv_type = answers.get("investigation_type", "general")
        doc_count = answers.get("document_count", 0)
        volume_tb = answers.get("total_volume_tb", 0)

        one_time_total = cost.get("one_time", {}).get("total", 0)
        monthly_total = cost.get("monthly", {}).get("total", 0)

        console_url = (
            "https://console.amazonaws-us-gov.com" if is_govcloud
            else "https://console.aws.amazon.com"
        )

        guide = f"""# Deployment Guide — Investigative Case Management Platform

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

## Overview

This guide walks you through deploying the Investigative Case Management
Platform into your AWS account. The deployment uses a CloudFormation template
that provisions all required infrastructure automatically.

**Investigation Type:** {inv_type}
**Estimated Documents:** {doc_count:,}
**Estimated Volume:** {volume_tb} TB
**Estimated One-Time Cost:** ${one_time_total:,.2f}
**Estimated Monthly Cost:** ${monthly_total:,.2f}
**Target Region:** {region}

---

## Prerequisites

1. An AWS account with administrator access{" (GovCloud)" if is_govcloud else ""}
2. AWS CLI configured with credentials for the target account
3. An S3 bucket in **{region}** for the deployment artifacts
4. A valid email address for admin notifications

---

## Step 1: Upload Lambda Code to S3

Upload the `lambda-code.zip` file to your deployment S3 bucket:

```bash
aws s3 cp lambda-code.zip s3://YOUR-DEPLOYMENT-BUCKET/deployments/lambda-code.zip \\
    --region {region}
```

---

## Step 2: Deploy the CloudFormation Stack

### Option A: AWS Console

1. Open the CloudFormation console: {console_url}/cloudformation
2. Click **Create stack** → **With new resources (standard)**
3. Select **Upload a template file** and upload `template.yaml`
4. Fill in the parameters:
   - **EnvironmentName**: A prefix for resource names (e.g., `prod`)
   - **AdminEmail**: Your email for alarm notifications
   - **VpcCidr**: VPC CIDR block (default `10.0.0.0/16` is fine for most cases)
   - **DeploymentBucketName**: The S3 bucket name from Step 1
   - **LambdaCodeKey**: S3 key for the Lambda zip (default `deployments/lambda-code.zip`)
5. Click **Next** through options, acknowledge IAM capabilities, and click **Create stack**
6. Wait 30-45 minutes for the stack to complete

### Option B: AWS CLI

```bash
aws cloudformation create-stack \\
    --stack-name investigator-platform \\
    --template-body file://template.yaml \\
    --parameters \\
        ParameterKey=EnvironmentName,ParameterValue=prod \\
        ParameterKey=AdminEmail,ParameterValue=admin@example.com \\
        ParameterKey=DeploymentBucketName,ParameterValue=YOUR-DEPLOYMENT-BUCKET \\
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \\
    --region {region}
```

---

## Step 3: Verify the Deployment

Once the stack status shows **CREATE_COMPLETE**:

1. Go to the **Outputs** tab of the CloudFormation stack
2. Note the following values:
   - **InvestigatorURL** — Open this URL to access the investigator interface
   - **ApiGatewayURL** — The API endpoint (used by the frontend automatically)
   - **S3DataBucket** — Upload case documents to this bucket
   - **AuroraEndpoint** — Database endpoint (for admin use)
   - **NeptuneEndpoint** — Graph database endpoint (for admin use)

---

## Step 4: Access the Investigator Interface

1. Open the **InvestigatorURL** from the stack outputs in your browser
2. The platform is ready to use — create a new case and start uploading documents

---

## Step 5: Upload Case Documents

Upload documents to the S3 data bucket under the case prefix:

```bash
aws s3 cp ./my-documents/ s3://DATA-BUCKET/cases/CASE-ID/raw/ \\
    --recursive --region {region}
```

Or use the investigator interface to upload documents directly.

---

## Architecture Summary

The deployed stack includes:

| Service | Purpose |
|---------|---------|
| Amazon VPC | Network isolation with private subnets |
| Amazon Aurora Serverless v2 | Case metadata, pipeline config, audit logs |
| Amazon Neptune Serverless | Knowledge graph for entity relationships |
| Amazon OpenSearch Serverless | Vector search and keyword search |
| AWS Lambda | API handlers and pipeline processing |
| AWS Step Functions | Ingestion pipeline orchestration |
| Amazon API Gateway | REST API for frontend |
| Amazon S3 | Document storage and static website hosting |
| Amazon CloudFront | HTTPS frontend delivery |
| Amazon Bedrock | Entity extraction and embeddings |
| Amazon CloudWatch | Monitoring and alarms |

---

## Troubleshooting

- **Stack creation fails**: Check the **Events** tab for the first `CREATE_FAILED` event
- **Lambda errors**: Check CloudWatch Logs for the Lambda function group
- **Database connectivity**: Ensure the Lambda functions are in the VPC private subnets
- **Frontend not loading**: Verify CloudFront distribution status is **Deployed**

---

## Cost Management

- The platform uses serverless services that scale to zero when idle
- Aurora, Neptune, and OpenSearch have minimum capacity units that incur baseline costs
- Monitor costs via AWS Cost Explorer, filtered by the stack's resource tags
"""
        return guide

    # ------------------------------------------------------------------
    # Tier-aware deployment (customer-deployment-wizard)
    # ------------------------------------------------------------------

    MODULE_FILES = {
        "investigator": ["investigator.html"],
        "prosecutor": ["prosecutor.html"],
        "network_discovery": ["network_discovery.html"],
        "document_assembly": ["document_assembly.html"],
    }
    SHARED_FILES = ["chatbot.html", "pipeline-config.html", "portfolio.html",
                    "workbench.html", "wizard.html", "deployment-wizard.html", "config.js"]

    def determine_tier(self, document_count: int) -> str:
        if document_count < 100_000:
            return "Small"
        if document_count < 1_000_000:
            return "Medium"
        if document_count < 10_000_000:
            return "Large"
        return "Enterprise"

    def get_tier_sizing(self, tier: str) -> dict:
        from services.cost_calculator import TIER_SIZING
        return TIER_SIZING.get(tier, TIER_SIZING["Small"])

    def _select_frontend_files(self, modules: list[str]) -> list[str]:
        files = list(self.SHARED_FILES)
        for mod in modules:
            files.extend(self.MODULE_FILES.get(mod, []))
        return files

    def _render_cfn_for_tier(self, answers: dict, config: dict, tier: str) -> str:
        """Render CloudFormation template with tier-specific sizing."""
        sizing = self.get_tier_sizing(tier)
        region = answers.get("aws_region", "us-east-1")
        is_govcloud = region.startswith("us-gov-")
        partition = "aws-us-gov" if is_govcloud else "aws"
        kms_arn = answers.get("kms_key_arn", "")
        vpc_cidr = answers.get("vpc_cidr", "10.0.0.0/16")

        nep = sizing.get("neptune", {})
        aur = sizing.get("aurora", {})
        oss = sizing.get("opensearch", {})

        template = f"""AWSTemplateFormatVersion: '2010-09-09'
Description: Research Analyst Platform - {tier} Tier Deployment

Parameters:
  EnvironmentName:
    Type: String
    Default: prod
  AdminEmail:
    Type: String
  VpcCidr:
    Type: String
    Default: '{vpc_cidr}'
  DeploymentBucketName:
    Type: String
  LambdaCodeKey:
    Type: String
    Default: deployments/lambda-code.zip
  KmsKeyArn:
    Type: String
    Default: '{kms_arn}'
  DataVolumeTier:
    Type: String
    Default: '{tier}'
    AllowedValues: [Small, Medium, Large, Enterprise]

Resources:
  # VPC
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: !Ref VpcCidr
      EnableDnsHostnames: true
      EnableDnsSupport: true

  # Aurora PostgreSQL Serverless v2
  AuroraCluster:
    Type: AWS::RDS::DBCluster
    Properties:
      Engine: aurora-postgresql
      EngineVersion: '15.4'
      ServerlessV2ScalingConfiguration:
        MinCapacity: {aur.get('min_acu', 0.5)}
        MaxCapacity: {aur.get('max_acu', 4)}
      {'KmsKeyId: !Ref KmsKeyArn' if kms_arn else '# KMS not configured'}

  # Neptune
  NeptuneCluster:
    Type: AWS::Neptune::DBCluster
    Properties:
      {'ServerlessScalingConfiguration:' if nep.get('type') == 'serverless' else f"# Neptune instance type: {nep.get('type', 'serverless')}"}
      {'  MinCapacity: ' + str(nep.get('min_ncu', 1)) if nep.get('type') == 'serverless' else ''}
      {'  MaxCapacity: ' + str(nep.get('max_ncu', 4)) if nep.get('type') == 'serverless' else ''}
      {'KmsKeyId: !Ref KmsKeyArn' if kms_arn else '# KMS not configured'}

  # OpenSearch Serverless
  SearchCollection:
    Type: AWS::OpenSearchServerless::Collection
    Properties:
      Name: !Sub '${{EnvironmentName}}-search'
      Type: VECTORSEARCH
      # OCU count: {oss.get('ocu', 2)}

  # S3 Data Lake
  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${{EnvironmentName}}-data-lake-${{AWS::AccountId}}'
      {'BucketEncryption:' if kms_arn else '# Default encryption'}
      {'  ServerSideEncryptionConfiguration:' if kms_arn else ''}
      {'    - ServerSideEncryptionByDefault:' if kms_arn else ''}
      {'        SSEAlgorithm: aws:kms' if kms_arn else ''}
      {'        KMSMasterKeyID: !Ref KmsKeyArn' if kms_arn else ''}

  # CloudFront + S3 Frontend
  FrontendBucket:
    Type: AWS::S3::Bucket
    Properties:
      WebsiteConfiguration:
        IndexDocument: investigator.html

  CloudFrontDistribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Origins:
          - DomainName: !GetAtt FrontendBucket.RegionalDomainName
            Id: S3Origin
        DefaultCacheBehavior:
          TargetOriginId: S3Origin
          ViewerProtocolPolicy: redirect-to-https
        Enabled: true

Outputs:
  FrontendURL:
    Value: !Sub 'https://${{CloudFrontDistribution.DomainName}}'
  ApiGatewayURL:
    Value: !Sub 'https://${{EnvironmentName}}-api.execute-api.{region}.{partition}.com/v1'
  S3DataBucket:
    Value: !Ref DataBucket
  AuroraEndpoint:
    Value: !GetAtt AuroraCluster.Endpoint.Address
  NeptuneEndpoint:
    Value: !GetAtt NeptuneCluster.Endpoint
"""
        return template

    def _generate_helper_scripts(self, answers: dict) -> dict[str, str]:
        region = answers.get("aws_region", "us-east-1")
        bucket = answers.get("s3_bucket_name", "YOUR-BUCKET")
        return {
            "scripts/migrate_db.sh": f"""#!/bin/bash
# Run Aurora schema migrations
STACK_NAME="${{1:-research-analyst}}"
ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='AuroraEndpoint'].OutputValue" --output text --region {region})
echo "Running migrations against $ENDPOINT"
for f in migrations/*.sql; do
    echo "Applying $f..."
    psql -h $ENDPOINT -U postgres -d research_analyst -f $f
done
echo "Migrations complete."
""",
            "scripts/seed_statutes.sh": f"""#!/bin/bash
# Seed statute reference data
STACK_NAME="${{1:-research-analyst}}"
ENDPOINT=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='AuroraEndpoint'].OutputValue" --output text --region {region})
echo "Seeding statutes to $ENDPOINT"
psql -h $ENDPOINT -U postgres -d research_analyst -f seeds/seed_statutes.sql
echo "Seeding complete."
""",
            "scripts/deploy_lambdas.sh": f"""#!/bin/bash
# Package and deploy Lambda code
BUCKET="{bucket}"
REGION="{region}"
echo "Packaging Lambda code..."
cd src && zip -r ../lambda-code.zip . -x '__pycache__/*' '*.pyc' && cd ..
echo "Uploading to s3://$BUCKET/deployments/lambda-code.zip"
aws s3 cp lambda-code.zip s3://$BUCKET/deployments/lambda-code.zip --region $REGION
echo "Updating Lambda functions..."
aws lambda update-function-code --function-name ${{STACK_NAME}}-CaseFilesLambda --s3-bucket $BUCKET --s3-key deployments/lambda-code.zip --region $REGION
echo "Deploy complete."
""",
        }

    def _generate_cost_estimate_md(self, cost: dict, answers: dict) -> str:
        tier = cost.get("tier", "Small")
        monthly = cost.get("monthly", {})
        annual = cost.get("annual", 0)
        one_time = cost.get("one_time", {})
        return f"""# Cost Estimate — Research Analyst Platform

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
Tier: {tier}
Region: {answers.get('aws_region', 'us-east-1')}
Documents: {answers.get('document_count', 0):,}
Data Volume: {cost.get('total_data_volume_gb', 0):.1f} GB

## Monthly Recurring Costs

| Service | Monthly Cost |
|---------|-------------|
| Aurora PostgreSQL | ${monthly.get('aurora', 0):,.2f} |
| Neptune Graph | ${monthly.get('neptune', 0):,.2f} |
| OpenSearch Serverless | ${monthly.get('opensearch', 0):,.2f} |
| S3 Storage | ${monthly.get('s3', 0):,.2f} |
| Lambda Compute | ${monthly.get('lambda', 0):,.2f} |
| API Gateway | ${monthly.get('api_gateway', 0):,.2f} |
| Bedrock AI | ${monthly.get('bedrock', 0):,.2f} |
| CloudFront CDN | ${monthly.get('cloudfront', 0):,.2f} |
| **Total Monthly** | **${monthly.get('total', 0):,.2f}** |

## Annual Cost: ${annual:,.2f}

## One-Time Ingestion Costs

| Item | Cost |
|------|------|
| Ingestion Processing | ${one_time.get('ingestion_processing', 0):,.2f} |
| **Total One-Time** | **${one_time.get('total', 0):,.2f}** |
"""

    def generate_deployment_package_zip(self, answers: dict, config: dict, cost: dict) -> bytes:
        """Generate complete ZIP deployment package."""
        tier = self.determine_tier(answers.get("document_count", 0))
        modules = answers.get("modules", ["investigator"])

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. CloudFormation template
            cfn = self._render_cfn_for_tier(answers, config, tier)
            zf.writestr("deploy.yaml", cfn)

            # 2. Frontend files
            frontend_dir = _PROJECT_ROOT / "src" / "frontend"
            for fname in self._select_frontend_files(modules):
                fpath = frontend_dir / fname
                if fpath.exists():
                    content = fpath.read_text(encoding="utf-8")
                    # Replace API_URL with placeholder for deployment
                    if fname == "config.js":
                        content = content.replace(
                            "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1",
                            "__API_URL__"
                        )
                    zf.writestr(f"frontend/{fname}", content)

            # 3. Helper scripts
            for script_path, script_content in self._generate_helper_scripts(answers).items():
                zf.writestr(script_path, script_content)

            # 4. Deployment guide
            guide = self._generate_deployment_guide(answers, cost)
            zf.writestr("DEPLOYMENT_GUIDE.md", guide)

            # 5. Cost estimate
            cost_md = self._generate_cost_estimate_md(cost, answers)
            zf.writestr("COST_ESTIMATE.md", cost_md)

        return buf.getvalue()
