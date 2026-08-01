# Investigative Intelligence Platform — Environment Setup Guide

**For:** Solutions team members deploying into their own AWS account  
**Source code:** GitLab `git@ssh.gitlab.aws.dev:agentic-ai-demos/agentic-ai-demo-investigative-intelligence.git`  
**Reference environment:** Account 974220725866, us-east-1  
**Date:** May 2026

---

## Quick Start (30-minute path to working demo)

### Prerequisites

- AWS account with admin access
- Python 3.12+
- Node.js 18+ (for CDK)
- AWS CDK v2 installed (`npm install -g aws-cdk`)
- AWS CLI configured with credentials

### Step 1: Clone the repo

```bash
git clone git@ssh.gitlab.aws.dev:agentic-ai-demos/agentic-ai-demo-investigative-intelligence.git
cd agentic-ai-demo-investigative-intelligence
```

### Step 2: Install CDK dependencies

```bash
cd infra/cdk
pip install -r requirements.txt
cd ../..
```

### Step 3: Bootstrap CDK (first time only)

```bash
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1
```

### Step 4: Deploy the stack

```bash
cd infra/cdk
cdk deploy --require-approval never
```

This creates: VPC, Aurora Serverless v2, Neptune Serverless, S3 bucket, Lambda functions, Step Functions pipeline, API Gateway, all VPC endpoints.

Deployment takes ~25 minutes (Neptune and Aurora provisioning).

### Step 5: Deploy Lambda code

```bash
cd ../..
pip install PyPDF2 -t src/ --upgrade

# Clean and package (PowerShell)
Get-ChildItem -Path src -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Compress-Archive -Path src/* -DestinationPath lambda-update.zip -Force

# Or on Linux/Mac:
# find src -type d -name __pycache__ -exec rm -rf {} +
# cd src && zip -r ../lambda-update.zip . && cd ..

# Upload to S3 and deploy
aws s3 cp lambda-update.zip s3://YOUR-BUCKET/deploy/lambda-update.zip
aws lambda update-function-code \
  --function-name YOUR-CASE-FILES-LAMBDA \
  --s3-bucket YOUR-BUCKET \
  --s3-key deploy/lambda-update.zip
```

### Step 6: Load sample data

```bash
# Copy demo case data from the reference environment (requires cross-account access)
aws s3 sync s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/ \
  s3://YOUR-BUCKET/cases/YOUR-CASE-ID/ --source-region us-east-1
```

### Step 7: Open the frontend

Open `src/frontend/investigator.html` in a browser. Update the API endpoint URL at the top of the file to point to your API Gateway URL.

---

## Architecture Overview

```
Frontend (HTML/JS) — investigator.html, prosecutor.html, batch-loader.html
        |
        v (HTTPS)
API Gateway (REST) — LambdaRestApi with {proxy+}
        |
        v
Lambda (case_files.py dispatcher)
  Routes: /case-files, /search, /patterns, /drill-down, /cross-case, /batch-loader
        |
   +---------+---------+
   |         |         |
   v         v         v
Aurora PG  Neptune   Bedrock
(pgvector) (Graph)   (Claude/Titan)
```

---

## AWS Services Required

| Service | Purpose | Minimum Config |
|---------|---------|----------------|
| Aurora Serverless v2 | Document store + pgvector embeddings | 0.5 ACU min, PostgreSQL 15 |
| Neptune Serverless | Knowledge graph | 1 NCU min |
| S3 | Raw documents + artifacts | Standard bucket |
| Lambda | All compute | Python 3.12, VPC-attached |
| Step Functions | Ingestion pipeline | Standard workflow |
| Bedrock | AI (Claude Haiku + Titan Embed) | Enable model access |
| API Gateway | REST API | Regional endpoint |
| Secrets Manager | DB credentials | 1 secret |

**Estimated monthly cost (idle):** ~$50-80/month (Aurora + Neptune minimums)
**Estimated monthly cost (active demo):** ~$150-200/month

---

## Critical Configuration Notes

### 1. Enable Bedrock Model Access (FIRST)

Before deploying, enable these models in the Bedrock console:
- `anthropic.claude-3-haiku-20240307-v1:0` (entity extraction)
- `amazon.titan-embed-text-v2:0` (embeddings)

### 2. ACCESS_CONTROL_ENABLED = false

The Lambda environment variable `ACCESS_CONTROL_ENABLED` must be set to `false`. Without this, all API calls return 401 Unauthorized.

### 3. VPC Endpoint Security Groups

Every Lambda SG must be in every VPC endpoint SG it needs. CDK handles this automatically, but verify after deploy.

### 4. Lambda Timeout

CaseFiles Lambda: 300s minimum. Ingestion Lambdas: 300s minimum. VPC cold starts + Secrets Manager + Bedrock calls need time.

### 5. Neptune HTTP API

All Neptune queries use HTTP REST API (not WebSocket gremlinpython). This is intentional for VPC Lambda compatibility.

---

## Data Loading Options

### Option A: Copy pre-processed data (fastest)

```bash
aws s3 sync s3://research-analyst-data-lake-974220725866/cases/ed0b6c27-3b6b-4255-b9d0-efe8f4383a99/ \
  s3://YOUR-BUCKET/cases/YOUR-CASE-ID/
```

Then trigger ingestion pipeline to process through entity extraction and graph loading.

### Option B: Ingest your own documents

1. Upload PDFs to `s3://YOUR-BUCKET/cases/YOUR-CASE-ID/raw/`
2. Use batch loader UI or API: `POST /case-files/{id}/ingest`

### Option C: CLI batch loader

```bash
python scripts/batch_loader.py \
  --case-id YOUR-CASE-ID \
  --source-bucket YOUR-BUCKET \
  --source-prefix cases/YOUR-CASE-ID/raw/ \
  --batch-size 50
```

---

## Frontend Pages

| Page | File | Purpose |
|------|------|---------|
| Investigator | `src/frontend/investigator.html` | Main workflow: AI briefing, search, patterns, timeline, map |
| Prosecutor | `src/frontend/prosecutor.html` | Case strength, element matrix, charging decisions |
| Batch Loader | `src/frontend/batch-loader.html` | Document ingestion with progress |
| Data Loader | `src/frontend/data-loader.html` | Drag-and-drop upload |
| Admin | `src/frontend/admin.html` | User management |
| Pipeline Config | `src/frontend/pipeline-config.html` | Per-case pipeline settings |

Update `API_BASE` at the top of each HTML file to your API Gateway URL.

---

## API Endpoints

Base: `https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/v1`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/case-files` | List all cases |
| GET | `/case-files/{id}` | Case details |
| POST | `/case-files/{id}/search` | Semantic search |
| POST | `/case-files/{id}/patterns` | Pattern discovery |
| POST | `/case-files/{id}/drill-down` | AI analysis |
| POST | `/case-files/{id}/cross-case` | Cross-case analysis |
| GET | `/case-files/{id}/timeline` | Timeline events |
| GET | `/case-files/{id}/findings` | Findings |
| POST | `/batch-loader/start` | Start batch ingestion |
| GET | `/batch-loader/status/{case_id}` | Batch progress |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| All API calls return 401 | Set `ACCESS_CONTROL_ENABLED=false` in Lambda env vars |
| Lambda timeout at 60s | Increase to 300s for all VPC Lambdas |
| "Connect timeout on endpoint URL" | Add Lambda SG to VPC endpoint SG (port 443) |
| Neptune queries fail | Add Lambda SG to Neptune SG (port 8182) |
| Bedrock calls fail | Enable model access in console; check VPC endpoint |
| Frontend "Failed to fetch" | Update API_BASE URL; check CORS config |
| CDK deploy fails (AOSS conflict) | Run AOSS cleanup (see `docs/deployment-guide.md`) |

---

## Reference

- **Full deployment guide:** `docs/deployment-guide.md`
- **Lessons learned (26+ issues):** `docs/lessons-learned.md`
- **Data sharing guide:** `docs/data-sharing-guide.md`
- **Reference API:** `https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1`
- **Demo case:** `ed0b6c27-3b6b-4255-b9d0-efe8f4383a99` (~6,000 docs)
