# Lessons Learned — Deployment & Batch Loader Wiring

This document captures every issue encountered during deployment and batch loader testing.
Any spec that touches infrastructure, Lambda packaging, or the batch loader MUST reference this doc.
Any future AI assistant session MUST read this doc before making changes.

## CRITICAL RULE: DO NOT REWRITE WORKING CODE

When creating specs or implementing new features, NEVER rewrite modules that are already working in production.
The batch loader handler, CDK stack, and case_files dispatcher were working — then a spec rewrote them
and broke everything. Always EXTEND, never REPLACE working code.

---

## Issue 1: CloudFormation 500-Resource Limit

**Problem**: CDK stack had 567 resources, exceeding the 500 limit.
**Root cause**: Each API Lambda created ~5 resources (function, role, policy, SG, SG ingress rules). With 25 Lambdas + 104 API Gateway resources + 204 Lambda permissions = 567.
**Fix**: Consolidated all API Lambdas into a single `case_files` mega-dispatcher. Used `LambdaRestApi` with `proxy=True` for a single `{proxy+}` catch-all route. Reduced to 100 resources.
**CDK code**: `_create_api_lambdas()` returns only `{"case_files": ...}`. `_create_api_gateway()` uses `apigw.LambdaRestApi(handler=cf_lambda, proxy=True)`.
**File**: `infra/cdk/stacks/research_analyst_stack.py`

## Issue 2: AOSS Orphaned Resources After Failed Deploys

**Problem**: CDK deploy fails → rollback → AOSS policies/VPC endpoints/collections become orphaned → next deploy fails with "already exists".
**Root cause**: AOSS resources are account-level, not stack-scoped. CloudFormation rollback removes them from stack state but not from the account.
**Fix**: Run cleanup before every deploy attempt:
```bash
aws opensearchserverless delete-security-policy --name research-analyst-search-enc --type encryption
aws opensearchserverless delete-security-policy --name research-analyst-search-net --type network
aws opensearchserverless delete-access-policy --name research-analyst-search-dap --type data
aws ec2 describe-vpc-endpoints --filters "Name=service-name,Values=com.amazonaws.us-east-1.aoss" --query "VpcEndpoints[].VpcEndpointId" --output text | xargs aws ec2 delete-vpc-endpoints --vpc-endpoint-ids
aws opensearchserverless list-collections --query "collectionSummaries[?name=='research-analyst-search'].id" --output text | xargs -I{} aws opensearchserverless delete-collection --id {}
sleep 30
```

## Issue 3: AOSS VPC Endpoint DNS Conflict

**Problem**: `private-dns-enabled cannot be set because there is already a conflicting DNS domain for aoss.us-east-1.amazonaws.com`
**Root cause**: Orphaned VPC endpoint from previous failed deploy still owns the DNS domain.
**Fix**: Delete the orphaned VPC endpoint first (see Issue 2 cleanup).

## Issue 4: Step Functions ASL Placeholder Mismatch

**Problem**: `SCHEMA_VALIDATION_FAILED: Value is not a valid resource ARN at /States/ResolveConfig/Resource`
**Root cause**: The ASL definition uses `${ResolveConfigLambdaArn}`, `${ClassificationLambdaArn}`, `${RekognitionLambdaArn}` but CDK `definition_substitutions` had different key names (`IngestionResolveConfigLambdaArn`, etc.).
**Fix**: Add matching substitution keys in CDK:
```python
definition_substitutions={
    # ... existing keys ...
    "ResolveConfigLambdaArn": ingestion_lambdas["resolve_config"].function_arn,
    "ClassificationLambdaArn": ingestion_lambdas["extract"].function_arn,
    "RekognitionLambdaArn": ingestion_lambdas["rekognition"].function_arn,
}
```
**File**: `infra/cdk/stacks/research_analyst_stack.py` line ~747

## Issue 5: ACCESS_CONTROL_ENABLED Not Set

**Problem**: All API calls return 401 UNAUTHORIZED — "User identity could not be resolved".
**Root cause**: The `@with_access_control` decorator on `dispatch_handler` blocks all requests when `ACCESS_CONTROL_ENABLED` env var is not set (defaults to enabled).
**Fix**: Add `ACCESS_CONTROL_ENABLED=false` to Lambda environment variables in CDK:
```python
lambda_env["ACCESS_CONTROL_ENABLED"] = "false"
```
Also set it directly via CLI for immediate effect:
```bash
aws lambda update-function-configuration --function-name <name> --environment file://env_update.json
```
**File**: `infra/cdk/stacks/research_analyst_stack.py` in `_build_lambda_env()`

## Issue 6: batch_loader Modules Not in Lambda Package

**Problem**: `No module named 'scripts'` — Lambda handler imports `from scripts.batch_loader.config import BatchConfig`.
**Root cause**: Lambda code is deployed from `src/` directory. The `scripts/` folder is not included in the Lambda zip.
**Fix**: 
1. Copy `scripts/batch_loader/` to `src/batch_loader/`
2. Change all imports from `from scripts.batch_loader.*` to `from batch_loader.*` in:
   - `src/lambdas/api/batch_loader_handler.py`
   - All 8 modules in `src/batch_loader/*.py` (internal cross-imports)
**Command**: 
```bash
Copy-Item -Recurse -Force "scripts/batch_loader" "src/batch_loader"
# Then fix imports in handler and all batch_loader modules
```

## Issue 7: CostEstimator Pricing File Path

**Problem**: `FileNotFoundError: No such file or directory: '/var/config/aws_pricing.json'`
**Root cause**: `CostEstimator._load_pricing()` uses `os.path.dirname()` × 3 to find `config/aws_pricing.json` relative to the file. In Lambda (`/var/task/batch_loader/cost_estimator.py`), 3 levels up = `/var/` which is wrong.
**Fix**: 
1. Copy `config/aws_pricing.json` to `src/config/aws_pricing.json`
2. Update `_load_pricing()` to try multiple paths including `LAMBDA_TASK_ROOT/config/` with a fallback to default pricing values.
**File**: `src/batch_loader/cost_estimator.py`

## Issue 8: PyPDF2 Not in Lambda Package

**Problem**: `No module named 'PyPDF2'` — extraction phase fails on every file.
**Root cause**: PyPDF2 was installed in `src/` locally but `Compress-Archive` may not have included it properly, or the Lambda zip was built before PyPDF2 was installed.
**Fix**: Ensure PyPDF2 is installed in `src/` before building the zip:
```bash
pip install PyPDF2 -t src/ --upgrade
```
Then rebuild and deploy:
```bash
Compress-Archive -Path src/* -DestinationPath lambda-update.zip -Force
aws lambda update-function-code --function-name <name> --zip-file fileb://lambda-update.zip
```

## Issue 9: Lambda VPC Endpoint Missing for Self-Invoke

**Problem**: Batch starts but async worker never runs. Progress stuck at "discovery" with 0 extraction progress.
**Root cause**: The batch loader's start handler calls `lambda.invoke()` to self-invoke the async worker. But the Lambda is in a VPC and can't reach the Lambda service API without a VPC endpoint.
**Fix**: Create a Lambda VPC endpoint:
```bash
aws ec2 create-vpc-endpoint --vpc-id vpc-0b42c848c0b11ed25 \
  --vpc-endpoint-type Interface \
  --service-name com.amazonaws.us-east-1.lambda \
  --subnet-ids <subnet-ids> \
  --security-group-ids <default-sg> \
  --private-dns-enabled
```
Then add SG ingress rule so the Lambda's SG can reach the endpoint:
```bash
aws ec2 authorize-security-group-ingress --group-id <vpce-sg> \
  --protocol tcp --port 443 --source-group <lambda-sg>
```

## Issue 10: Lambda Timeout Too Short for Batch Extraction

**Problem**: Worker runs for 300s (5 min) then times out during extraction of 100+ PDFs.
**Root cause**: CaseFiles Lambda had 300s timeout. Extracting 100+ PDFs from S3 with PyPDF2 takes longer.
**Fix**: Increase timeout to 900s (15 min):
```bash
aws lambda update-function-configuration --function-name <name> --timeout 900
```
Also update CDK: `timeout_seconds=900` in `_create_api_lambdas()`.

## Issue 11: Stale Batch Progress Blocking New Batches

**Problem**: "Batch batch_XXXXXXXX is already running (status: discovery)" — can't start new batch.
**Root cause**: Previous batch failed/timed out but left a progress file in S3 with non-terminal status.
**Fix**: Delete the stale progress file:
```bash
aws s3 rm s3://research-analyst-data-lake-974220725866/batch-progress/<case_id>/batch_progress.json
```
**Future improvement**: Add a "Cancel Batch" button to the UI, and auto-expire batches that haven't updated in 15+ minutes.

## Issue 12: CDK Deploy Overwrites Weekend Config Changes

**Problem**: Haiku model was set on Lambda over the weekend, but CDK deploy reset it to Sonnet.
**Root cause**: CDK stack hardcoded `BEDROCK_LLM_MODEL_ID` to Sonnet. Any `cdk deploy` overwrites manual Lambda env var changes.
**Fix**: Always update the CDK stack source when changing Lambda env vars, not just the live Lambda.
**Current setting**: `anthropic.claude-3-haiku-20240307-v1:0` (3x faster, 10x cheaper than Sonnet)
**File**: `infra/cdk/stacks/research_analyst_stack.py` in `_build_lambda_env()`

## Speed-Up Ideas (Documented for Next Session)

1. Increase Step Functions Map concurrency from 5 to 20-50 (ASL change)
2. Increase sub-batch size from 50 to 100+ (fewer SFN executions)
3. Skip entity extraction for initial bulk load — just embeddings + text, run entities later
4. Haiku instead of Sonnet — DONE, already applied
5. SQS fan-out: skip Step Functions, put each doc on SQS, 100+ Lambda workers parallel
6. Neptune CSV bulk loader instead of per-entity Gremlin (already in ASL for batches > 20)
7. Bedrock Batch Inference API for bulk entity extraction (50% cheaper, async)
8. Step Functions Distributed Map for 10K+ concurrent executions

## Issue 13: Neptune SG Missing New Lambda SG After Consolidation

**Problem**: "Graph load failed: Failed to fetch" on investigator page for all cases.
**Root cause**: CDK consolidation changed the API Lambda from multiple Lambdas (each with their own SG) to a single CaseFiles Lambda with SG `sg-05ff17c74d15959e7`. Neptune's SG only allowed the old Lambda SGs, not the new one.
**Fix**: Add the new Lambda SG to Neptune's SG inbound on port 8182:
```bash
aws ec2 authorize-security-group-ingress --group-id <neptune-sg> --protocol tcp --port 8182 --source-group <lambda-sg>
```

## Issue 14: CORS OPTIONS Missing on LambdaRestApi Proxy

**Problem**: All POST/PUT requests from the investigator page return "Failed to fetch" after CDK consolidation to `LambdaRestApi` with `proxy=True`.
**Root cause**: The old API Gateway had explicit CORS OPTIONS methods on each route (added via `add_routes.py`). The new `LambdaRestApi` with `proxy=True` creates a single `{proxy+}` resource with only an ANY method — no OPTIONS method for CORS preflight. Browsers running from `file://` send preflight OPTIONS requests which API Gateway rejects with 500 before reaching the Lambda.
**Fix (permanent — applied in CDK)**: Added `default_cors_preflight_options` to the `LambdaRestApi` in `_create_api_gateway()`:
```python
api = apigw.LambdaRestApi(
    self, "ResearchAnalystApi",
    handler=cf_lambda,
    proxy=True,
    default_cors_preflight_options=apigw.CorsOptions(
        allow_origins=apigw.Cors.ALL_ORIGINS,
        allow_methods=apigw.Cors.ALL_METHODS,
        allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"],
    ),
)
```
This creates OPTIONS mock integrations on every resource automatically during `cdk deploy`, so the manual API Gateway CLI commands are no longer needed after each deploy.
**Status**: FIXED in CDK — requires `cdk deploy` to take effect.

## Issue 15: {proxy+} pathParameters Missing After Lambda Consolidation

**Problem**: All POST/PUT/DELETE requests to sub-resources (e.g., `/case-files/{id}/patterns`) return 500 "Internal server error" through API Gateway, but work fine when Lambda is invoked directly.
**Root cause**: When API Gateway uses `{proxy+}`, `event["pathParameters"]` only contains `{"proxy": "case-files/<uuid>/patterns"}` — it does NOT contain `{"id": "<uuid>"}`. The `_normalize_resource()` function in `case_files.py` reconstructed the `event["resource"]` template but never populated `event["pathParameters"]` with the extracted IDs. All sub-handlers (patterns, search, drill-down, etc.) call `event["pathParameters"]["id"]` and get nothing.
**Fix**: Updated `_normalize_resource()` to also extract path parameters and populate `event["pathParameters"]` with the correct keys (`id`, `docId`, `doc_id`, `pid`, `run_id`, `batch_id`, `v`, `step`).
**File**: `src/lambdas/api/case_files.py` — `_normalize_resource()` function
**Impact**: This affects ALL sub-resource routes under `/case-files/{id}/...`, `/admin/users/{id}`, `/decisions/{id}/...`, etc.
**Deployment**: Requires Lambda code redeployment (`Compress-Archive src/* → lambda-update.zip → update-function-code`).

## Issue 17: PyPDF2 "EOF marker not found" on Scanned Document PDFs

**Problem**: Batch loader fails with `PyPDF2 failed: EOF marker not found` on hundreds of PDFs in DataSet12, retries 3 times per file, then quarantines them.
**Root cause**: Many Epstein dataset PDFs (especially DataSet12) are scanned document images saved as PDF containers. They have no text layer and no proper PDF EOF structure. PyPDF2 can only extract text from PDFs with embedded text — it cannot OCR images.
**Impact**: ~60-80% of DataSet12 files fail extraction. The batch loader correctly quarantines them and continues, but no text is extracted for those documents.
**Fix (future)**: Add a Textract fallback in `scripts/batch_loader/extractor.py`: when PyPDF2 fails with EOF/parse errors, send the PDF to AWS Textract for OCR instead of quarantining. This is needed for the full 331K file load.
**Workaround (now)**: The successfully processed docs (with real text) are sufficient for demo purposes. Re-run the batch to continue from the cursor — already-processed files are skipped.
**File**: `scripts/batch_loader/extractor.py`

## Issue 18: Ingestion Pipeline Lambdas Timeout at 60s in VPC (Sandbox.Timedout)

**Problem**: ALL Step Functions pipeline executions fail with `Sandbox.Timedout: Task timed out after 60.00 seconds` at the `ResolveConfig` step. The batch loader sends documents to the ingest API, Step Functions triggers, but every execution fails. Result: `documents` table in Aurora is empty for the case despite 7200+ files being processed by the batch loader.
**Root cause**: Four ingestion Lambdas (ResolveConfig, Parse, StoreArtifact, UpdateStatus) had default 60-second timeouts. In a VPC, cold starts take 5-10s, Secrets Manager retrieval takes 5-10s through the VPC endpoint, and the actual work takes 10-30s. Total exceeds 60s on cold start.
**Impact**: The batch loader's CLI extraction (PyPDF2 + Neptune graph load) works fine because it runs locally. But the Step Functions pipeline (which inserts into Aurora `documents` table, generates embeddings, and does full entity extraction) fails silently. The UI shows "7200 docs" from the `case_files.document_count` counter, but the `documents` table has 0 rows. This breaks: AI Briefing (needs documents), semantic search (needs embeddings), and drill-down (needs document text).
**Fix**: Increase all ingestion Lambda timeouts to 300s and memory to 512MB:
- ResolveConfig: 60s/256MB → 300s/512MB
- Parse: 60s/256MB → 300s/512MB
- StoreArtifact: 60s/256MB → 300s/512MB
- UpdateStatus: 60s/256MB → 300s/512MB
- Upload: 120s → 300s (for large batches)
**CDK fix**: Updated `_create_ingestion_lambdas()` with explicit `timeout_seconds` for all Lambdas.
**CLI fix**: `aws lambda update-function-configuration --function-name <name> --timeout 120`
**Prevention**: Never use default Lambda timeout (3s) or less than 300s for VPC-attached Lambdas. Minimum 300s and 512MB memory for any Lambda that calls Secrets Manager, Aurora, or Bedrock through VPC endpoints. More memory = faster cold starts because Lambda allocates CPU proportional to memory.
**File**: `infra/cdk/stacks/research_analyst_stack.py` in `_create_ingestion_lambdas()`

## Issue 20: Missing pipeline_configs and system_default_config Tables

**Problem**: Step Functions pipeline fails at ResolveConfig with `relation "system_default_config" does not exist`.
**Root cause**: The configurable-pipeline spec created `config_resolution_service.py` which queries `system_default_config` and `pipeline_configs` tables, but the migration (`scripts/migrations/001_pipeline_config_tables.sql`) was never run against the production database.
**Fix**: Create the tables via RDS Data API:
```sql
CREATE TABLE IF NOT EXISTS system_default_config (config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), version INTEGER NOT NULL, config_json JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), created_by TEXT NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE);
INSERT INTO system_default_config (version, config_json, created_by) SELECT 1, '{}'::jsonb, 'system' WHERE NOT EXISTS (SELECT 1 FROM system_default_config WHERE is_active = TRUE);
CREATE TABLE IF NOT EXISTS pipeline_configs (config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), case_id UUID NOT NULL, version INTEGER NOT NULL DEFAULT 1, config_json JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), created_by TEXT NOT NULL DEFAULT '', is_active BOOLEAN NOT NULL DEFAULT TRUE);
```
**Prevention**: Add all spec migrations to the deployment checklist. When a spec creates new services that query new tables, the migration MUST be run before the pipeline can use those services.

## Issue 21: Ingestion Lambda SG Not in Secrets Manager VPC Endpoint SG

**Problem**: ResolveConfig Lambda hangs for 300s then times out trying to reach Secrets Manager, even with increased timeout.
**Root cause**: CDK creates a separate SG for each Lambda. The Secrets Manager VPC endpoint SG only had the old Lambda SGs (from before consolidation) and the CaseFiles Lambda SG. The new ingestion Lambda SGs (created by CDK for each ingestion Lambda) were never added.
**Fix**: Add each ingestion Lambda's SG to the Secrets Manager VPC endpoint SG on port 443:
```bash
aws ec2 authorize-security-group-ingress --group-id <secrets-manager-vpce-sg> --protocol tcp --port 443 --source-group <lambda-sg>
```
**Prevention**: After every CDK deploy, verify ALL Lambda SGs are in ALL VPC endpoint SGs they need to reach. The deployment checklist should include: "For each VPC endpoint SG, verify all Lambda SGs that need access are in the inbound rules."

## Issue 22: ResolveConfig Lambda Doesn't Pass Through Input Fields to Step Functions

**Problem**: Pipeline fails at `CheckSampleMode` Choice state with "Invalid path '$.sample_mode': The choice state's condition path references an invalid value."
**Root cause**: Two issues: (1) The `ingest_handler` never included `sample_mode` in the Step Functions input. The ASL's `CheckSampleMode` Choice state references `$.sample_mode` which doesn't exist, causing a runtime error. (2) The initial fix (returning merged event from Lambda) caused double-nesting: `ResultPath: "$.effective_config"` placed the Lambda output at `$.effective_config`, so the actual config ended up at `$.effective_config.effective_config`.
**Fix (correct — applied April 2)**: 
1. Added `"sample_mode": False` to the SFN input in `src/lambdas/api/ingestion.py` so `$.sample_mode` exists at the top level.
2. Reverted `resolve_config_handler.py` to return just `result.effective_json` (the config dict). With `ResultPath: "$.effective_config"`, this places the config exactly at `$.effective_config` — no double-nesting.
**Key insight**: When a Step Functions state uses `ResultPath: "$.some_field"`, the Lambda output goes INTO that field. The Lambda should NOT wrap its output — it should return only the data that belongs at that path. The original input fields (`case_id`, `upload_result`, etc.) are preserved automatically by Step Functions when using `ResultPath` (it merges, not replaces).
**Files**: `src/lambdas/api/ingestion.py`, `src/lambdas/ingestion/resolve_config_handler.py`
**Prevention**: When a Step Functions Choice state references a variable, ensure ALL callers that start the state machine include that variable in the input. Don't rely on intermediate Lambda steps to inject it — `ResultPath` nesting makes that unreliable.

## Issue 23: Map State $.Map.Item.Value Should Be $$.Map.Item.Value

**Problem**: ProcessDocuments Map state fails with "The JSONPath '$.Map.Item.Value' could not be found in the input".
**Root cause**: The ASL used `$.Map.Item.Value` in the Map state's Parameters to reference the current iteration item. In Step Functions, `$.` refers to the state input, while `$$.` refers to the context object (which includes `Map.Item.Value`). The correct syntax is `$$.Map.Item.Value`.
**Fix**: Updated the ASL `ProcessDocuments` Map state Parameters from `"document_id.$": "$.Map.Item.Value"` to `"document_id.$": "$$.Map.Item.Value"`. Updated via `aws stepfunctions update-state-machine` CLI (no CDK deploy needed).
**File**: `infra/step_functions/ingestion_pipeline.json`
**Prevention**: Always use `$$` prefix for Step Functions context object references (`Map.Item.Value`, `Map.Item.Index`, `Execution.Id`, etc.). Single `$` is for state input data.

## Issue 24: CheckRekognitionEnabled Fails When effective_config Is Empty

**Problem**: Pipeline fails at `CheckRekognitionEnabled` with "Invalid path '$.effective_config.rekognition.enabled': The choice state's condition path references an invalid value."
**Root cause**: The Choice state checked `$.effective_config.rekognition.enabled` directly. When `effective_config` is `{}` (empty — no case-level or system-level config), the path `rekognition.enabled` doesn't exist. Step Functions throws a runtime error instead of falling through to Default.
**Fix**: Wrapped the BooleanEquals check with an `And` condition that first checks `IsPresent`:
```json
"And": [
  {"Variable": "$.effective_config.rekognition", "IsPresent": true},
  {"Variable": "$.effective_config.rekognition.enabled", "BooleanEquals": true}
]
```
Updated via `aws stepfunctions update-state-machine` CLI.
**File**: `infra/step_functions/ingestion_pipeline.json`
**Prevention**: Always use `IsPresent` guard before accessing nested paths in Step Functions Choice states. If the path might not exist, check existence first.

## Issue 25: ClassifyDocument Step Calls Wrong Lambda — All Docs Fail Silently

**Problem**: Pipeline executions show SUCCEEDED but Aurora `documents` table has 0 rows. Every document is logged as "failed" inside the Map state, but the Map itself succeeds (failures are caught by LogDocumentFailure).
**Root cause**: The ASL's `ClassifyDocument` Task state used `${ClassificationLambdaArn}` which CDK mapped to the extract Lambda (`extract_handler.py`). The extract handler expects `{"raw_text": "..."}` but ClassifyDocument passes `{"parse_result": {...}}`. The extract handler throws `KeyError: 'raw_text'`, retries 3 times, then the Catch sends it to LogDocumentFailure. The document never reaches ExtractEntities, GenerateEmbedding, or StoreArtifact. The pipeline "succeeds" because the Map's error handling is graceful — but zero docs actually get processed.
**Fix**: Replaced the ClassifyDocument Task state with a Pass state that skips classification and passes through to ExtractEntities. Updated via `aws stepfunctions update-state-machine` CLI.
**File**: `infra/step_functions/ingestion_pipeline.json`
**Prevention**: When mapping ASL Lambda ARN placeholders to actual Lambdas, verify the Lambda's expected input matches what the ASL state passes. A Lambda that "succeeds" in Step Functions doesn't mean the document was processed — check the Map iteration results.

## Issue 26: Embed Step Fails with AOSS 401 for Enterprise Tier Cases

**Problem**: GenerateEmbedding step fails with `HTTP Error 401` from OpenSearch Serverless. Documents never get inserted into Aurora.
**Root cause**: The Epstein Combined case had `search_tier = 'enterprise'`, which routes the embed handler to OpenSearch Serverless instead of Aurora pgvector. The AOSS data access policy uses account root principal, but the embed Lambda's IAM role doesn't have the correct AOSS API permissions or the SigV4 signing isn't working correctly.
**Fix (immediate)**: Changed the case's `search_tier` to `standard` in both `case_files` and `matters` tables. This routes embeddings to Aurora pgvector which works.
**Fix (future)**: Debug AOSS IAM auth — the embed Lambda needs `aoss:APIAccessAll` permission and the request must be SigV4-signed. The `opensearch_serverless_backend.py` may not be signing requests correctly.
**Files**: Aurora `case_files` and `matters` tables
**Prevention**: Default new cases to `standard` tier unless AOSS auth is verified working. Test the embed step with a single doc before running large batches.

## Issue 19: Batch Loader document_count vs documents Table Mismatch

**Problem**: The investigator UI shows "7200 docs" but the AI Briefing shows "50 docs, 0 entities". The `case_files.document_count` is updated by the batch loader's ledger, but the `documents` table has 0 rows for the case.
**Root cause**: The batch loader has two data paths: (1) local extraction (PyPDF2 → text → Neptune entities) which works, and (2) Step Functions pipeline (ingest API → parse → extract → embed → graph load → update status) which inserts into the `documents` table. When the pipeline fails (Issue 18), path 1 succeeds but path 2 doesn't. The `document_count` in `case_files` is updated by the ledger based on files processed, not documents inserted.
**Impact**: The graph has entities (from path 1), but Aurora has no document rows (path 2 failed). AI Briefing, search, and drill-down all depend on the `documents` table.
**Fix**: After fixing Lambda timeouts (Issue 18), re-run the batch loader to trigger the pipeline again. The pipeline will now succeed and populate the `documents` table.
**Prevention**: The batch loader should verify that `documents` table rows were actually created after pipeline completion, not just count files processed. Add a post-batch verification step.

## Issue 16: Orphaned API Gateway Routes from add_routes.py Block Deployments

**Problem**: `aws apigateway create-deployment` fails with "No integration defined for method" after CDK consolidation.
**Root cause**: The old `add_routes.py` script created explicit API Gateway routes (e.g., `/batch-loader/start`, `/admin/users`, `/statutes`) with integrations pointing to individual Lambda functions. After CDK consolidation to a single `{proxy+}` Lambda, these old routes remained in API Gateway with broken integrations (pointing to deleted Lambdas). Some had methods with no integration at all (e.g., OPTIONS added manually without a MOCK integration). API Gateway refuses to deploy if ANY method on ANY resource lacks an integration.
**Fix**: Delete all explicit routes except `/` and `/{proxy+}`:
```powershell
$resources = (aws apigateway get-resources --rest-api-id $API_ID --output json) | ConvertFrom-Json
# Delete deepest paths first (3 passes needed for nested resources)
for ($pass = 0; $pass -lt 3; $pass++) {
    $old = $resources.items | Where-Object { $_.path -ne "/" -and $_.path -ne "/{proxy+}" } | Sort-Object { ($_.path -split "/").Count } -Descending
    foreach ($r in $old) {
        aws apigateway delete-resource --rest-api-id $API_ID --resource-id $r.id 2>&1 | Out-Null
    }
    $resources = (aws apigateway get-resources --rest-api-id $API_ID --output json) | ConvertFrom-Json
}
```
Then recreate the OPTIONS MOCK integration on `{proxy+}` and deploy.
**Prevention**: Never run `add_routes.py` after CDK consolidation. The `{proxy+}` catch-all handles all routes. CDK's `default_cors_preflight_options` handles OPTIONS automatically.
**File**: `infra/cdk/add_routes.py` — DO NOT RUN this script anymore

---

## Required VPC Endpoints (Complete List)

| Endpoint | Service | Purpose |
|----------|---------|---------|
| S3 (Gateway) | com.amazonaws.{region}.s3 | S3 access |
| Bedrock Runtime | com.amazonaws.{region}.bedrock-runtime | Entity extraction + embeddings |
| Secrets Manager | com.amazonaws.{region}.secretsmanager | DB credentials |
| Step Functions | com.amazonaws.{region}.states | Pipeline orchestration |
| AOSS | com.amazonaws.{region}.aoss | OpenSearch Serverless |
| Lambda | com.amazonaws.{region}.lambda | Batch loader self-invoke |

ALL Interface endpoints need: private DNS enabled, Lambda SG allowed inbound on 443.

---

## Lambda Deployment Package Checklist

Before deploying Lambda code, verify ALL of these are in `src/`:

- [ ] `src/batch_loader/` — copied from `scripts/batch_loader/`, imports fixed
- [ ] `src/config/aws_pricing.json` — copied from `config/`
- [ ] `src/PyPDF2/` — installed via `pip install PyPDF2 -t src/`
- [ ] All `batch_loader/*.py` imports use `from batch_loader.*` not `from scripts.batch_loader.*`
- [ ] `batch_loader_handler.py` imports use `from batch_loader.*` not `from scripts.batch_loader.*`

## CDK Stack Checklist

Before running `cdk deploy`:

- [ ] Run AOSS cleanup (Issue 2) if previous deploy failed
- [ ] `ACCESS_CONTROL_ENABLED=false` in `_build_lambda_env()`
- [ ] Step Functions substitutions include `ResolveConfigLambdaArn`, `ClassificationLambdaArn`, `RekognitionLambdaArn`
- [ ] CaseFiles Lambda timeout = 900s
- [ ] `LambdaRestApi` with `proxy=True` (not individual routes)
- [ ] Lambda VPC endpoint exists with correct SG rules

## Post-Deploy Checklist

After `cdk deploy` succeeds:

- [ ] Verify Lambda has `ACCESS_CONTROL_ENABLED=false` env var
- [ ] Verify Lambda VPC endpoint is available
- [ ] Verify Lambda SG → VPC endpoint SG ingress rule on 443
- [ ] Deploy Lambda code: `Compress-Archive -Path src\* -DestinationPath lambda-update.zip -Force; aws s3 cp lambda-update.zip s3://research-analyst-data-lake-974220725866/deploy/lambda-update.zip; aws lambda update-function-code --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --s3-bucket research-analyst-data-lake-974220725866 --s3-key deploy/lambda-update.zip`
- [ ] Delete orphaned API Gateway routes from add_routes.py if present (Issue 16)
- [ ] Verify only `/` and `/{proxy+}` resources exist in API Gateway
- [ ] Verify CORS OPTIONS is working (CDK now handles this automatically via `default_cors_preflight_options`)
- [ ] Verify Neptune SG allows Lambda SG on port 8182 (Issue 13)
- [ ] Test: `GET /case-files` returns 200 with cases
- [ ] Test: `POST /case-files/{id}/patterns` with `{"graph":true}` returns 200 (Issue 15)
- [ ] Test: `GET /batch-loader/discover?case_id=...&batch_size=10` returns 200
- [ ] Run migration 007 if needed


## Issue 27: fast_load.py Sends s3_keys but Ingest API Expects files with base64 Content

**Problem**: `fast_load.py` sends `{"source_bucket": "...", "s3_keys": [...], "skip_duplicates": true}` to `POST /case-files/{id}/ingest`, but the `ingest_handler` in `ingestion.py` expects `{"files": [{"filename": "...", "content_base64": "..."}]}`. The handler validates `body.get("files", [])` and returns 400 "No files provided for ingestion" because `s3_keys` is not recognized.
**Root cause**: Two different ingestion interfaces exist: (1) the API handler (`ingestion.py`) which accepts base64-encoded file content for browser uploads, and (2) the batch loading scripts which have files already in S3 and just need to trigger the Step Functions pipeline. The `fast_load.py` script was written to call the API but sends the wrong payload format.
**Fix**: Changed `fast_load.py` to bypass the ingest API entirely and trigger Step Functions directly via `boto3 sfn.start_execution()`, passing `document_ids` derived from S3 key filenames. This is the same approach used by `process_new_epstein_pdfs.py`.
**Prevention**: When files are already in S3, NEVER call the ingest API — it's designed for browser uploads with base64 content. Instead, trigger Step Functions directly with `upload_result.document_ids`. The two ingestion paths are:
  - **Browser upload path**: `POST /case-files/{id}/ingest` with `files[].content_base64` → handler uploads to S3 → triggers SFN
  - **Batch/CLI path**: Files already in S3 → trigger SFN directly via `sfn.start_execution()` with `document_ids`
**File**: `scripts/fast_load.py`


## Issue 28: PyMuPDF Windows Binaries Don't Work on Lambda (Amazon Linux)

**Problem**: PyMuPDF installed from Windows (`pip install PyMuPDF`) includes Windows `.pyd` DLLs, not Linux `.so` shared objects. When deployed to Lambda (Amazon Linux 2), `import fitz` fails silently and no images are extracted from PDFs.
**Root cause**: `pip install` defaults to the current platform's binaries. The Lambda zip was built on Windows, so it contained Windows-only native extensions.
**Fix**: Install with explicit Linux platform targeting:
```
pip install --platform manylinux2014_x86_64 --only-binary=:all: PyMuPDF Pillow -t src/ --upgrade
```
Then rebuild zip and redeploy Parse Lambda.
**Prevention**: ALWAYS use `--platform manylinux2014_x86_64 --only-binary=:all:` when installing native Python packages destined for Lambda. This applies to PyMuPDF, Pillow, numpy, and any package with C extensions.
**File**: `src/services/pdf_image_extractor.py`, Parse Lambda

## Issue 29: Bedrock Returns JSON-Wrapped Analysis Text

**Problem**: The question-answer Level 2 endpoint returned `analysis` field containing raw JSON like `{"analysis": "actual text...", "citations": []}` instead of plain text. The frontend displayed this raw JSON to the user.
**Root cause**: `_parse_json_response` in `QuestionAnswerService` failed to parse Bedrock's response (due to trailing commas, truncation, or extra whitespace). The fallback `parsed.get("analysis", raw)` stored the entire raw Bedrock output (a JSON string) as the `analysis` value.
**Fix**: (1) Made `_parse_json_response` more robust — handles preamble text, trailing commas, embedded JSON objects. (2) Added `_extract_text_from_analysis` that detects when the analysis value is itself JSON and extracts the inner text. (3) Added frontend safety net in `_renderLevel2Content` and `_renderLevel3Modal`.
**Prevention**: Always validate that text fields returned to the frontend are plain text, not JSON. When using LLM JSON output, always have a fallback extraction path for malformed responses.
**File**: `src/services/question_answer_service.py`, `src/frontend/investigator.html`


## Issue 30: Browser Caching Prevents Local file:// HTML Updates

**Problem**: Changes to `investigator.html` are not reflected in the browser even after Ctrl+Shift+R hard refresh. The face crops section shows "Loading face crops..." spinner indefinitely because the browser serves the old cached JavaScript.
**Root cause**: Chrome aggressively caches `file://` protocol pages. `Ctrl+Shift+R` does not always force a reload of local HTML files. The browser's disk cache retains the old version.
**Fix**: Open the file in a different browser (Edge, Firefox) or use Chrome Incognito mode. Alternatively, add a cache-busting query parameter to the file URL: `investigator.html?v=2`.
**Prevention**: When developing locally with `file://`, always test in Incognito mode or use a local HTTP server (`python -m http.server 8080` in the `src/frontend/` directory) which respects cache headers properly.
**Related fixes applied**: 
- `_loadFaceCrops` now uses cached `window._rawEntityPhotos` instead of making a second API call
- `openEntity` Promise.all has `.catch()` fallbacks so search/patterns failures don't block the drill-down
- Patterns call has a 15-second timeout via `Promise.race`
**File**: `src/frontend/investigator.html`


## Visual Evidence Pipeline — Post-Processing Steps

The SFN ingestion pipeline handles per-document visual analysis automatically (Rekognition labels, face detection, face cropping, AI image descriptions). However, three post-processing steps run AFTER the pipeline completes and operate on the full corpus of extracted images:

### Step 1: Batch Rekognition Labels (already in SFN per-doc, but batch script for bulk re-processing)
```bash
python scripts/batch_rekognition_labels.py --case-id <CASE_ID> --parallel 5
```
- Runs `detect_labels` on all extracted images in `cases/{case_id}/extracted-images/`
- Saves `batch_labels_summary.json` and `batch_labels_details.json` to `cases/{case_id}/rekognition-artifacts/`
- Supports resume via local progress file
- The SFN pipeline's Rekognition step does this per-batch, but this script processes the full corpus

### Step 2: Face Matching (NOT in SFN — post-processing only)
```bash
python scripts/match_faces.py --case-id <CASE_ID> --comparison-log scripts/face_match_log.json
```
- Compares unidentified face crops against known entity demo photos using `CompareFaces`
- Copies matched crops to `face-crops/{entity_name}/` folders
- Supports incremental runs — skips already-completed comparisons via comparison log
- Merges results cumulatively into `face_match_results.json`
- Re-run after adding new entity photos to `face-crops/demo/`

### Step 3: Neptune Visual Entity Loading (NOT in SFN — post-processing only)
```bash
python scripts/load_rekognition_to_graph.py --mode labels --case-id <CASE_ID> --sync-combined
```
- Reads `batch_labels_details.json` and creates Visual_Entity nodes in Neptune
- Creates DETECTED_IN edges (entity → document) and CO_OCCURS_WITH edges (entity ↔ entity)
- Generates Neptune bulk-load CSVs and triggers the bulk loader
- `--sync-combined` copies artifacts to the combined case

### Customer Deployment: Full Pipeline Sequence
For a new case ingestion, the complete sequence is:
1. Upload files to S3 → trigger SFN pipeline via `fast_load.py` or data-loader.html
2. SFN pipeline processes each batch: Parse → Rekognition → FaceCrop → ImageDescription → GraphLoad
3. After all batches complete, run post-processing:
   - `batch_rekognition_labels.py` (if full-corpus label analysis needed)
   - `match_faces.py` (match detected faces against known entities)
   - `load_rekognition_to_graph.py --mode labels` (load visual entities into Neptune)
4. Sync artifacts to combined case if using multi-case aggregation

### Data Loader UI Integration
The `data-loader.html` page (case-type-profiles spec) drives steps 1-2 from the browser. Steps 3-4 are currently CLI scripts. Future enhancement: add a "Post-Processing" section to data-loader.html that triggers these scripts via a Lambda endpoint.


## Issue 31: Rekognition "Weapon/Gun/Rifle" False Positives on Redacted Documents

**Problem**: Rekognition `detect_labels` classifies redaction bars (black rectangles) on legal documents as "Gun", "Rifle", or "Weapon". The 41 "Weapon" detections and 21 "Gun" detections in the Epstein case are almost entirely redacted email correspondence, not actual weapons.
**Root cause**: Rekognition's object detection model sees dark rectangular silhouettes that resemble weapon shapes. When a document has heavy redaction (black bars over names, addresses, phone numbers), the model matches the shape pattern.
**Impact**: Misleading label counts in the Visual Evidence Summary — investigators see "Weapon: 41" and expect actual weapon imagery.
**Fix (recommended)**: Add a redaction false-positive filter: when an image has BOTH a document-type label (Text, Page, Letter, Document) AND a weapon-type label (Weapon, Gun, Rifle, Pistol, Knife), flag the weapon label as `likely_false_positive: true` and add a `redaction_detected` flag. The frontend should show these with a warning indicator.
**Alternative**: Use the AI Image Description feature (Bedrock Claude vision) on weapon-flagged images — Claude correctly identifies "redacted email correspondence" rather than "weapon".
**Prevention**: For case types with heavy document redaction (legal, financial, government), add a post-processing step that cross-references weapon labels with document labels and flags co-occurrences as likely false positives.

## Clickable Label Gallery (Faceted Image Browsing)

**Feature**: Label tags in the Visual Evidence Summary are clickable. Clicking "Weapon: 41 →" opens a full-screen image gallery filtered to that label, with thumbnails showing source document IDs, all detected labels, and face counts. This follows the Palantir Gotham / Relativity / Cellebrite pattern of faceted evidence browsing.
**Implementation**: Frontend-only — `_openLabelGallery(labelName)` calls `GET /case-files/{id}/image-evidence?label_filter={label}` and renders a grid overlay.
**File**: `src/frontend/investigator.html`

## Video Processing Capability

**Status**: The pipeline supports video processing via `rekognition_handler.py` with `_process_video()` and `_process_video_faces_only()` functions. Controlled by `video_processing_mode` config: "skip" (default), "faces_only", or "full".
**Cost**: $0.10/min for label detection, $0.10/min for face detection. A 25-minute batch costs ~$5.
**No video files exist** in the current Epstein case data — all files are PDFs. To demo video capability, sample investigative-style video content would need to be sourced and uploaded to `cases/{case_id}/raw/`.
**Rekognition Video API**: Async — `start_label_detection` / `start_face_detection` submit jobs, poll `get_label_detection` / `get_face_detection` for results. Each video takes 1-10 minutes to process.


## Issue 31: Lambda Direct Upload Timeout — Must Deploy via S3

**Problem**: `aws lambda update-function-code --zip-file fileb://lambda-update.zip` consistently times out from Kiro's shell (and often from PowerShell too). The Lambda zip is ~50-80MB and the direct upload takes longer than the CLI timeout allows. Multiple deploy attempts across an entire session failed silently — the Lambda `LastModified` timestamp never changed.
**Root cause**: The `--zip-file fileb://` flag uploads the zip directly from the local machine to the Lambda service. For large zips (>30MB) on slower connections or through Kiro's terminal, this exceeds the default CLI timeout. The command appears to hang and eventually times out without updating the Lambda.
**Fix**: Always deploy Lambda via S3 intermediate:
```powershell
# Step 1: Create zip
Compress-Archive -Path src\* -DestinationPath lambda-update.zip -Force

# Step 2: Upload to S3 (fast, reliable)
aws s3 cp lambda-update.zip s3://research-analyst-data-lake-974220725866/deploy/lambda-update.zip

# Step 3: Update Lambda from S3 (fast, no upload timeout)
aws lambda update-function-code --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --s3-bucket research-analyst-data-lake-974220725866 --s3-key deploy/lambda-update.zip
```
**Prevention**: NEVER use `--zip-file fileb://` for Lambda deploys. ALWAYS use the S3 intermediate path. The S3 upload is chunked and reliable, and the Lambda update-from-S3 is a fast metadata operation that doesn't timeout.
**Impact**: This issue blocked ALL backend changes for an entire session — AI Briefing fix, OSINT Research Agent, pattern filtering, and graph_case_id resolution were all written but never deployed until the S3 method was used.
**Files**: All Lambda handler and service files

## Issue 32: AI Briefing 404 for Cases Without Prior Analysis

**Problem**: The AI Intelligence Briefing shows "Failed to load AI Briefing" for any case that hasn't had `POST /investigator-analysis` called previously (e.g., the Ancient Aliens case). The `get_analysis` handler returned a 404 when `engine.get_analysis_status(case_id)` returned None.
**Root cause**: The handler treated "no analysis exists" as a 404 error. But the Command Center data (prosecution readiness, intelligence quality indicators) can still be computed from graph/entity data without a prior analysis run.
**Fix**: Changed the handler to return `{"status": "no_analysis", "case_id": case_id}` with a 200 status when no analysis exists, then still attempts to attach Command Center data. The frontend already handles the `command_center` key gracefully.
**Additional fix**: The `graph_case_id` was hardcoded to the Epstein Neptune case ID. Changed to dynamically look up `parent_case_id` from Aurora — combined cases use the parent, standalone cases use their own ID.
**File**: `src/lambdas/api/investigator_analysis.py`


## Issue 33: OSINT Research Agent — VPC Lambda Cannot Reach Public Internet (Brave Search API)

**Problem**: The OSINT Research Agent's "Research This Externally" button shows "Failed to fetch" or returns 0 sources. The Lambda is in a VPC and cannot reach the Brave Search API (`api.search.brave.com`) on the public internet.

**Root Cause Chain**:
1. Lambda is deployed in VPC subnets (`subnet-08c5dc41e84a46eb5`, etc.) for Aurora/Neptune access
2. VPC has a NAT Gateway (`nat-0bac4ae7c6aaff3db`) but it was NOT wired to any route table
3. Lambda subnets used the main route table which routes `0.0.0.0/0` to an Internet Gateway (IGW) — this doesn't work for Lambda because Lambda ENIs don't get public IPs
4. Even after creating a private route table (`rtb-02ddde46e21106c89`) with NAT route and associating all 6 Lambda subnets, the API Gateway 29-second timeout kills the request before the OSINT pipeline completes

**Debugging Steps Performed**:
1. Confirmed `BRAVE_SEARCH_API_KEY` env var was missing → set via `scripts/set_brave_key.py`
2. Checked Lambda logs — no OSINT log entries (Lambda completing in 1-2ms = not reaching OSINT code)
3. Confirmed API Gateway is proxy (`/{proxy+}`) — route exists
4. Checked security group `sg-05ff17c74d15959e7` — all outbound allowed (`-1` protocol, `0.0.0.0/0`)
5. Found NAT Gateway exists but no route table references it
6. Created private route table `rtb-02ddde46e21106c89` with `0.0.0.0/0 → nat-0bac4ae7c6aaff3db`
7. Associated all 6 Lambda subnets with the new route table
8. Still failing — API Gateway integration timeout is 29,000ms (29s hard limit)
9. Optimized OSINT pipeline: skip page fetching, limit to 2 queries, use snippets only, reduce time budget to 20s

**Fix Applied**:
- Created route table `rtb-02ddde46e21106c89` with NAT Gateway route
- Associated Lambda subnets: `subnet-08c5dc41e84a46eb5`, `subnet-08daeb0b5e4e1bf85`, `subnet-07cffe5b0b84b3499`, `subnet-0d4d796be847de3b0`, `subnet-023e2e0e7b9bd70c6`, `subnet-037765830e6460aff`
- Reduced `TIME_BUDGET_SECONDS` from 25 to 20
- Skipped page fetching (use Brave search snippets directly)
- Limited queries to 2 (was unlimited)
- Increased web search client timeout from 5s to 10s (NAT adds latency)
- Tightened contradiction detection and timeline correlation time checks

**CloudFormation/CDK Requirements for Rebuild**:
- Lambda MUST be in private subnets with route to NAT Gateway (NOT public subnets with IGW)
- Route table: `0.0.0.0/0 → NAT Gateway` (NOT `0.0.0.0/0 → IGW`)
- NAT Gateway must be in a public subnet with Elastic IP
- API Gateway integration timeout: 29s max (REST API hard limit) — OSINT pipeline must complete within this
- Environment variable: `BRAVE_SEARCH_API_KEY` must be set on Lambda
- Security group: outbound HTTPS (443) to `0.0.0.0/0` required

**Key Lesson**: VPC Lambdas that need public internet access MUST use private subnets routed through a NAT Gateway. The default VPC route table with an IGW does NOT work for Lambda because Lambda ENIs don't receive public IPs. This is a common gotcha when adding external API calls to an existing VPC Lambda.

**Files**: `src/services/osint_research_service.py`, `src/services/web_search_client.py`, `src/lambdas/api/osint_handler.py`, `scripts/set_brave_key.py`


## Lesson 19: Master Tester Requirement for Every New Feature (April 12, 2026)

**Problem:** New features (Theory Engine, Anomaly Radar, Command Center) consistently required 3-5 deployment iterations to fix issues that should have been caught before the first deploy. Root causes:
1. Wrong database column names (guessing instead of verifying against actual schema)
2. Stale `.pyc` bytecode files included in Lambda zips, causing `ModuleNotFoundError`
3. Feature flags defaulting to wrong values, breaking existing functionality
4. API Gateway 29-second timeout not accounted for in slow operations
5. Frontend calling non-existent API endpoints

**Mandatory Pre-Deploy Checklist (add to every new feature):**
1. **Verify database schema** — query the actual Aurora tables to confirm column names before writing SQL
2. **Clean __pycache__** — run `Get-ChildItem -Path src -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force` before every Lambda zip
3. **Test API endpoint directly** — use `Invoke-RestMethod` to test each new endpoint before deploying frontend
4. **Check CloudWatch logs** — after first deploy, immediately check logs for errors before telling user to test
5. **Verify route matching** — confirm the new route is matched in `case_files.py` dispatcher
6. **Test with actual case data** — don't assume data exists; verify with a query first
7. **Feature flag defaults** — new flags should default to "true" (enabled) for existing environments, "false" only for GovCloud configs
8. **Time budget** — any operation that queries Neptune or calls Bedrock must complete within 25 seconds (API Gateway timeout is 29s)

**Hook created:** `clean-pycache-deploy` — removes all `__pycache__` and `.pyc` files before deployment


---

## Issue 22: Epstein Main Has 345K Docs But 0 Entities in Aurora

**Problem**: Epstein Main case (7f05e8d5) has 345,904 raw files in S3 and 345,898 documents in Aurora, but 0 entities in the Aurora entities table. Neptune has entity data but Aurora doesn't.
**Root cause**: Same as Epstein Combined — entity extraction via Bedrock either failed or was skipped during batch loads. Neptune was populated via the Rekognition/visual pipeline but the Aurora entities table was never populated.
**Fix**: Run `python scripts/sync_neptune_to_aurora.py --case-id 7f05e8d5-4492-4f19-8894-25367606db96` to sync Neptune entities to Aurora.
**Prevention**: The existing pipeline's extract_handler.py already writes entities to Aurora with ON CONFLICT DO UPDATE. This issue only affects cases where entity extraction was skipped during the original batch loads.
**Reference**: See docs/data-inventory-and-ingestion-plan.md for full inventory.

## Issue 23: Neptune-Aurora Entity Gap Pattern

**Problem**: Multiple cases (Epstein Combined, Epstein Main, Ancient Aliens) had entities in Neptune but 0 in Aurora. This caused theories, case files, anomaly detection, and legal analysis to fail or return empty results.
**Root cause**: The Rekognition/visual pipeline populates Neptune directly. The text-based entity extraction pipeline populates both Aurora and Neptune. When text extraction fails/skips, Neptune has data but Aurora doesn't.
**Fix**: Created `scripts/sync_neptune_to_aurora.py` and `src/lambdas/api/neptune_aurora_sync.py` to sync Neptune entities to Aurora on demand.
**Key insight**: Always check both Neptune AND Aurora entity counts when debugging empty results. The Knowledge Graph may work perfectly (Neptune) while theories/case files fail (Aurora).

## Issue 24: API Gateway 29-Second Timeout on Case File Generation

**Problem**: Theory case file regeneration times out with 504 error. Lambda timeout is 900s but API Gateway has a hard 29-second limit.
**Root cause**: Case file generation makes a Bedrock call with a large prompt (13 sections). Adding a second dedicated Bedrock call for legal analysis pushed total time over 29 seconds.
**Fix**: Removed the second Bedrock call. Reduced evidence from 20 docs to 10, text excerpts from 200 to 150 chars, entities from 30 to 20 in the prompt. Single Bedrock call generates all 13 sections.
**Prevention**: Any Lambda behind API Gateway must complete within 29 seconds. For long-running operations, use async invocation (InvocationType=Event) or Step Functions.

## Issue 25: Data Inventory — What's Actually Loaded

**Discovery**: Epstein Main has 345,904 files — far more than the 8,974 in Epstein Combined. This was not documented and was missed in previous sessions.
**Key numbers**:
- Epstein Main: 345,904 S3 raw files, 345,898 Aurora docs, 0 entities (needs sync)
- Epstein Combined: 8,980 S3 raw files, 8,974 Aurora docs, 21,488 entities
- Ancient Aliens: 240 S3 raw files, 40 Aurora docs, 36,358 entities
- Source bucket: DS1-5 loaded (4.3 GB), DS8-12 placeholder only
**Reference**: See docs/data-inventory-and-ingestion-plan.md for full inventory and ingestion plan.
**Prevention**: Always run `python scripts/_inventory.py` before making assumptions about data availability.


## Issue 34: Epstein Main Has 345K S3 Files But 0 Aurora Document Rows

**Problem**: The Epstein Main case (`7f05e8d5`) shows 345,904 files in S3 under `cases/7f05e8d5.../raw/` but the Aurora `documents` table has 0 rows for this case_id. All features that depend on document content (Did You Know, Anomaly Radar, KNN search, case file generation, text search) fail or return empty results. The `case_files.document_count` was set from S3 file counts via `scripts/update_case_doc_counts.py`, not from actual Aurora rows.
**Root cause**: Files were uploaded to S3 but never processed through the Step Functions ingestion pipeline. The pipeline (parse → extract → embed → graph → store) was not run on these files. Neptune entities (44,806) and relationships (65,675) were loaded separately via direct graph loading, not through the pipeline.
**Fix**: Run `scripts/batch_loader.py` with correct parameters:
```bash
python scripts/batch_loader.py --confirm --max-batches 2 --case-id 7f05e8d5-4492-4f19-8894-25367606db96 --source-bucket research-analyst-data-lake-974220725866 --source-prefixes cases/7f05e8d5-4492-4f19-8894-25367606db96/raw/
```
**Changes required**: 
- `src/batch_loader/discovery.py`: Updated `list_all_raw_keys()` to accept `.txt` files in addition to `.pdf`
- `src/batch_loader/config.py`: Added `--source-bucket` CLI argument
**Estimated cost**: ~$135 for full 345K docs (Textract + Bedrock entity extraction + Titan Embed + Neptune)
**Plan**: Phase 1: 10K validation → Phase 2: 90K overnight → Phase 3: 245K remaining
**Prevention**: Always verify Aurora `documents` table row count matches expected count after ingestion. The `refresh_case_stats` action now does this automatically.

## Issue 35: Evidence Starvation — Case File Generator Uses Blind Recency Query

**Problem**: `generate_case_file()` fetched only 15 documents via `ORDER BY indexed_at DESC LIMIT 15` with 150-char snippets, regardless of relevance to the theory. Legal analysis section (section 12) was consistently empty due to single Bedrock call token exhaustion. Confidence score showed 80 despite sparse content.
**Root cause**: Evidence query had no semantic relevance filtering. Single Bedrock call with `max_tokens=4096` for all 13 sections. No confidence penalty for empty sections.
**Fix (deployed Lambda v5, 2026-04-13)**:
- KNN semantic search via pgvector (`_fetch_knn_evidence()`) — 30 most relevant docs at 300 chars
- Two-pass Bedrock generation: Pass 1 (sections 1-11, 6144 tokens), Pass 2 (legal analysis, 4096 tokens)
- KNN entity enrichment from retrieved documents (up to 40 entities)
- Confidence penalty: 5 points per gap detected
**Spec**: `.kiro/specs/case-file-evidence-starvation/`

## Issue 36: Stuck AI Intelligence Briefing — No Expiry on Processing Cache

**Problem**: `investigator_analysis_cache` row with `status="processing"` had no expiry. If the async Lambda timed out, the UI showed "Analysis in progress..." indefinitely with no way to retry.
**Fix (deployed Lambda v5, 2026-04-13)**: Added 15-minute expiry check to `get_analysis_status()`. Processing rows older than 15 minutes are auto-deleted, allowing fresh analysis. Also added 60-second per-service timeouts for pattern_discovery, hypothesis_generation, and _generate_leads on large cases (>10K docs).
**Spec**: `.kiro/specs/case-file-evidence-starvation/`


## Issue 37: Enterprise Tier Cases Produce 0 Aurora Documents (Embed Step AOSS 401)

**Problem**: Epstein Main case (`7f05e8d5`) processed 10,000 files through the pipeline — entities and graph data loaded successfully (73K entities, 107K relationships) but Aurora `documents` table had 0 rows. The Embed step routes to OpenSearch Serverless for `enterprise` tier cases, which fails with AOSS 401 auth errors (Issue 26). Documents never reach Aurora.
**Root cause**: The case was created with `search_tier=enterprise`. The Embed Lambda checks the case's search_tier and routes to AOSS for enterprise, Aurora pgvector for standard. AOSS auth is broken (Issue 26), so enterprise tier cases silently lose all document text and embeddings.
**Fix**: Changed case to `standard` tier via `update_case_name` action with `search_tier: "standard"`. Also need to default new cases to `standard` tier until AOSS auth is fixed.
**Prevention**: 
1. Default all new cases to `standard` tier in `CaseFileService.create_case_file()` and `MatterService.create_matter()`
2. Add a pre-flight check in the batch loader that warns if the target case is `enterprise` tier
3. Fix AOSS auth (separate issue) before enabling enterprise tier
**Files**: `src/services/case_file_service.py`, `src/services/matter_service.py`, `scripts/batch_loader.py`


## Issue 38: Extraction Cache Saves Textract Costs on Re-Runs

**Not a bug — a feature to document.** The batch loader's `TextExtractor` caches extracted text to S3 at `textract-output/batch_{batch_id}/{filename}.json`. On re-runs, `_check_cache()` reads the cached text and skips PyPDF2/Textract entirely. This means re-processing the same documents (e.g., after fixing the enterprise tier issue) only costs Bedrock entity extraction + embeddings, not Textract OCR.
**Cost savings**: ~$1.85 per 5K-doc batch saved on re-runs (Textract cost eliminated).
**Colleague note**: When handing off to colleagues, mention that re-ingesting the same PDFs is cheap because extraction is cached. Only new PDFs incur Textract costs.
**File**: `src/batch_loader/extractor.py` — `_check_cache()` and `_save_to_cache()` methods.


## Issue 32: Long-Running Scripts Die When Laptop Sleeps or Loses Internet

**Problem**: Overnight batch processes (embedding backfill, entity extraction) run as Python scripts on the local laptop. When the laptop goes to sleep or loses internet, the script dies mid-batch. The embedding backfill died after processing ~20K of 59K docs when the laptop slept. Entity extraction had the same risk.

**Root cause**: Local Python scripts depend on continuous internet connectivity to invoke Lambda. Laptop sleep kills the process.

**Fix**: For any batch process expected to run longer than 30 minutes, launch a small EC2 instance (t3.small, ~$0.02/hr) with a userdata script that:
1. Downloads the batch script from S3
2. Runs it unattended
3. Uploads logs to S3 when done
4. Self-terminates

**Pattern**:
```bash
# Upload script to S3
aws s3 cp scripts/my_batch_script.py s3://BUCKET/deploy/my_batch_script.py

# Launch EC2 with userdata that downloads and runs it
aws ec2 run-instances --image-id ami-XXXX --instance-type t3.small \
  --iam-instance-profile Name=NikityLoaderEC2Profile \
  --user-data file://scripts/ec2_userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=batch-job}]"
```

**Key details**:
- Use Amazon Linux 2023 which has `python3` (3.11) pre-installed — do NOT use `python3.12` (not in default repos)
- IAM instance profile needs: Lambda invoke, S3 read, EC2 terminate-instances
- Script should self-terminate via instance metadata + `aws ec2 terminate-instances`
- All work is saved to Aurora per-batch, so interruptions don't lose data — just restart

**Prevention**: Always use EC2 for batch processes. Never rely on the laptop staying awake for overnight runs.

**Files**: `scripts/ec2_entity_userdata.sh`, `scripts/ec2_entity_backfill.py`


## Issue 33: Always Verify Long-Running Processes — Don't Assume They're Working

**Problem**: EC2 entity extraction was launched but the userdata script failed silently. The EC2 showed "running" state but was doing nothing. Entity count didn't change for hours. The issue was only discovered when the user asked for a status check — not proactively by the developer.

**Root cause**: Assumed the EC2 was working because `describe-instances` showed "running." Never verified the userdata script actually executed. The first EC2 attempt (Nikity loader) had the same failure pattern — should have learned from it.

**Rules for long-running processes**:
1. After launching ANY long-running process (EC2, background script, batch job), verify it's actually working within 5 minutes — don't just check the container is running, check the WORK is happening
2. For EC2 userdata: check console output within 3-5 minutes to confirm the script started
3. For batch jobs: check the output metric (entity count, doc count, etc.) is actually increasing
4. Check every hour on any process expected to run longer than 1 hour
5. If a process type has failed before (e.g., EC2 userdata), test the fix immediately before walking away
6. Never tell the user "it's running" without verifying the actual work output changed

**Prevention**: Before starting any new long-running task, always:
- Verify the previous similar task completed successfully
- Test with a small batch first (10 docs, not 60K)
- Check the actual output metric (not just process status) within 5 minutes
- Set a mental checkpoint to re-verify in 1 hour


## Issue 34: Geospatial Map Crashes with "Invalid LatLng object: (NaN, NaN)"

**Problem**: The geospatial evidence map shows a blank screen or "Map load failed: Invalid LatLng object: (NaN, NaN)". This happens when Neptune returns location entities that the geocoding service can't resolve to coordinates, or when OCR noise entities (e.g., "Rear. •COX #", "KO E P S OF", "STATE") are typed as locations.

**Root causes (multiple):**
1. Location entities from Neptune include OCR noise that can't be geocoded → coordinates are undefined/NaN
2. Leaflet's `L.circleMarker()` crashes on NaN coordinates instead of silently skipping
3. `L.featureGroup().fitBounds()` crashes if any marker in the group has NaN coordinates
4. Travel line arc calculation divides by zero when two locations have identical coordinates (dist=0)
5. Referencing undeclared JavaScript variables (e.g., `selectedCaseName`) crashes the entire page — not just the map

**Fixes applied:**
1. **Marker creation**: Added `if (isNaN(coords.lat) || isNaN(coords.lng)) return;` before creating any `L.circleMarker`
2. **fitBounds**: Wrapped in try-catch with fallback to `mapInstance.setView([30, -40], 3)`
3. **Travel lines**: Added NaN check on both endpoints before creating polylines
4. **Arc midpoint**: Added `if (dist === 0) continue;` to prevent division by zero
5. **Location dedup**: Deduplicate location nodes by name before geocoding
6. **Location filtering**: Skip locations with names shorter than 3 characters

**CRITICAL RULE — Data Loading Must Not Break the Frontend:**
When loading new data (entities, documents, embeddings) into Aurora or Neptune:
- OCR noise WILL produce garbage entity names typed as "location"
- The geocoding service only resolves ~200 curated location names
- Any unresolved location produces undefined coordinates
- The frontend MUST gracefully handle undefined/NaN coordinates at EVERY point where Leaflet LatLng objects are created
- NEVER reference undeclared JavaScript variables — always check with `typeof` or use optional chaining
- ALWAYS test the geospatial map after any data loading operation before telling the user it's done

**Prevention checklist after data loading:**
1. Test the map tab on every case that received new data
2. Check for OCR noise in location entities: `SELECT canonical_name FROM entities WHERE entity_type='location' AND case_file_id='...' AND LENGTH(canonical_name) < 3`
3. Run the noise entity cleanup script: `python scripts/cleanup_noise_entities.py`
4. Verify the geocode endpoint resolves locations: `python scripts/test_geocode.py`

**Files**: `src/frontend/investigator.html` (loadMap function, drawTravelLines function)


## Issue 39: Neptune addE() Requires __.V() Not g.V() for Anonymous Traversals

**Problem**: All `addE().to(g.V('id'))` Gremlin queries fail with 500 `InternalFailureException`: "The child traversal was not spawned anonymously - use the __ class rather than a TraversalSource to construct the child traversal."
**Root cause**: Neptune's Gremlin HTTP API requires anonymous traversals in `.to()` and `.from()` steps. `g.V()` is a TraversalSource (starts a new traversal from the graph), while `__.V()` is an anonymous traversal (a child step within the current traversal). The `.to()` step expects a child traversal.
**Fix**: Use `__.V('id')` instead of `g.V('id')` in all `.to()` and `.from()` clauses:
```
# WRONG — fails with 500
g.V('person-id').addE('RELATED_TO').to(g.V('location-id'))

# CORRECT — works
g.V('person-id').addE('RELATED_TO').to(__.V('location-id'))
```
**Prevention**: ALWAYS use `__.V()` for anonymous traversals in Gremlin HTTP API. This applies to `.to()`, `.from()`, `.where()`, `.filter()`, and any step that takes a child traversal.
**Files**: `scripts/fix_combined_edges_final.py`, `src/lambdas/api/case_files.py` (gremlin_query handler)

## Issue 40: Patterns API limit(200) Misses Low-Degree Location Nodes

**Problem**: New location nodes added to Neptune (Marrakesh, Islip, Palm Beach, etc.) with 1-2 edges didn't appear in the patterns API response. The geospatial map showed only high-degree locations (New York, Paris, Washington).
**Root cause**: The `_get_graph()` function in `patterns.py` used a single query with `.limit(200)` that returned the first 200 vertices Neptune found (in storage order). New low-degree locations were not in those 200. The code then said "Always include ALL location nodes" but it could only include locations from the 200 it already fetched.
**Fix**: Split into two queries: (1) query ALL location nodes separately (no limit), (2) query top 200 non-location nodes. Merge and dedup. This ensures every location in Neptune appears on the map regardless of degree.
**File**: `src/lambdas/api/patterns.py` — `_get_graph()` function
**Prevention**: When a specific entity type must be exhaustively included (like locations for the map), query it separately rather than relying on a limited general query.

## Issue 41: EC2 Entity Extraction May Be Stuck (April 16, 2026)

**Problem**: EC2 `i-06144ab22c4a90751` has been running for 27+ hours but entity count for Epstein Main hasn't changed from 33,509 (60,496 remaining). The EC2 may be stuck or erroring silently.
**Action needed**: Check EC2 console output or SSM for logs. If stuck, terminate and relaunch with fresh userdata.
**Lesson**: Always check that the actual metric (entity count) is increasing, not just that the EC2 shows "running". Check every hour as instructed.
