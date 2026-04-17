# Investigative Intelligence Platform — Multi-Environment Deployment Architecture

**Document Version:** 1.0
**Date:** April 11, 2026
**Author:** Emerging Tech Solutions
**Classification:** AWS Internal / NDA

---

## Executive Summary

The Investigative Intelligence Platform is a serverless AI-powered investigative analysis system built on AWS. It ingests, processes, and analyzes large volumes of evidence (documents, images, financial records) using Bedrock LLMs, knowledge graphs, and vector search to accelerate investigations.

This document describes the architecture for deploying the platform across multiple AWS environments — from internal demo accounts to FedRAMP High GovCloud production accounts. The deployment system is config-driven: one codebase produces environment-specific CloudFormation templates that adapt to service availability, security requirements, and compliance controls.

---

## 1. Platform Architecture Overview

### 1.1 AWS Services Used

| Service | Purpose | GovCloud Available |
|---------|---------|-------------------|
| Aurora Serverless v2 (PostgreSQL 16 + pgvector) | Document storage, entity storage, vector search, findings | Yes |
| Neptune Serverless | Knowledge graph (entity relationships, network analysis) | Limited (check region) |
| OpenSearch Serverless (VECTORSEARCH) | Enterprise vector search, semantic retrieval | No (use provisioned or skip) |
| Lambda (Python 3.12) | All compute — API handlers, ingestion pipeline workers | Yes |
| Step Functions | Ingestion pipeline orchestration (8-step workflow) | Yes |
| API Gateway (REST) | HTTP API for frontend and integrations | Yes |
| S3 | Data lake (raw documents, extracted text, embeddings, artifacts) | Yes |
| Bedrock | LLM inference (entity extraction, analysis, discoveries) | Yes (limited models) |
| Bedrock Knowledge Base | RAG retrieval over document corpus | Yes |
| Rekognition | Face detection, label detection, celebrity recognition | Yes |
| Textract | OCR for scanned documents | Yes |
| Secrets Manager | Aurora database credentials | Yes |

### 1.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (S3)                             │
│                    investigator.html                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────────┐
│                     API Gateway (REST)                           │
│                   /{proxy+} → Lambda                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    Lambda Functions                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐     │
│  │ case_files   │  │ ingestion    │  │ entity_resolution  │     │
│  │ (mega-       │  │ pipeline     │  │                    │     │
│  │  dispatcher) │  │ (8 workers)  │  │                    │     │
│  └──────┬───────┘  └──────┬───────┘  └────────────────────┘     │
└─────────┼─────────────────┼─────────────────────────────────────┘
          │                 │
    ┌─────▼─────┐    ┌──────▼──────┐
    │           │    │  Step       │
    │  Bedrock  │    │  Functions  │
    │  (LLM +   │    │  (Pipeline) │
    │  Embed)   │    │             │
    └───────────┘    └─────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                      Data Layer (VPC)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Aurora       │  │ Neptune      │  │ OpenSearch          │    │
│  │ Serverless v2│  │ Serverless   │  │ Serverless          │    │
│  │ (PostgreSQL  │  │ (Knowledge   │  │ (Vector Search)     │    │
│  │  + pgvector) │  │  Graph)      │  │                     │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    S3 Data Lake                            │   │
│  │  cases/{id}/raw/  |  extractions/  |  neptune-bulk-load/ │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Ingestion Pipeline (Step Functions)

The 8-step pipeline processes documents from raw upload to searchable intelligence:

1. **Resolve Config** — determine processing parameters per document
2. **Upload** — stage document in S3
3. **Parse** — extract text (Textract OCR for images/PDFs, direct read for text)
4. **Extract** — Bedrock LLM entity extraction (people, orgs, locations, dates, financial)
5. **Embed** — generate vector embeddings (Titan Embed v2)
6. **Store Artifact** — write to Aurora (documents, entities) and OpenSearch (vectors)
7. **Graph Load** — create/update Neptune knowledge graph nodes and edges
8. **Update Status** — mark document as processed

---

## 2. Deployment Tiers

### 2.1 Tier 1: Demo (Isengard Standard)

**Purpose:** Quick demo for colleagues. Full platform, minimal security.

| Setting | Value |
|---------|-------|
| Account | Any Isengard account |
| Region | us-east-1 (or any commercial) |
| VPC | Create new (10.0.0.0/16) |
| Subnets | Public (for simplicity) |
| Aurora | 0.5–4 ACU |
| Neptune | Enabled, 1–4 NCU |
| OpenSearch | Serverless |
| Encryption | AWS-managed (default) |
| Bedrock Models | Claude 3 Haiku + Titan Embed v2 |
| Deploy Time | ~20 minutes |
| Estimated Cost | ~$15/day idle, ~$50/day active |

### 2.2 Tier 2: GovCloud Test (Isengard GovCloud)

**Purpose:** Validate FedRAMP compliance, test GovCloud service availability.

| Setting | Value |
|---------|-------|
| Account | GovCloud Isengard account |
| Region | us-gov-west-1 |
| VPC | Create new (10.0.0.0/16) |
| Subnets | Private with NAT gateway |
| Aurora | 0.5–4 ACU |
| Neptune | Disabled (verify availability first) |
| OpenSearch | Disabled (not available in GovCloud Serverless) |
| Encryption | KMS CMK |
| TLS | Enforced |
| VPC Flow Logs | Enabled |
| Bedrock Models | FedRAMP High approved only |
| Deploy Time | ~25 minutes |

### 2.3 Tier 3: Customer Production (DOJ GovCloud)

**Purpose:** Production deployment with full compliance controls.

| Setting | Value |
|---------|-------|
| Account | Customer AWS GovCloud account |
| Region | us-gov-west-1 |
| VPC | Customer-provided or new |
| Subnets | Private with NAT gateway |
| Aurora | 2–16 ACU (500TB ingestion capacity) |
| Neptune | Disabled unless verified available |
| OpenSearch | Disabled (use Aurora pgvector) |
| Encryption | Customer KMS CMK |
| TLS | Enforced |
| VPC Flow Logs | Enabled |
| CloudTrail | Enabled |
| Tagging | Compliance=FedRAMP-High, DataClassification=CUI |
| Bedrock Models | FedRAMP High, excluded providers per customer policy |

---

## 3. Config-Driven Deployment System

### 3.1 How It Works

One codebase, multiple config files. Each config file describes a target environment:

```
infra/cdk/deployment-configs/
  ├── default.json              ← Current dev (backward compatible)
  ├── isengard-demo.json        ← Colleague demos
  ├── govcloud-isengard.json    ← GovCloud SA test
  └── govcloud-production.json  ← Customer production
```

Deploy command:
```bash
python deploy.py --config infra/cdk/deployment-configs/govcloud-isengard.json
```

This produces a CloudFormation template tailored to that environment. Non-technical users can also deploy the template directly via the CloudFormation console.

### 3.2 What the Config Controls

| Config Section | What It Controls |
|---------------|-----------------|
| `vpc` | Create new VPC or import existing, CIDR block |
| `aurora` | Capacity (ACU), subnet placement (public/private), KMS encryption |
| `neptune` | Enable/disable, capacity (NCU), subnet placement |
| `opensearch` | Mode: serverless, provisioned, or disabled |
| `encryption` | KMS key ARN, TLS enforcement |
| `bedrock` | LLM model ID, embedding model ID, excluded providers |
| `features` | Pipeline-only mode, Rekognition enable/disable |
| `tags` | Mandatory resource tags for compliance |
| `logging` | VPC flow logs, CloudTrail |

### 3.3 Graceful Degradation

When a service is disabled (e.g., Neptune in GovCloud), the platform adapts at runtime:

| Disabled Service | Fallback Behavior |
|-----------------|-------------------|
| Neptune | Knowledge graph features return empty results. Network analysis unavailable. Entity relationships stored in Aurora only. |
| OpenSearch Serverless | Vector search falls back to Aurora pgvector. Slightly slower but functionally equivalent. |
| Rekognition | Image analysis features disabled. Documents processed as text only. |

No code changes needed — Lambda functions check environment variables at runtime and degrade gracefully.

---

## 4. GovCloud Considerations

### 4.1 GovCloud vs Commercial — Key Differences

| Aspect | Commercial (aws) | GovCloud (aws-us-gov) |
|--------|-----------------|----------------------|
| Partition | `arn:aws:` | `arn:aws-us-gov:` |
| Regions | us-east-1, us-west-2, etc. | us-gov-west-1, us-gov-east-1 |
| Default VPC | Usually exists | Often does not exist |
| OpenSearch Serverless | Available | Not available |
| Neptune Serverless | Available | Check region availability |
| Bedrock Models | Full catalog | FedRAMP High subset only |
| Rekognition | Full features | Available with limitations |
| IAM | Standard | Same, but partition-aware ARNs required |
| S3 | Standard | Same, different endpoint format |
| CloudTrail | Optional | Typically mandatory |
| KMS | Optional | Typically mandatory (CMK) |

### 4.2 Federal Security Controls

The deployment system enforces these controls when deploying to GovCloud:

1. All databases in private subnets (no public internet access)
2. NAT gateway for outbound traffic (Bedrock API calls, S3 access)
3. KMS customer-managed key encryption for all data at rest
4. TLS 1.2+ enforced on all connections
5. VPC flow logs enabled and sent to CloudWatch
6. All resources tagged with compliance metadata
7. No hardcoded credentials — all secrets via Secrets Manager
8. IAM least-privilege policies with partition-aware ARNs
9. S3 bucket policy denying non-TLS requests
10. Block all public access on S3 buckets

### 4.3 FedRAMP Bedrock Model Availability

Based on the platform's FedRAMP Model Registry (`config/bedrock_models.json`):

**FedRAMP High (GovCloud):**
- Amazon Titan Text Express/Lite
- Amazon Titan Embed Text v2
- Anthropic Claude 3 Haiku/Sonnet
- Anthropic Claude 3.5 Sonnet
- Meta Llama 3 (8B/70B Instruct)

**FedRAMP Moderate (Commercial):**
- All FedRAMP High models, plus:
- Amazon Nova Pro/Lite/Micro
- Mistral Large/Small
- AI21 Jamba

The deployment config specifies which models to use and which providers to exclude. For example, if a customer policy prohibits a specific provider, the config's `excluded_providers` array blocks those models at deployment time.

### 4.4 DOJ-Specific Considerations

Based on publicly available information about federal law enforcement cloud deployments:

1. **Data Classification:** DOJ data is typically CUI (Controlled Unclassified Information) or higher. All storage must be encrypted with agency-controlled KMS keys.

2. **Network Isolation:** DOJ environments typically require VPC endpoints for AWS service access rather than NAT gateway internet egress. The deployment config can be extended to support VPC endpoints for S3, Bedrock, Secrets Manager, and Step Functions.

3. **Audit Logging:** All API calls must be logged via CloudTrail. All data access must be auditable. The platform's API Gateway access logs and Lambda CloudWatch logs provide this.

4. **Access Control:** DOJ environments use AWS SSO with PIV/CAC card authentication. The platform's API Gateway can be configured with IAM authorization or Cognito user pools for access control.

5. **Data Residency:** All data must remain within the GovCloud partition. No cross-partition data transfer. The platform's S3 data lake and Aurora database are region-bound by design.

6. **Incident Response:** CloudWatch alarms should be configured for Lambda errors, Aurora connection failures, and Step Functions execution failures. This is a post-deployment configuration step.

---

## 5. Deployment Runbook

### 5.1 Prerequisites

| Requirement | Demo (Tier 1) | GovCloud (Tier 2/3) |
|------------|---------------|---------------------|
| AWS CLI v2 | Required | Required |
| Python 3.12+ | Required | Required |
| AWS CDK v2 | Required (for synth) | Optional (can use template) |
| Node.js 18+ | Required (for CDK) | Optional |
| AWS Account Access | Admin or PowerUser | Admin with GovCloud access |
| Git | Required | Required |

### 5.2 Tier 1: Demo Deployment (10 Steps)

```
Step 1:  Clone the repository
         git clone <repo-url> && cd investigative-intelligence

Step 2:  Install CDK dependencies
         cd infra/cdk && pip install -r requirements.txt

Step 3:  Configure AWS credentials
         aws configure  (or set AWS_PROFILE)

Step 4:  Bootstrap CDK (first time only)
         cdk bootstrap aws://ACCOUNT_ID/REGION

Step 5:  Copy and edit config
         cp deployment-configs/isengard-demo.json deployment-configs/my-demo.json
         # Edit: set account and region if not using env vars

Step 6:  Deploy
         python deploy.py --config deployment-configs/my-demo.json

Step 7:  Run Aurora migrations
         python ../../scripts/migrate_via_lambda.py

Step 8:  Upload frontend
         aws s3 cp ../../src/frontend/investigator.html \
           s3://research-analyst-data-lake-ACCOUNT_ID/frontend/investigator.html \
           --content-type "text/html"

Step 9:  Load sample data (optional)
         # Upload sample documents to S3, trigger pipeline via API

Step 10: Verify
         curl https://API_URL/v1/health
         # Open frontend URL in browser
```

### 5.3 Tier 2: GovCloud Deployment

Same as Tier 1, but:
- Use `govcloud-isengard.json` config
- Set `AWS_DEFAULT_REGION=us-gov-west-1`
- Ensure GovCloud credentials are configured
- KMS key must be created first (or use `aws kms create-key`)
- Neptune and OpenSearch are disabled — graph and vector features use fallbacks

### 5.4 CloudFormation Console Deployment (No CDK Required)

For non-technical users who prefer the AWS Console:

1. Obtain the CloudFormation template file (`.template.json`) from the build team
2. Open AWS CloudFormation Console → Create Stack → Upload Template
3. Fill in parameters: EnvironmentName, Region, KMSKeyArn (if applicable)
4. Click Create Stack
5. Wait for CREATE_COMPLETE (~20 minutes)
6. Note the Outputs tab for API URL and S3 bucket name
7. Run Aurora migrations and upload frontend (requires CLI)

---

## 6. Modular CDK Architecture

### 6.1 Construct Hierarchy

```
ResearchAnalystStack
  ├── VpcConstruct          — VPC, subnets, NAT, flow logs
  ├── SecurityConstruct     — S3 bucket, KMS, TLS policies
  ├── AuroraConstruct       — Aurora cluster, RDS Proxy, security group
  ├── NeptuneConstruct      — Neptune cluster (conditional), security group
  ├── OpenSearchConstruct   — OpenSearch collection (conditional), VPC endpoint
  ├── LambdaConstruct       — All Lambda functions, IAM roles, env vars
  ├── PipelineConstruct     — Step Functions state machine
  └── ApiConstruct          — API Gateway (conditional)
```

### 6.2 Conditional Resource Creation

Each construct checks its config section and skips resource creation when disabled:

- `NeptuneConstruct`: creates nothing when `neptune.enabled=false`
- `OpenSearchConstruct`: creates nothing when `opensearch.mode="disabled"`
- `ApiConstruct`: creates nothing when `features.pipeline_only=true`
- `LambdaConstruct`: skips Rekognition Lambda when `features.rekognition=false`

### 6.3 Partition-Aware IAM

All IAM policy ARNs use `${AWS::Partition}` instead of hardcoded `aws`:

```
Before: arn:aws:bedrock:us-east-1::foundation-model/...
After:  arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/...
```

This ensures the same template works in both commercial and GovCloud partitions.

---

## 7. Scaling for 500TB Ingestion

### 7.1 Architecture for Large-Scale Ingestion

For a 500TB pilot ingestion:

| Component | Configuration |
|-----------|--------------|
| Aurora | 8–16 ACU max capacity (auto-scales) |
| S3 | Standard tier, IA transition at 90 days |
| Lambda | 512MB–1GB memory, 15-minute timeout for large documents |
| Step Functions | 24-hour timeout, Express workflows for high-throughput |
| Bedrock | Provisioned throughput for sustained entity extraction |
| Batch Size | 5,000 documents per batch, 50 per sub-batch |

### 7.2 Estimated Processing Rates

| Document Type | Processing Rate | 500TB Estimate |
|--------------|----------------|----------------|
| Text files (< 1MB) | ~200 docs/minute | ~3 days |
| PDFs (1-10MB) | ~50 docs/minute | ~2 weeks |
| Scanned images (OCR) | ~20 docs/minute | ~4 weeks |
| Mixed corpus | ~80 docs/minute | ~2 weeks |

### 7.3 Cost Estimates (500TB Pilot)

| Service | Estimated Cost |
|---------|---------------|
| S3 Storage (500TB) | ~$11,500/month |
| Aurora (sustained processing) | ~$2,000/month |
| Bedrock (entity extraction) | ~$5,000–15,000 (one-time) |
| Lambda (processing) | ~$500 (one-time) |
| Neptune (graph) | ~$500/month |
| Step Functions | ~$200 (one-time) |
| **Total (first month)** | **~$20,000–30,000** |

---

## 8. Next Steps

1. Build the config-driven CDK (this week)
2. Test in Isengard standard account (clean room validation)
3. Test in GovCloud Isengard account with SA
4. Create deployment runbook with screenshots
5. Package CloudFormation template for distribution
6. Customer deployment planning with DOJ team

---

## Appendix A: Deployment Config Schema

See `infra/cdk/deployment-configs/` for complete examples. Key fields:

```json
{
  "environment_name": "govcloud-test",
  "account": "CDK_DEFAULT_ACCOUNT",
  "region": "us-gov-west-1",
  "partition": "aws-us-gov",
  "vpc": { "create_new": true, "cidr": "10.0.0.0/16" },
  "aurora": { "min_capacity": 0.5, "max_capacity": 4, "subnet_type": "PRIVATE_WITH_EGRESS" },
  "neptune": { "enabled": false },
  "opensearch": { "mode": "disabled" },
  "encryption": { "kms_key_arn": "arn:aws-us-gov:kms:...", "enforce_tls": true },
  "bedrock": { "llm_model_id": "anthropic.claude-3-haiku-20240307-v1:0", "embedding_model_id": "amazon.titan-embed-text-v2:0" },
  "features": { "pipeline_only": false, "rekognition": false },
  "tags": { "Compliance": "FedRAMP-High" },
  "logging": { "vpc_flow_logs": true }
}
```

## Appendix B: Current Platform Capabilities

| Feature | Description | Status |
|---------|-------------|--------|
| Document Ingestion Pipeline | 8-step serverless pipeline (upload → parse → extract → embed → store → graph → status) | Production |
| Intelligence Search | Keyword (BM25), Semantic (kNN), Hybrid search across evidence | Production |
| Knowledge Graph | Neptune-based entity relationship visualization | Production |
| AI Intelligence Briefing | Bedrock-powered case narrative with Command Center indicators | Production |
| Case Health Bar | 6 SVG radial gauges showing investigation health at a glance | Production |
| Did You Know | AI-generated investigative discoveries with feedback learning | Production |
| Anomaly Radar | 5-dimension statistical anomaly detection with sparklines | Production |
| Investigative Findings Drilldown | 3-level drill: Investigation Leads → Evidence Thread → Source Documents | Production |
| Research Hub | 4-panel research workspace: Chat, Compare, Discovery, External Research | Production |
| Cross-Case Analysis | Entity overlap detection across multiple investigations | Production |
| Entity Resolution | LLM-powered duplicate entity merging in Neptune | Production |
| Report Generation | Case Summary, Prosecution Memo, Entity Dossier, Evidence Inventory, Subpoena List | Production |
| Image Analysis | Rekognition face/label detection, celebrity recognition | Production |
| FedRAMP Model Registry | Configurable Bedrock model selection with provider exclusion | Production |


---

## 9. Code Compliance & Federal Deployment Readiness

### 9.1 Re-Deployment After Changes

The deployment system is designed for continuous updates. At any point after making changes to the application code:

1. Run `python deploy.py --config <your-config>.json`
2. CDK packages the current state of `src/` into a Lambda zip
3. CloudFormation performs a rolling update — only changed resources are updated
4. Aurora, Neptune, S3 data are untouched — no data loss
5. Lambda functions get the new code, API Gateway stays up
6. Zero downtime for end users

You can deploy daily, weekly, or on-demand. Each deployment is a point-in-time snapshot of whatever code exists in the repository at that moment.

### 9.2 Software Supply Chain Assessment

**Python Runtime:**
- Lambda uses AWS-managed Python 3.12 runtime (patched and maintained by AWS)
- No custom Python packages installed — all code uses standard library + boto3 (pre-installed in Lambda)
- No `requirements.txt` or `pip install` in the Lambda deployment — zero third-party dependency risk
- This is a significant compliance advantage: the entire dependency chain is AWS-managed

**Frontend:**
- Single HTML file (`investigator.html`) with all CSS and JavaScript inline
- One external dependency: `vis-network` loaded from `unpkg.com` CDN for graph visualization
- **Action Required for Production:** Bundle `vis-network.min.js` locally in S3 to eliminate external CDN dependency. Federal environments should not load scripts from external CDNs.

**Infrastructure as Code:**
- CDK (Python) generates CloudFormation templates — standard AWS tooling
- CloudFormation templates are JSON — auditable, version-controlled, reproducible
- No custom CloudFormation resources or macros — all native AWS resource types

### 9.3 Federal Code Approval Process — What to Expect

| Phase | What Happens | Timeline | Required For |
|-------|-------------|----------|-------------|
| PoC in Isengard | No approval needed — AWS-internal account | Immediate | SA demo, technical validation |
| Pilot with test data | Provisional ATO or "ATO with conditions" | 2-4 weeks | Customer GovCloud with synthetic data |
| Production with real data | Full ATO (Authority to Operate) | 2-6 months | Customer GovCloud with CUI/real evidence |

### 9.4 Authority to Operate (ATO) Considerations

An ATO is a formal security authorization required before software runs in a federal production environment. Key elements:

1. **System Security Plan (SSP):** Documents the system architecture, data flows, security controls, and boundaries. The deployment architecture document (this document) serves as the foundation for the SSP.

2. **Security Control Assessment:** Maps the system against NIST 800-53 controls (required for FedRAMP). Key controls the platform addresses:
   - AC (Access Control): API Gateway + IAM authorization
   - AU (Audit): CloudTrail + CloudWatch Logs + VPC Flow Logs
   - SC (System Communications): TLS 1.2+ enforced, VPC isolation
   - IA (Identification/Authentication): Secrets Manager for DB credentials
   - MP (Media Protection): KMS encryption at rest, S3 bucket policies
   - SI (System Integrity): Lambda managed runtime, no custom OS

3. **Continuous Monitoring:** Post-ATO requirement. CloudWatch alarms, GuardDuty, and Security Hub provide this.

### 9.5 Static Application Security Testing (SAST)

Federal deployments typically require a SAST scan of custom code. What a scan would find in this codebase:

**Strengths (will pass):**
- All SQL queries use parameterized statements (`%s` placeholders, not string concatenation) — no SQL injection risk
- HTML output is escaped via the `esc()` function — XSS mitigation
- No hardcoded credentials — all secrets via Secrets Manager and environment variables
- No file system writes — Lambda is read-only except `/tmp`
- No user-uploaded code execution — all processing is server-side via Bedrock

**Items to address before production scan:**
- The `vis-network` CDN load should be replaced with a local bundle
- Some Lambda functions have broad IAM permissions (e.g., `bedrock:InvokeModel` on `*`) — tighten to specific model ARNs for production
- API Gateway currently has no authentication — add IAM auth or Cognito for production
- CORS is set to allow all origins (`*`) — restrict to specific frontend domain for production

### 9.6 AI-Generated Code Disclosure

A significant portion of this codebase was developed with AI assistance (Kiro/Claude). Federal agencies are increasingly adopting AI-assisted development, but transparency is important:

- The code is human-reviewed and tested before deployment
- All AI-generated code follows the same security patterns (parameterized SQL, HTML escaping, least-privilege IAM)
- The code is version-controlled in Git with full change history
- Some agencies may require disclosure of AI-assisted development in the SSP

### 9.7 Pre-Deployment Checklist for SA Handoff

Before handing the deployment package to an SA or customer, verify:

| Item | Status | Action |
|------|--------|--------|
| vis-network bundled locally (not CDN) | Pending | Download and include in S3 |
| API Gateway authentication configured | Pending | Add IAM auth or Cognito |
| CORS restricted to specific origin | Pending | Update API Gateway CORS |
| IAM policies scoped to specific resources | Pending | Tighten Bedrock/Neptune ARNs |
| Python dependency audit (`pip list`) | Pending | Document Lambda runtime packages |
| SAST scan completed | Pending | Run SonarQube or equivalent |
| CloudTrail enabled in config | Done | `govcloud-production.json` includes it |
| KMS encryption configured | Done | Config-driven per environment |
| VPC flow logs enabled | Done | Config-driven per environment |
| Private subnets for databases | Done | Config-driven per environment |
| TLS enforced | Done | Config-driven per environment |
| FedRAMP model registry | Done | `config/bedrock_models.json` |
| Deployment architecture document | Done | This document |

### 9.8 Questions to Ask the SA Before GovCloud Deployment

1. **Account access:** Do you have an Isengard GovCloud account in `us-gov-west-1`? What IAM permissions do you have?

2. **Service availability:** Is Neptune Serverless available in your GovCloud region? (If not, we deploy without it — graph features degrade gracefully)

3. **KMS:** Do you have an existing KMS key we should use, or should the stack create one?

4. **VPC:** Do you have an existing VPC with private subnets and NAT gateway, or should the stack create one?

5. **Bedrock access:** Is Bedrock enabled in your GovCloud account? Which models are available? Any provider restrictions?

6. **SCPs:** Are there Service Control Policies that block specific AWS services or actions? (e.g., some SCPs block `neptune:*` or `opensearch:*`)

7. **Tagging requirements:** Are there mandatory tags required on all resources? (e.g., `CostCenter`, `Owner`, `DataClassification`)

8. **Network restrictions:** Are there restrictions on outbound internet access from the VPC? (Needed for Bedrock API calls via NAT gateway)

9. **CloudFormation permissions:** Can you create CloudFormation stacks with `CAPABILITY_IAM`? Some accounts restrict IAM resource creation.

10. **Data for testing:** Can we use synthetic/public data (e.g., Ancient Aliens transcripts) for the GovCloud test, or do you need sanitized real data?

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Neptune not available in GovCloud region | Medium | Low | Platform degrades gracefully — graph features disabled, entity relationships stored in Aurora only |
| OpenSearch Serverless not available in GovCloud | High | Low | Platform falls back to Aurora pgvector for all vector search |
| SCP blocks required AWS service | Medium | High | Pre-deployment checklist includes SCP review with SA |
| Bedrock model not available in GovCloud | Low | Medium | FedRAMP model registry provides fallback models (Titan instead of Claude) |
| ATO process delays production deployment | High | High | Start with PoC in Isengard (no ATO needed), build SSP in parallel |
| vis-network CDN blocked by network policy | High | Medium | Bundle locally before GovCloud deployment |
| Lambda cold start latency in VPC | Medium | Low | RDS Proxy handles connection pooling; Lambda SnapStart if needed |
| 500TB ingestion exceeds Bedrock throughput limits | Medium | Medium | Request provisioned throughput; batch processing with backoff |
| Customer requires VPC endpoints instead of NAT | Medium | Medium | Config can be extended to support VPC endpoints for S3, Bedrock, STS |


---

## 11. Production Scale Architecture Roadmap

### 11.1 Current Architecture Limits

| Component | Current Capacity | Breaking Point | Production Target |
|-----------|-----------------|----------------|-------------------|
| Users | 1-10 concurrent | ~50 concurrent (Lambda cold starts) | 500-1,000 concurrent |
| Cases | ~10 active | ~100 (Neptune query latency) | 10,000+ |
| Batch loads | 1 sequential | 1 at a time (batch lock) | 50+/week parallel |
| Documents | ~50K ingested | ~200K (Aurora storage) | Millions |
| Storage | ~50GB | ~500GB (S3 lifecycle) | 500TB+ |
| API latency | 2-15s (cold start) | 29s (API GW timeout) | <2s p95 |

### 11.2 Production Architecture Changes

**Tier 1: Immediate (before pilot)**
- Add Cognito authentication + API Gateway authorizer
- Add CloudFront for frontend (WAF, caching, HTTPS)
- Add Lambda provisioned concurrency (eliminate cold starts)
- Add ElastiCache Redis for anomaly/briefing/search result caching
- Split mega-dispatcher Lambda into 3 functions (API, Analysis, Batch)

**Tier 2: Scale (before 100+ users)**
- Fan-out parallel batch processing (8-16 concurrent jobs)
- Bedrock Provisioned Throughput for entity extraction
- Aurora read replicas for query-heavy workloads
- DynamoDB for session state and user preferences
- CloudWatch dashboards + alarms + X-Ray tracing
- SQS queues for async analysis jobs (anomaly, briefing, discovery)

**Tier 3: Enterprise (500+ users)**
- Multi-region Aurora Global Database
- Neptune read replicas or Neptune Analytics for heavy graph queries
- API Gateway usage plans + throttling per user/team
- S3 Intelligent-Tiering for 500TB+ storage
- Step Functions Express Workflows for high-throughput ingestion
- EventBridge for cross-case event correlation
- OpenSearch provisioned clusters (dedicated, not serverless) for predictable latency

### 11.3 Questions to Answer Before Production Architecture

1. How many concurrent users will access the system during peak hours?
2. What is the average case size (document count, total GB)?
3. How many new cases per week? How many documents per case?
4. What is the acceptable API response time (p50, p95, p99)?
5. Do investigators need real-time collaboration on the same case?
6. What is the data retention policy (how long do cases stay active)?
7. Are there cross-case search requirements (search across all cases)?
8. What authentication system does DOJ use (PIV/CAC, Okta, Azure AD)?
9. Are there network restrictions (VPC endpoints only, no NAT)?
10. What is the budget for ongoing infrastructure costs?
11. Is there a disaster recovery requirement (RPO/RTO)?
12. Do different teams need isolated data (multi-tenancy model)?

### 11.4 Cost Estimates at Scale

| Scale | Monthly Estimate | Key Cost Drivers |
|-------|-----------------|-----------------|
| Pilot (10 users, 10 cases) | $500-1,000 | Aurora + Neptune idle, Bedrock on-demand |
| Department (100 users, 100 cases) | $3,000-8,000 | Provisioned concurrency, ElastiCache, Bedrock |
| Enterprise (500 users, 1000 cases) | $15,000-40,000 | Aurora replicas, Bedrock provisioned, Neptune scaled |
| Full scale (1000 users, 10K cases, 500TB) | $50,000-100,000 | Multi-region, provisioned everything, S3 storage |


---

## 12. Post-Deployment Checklist

After deploying the CloudFormation stack, these steps must be completed in order:

### 12.1 Required Aurora Migrations

Run these SQL migrations against Aurora to create the application tables:

```bash
# Base schema (case_files, documents, entities, findings, pattern_reports)
python scripts/migrate_via_lambda.py src/db/migrations/001_base_schema.sql

# Discovery Engine (discovery_history, discovery_feedback)
python scripts/migrate_via_lambda.py src/db/migrations/015_discovery_engine.sql

# Theory Engine (theories table with ACH scores)
python scripts/migrate_via_lambda.py src/db/migrations/016_theory_engine.sql
```

### 12.2 Lambda Environment Variables

The following environment variables must be set on the Lambda function. The CDK config handles this automatically, but if deploying via CloudFormation console, verify these are present:

| Variable | Required | Description |
|----------|----------|-------------|
| NEPTUNE_ENABLED | Yes | "true" or "false" — controls Neptune feature flag |
| OPENSEARCH_ENABLED | Yes | "true" or "false" — controls OpenSearch feature flag |
| REKOGNITION_ENABLED | Yes | "true" or "false" — controls Rekognition feature flag |
| NEPTUNE_ENDPOINT | Yes | Neptune cluster endpoint (empty string if disabled) |
| NEPTUNE_PORT | Yes | "8182" |
| OPENSEARCH_ENDPOINT | Yes | OpenSearch endpoint URL (empty string if disabled) |
| OPENSEARCH_COLLECTION_ID | Yes | OpenSearch collection ID (empty string if disabled) |
| AURORA_PROXY_ENDPOINT | Yes | RDS Proxy endpoint |
| AURORA_SECRET_ARN | Yes | Secrets Manager ARN for Aurora credentials |
| AURORA_DB_NAME | Yes | "research_analyst" |
| BEDROCK_LLM_MODEL_ID | Yes | e.g., "anthropic.claude-3-haiku-20240307-v1:0" |
| BEDROCK_EMBEDDING_MODEL_ID | Yes | "amazon.titan-embed-text-v2:0" |
| S3_BUCKET_NAME | Yes | Data lake bucket name |
| S3_DATA_BUCKET | Yes | Same as S3_BUCKET_NAME |
| STATE_MACHINE_ARN | Yes | Step Functions state machine ARN |
| BULK_LOAD_THRESHOLD | Yes | "20" |
| ACCESS_CONTROL_ENABLED | Yes | "false" (or "true" for production) |

### 12.3 Frontend Deployment

```bash
aws s3 cp src/frontend/investigator.html \
  s3://research-analyst-data-lake-ACCOUNT_ID/frontend/investigator.html \
  --content-type "text/html"
```

### 12.4 Verification Steps

1. Open the frontend URL in a browser
2. Create a test case via the UI
3. Upload a sample document
4. Verify the pipeline processes it (check Step Functions console)
5. Verify the Knowledge Graph loads
6. Click "Generate Theories" — should produce 10-20 theories after 20-30 seconds
7. Verify the Case Health Bar shows scores
8. Verify Did You Know cards appear (after Discovery Engine migration)

### 12.5 Known Issues and Workarounds

| Issue | Workaround |
|-------|-----------|
| Anomaly Radar times out for cases with large Neptune graphs | The time-budgeted anomaly detection runs fast Aurora detectors first. Neptune-heavy cases may show partial results. Production fix: async anomaly computation with Aurora caching. |
| vis-network loaded from CDN | For federal/air-gapped environments, download vis-network.min.js and serve from S3 alongside the HTML. |
| Feature flags default to "true" | If NEPTUNE_ENABLED/OPENSEARCH_ENABLED/REKOGNITION_ENABLED env vars are not set, services are enabled by default. GovCloud deployments must explicitly set these to "false" via the CDK config. |

---

## 13. Well-Architected Framework Alignment

This section maps the platform's infrastructure controls to the six pillars of the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html). All controls are config-driven — demo deployments use permissive defaults while production and GovCloud deployments activate hardened settings via the deployment config JSON.

### 13.1 Operational Excellence

| Control | Description | Config Key |
|---------|-------------|------------|
| X-Ray active tracing | Enabled unconditionally on all Lambda functions via `Tracing.ACTIVE`. Provides distributed trace maps across Lambda → Aurora → Bedrock → Neptune call chains. | _(always on)_ |
| CloudWatch error alarms | Alarms fire when any Lambda function's `Errors` metric sum exceeds 5 in a 5-minute window. Separate alarm per function. | _(always on)_ |
| CloudWatch duration alarm | Alarm fires when the `case_files` Lambda p95 duration exceeds 60 000 ms in a 5-minute window. | _(always on)_ |
| Step Functions failure alarm | Alarm fires when `ExecutionsFailed` sum exceeds 1 in a 5-minute window. | _(always on)_ |
| SNS alarm notifications | When configured, all CloudWatch alarms publish to an SNS topic for email/PagerDuty/Slack integration. | `monitoring.alarm_sns_topic_arn` |
| API Gateway access logging | CLF-format access logs written to a CloudWatch Logs log group with 90-day retention. | `api.access_logging` |
| Conditional CloudTrail | Management-event trail stored in the S3 data lake under `cloudtrail/` prefix for API-call auditing. | `logging.cloudtrail` |

### 13.2 Security

| Control | Description | Config Key |
|---------|-------------|------------|
| Config-driven CORS origins | Production deployments restrict `Access-Control-Allow-Origin` to an explicit list of frontend domains. Demo deployments default to `ALL_ORIGINS`. | `api.cors_allow_origins` |
| Scoped Bedrock IAM | When model IDs are configured, IAM policies grant `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` only on the specific foundation-model ARNs instead of `foundation-model/*`. | `bedrock.llm_model_id`, `bedrock.embedding_model_id` |
| KMS encryption on SQS DLQ | The Lambda Dead Letter Queue is encrypted with a customer-managed KMS key when provided; otherwise SQS-managed encryption is used. | `encryption.kms_key_arn` |
| KMS encryption on CloudTrail | CloudTrail logs are encrypted with the same KMS key when both CloudTrail and the KMS key are configured. | `encryption.kms_key_arn` |
| S3 bucket RETAIN policy | Production deployments set the S3 data lake bucket to `RemovalPolicy.RETAIN` so that `cdk destroy` cannot delete investigation evidence. | `s3.removal_policy` |
| TLS enforcement on S3 | The S3 data lake bucket enforces TLS for all requests via a bucket policy condition. | `encryption.enforce_tls` |
| Partition-aware IAM ARNs | All Bedrock model ARNs use `${AWS::Partition}` via `Fn.sub` so the same codebase deploys correctly to both commercial and GovCloud partitions. | _(automatic)_ |

### 13.3 Reliability

| Control | Description | Config Key |
|---------|-------------|------------|
| Lambda Dead Letter Queue | A shared SQS queue (`research-analyst-dlq`) captures failed async Lambda invocations with a 14-day message retention period, preventing silent data loss. | _(always on)_ |
| API Gateway stage throttling | Stage-level burst and steady-state rate limits prevent a runaway client from exhausting Lambda concurrency and degrading the platform for all users. | `api.throttle_burst_limit`, `api.throttle_rate_limit` |
| Graceful degradation | Neptune, OpenSearch, and Rekognition are feature-flagged. When disabled in the deployment config, the platform continues to operate using Aurora-only code paths. | `neptune.enabled`, `opensearch.enabled`, `rekognition.enabled` |
| Analysis cache expiry | The investigator AI engine uses a 15-minute TTL on in-progress analysis entries, preventing stuck analyses from blocking subsequent requests. | _(hardcoded)_ |
| Per-service timeouts | Large case analysis operations enforce a 60-second timeout per downstream service call to prevent cascading delays. | _(hardcoded)_ |

### 13.4 Performance Efficiency

| Control | Description | Config Key |
|---------|-------------|------------|
| API Gateway throttling | Rate limits prevent resource saturation under load, ensuring consistent response times for concurrent users. | `api.throttle_burst_limit`, `api.throttle_rate_limit` |
| X-Ray distributed tracing | Trace maps identify latency bottlenecks across the Lambda → Aurora → Bedrock → Neptune call chain, enabling targeted optimization. | _(always on)_ |
| KNN semantic search (pgvector) | Evidence retrieval uses vector similarity search on Aurora pgvector instead of blind recency queries, returning the most relevant evidence per analysis section. | _(always on)_ |
| Two-pass Bedrock generation | Case file generation uses dedicated token budgets per section group, preventing any single section from consuming the entire context window. | _(always on)_ |

### 13.5 Cost Optimization

| Control | Description | Config Key |
|---------|-------------|------------|
| Serverless-first architecture | All compute (Lambda), database (Aurora Serverless v2, Neptune Serverless), and storage (S3) use pay-per-use serverless pricing with no idle baseline cost. | _(architectural)_ |
| S3 Intelligent-Tiering lifecycle | Objects transition to Infrequent Access after 90 days, reducing storage costs for aging investigation data. | _(always on)_ |
| Bedrock on-demand pricing | LLM inference uses on-demand Bedrock pricing with no provisioned throughput, appropriate for demo and pilot workloads. | _(always on)_ |
| Config-driven feature flags | Unused services (Neptune, OpenSearch, Rekognition) can be disabled via config, eliminating their resource costs entirely. | `neptune.enabled`, `opensearch.enabled`, `rekognition.enabled` |

### 13.6 Sustainability

| Control | Description | Config Key |
|---------|-------------|------------|
| Serverless compute scales to zero | Lambda functions, Aurora Serverless v2, and Neptune Serverless consume no compute resources when idle, minimizing energy use during off-hours. | _(architectural)_ |
| No persistent EC2 instances | The platform has zero always-on virtual machines — all compute is event-driven. | _(architectural)_ |
| Config-driven resource creation | Disabled services (Neptune, OpenSearch, Rekognition) create no cloud resources at all, avoiding idle infrastructure. | `neptune.enabled`, `opensearch.enabled`, `rekognition.enabled` |
| S3 lifecycle rules | Automatic transition to lower-cost storage tiers and eventual expiration reduces the long-term storage footprint. | _(always on)_ |

### 13.7 Control-to-Config Summary

The table below provides a quick reference mapping each Well-Architected control to its deployment config key.

| Control | Config Key | Default | Production Value |
|---------|------------|---------|-----------------|
| API throttle burst limit | `api.throttle_burst_limit` | 100 | 100 |
| API throttle rate limit | `api.throttle_rate_limit` | 50 | 50 |
| CORS allowed origins | `api.cors_allow_origins` | `ALL_ORIGINS` | Explicit origin list |
| API access logging | `api.access_logging` | `false` | `true` |
| S3 removal policy | `s3.removal_policy` | `"DESTROY"` | `"RETAIN"` |
| SNS alarm topic | `monitoring.alarm_sns_topic_arn` | _(none)_ | SNS topic ARN |
| CloudTrail | `logging.cloudtrail` | `false` | `true` |
| KMS encryption (DLQ + CloudTrail) | `encryption.kms_key_arn` | _(none — SQS-managed)_ | KMS key ARN |
| Scoped Bedrock IAM (LLM) | `bedrock.llm_model_id` | _(wildcard)_ | Model ID |
| Scoped Bedrock IAM (Embedding) | `bedrock.embedding_model_id` | _(wildcard)_ | Model ID |
| TLS enforcement on S3 | `encryption.enforce_tls` | _(varies)_ | `true` |
| Neptune feature flag | `neptune.enabled` | `true` | Per-environment |
| OpenSearch feature flag | `opensearch.enabled` | `true` | Per-environment |
| Rekognition feature flag | `rekognition.enabled` | `true` | Per-environment |
| X-Ray tracing | _(unconditional)_ | Active | Active |
| Lambda DLQ | _(unconditional)_ | 14-day retention | 14-day retention |
| CloudWatch alarms | _(unconditional)_ | Created | Created |


---

## 14. Production Readiness Gap Analysis

This section documents the engineering work required to move from the current PoC/pilot state to a production deployment supporting thousands of users, thousands of cases, and petabytes of data. These items are documented for planning purposes and are not being addressed in the current sprint.

### 14.1 Authentication & Authorization (Priority: Critical)

| Item | Current State | Production Requirement |
|------|--------------|----------------------|
| API Authentication | None — open API | Cognito User Pools + API Gateway Authorizer (or IAM auth for service-to-service) |
| User Identity | No user tracking | PIV/CAC integration via AWS SSO for DOJ; Cognito for commercial |
| Multi-tenancy | All cases visible to all users | Organization/team-based case isolation with row-level security |
| RBAC | No roles | Investigator, Analyst, Admin, Read-Only roles with scoped permissions |

### 14.2 Performance & Caching (Priority: High)

| Item | Current State | Production Requirement |
|------|--------------|----------------------|
| Caching layer | None — every request hits Aurora/Neptune/Bedrock | ElastiCache Redis for briefings, anomaly results, search results, entity lists |
| Lambda architecture | Single mega-dispatcher (case_files) handles all routes | Split into 3-5 focused functions: API, Analysis, Batch, Search, Graph |
| Cold starts | 2-15s on first request | Lambda Provisioned Concurrency (eliminate cold starts) |
| Frontend delivery | S3 direct | CloudFront CDN with WAF, caching, HTTPS, custom domain |
| Case file generation | Synchronous (29s API Gateway timeout) | Async pattern (Lambda self-invoke, poll for completion) |

### 14.3 Query Scalability (Priority: High — Spec Created)

| Item | Current State | Production Requirement |
|------|--------------|----------------------|
| Unbounded queries | 7 identified queries with no LIMIT on documents/entities tables | Add LIMIT/pagination to all queries (spec: `.kiro/specs/large-case-scalability/`) |
| Knowledge graph viz | Renders all entities in browser (vis-network) | Top-N filtering with "Load More" pagination |
| O(n²) vector pattern discovery | Self-join on documents table | LIMIT subquery or sampling |
| Entity list loading | Loads all entities into dropdown | Paginated search with typeahead |

### 14.4 Data Scale (Priority: Medium)

| Item | Current State | Production Requirement |
|------|--------------|----------------------|
| Ingestion throughput | Sequential batch processing (~80 docs/min) | Fan-out parallel processing (8-16 concurrent Step Functions, SQS queues) |
| Bedrock throughput | On-demand pricing | Provisioned Throughput for sustained PB-scale entity extraction |
| Aurora capacity | 0.5-4 ACU (auto-scale) | 8-64 ACU with read replicas for query-heavy workloads |
| S3 storage | Standard tier | S3 Intelligent-Tiering for PB-scale cost optimization |
| Neptune | Serverless 1-4 NCU | Neptune Analytics or provisioned clusters for heavy graph queries |

### 14.5 Reliability & DR (Priority: Medium)

| Item | Current State | Production Requirement |
|------|--------------|----------------------|
| Region | Single region (us-east-1) | Multi-region with Aurora Global Database for DR |
| Backup | Aurora automated backups | Cross-region backup replication, S3 cross-region replication |
| RPO/RTO | Undefined | Define per customer requirement (typical federal: RPO 1hr, RTO 4hr) |
| Circuit breakers | Basic try/except | Proper circuit breaker pattern for Bedrock/Neptune calls |

### 14.6 Observability (Priority: Medium — Partially Done)

| Item | Current State | Production Requirement |
|------|--------------|----------------------|
| X-Ray tracing | Coded in CDK (not yet deployed) | Deploy via `cdk deploy` |
| CloudWatch alarms | Coded in CDK (not yet deployed) | Deploy + configure SNS notifications |
| CloudWatch dashboards | None | Custom dashboards for ingestion throughput, API latency, error rates |
| Centralized logging | CloudWatch Logs per function | Log aggregation with structured JSON logging |

### 14.7 Frontend Hardening (Priority: Low)

| Item | Current State | Production Requirement |
|------|--------------|----------------------|
| vis-network CDN | Loaded from unpkg.com | Bundle locally in S3 (federal environments block external CDNs) |
| CORS | ALL_ORIGINS (demo default) | Restrict to specific frontend domain |
| Error handling | Basic alert() on failures | User-friendly error messages with retry guidance |
| Accessibility | Not audited | WCAG 2.1 AA compliance audit |

### 14.8 Estimated Timeline

| Phase | Scope | Duration | Team Size |
|-------|-------|----------|-----------|
| Phase 1: Auth + Async | Cognito, async case files, split Lambda | 1 week | 1-2 devs |
| Phase 2: Scale | Query limits, caching, CloudFront | 1 week | 1-2 devs |
| Phase 3: Harden | Multi-tenancy, RBAC, DR planning | 1-2 weeks | 2 devs |
| Phase 4: Deploy WAF | Run `cdk deploy` with WAF changes, verify | 1 day | 1 dev |
| **Total** | **Production-ready** | **3-5 weeks** | **1-2 devs** |


---

## 15. Well-Architected Framework Alignment

A code review against the AWS Well-Architected Framework identified gaps across the Reliability, Security, Operational Excellence, and Performance Efficiency pillars. The following changes were implemented in the CDK infrastructure and application code. All changes are config-driven — demo configs remain permissive while production configs enforce hardened controls.

### 15.1 Operational Excellence

| Control | Implementation | Config Key | Status |
|---------|---------------|------------|--------|
| API Gateway throttling | Stage-level burst/rate limits via `StageOptions` | `api.throttle_burst_limit`, `api.throttle_rate_limit` | ✅ Implemented |
| API Gateway access logging | CloudWatch Logs with CLF format, 90-day retention | `api.access_logging` | ✅ Implemented |
| Lambda X-Ray tracing | `Tracing.ACTIVE` on all Lambda functions via `_make_lambda` | Automatic | ✅ Implemented |
| CloudWatch alarms | Observability construct with error/duration/failure alarms | `monitoring.alarm_sns_topic_arn` | ✅ Implemented |
| Lambda Dead Letter Queues | Shared SQS DLQ (`research-analyst-dlq`) for all async Lambdas, 14-day retention | Automatic, KMS via `encryption.kms_key_arn` | ✅ Implemented |
| Conditional CloudTrail | Trail logging management events to S3 data lake under `cloudtrail/` prefix | `logging.cloudtrail` | ✅ Implemented |

### 15.2 Security

| Control | Implementation | Config Key | Status |
|---------|---------------|------------|--------|
| Config-driven CORS origins | `allow_origins` from deployment config, defaults to `ALL_ORIGINS` for demo | `api.cors_allow_origins` | ✅ Implemented |
| Scoped Bedrock IAM | Model-specific ARNs using `Fn.sub` with `${AWS::Partition}` for GovCloud compatibility | `bedrock.llm_model_id`, `bedrock.embedding_model_id` | ✅ Implemented |
| S3 removal policy | `RETAIN` in production prevents `cdk destroy` data loss | `s3.removal_policy` | ✅ Implemented |
| Label-based access control | `SecurityLabel` hierarchy (PUBLIC → TOP_SECRET), `AccessControlMiddleware` decorator, `LabelBasedProvider` | `ACCESS_CONTROL_ENABLED` env var | ✅ Implemented (disabled for demo) |
| Immutable audit trail | `AuditService` with append-only `label_audit_log` table, access denial logging | Application code | ✅ Implemented |
| Encryption at rest | KMS CMK for Aurora, Neptune, S3, SQS DLQ, CloudTrail | `encryption.kms_key_arn` | ✅ Implemented |
| TLS enforcement | Enforced on all connections in production configs | `encryption.enforce_tls` | ✅ Implemented |
| VPC isolation | All databases in private subnets, Lambda in VPC, VPC endpoints for AWS services | `vpc.subnet_type` | ✅ Implemented |
| API authentication | Not yet implemented — open API with `ACCESS_CONTROL_ENABLED=false` | — | ❌ Production gap |
| RBAC roles | Not yet implemented — all users have same access level | — | ❌ Production gap |
| Row-Level Security | Designed but not implemented — PostgreSQL RLS policies for team/case isolation | — | ❌ Production gap |

### 15.3 Reliability

| Control | Implementation | Config Key | Status |
|---------|---------------|------------|--------|
| Lambda DLQ | Failed async invocations captured in SQS for investigation | Automatic | ✅ Implemented |
| Retry policies | Step Functions: 3 attempts, exponential backoff (2x), 2-5s start | ASL definition | ✅ Implemented |
| Bedrock client timeouts | `read_timeout=120`, `connect_timeout=10`, adaptive retries | Application code | ✅ Implemented |
| Graceful degradation | Neptune/OpenSearch/Rekognition feature-flagged, platform continues without them | Config-driven | ✅ Implemented |
| Connection pooling | RDS Proxy for Aurora connections from Lambda | CDK infrastructure | ✅ Implemented |
| Circuit breakers | Not yet implemented — basic try/except only | — | ❌ Production gap |
| Multi-AZ | Aurora Serverless v2 is multi-AZ by default | Automatic | ✅ Built-in |

### 15.4 Performance Efficiency

| Control | Implementation | Config Key | Status |
|---------|---------------|------------|--------|
| Chunked entity extraction | 10K char chunks with 500 char overlap, cross-chunk deduplication | Application code | ✅ Implemented |
| Embedding text truncation | 20K char limit for Titan Embed (prevents token overflow) | Application code | ✅ Implemented |
| KNN vector search | pgvector with IVFFlat index (100 lists) for cosine similarity | Aurora schema | ✅ Implemented |
| Consolidated Lambda | Single mega-dispatcher (`case_files.py`) reduces stack from 567 to ~100 resources | CDK architecture | ✅ Implemented |
| Neptune HTTP API | HTTP instead of WebSocket to avoid Lambda cold-start timeout | Application code | ✅ Implemented |
| Provisioned concurrency | Not yet configured — cold starts on first request | — | ❌ Production gap |
| Caching layer | Not yet implemented — no ElastiCache/Redis | — | ❌ Production gap |
| Query pagination | 7 unbounded queries identified — need LIMIT/OFFSET | — | ❌ Production gap |

### 15.5 Cost Optimization

| Control | Implementation | Config Key | Status |
|---------|---------------|------------|--------|
| Serverless-first | Aurora Serverless v2, Neptune Serverless, Lambda, Step Functions | CDK architecture | ✅ Implemented |
| S3 lifecycle | Intelligent-Tiering for data lake | CDK infrastructure | ✅ Implemented |
| Config-driven capacity | Aurora ACU, Neptune NCU configurable per environment | `aurora.min_capacity`, `neptune.min_ncu` | ✅ Implemented |
| Bedrock on-demand | No provisioned throughput for demo — scales to zero | Default | ✅ Implemented |
| Cost tagging | Environment and compliance tags on all resources | `tags` config section | ✅ Implemented |

### 15.6 Production Gaps — Authentication Roadmap

The most critical production gap is API authentication. The platform currently runs with `ACCESS_CONTROL_ENABLED=false`, meaning all API endpoints are open. The recommended implementation path:

**Phase 1: Cognito User Pool (1 week)**
- Create Cognito User Pool with SAML federation support
- Add Cognito Authorizer to API Gateway
- Map Cognito groups to platform roles (Investigator, Analyst, Admin, Read-Only)
- Frontend: add login page with Cognito Hosted UI redirect

**Phase 2: RBAC Enforcement (1 week)**
- Enable `ACCESS_CONTROL_ENABLED=true` in Lambda env vars
- Map Cognito JWT claims to `UserContext` in `AccessControlMiddleware`
- Enforce role-based feature access (e.g., only Admin can delete cases)
- Enforce label-based document filtering per user clearance level

**Phase 3: Row-Level Security (1-2 weeks)**
- Add `case_assignments` table mapping users to cases
- Create PostgreSQL RLS policies on `documents`, `entities`, `case_files` tables
- Set `app.current_user_id` session variable via RDS Proxy on each request
- Test team isolation: users only see cases they're assigned to

**Phase 4: PIV/CAC Integration (if required)**
- Configure SAML federation from agency IdP (e.g., ADFS with PIV/CAC)
- Map PIV certificate attributes to Cognito user attributes
- No code changes needed — Cognito handles the federation

**Estimated effort:** 3-5 weeks for Phases 1-3, 1 additional week for Phase 4 if PIV/CAC is required.
