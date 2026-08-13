# Investigative Intelligence Platform — Colleague Handoff Guide

**What this is:** A complete AI-powered investigative intelligence platform (document ingestion, entity extraction, knowledge graph, semantic search, AI analysis, pattern discovery, timeline, geospatial mapping, prosecution assessment).

**Who it's for:** Solutions Architects → ProServe → Customer deployment

---

## Step 1: Get the Code

```bash
# Internal GitLab (requires mwinit)
git clone git@ssh.gitlab.aws.dev:agentic-ai-demos/agentic-ai-demo-investigative-intelligence.git
cd agentic-ai-demo-investigative-intelligence
```

**Prerequisites:**
- Run `mwinit -f` in your terminal first (refreshes Midway SSH certs)
- If you don't have an SSH key: `ssh-keygen -t ecdsa -b 256`

---

## Step 2: Deploy to Your AWS Account (30 minutes)

### Requirements
- AWS account with admin access
- Python 3.12+
- Node.js 18+ (for CDK)
- AWS CDK v2: `npm install -g aws-cdk`
- AWS CLI configured

### Deploy

```bash
# Install CDK dependencies
cd infra/cdk
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1

# Deploy everything
cdk deploy --require-approval never
```

This creates: VPC, Aurora Serverless v2 (PostgreSQL + pgvector), Neptune Serverless (knowledge graph), S3 bucket, Lambda functions, Step Functions pipeline, API Gateway, all VPC endpoints.

**Deployment takes ~25 minutes** (Neptune and Aurora provisioning).

---

## Step 3: Critical Post-Deploy Configuration

### 3a. Enable Bedrock Models (DO THIS FIRST)

In the AWS Console → Bedrock → Model access, enable:
- `anthropic.claude-3-haiku-20240307-v1:0` (entity extraction, AI analysis)
- `amazon.titan-embed-text-v2:0` (embeddings)

### 3b. Set ACCESS_CONTROL_ENABLED = false

In Lambda console → your CaseFiles Lambda → Configuration → Environment variables:
- Set `ACCESS_CONTROL_ENABLED` = `false`

Without this, ALL API calls return 401 Unauthorized.

### 3c. Lambda Timeout

Set all Lambda functions to **300 seconds** minimum (VPC cold starts + Bedrock calls need time).

---

## Step 4: Deploy Lambda Code

```bash
# From project root
pip install PyPDF2 -t src/ --upgrade

# Clean pycache (PowerShell)
Get-ChildItem -Path src -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

# Package
Compress-Archive -Path src/* -DestinationPath lambda-update.zip -Force

# Upload and deploy
aws s3 cp lambda-update.zip s3://YOUR-BUCKET/deploy/lambda-update.zip
aws lambda update-function-code \
  --function-name YOUR-CASE-FILES-LAMBDA \
  --s3-bucket YOUR-BUCKET \
  --s3-key deploy/lambda-update.zip
```

---

## Step 5: Load Demo Data

### Option A: Copy pre-processed data from reference environment (fastest)

Ask Vina for cross-account S3 access, then:

```bash
aws s3 sync \
  s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/ \
  s3://YOUR-BUCKET/cases/YOUR-CASE-ID/ \
  --source-region us-east-1
```

This gives you ~6,000 pre-processed Epstein case documents ready to go.

### Option B: Ingest your own documents

Upload PDFs to `s3://YOUR-BUCKET/cases/YOUR-CASE-ID/raw/` and use the batch loader UI.

**IMPORTANT: Always use tiered processing for large datasets.** Never bulk-load raw documents
directly into Aurora/Neptune/OpenSearch. See `docs/lessons-learned-tiered-data-processing.md`.

```bash
# Tier 1: Keyword filter (free, 23 seconds for 3,804 files)
python scripts/epstein_tiered_scan.py --tier 1

# Tier 2: Embed only filtered files ($0.02 for 225 files)
python scripts/epstein_tiered_scan.py --tier 2

# Tier 3: Claude Haiku on top matches ($0.25 for 195 files)
python scripts/epstein_tiered_scan.py --tier 3
```

This eliminates 94% of junk (blank pages, forms, cover sheets) before it reaches
the knowledge graph, keeping Neptune/OpenSearch clean and k-NN searches accurate.

---

## Step 6: Open the Frontend

1. Open `src/frontend/investigator.html` in a browser
2. Update `API_BASE` at the top of the file to your API Gateway URL
3. Your API URL is in the CDK output after deploy (format: `https://XXXXXXX.execute-api.us-east-1.amazonaws.com/v1`)

### Available Pages

| Page | File | What it does |
|------|------|-------------|
| Investigator | `investigator.html` | Main workflow: AI briefing, search, patterns, timeline, map |
| Prosecutor | `prosecutor.html` | Case strength assessment, element matrix, charging decisions |
| Batch Loader | `batch-loader.html` | Document ingestion with progress tracking |
| Data Loader | `data-loader.html` | Drag-and-drop upload |
| Admin | `admin.html` | User/access management |
| Pipeline Config | `pipeline-config.html` | Per-case pipeline settings |

---

## Architecture Overview

```
Frontend (HTML/JS) — static files, open in browser
        |
        v (HTTPS)
API Gateway (REST)
        |
        v
Lambda (Python 3.12, VPC-attached)
  Routes: /case-files, /search, /patterns, /drill-down, /cross-case, /batch-loader, /timeline, /findings
        |
   +---------+---------+---------+
   |         |         |         |
   v         v         v         v
Aurora PG  Neptune   Bedrock    S3
(pgvector) (Graph)   (Claude)   (Docs)
```

---

## AWS Services & Estimated Cost

| Service | Purpose | Monthly Cost (idle) |
|---------|---------|-------------------|
| Aurora Serverless v2 | Document store + pgvector | ~$30 |
| Neptune Serverless | Knowledge graph | ~$20 |
| Lambda | All compute | ~$5 |
| S3 | Documents | ~$2 |
| API Gateway | REST API | ~$1 |
| Bedrock | AI (pay per use) | $0 idle |
| **Total (idle)** | | **~$50-80/month** |
| **Total (active demo)** | | **~$150-200/month** |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| All API calls return 401 | Set `ACCESS_CONTROL_ENABLED=false` in Lambda env vars |
| Lambda timeout at 60s | Increase to 300s |
| "Connect timeout on endpoint URL" | Lambda SG needs to be in VPC endpoint SG (port 443) |
| Neptune queries fail | Lambda SG needs Neptune SG access (port 8182) |
| Bedrock calls fail | Enable model access in console; verify VPC endpoint exists |
| Frontend "Failed to fetch" | Update API_BASE URL; check CORS |

---

## For ProServe Handoff

When passing to ProServe for customer deployment:

1. **Code:** GitLab repo (they need Midway access) or zip the repo
2. **Data:** Either grant S3 cross-account access or provide a data export
3. **Config:** Customer will need their own AWS account, Bedrock model access enabled
4. **Customization points:**
   - Entity extraction prompts (in `src/services/entity_extraction_service.py`)
   - Case type profiles (configurable per use case)
   - Access control rules (multi-tenant, role-based)
   - Pipeline configuration (what AI steps to run)
5. **What to demo:** Start with Investigator page → AI Briefing → Search → Patterns → Timeline

---

## Key Contacts

- **Vina** — Platform architect, S3 data access, architecture questions
- **GitLab repo owner** — agentic-ai-demos group

---

## Reference Links

- Full deployment guide: `docs/deployment-guide.md`
- Lessons learned (52+ issues): `docs/lessons-learned.md`
- **Tiered data processing (MUST READ):** `docs/lessons-learned-tiered-data-processing.md`
- Data sharing guide: `docs/data-sharing-guide.md`
- Environment setup (detailed): `docs/environment-setup-guide.md`
- 500TB ingestion architecture: `docs/500tb-ingestion-architecture.md`
