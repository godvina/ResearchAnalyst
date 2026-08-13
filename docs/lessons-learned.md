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


## Issue 42: Python Threading with boto3 Doesn't Parallelize Lambda Invocations

**Problem**: The parallel entity extraction EC2 (`entity-parallel-20t`) used Python `ThreadPoolExecutor` with 20 threads, but entity count barely moved (27 docs in 2 hours vs expected 300/min).
**Root cause**: Python's GIL (Global Interpreter Lock) prevents true parallelism with threads. While boto3 calls are I/O-bound and should release the GIL, the `ThreadPoolExecutor` approach with 20 threads sharing a single process may have hit Lambda concurrency throttling or connection pool limits.
**Fix**: Use `multiprocessing.Process` instead of threads. Each process gets its own Python interpreter, its own boto3 client, and its own connection pool. 10 processes = 10 truly parallel Lambda invocations.
**Script**: `scripts/ec2_entity_fast.py` — uses `multiprocessing.Process` with 10 workers
**Prevention**: For parallel Lambda invocations from EC2, always use `multiprocessing` not `threading`. Each worker must create its own `boto3.client()`.

## CRITICAL RULE: Check Long-Running EC2 Processes Every Hour

**Problem**: Entity extraction EC2 was stuck for hours without being noticed. The user had to ask for status.
**Rule**: On EVERY prompt, check the status of any running EC2 processes. Report the entity count and whether it's increasing. If count hasn't changed in 1 hour, investigate and restart.
**Hook created**: `check-ec2-status` — fires on every promptSubmit to remind checking.


## Issue 43: Entity Backfill Count Never Decreases — Docs Re-Processed Infinitely

**Problem**: The `backfill_entities_batch` action processes 20 docs per call and reports "processed: 20, entities_extracted: 65" — but the `backfill_entities_count` always returns the same "missing_count: 53,811". The same docs are re-processed every batch.
**Root cause**: UNDER INVESTIGATION. The `NOT EXISTS (SELECT 1 FROM entities e WHERE e.document_id = d.document_id)` subquery still finds the same documents after entities are inserted. Possible causes:
1. The `ON CONFLICT DO NOTHING` is silently dropping all inserts due to a unique constraint
2. The `document_id` in the entities table doesn't match the `document_id` in the documents table
3. The transaction isn't being committed (psycopg2 autocommit may be off)
**Impact**: All EC2 entity extraction processes appeared stuck because the count never changed. They were actually processing docs but re-processing the same ones infinitely.
**Workaround needed**: Fix the entity insert to properly mark docs as processed, or change the batch query to use a different mechanism (e.g., a processed flag on the documents table).


## Issue 43: Never Terminate Working EC2 Extraction Processes to "Speed Them Up"

**Problem**: Three EC2 instances were running entity extraction at ~10 docs/min (serial approach, proven working). They were terminated and replaced with a parallel script (10 workers, then 3 workers) that saturated Lambda concurrency, causing ALL Lambda invocations to timeout — including status checks and the extraction itself.
**Root cause**: The single CaseFiles Lambda handles ALL API traffic. When multiple parallel workers each hold a Lambda invocation for 2-5 minutes (Bedrock entity extraction), no other invocations can get through. The Lambda isn't throttled by concurrency limits — it's that each invocation takes minutes, and the parallel workers consume all available execution slots.
**Impact**: Lost ~2 hours of extraction progress. Had to terminate the parallel EC2s and relaunch with the original serial approach.
**Fix**: Reverted to serial approach (1 worker, batch_size=10, 1 second between batches). This leaves Lambda available for other requests between batches.
**Prevention**: 
1. **NEVER terminate a working EC2 extraction process** unless it's confirmed stuck (count not changing for 30+ minutes)
2. **Parallel entity extraction requires a SEPARATE Lambda** — cannot share the CaseFiles Lambda
3. If you want to speed up extraction, launch ADDITIONAL serial EC2 instances (2-3 max) rather than parallel workers within one instance
4. Always verify the count is increasing BEFORE terminating an existing process
**Files**: `scripts/ec2_entity_fast_with_sync.py` (DO NOT USE — saturates Lambda), `scripts/ec2_serial_with_sync.py` (USE THIS)


## Issue 44: Entity Extraction Backfill — Root Cause and Correct Architecture

**Problem**: Entity extraction backfill ran for 20+ hours processing ~300 docs total. Appeared to process 40K+ docs but was re-processing the same ones infinitely.

**Root cause**: The `entities` table has `UNIQUE (case_file_id, canonical_name, entity_type)` — one row per entity name per case. When doc A and doc B both mention "Jeffrey Epstein", the `ON CONFLICT DO UPDATE SET document_id = EXCLUDED.document_id` **overwrites** doc A's `document_id` with doc B's. The `NOT EXISTS (SELECT 1 FROM entities WHERE document_id = doc_A)` query then finds doc A again because its link was stolen. Same docs re-processed infinitely — burning Bedrock credits for nothing.

**Fix applied**: Created `entity_extraction_done` tracking table (separate from entities). Each processed doc gets an INSERT with `ON CONFLICT DO NOTHING`. Batch query uses `LEFT JOIN entity_extraction_done ... WHERE x.document_id IS NULL`. Count uses simple arithmetic: `total_docs - done_count`.

**Why this happened**: The backfill was a workaround because the original Step Functions pipeline failed (Issues 18-26). The pipeline's `extract_handler.py` handles entity aggregation correctly — it never overwrites `document_id`. The backfill code was written hastily and didn't account for the UNIQUE constraint behavior.

**Prevention**: 
1. Never use `ON CONFLICT DO UPDATE SET document_id = EXCLUDED.document_id` on a table with a UNIQUE constraint that doesn't include `document_id`
2. Always use a separate tracking mechanism (flag column or tracking table) for batch processing progress
3. The `entities` table is designed for one row per unique entity name — use `source_document_ids` JSONB array for document provenance

## Issue 45: ALTER TABLE ADD COLUMN DEFAULT on Large Table Locks Aurora

**Problem**: Deploying `ALTER TABLE documents ADD COLUMN IF NOT EXISTS entities_extracted BOOLEAN DEFAULT FALSE` on a table with 82K rows locked the entire `documents` table for 45+ minutes. All API requests touching the documents table hung, including the case list endpoint.

**Root cause**: In PostgreSQL < 11, `ALTER TABLE ADD COLUMN ... DEFAULT value` rewrites the entire table. Aurora Serverless at minimum capacity made this extremely slow. The table lock blocked all concurrent queries.

**Fix**: Rebooted Aurora to clear the lock. Replaced the approach with a separate `entity_extraction_done` tracking table (CREATE TABLE is instant, no table rewrite).

**Prevention**: 
1. **NEVER use ALTER TABLE ADD COLUMN with DEFAULT on large tables** in Aurora Serverless
2. Use separate tracking tables instead of adding columns to large tables
3. If you must add a column, use `ADD COLUMN ... DEFAULT NULL` (no rewrite in any PG version), then backfill values separately

## Bedrock Batch Inference — The Correct Architecture for Bulk Entity Extraction

### When to Use
- Any time you need to extract entities from more than ~1,000 documents
- Post-ingestion backfill when the Step Functions pipeline was skipped or failed
- Re-extraction after changing the entity extraction prompt
- DOJ pilot: 500TB dataset processing

### How It Works
1. **Generate JSONL**: Query Aurora for docs needing extraction, write prompts to S3 as JSONL
2. **Submit batch job**: One API call to `bedrock.create_model_invocation_job()`
3. **Bedrock processes internally**: Massively parallel, 50% cheaper than invoke_model
4. **Load results**: Read output JSONL from S3, insert entities into Aurora

### Cost Comparison (82K docs)
| Approach | Cost | Time | Infrastructure Impact |
|----------|------|------|----------------------|
| Serial invoke_model (EC2→Lambda→Bedrock) | ~$30 | ~237 days | Blocks API Lambda |
| Bedrock Batch Inference | ~$15 | ~4-6 hours | Zero Lambda impact |

### Prerequisites
1. **IAM Role**: `BedrockBatchInferenceRole` with S3 read/write + Bedrock trust policy
2. **EC2 Role**: `NikityLoaderEC2Role` needs `s3:PutObject`, `s3:GetObject`, `bedrock:CreateModelInvocationJob`, `iam:CreateRole`, `iam:PutRolePolicy`
3. **S3 location**: `s3://BUCKET/batch-inference/entity-extraction/{case_id}/input/` and `.../output/`

### Commands
```bash
# Option 1: Run from EC2 (recommended — survives laptop sleep)
aws s3 cp scripts/ec2_batch_generate_submit.py s3://BUCKET/deploy/
# Launch EC2 with ec2_batch_userdata.sh

# Option 2: Run locally (step by step)
python scripts/bedrock_batch_entity_extraction.py generate   # Write JSONL to S3
python scripts/bedrock_batch_entity_extraction.py submit     # Submit batch job
python scripts/bedrock_batch_entity_extraction.py status     # Check progress
python scripts/bedrock_batch_entity_extraction.py load       # Import results
```

### Files
- `scripts/bedrock_batch_entity_extraction.py` — Local CLI for step-by-step execution
- `scripts/ec2_batch_generate_submit.py` — EC2 unattended script (generate → submit → poll → load → self-terminate)
- `scripts/ec2_batch_userdata.sh` — EC2 userdata for launching the batch job
- `scripts/s3_batch_policy.json` — IAM policy for EC2 role

### JSONL Format (Anthropic Claude 3 Haiku)
```json
{"recordId": "doc-uuid", "modelInput": {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048, "messages": [{"role": "user", "content": "Extract named entities..."}]}}
```

### Troubleshooting
- **AccessDenied on S3 PutObject**: Add `s3:PutObject` to EC2 role policy for the batch-inference prefix
- **Job fails with ValidationException**: Check minimum record count (varies by model, typically 10+)
- **Job takes >24 hours**: Bedrock SLA is 24 hours max. Check job status for errors.
- **Output has many errors**: Check that `modelInput` format matches the model's InvokeModel body format exactly


## Issue 46: Bedrock Batch Inference — Model Compatibility

**Problem**: Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`) is marked Legacy and rejected by batch inference. Claude 3.5 Haiku not supported for batch in us-east-1. First batch job completed but all 75K records errored with "extraneous key [max_tokens] is not permitted" because JSONL used Anthropic format with Nova Lite model.

**Root cause**: Three issues compounded:
1. Anthropic models are legacy or not batch-enabled in this Isengard account
2. Amazon Nova Lite accepted the job but rejects Anthropic-format `modelInput` (`max_tokens`, `anthropic_version`)
3. Nova requires `inferenceConfig.maxTokens` and `messages[].content[].text` format

**Fix**: 
1. Use Amazon Nova Lite (`amazon.nova-lite-v1:0`) — confirmed working for batch inference
2. JSONL format for Nova:
```json
{"recordId": "doc-uuid", "modelInput": {"messages": [{"role": "user", "content": [{"text": "prompt..."}]}], "inferenceConfig": {"maxTokens": 2048}}}
```
3. NOT Anthropic format (this fails):
```json
{"recordId": "doc-uuid", "modelInput": {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048, "messages": [{"role": "user", "content": "prompt..."}]}}
```

**Prevention**: Always match the JSONL `modelInput` format to the target model's InvokeModel body format. Test with 1-2 records before submitting 75K.

## Issue 47: EC2 AMI boto3 Too Old for Bedrock Batch API

**Problem**: EC2 with Amazon Linux 2 (`ami-0c02fb55956c7d316`) installs boto3 1.33.13 via pip. This version doesn't have `create_model_invocation_job` (added in later boto3). The JSONL generation works but the batch submission fails with `AttributeError`.

**Fix**: Submit the batch job from the local machine (which has newer boto3/Python 3.12) instead of from EC2. The EC2 generates the JSONL to S3, then the local machine submits.

**Prevention**: For Bedrock batch operations, either:
1. Use a newer AMI with Python 3.11+ and recent boto3
2. Pin boto3 version: `pip3 install 'boto3>=1.34.0'` in the userdata script
3. Split the workflow: EC2 for data prep (JSONL generation), local/Lambda for API calls


## Issue 48: Aurora Bulk Load — NEVER Insert One Row at a Time via Lambda

**Problem**: Loading 75K Bedrock batch results into Aurora took ~67 hours because the load script called Lambda once per document (75K Lambda invocations, each doing 1-5 INSERTs). The Bedrock extraction itself only took 30 minutes.

**Root cause**: The load script (`ec2_load_batch_results.py`) processes each JSONL output line individually: parse → invoke Lambda → Lambda does INSERT → sleep 0.1s → next line. At ~0.5s per doc, 75K docs = 10+ hours. As the entities table grows, ON CONFLICT checks slow down further.

**Correct architecture for pilot (45 min total):**

| Step | Time | Method |
|------|------|--------|
| 1. Generate JSONL from Aurora | 4 min | EC2 → Lambda (paginated query) → S3 |
| 2. Bedrock Batch Inference | 30 min | One API call, Bedrock handles parallelism |
| 3. Load results into Aurora | **10 min** | EC2 direct Aurora connection OR batched Lambda (100 docs/call) |
| 4. Neptune sync | 30-60 min | EC2 → Lambda → Neptune Gremlin |

**How to fix Step 3 (two options):**

**Option A — EC2 direct Aurora connection (fastest, ~2 min):**
```python
import psycopg2
conn = psycopg2.connect(host=AURORA_ENDPOINT, dbname='research_analyst', user=USER, password=PASS)
cur = conn.cursor()
# Read JSONL output, parse entities, batch INSERT
for batch in chunks(all_records, 1000):
    values = [(case_id, doc_id, name, type, conf) for doc_id, entities in batch for name, type, conf in entities]
    psycopg2.extras.execute_values(cur, 
        "INSERT INTO entities (entity_id, case_file_id, document_id, canonical_name, entity_type, confidence) "
        "VALUES %s ON CONFLICT (case_file_id, canonical_name, entity_type) DO UPDATE SET "
        "occurrence_count = entities.occurrence_count + 1", values)
conn.commit()
```
Requires: Aurora endpoint + credentials on EC2 (via Secrets Manager), psycopg2 installed.

**Option B — Batched Lambda calls (fast, ~10 min):**
```python
# Send 100 docs per Lambda call instead of 1
batch = []
for record in output_lines:
    batch.append({"document_id": record["recordId"], "entities": parse_entities(record)})
    if len(batch) >= 100:
        invoke_lambda({"action": "bulk_insert_entities", "case_id": CASE_ID, "docs": batch})
        batch = []
```
Requires: New `bulk_insert_entities` Lambda action that does 100 INSERTs in one transaction.

**CRITICAL RULE**: Before building any data loading process, check this document. NEVER design a load that calls Lambda once per row. Always batch: 100+ rows per call, or connect to Aurora directly.

**Prevention checklist for any bulk load:**
1. Calculate total API calls BEFORE building: `total_rows / batch_size = total_calls`
2. If total_calls > 1,000, you need batching or direct DB connection
3. Estimate time: `total_calls × avg_call_time` — if > 30 min, redesign
4. For 500TB pilot: use Option A (direct Aurora) with multi-row INSERT and COPY command


## CRITICAL RULE: Verify Every EC2 Launch Within 2 Minutes

**Problem**: Multiple EC2 processes were launched and assumed to be working, only to discover hours later they had failed on startup (S3 AccessDenied, boto3 too old, script error, auto-chain launch failed silently).

**Rule**: After EVERY EC2 launch:
1. Wait 90-120 seconds for OS updates + script startup
2. Check console output for the script's first print statement
3. If no script output after 3 minutes, investigate immediately
4. If script started, check again at 5 minutes for first progress indicator
5. NEVER tell the user "it's running" until you've confirmed script output

**Pattern for verification:**
```python
# After launching EC2:
import time
time.sleep(120)
output = ec2.get_console_output(InstanceId=instance_id, Latest=True)
# Look for script markers like "===", "Starting", "Phase 1"
# If not found, the script hasn't started or failed
```

**This applies to**: Entity extraction, Neptune sync, batch generation, result loading — ANY EC2 process.


## CRITICAL RULE: Model Bake-Off Before Bulk Extraction (April 21, 2026)

**Problem**: Amazon Nova Lite was used for entity extraction on 75K documents without testing it against the actual data first. Result: 248K "entities" where ~75% are OCR garbage — `___` classified as "person", `[ ]` as "financial", `000!` as "event", `0279290` as "person". The model extracted formatting artifacts, page numbers, and OCR noise as entities. Only ~63K entities (25%) pass basic quality filters, and even those contain junk.

**Root cause**: Nova Lite was chosen because Claude Haiku was legacy and Claude 3.5 Haiku wasn't available for batch inference in us-east-1. We never tested a single page with Nova Lite before processing 75K documents. The model's entity extraction quality on OCR'd legal documents was never validated.

**Impact**: 
- 75K documents processed with a model that produces ~75% noise
- Neptune graph polluted with 1.3M garbage nodes (had to run overnight dedup)
- Weeks of cleanup work instead of clean data from the start
- The IPS algorithm, anomaly detectors, and prosecution readiness scoring all depend on entity quality — garbage in, garbage out

**MANDATORY RULE — Model Bake-Off Before ANY Bulk Extraction**:

Before processing more than 100 documents through entity extraction, you MUST:

1. **Select 10 representative documents** from the dataset — include:
   - Clean text documents (emails, letters)
   - OCR'd scanned documents (the hardest case)
   - Financial documents (statements, invoices)
   - Legal documents (court filings, depositions)
   - Mixed-quality documents (partially redacted, poor scans)

2. **Test ALL available models** on those 10 documents:
   - Amazon Nova Lite (`amazon.nova-lite-v1:0`)
   - Amazon Nova Pro (`amazon.nova-pro-v1:0`)
   - Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`) — if available
   - Claude 3.5 Haiku (`anthropic.claude-3-5-haiku-20241022-v1:0`) — if available
   - Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`) — gold standard reference

3. **Score each model** on:
   - **Precision**: What % of extracted entities are real? (not OCR noise)
   - **Recall**: What % of real entities in the document were found?
   - **Type accuracy**: Are entities classified correctly? (person vs location vs organization)
   - **Noise ratio**: How many garbage entities per real entity?
   - **Cost per document**: Input tokens + output tokens × model price

4. **Choose the model with the best precision/cost ratio** — not the cheapest model.
   - For legal/investigative documents: precision matters more than cost
   - A model that costs 3x more but produces 90% precision vs 25% precision saves weeks of cleanup
   - The cleanup cost (dedup, re-sync, re-extraction) always exceeds the model cost difference

5. **Document the bake-off results** in `docs/model-bakeoff-{case_name}.md`

6. **Build the bake-off into the pipeline** — the data-loader UI should have a "Test Extraction Quality" button that runs 10 sample docs through all available models and shows a comparison table before the user commits to bulk extraction.

**Script**: `scripts/model_bakeoff.py` — automated model comparison tool
**Prevention**: NEVER skip the bake-off. NEVER assume a model works well on your data because it works well on benchmarks. Test on YOUR actual documents.

**Cost comparison for Epstein Main (75K docs)**:
| Model | Est. Cost | Precision | Noise Ratio | Cleanup Cost |
|-------|-----------|-----------|-------------|--------------|
| Nova Lite | ~$15 | ~25% | 3:1 noise | ~$50+ (EC2 dedup, re-sync, re-extract) |
| Claude 3.5 Sonnet | ~$150 | ~90%+ (est.) | <0.1:1 | ~$0 |
| Claude 3 Haiku | ~$30 | ~70% (est.) | ~0.5:1 | ~$10 |

The "cheap" model cost $15 but created $50+ in cleanup. The "expensive" model would have cost $150 but produced clean data from the start. **Always choose quality over cost for entity extraction.**


## Issue 49: Master Entity Taxonomy Required Before Extraction

**Problem**: Entity extraction was run without a defined taxonomy of what entity types matter for the investigation. Nova Lite extracted 200+ entity types including `artifact`, `object`, `device`, `form`, `page`, `text`, `font`, `measurement`, `medical_condition`, `food`, `animal`, `music_genre` — none of which are investigatively relevant.

**Fix**: Created `docs/master-entity-taxonomy.md` — a 40-type taxonomy across 10 tiers covering all major federal investigation types (FBI, SEC, DEA, IRS-CI, ATF, ICE, etc.). The extraction prompt should explicitly list the entity types to extract, not let the model decide.

**MANDATORY RULE**: Before running entity extraction on a new case:
1. Review `docs/master-entity-taxonomy.md`
2. Select the relevant tiers for the case type
3. Include the selected types in the extraction prompt: "Extract ONLY the following entity types: person, organization, location, financial_amount, account_number, phone_number, email, address, date, event, flight, legal_case, statute, vehicle, substance, weapon, property, role"
4. This constrains the model to extract only what matters, dramatically reducing noise

**File**: `docs/master-entity-taxonomy.md`


## Issue 50: EC2 Userdata Must Always Install boto3 Before Running Python Scripts

**Problem**: Post-extraction chain EC2 (`i-09f7a6a43e4d95e7d`) crashed immediately with `ModuleNotFoundError: No module named 'boto3'`. The userdata had `pip3 install boto3 --quiet 2>/dev/null || true` which silently failed because pip3 wasn't in PATH on the AMI.

**Root cause**: Amazon Linux 2023 AMI (`ami-0c1fe732b5494dc14`) has Python 3.9 but boto3 is NOT pre-installed. The `pip3 install boto3 --quiet 2>/dev/null || true` suppressed the error. This was already documented in Issue 47 but the lesson wasn't applied.

**Fix**: Use a robust install chain that tries multiple approaches:
```bash
pip3 install boto3 --quiet 2>/dev/null || pip3 install boto3 || yum install -y python3-pip && pip3 install boto3
```

**MANDATORY EC2 USERDATA TEMPLATE** — Use this for ALL future EC2 scripts:
```bash
#!/bin/bash
set -e
BUCKET="research-analyst-data-lake-974220725866"
REGION="us-east-1"
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

echo "=== EC2 Script Starting ==="
echo "Instance: $INSTANCE_ID"
echo "Time: $(date)"

# MANDATORY: Install boto3 (not pre-installed on Amazon Linux 2023)
pip3 install boto3 || yum install -y python3-pip && pip3 install boto3

# Download script from S3
aws s3 cp s3://$BUCKET/deploy/MY_SCRIPT.py /tmp/MY_SCRIPT.py

# Run script
cd /tmp
python3 MY_SCRIPT.py 2>&1 | tee /tmp/script_log.txt

# Upload log
aws s3 cp /tmp/script_log.txt s3://$BUCKET/logs/MY_LOG_PREFIX/log_$(date +%Y%m%d_%H%M%S).txt

# Self-terminate
echo "=== Complete — Self-Terminating ==="
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
```

**Prevention**: NEVER use `|| true` or `2>/dev/null` on pip install in userdata. If the install fails, the script MUST fail loudly so you see it in console output. Always verify EC2 console output within 2 minutes per the Launch & Verify Protocol.


## Issue 51: Pre-Flight IAM Verification for EC2 Scripts

**Problem**: Chain EC2 crashed with `AccessDeniedException: lambda:InvokeFunction` because `DOJ-Processing-Role` didn't have Lambda invoke permission. This wasted 30 minutes of batch job polling time and required a relaunch.

**Root cause**: The EC2 IAM role was never verified against the script's AWS API calls before launch. The role had S3 and EC2 permissions (from previous scripts) but not Lambda invoke (needed for the new chain script).

**MANDATORY PRE-FLIGHT CHECK** — Before launching ANY EC2 script:

1. **List every AWS API call the script makes** (grep for `boto3.client` and method calls)
2. **Check the IAM role has permissions for each one**:
   ```bash
   aws iam list-role-policies --role-name <ROLE>
   aws iam get-role-policy --role-name <ROLE> --policy-name <POLICY>
   ```
3. **If missing, add the policy BEFORE launching EC2**
4. **Test with a dry-run invoke from local** if possible

**Common EC2 role permissions needed:**
| Script Type | Permissions Needed |
|------------|-------------------|
| S3 read/write | s3:GetObject, s3:PutObject, s3:ListBucket |
| Lambda invoke | lambda:InvokeFunction |
| Bedrock batch | bedrock:GetModelInvocationJob |
| EC2 self-terminate | ec2:TerminateInstances |
| EC2 launch (for chaining) | ec2:RunInstances, ec2:CreateTags, iam:PassRole |
| Neptune (direct) | neptune-db:* (via VPC, no IAM needed for HTTP API) |

**Prevention**: Add IAM verification to the Launch & Verify Protocol. Never assume a role has the right permissions because it worked for a different script.


## Issue 52: Model Output Format Verification During Bake-Off

**Problem**: Nova Pro batch output contained nested lists `[[{...}]]` instead of flat arrays `[{...}]` for some records. The load script crashed with `AttributeError: 'list' object has no attribute 'get'` because it assumed all entities were dicts.

**Root cause**: The bake-off tested entity extraction quality (precision, noise ratio) but never verified the JSON output structure. Different models return different formats — Nova wraps content in `output.message.content[0].text`, Anthropic uses `content[0].text`. And within the entity JSON, some models occasionally nest arrays.

**MANDATORY BAKE-OFF ADDITIONS:**
1. **Parse the raw response structure** for each model — verify the path to extract text
2. **Verify entity JSON format** — check that each element in the array is a dict with `name`, `type`, `confidence`
3. **Test with edge cases** — empty documents, very long documents, OCR garbage documents
4. **Build the parser DURING the bake-off** — don't write the parser after choosing the model
5. **Handle nested lists, strings, nulls** in the entity array — defensive parsing

**Prevention**: The `model_bakeoff.py` script should output a "Parser Compatibility" section showing the exact response path and any format anomalies found. The load script should handle `list`, `dict`, `str`, and `None` elements in the entity array.


## Issue 53: Neptune Re-Sync Uses Individual Upserts Instead of Bulk Load

**Problem**: The `ec2_neptune_resync.py` script upserts entities one at a time via Gremlin HTTP API. For 64,541 entities at ~0.15s per upsert = ~2.7 hours. This violates Issue 48's rule: "NEVER design a load that calls Lambda once per row."

**Root cause**: The script was written to use fold/coalesce upserts for correctness (no duplicates), but didn't consider the bulk alternative. Neptune supports CSV bulk loading via the Neptune Loader API, which processes millions of vertices in minutes.

**Correct approach for next time**: 
1. Generate Neptune CSV files (vertices.csv + edges.csv) from Aurora
2. Upload to S3
3. Call Neptune Loader API: `POST /loader` with S3 path
4. Neptune loads in parallel internally — 64K vertices in ~2-5 minutes

**For the current run**: Let it finish (working, just slow). Don't terminate a working process.

**Prevention**: Before any Neptune data load > 1,000 entities, use the Neptune Bulk Loader API with CSV format. Individual Gremlin upserts are only appropriate for < 1,000 entities or real-time single-entity operations.

## Issue 54: Failed to Verify EC2 Within 2 Minutes of Launch

**Problem**: Neptune re-sync EC2 launched at 12:44 UTC. First progress check was 42 minutes later. Console output showed startup but no progress lines. Could not confirm the script was actually processing entities.

**Root cause**: Didn't follow the Launch & Verify Protocol. Got distracted by other tasks (cleanup, quality checks) instead of verifying the launch immediately.

**Prevention**: The 2-minute verification is non-negotiable. Set a mental timer. If you can't see progress in the console output, use an alternative metric (Neptune node count, S3 log file, Lambda CloudWatch logs).


## Issue 55: Neptune Bulk Loader Requires S3 VPC Endpoint

**Problem**: Neptune Bulk Loader API returned `Unable to connect to s3 endpoint` despite having `NeptuneLoadFromS3` IAM role attached to the cluster.
**Root cause**: Neptune is in a VPC. The bulk loader needs to reach S3 from within the VPC. There's no S3 VPC Gateway endpoint configured for Neptune's VPC, or the route table doesn't include it.
**Fix needed**: Create an S3 Gateway VPC endpoint in Neptune's VPC and add it to the route table used by Neptune's subnets.
**Workaround used**: Gremlin fallback with simple `addV` using deterministic IDs (O(1) per vertex). Loaded 47,859 vertices in 32 minutes.
**Prevention**: Before using Neptune Bulk Loader, verify: (1) IAM role attached to cluster, (2) S3 VPC endpoint exists, (3) Route table includes S3 endpoint. Test with a 10-row CSV before bulk loading.

## Issue 56: fold/coalesce Upsert is O(n) on Large Neptune Graphs

**Problem**: Gremlin fold/coalesce upsert pattern scanned the entire graph (943K nodes) for each of 50K upserts. Result: 5 entities/minute instead of 1,500/minute.
**Root cause**: `g.V().has(label, 'name', X).fold().coalesce(unfold(), addV())` does a full scan when the graph is large and the property isn't indexed efficiently.
**Fix**: Use simple `addV` with deterministic vertex IDs: `g.addV(label).property(id, 'deterministic-id')`. Neptune rejects duplicates by ID automatically. This is O(1) per vertex regardless of graph size.
**Prevention**: Never use fold/coalesce on graphs with >10K vertices. Use deterministic IDs + simple addV, or use the Neptune Bulk Loader API.


## Issue 57: Frontend-Backend Contract Mismatch — Pattern Library "Try It" Buttons

**Problem**: Pattern Library "Anomaly Destination" card had `type: 'outlier'` in the frontend but the backend expected `anomaly_destination`. Every "Try It" click returned an error. The `anomaly_destination` detector didn't exist in the backend at all.

**Root cause**: Frontend and backend were built in the same task but the type strings weren't cross-checked. The backend detector map had 6 types, the frontend had 7 cards, and the 7th card used a different type name.

**MANDATORY PRE-DEPLOY CHECK — Frontend-Backend Contract Verification:**

Before deploying ANY feature that has both frontend and backend components:

1. **List every API call the frontend makes** — grep for `api('POST'`, `api('GET'`, `fetch(` in the HTML
2. **For each API call, verify the backend route exists** — grep for the path in case_files.py dispatcher
3. **For each parameter the frontend sends, verify the backend accepts it** — check the handler's expected fields
4. **Test every button/action in the UI** — not just the happy path, every clickable element
5. **Cross-check string constants** — if the frontend sends a type string, verify the exact same string exists in the backend's dispatch map

**Specific to Pattern Library**: Every card's `type` field must match a key in `anomaly_detect_handler`'s `detector_map`. When adding a new card, add the detector first, test the endpoint, then add the card.


## Issue 27: Neptune Graph Label Case ID ≠ Aurora Case ID (CRITICAL RECURRING)

**Problem**: All Neptune-dependent features (Anomaly Radar, Prosecution Readiness, graph highlighting, entity neighborhood) return empty/fail because the Lambda queries Neptune with `Entity_{aurora_case_id}` but the graph was loaded with a DIFFERENT case ID.
**Root cause**: The main case in Aurora has `case_id = 7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e` but the Neptune graph was loaded with label `Entity_7f05e8d5-4492-4f19-8894-25367606db96`. These are different UUIDs that share the same prefix. The `parent_case_id` column in `case_files` is supposed to bridge this gap but was never set.
**Impact**: Every service that queries Neptune finds 0 results. This breaks: AI Briefing leads, Anomaly Radar, Prosecution Readiness, graph highlighting, entity neighborhood, network analysis.
**Fix**: Set `parent_case_id` in Aurora's `case_files` table:
```sql
UPDATE case_files SET parent_case_id = '7f05e8d5-4492-4f19-8894-25367606db96' WHERE case_id = '7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e';
```
The `investigator_analysis.py` `get_analysis` handler already resolves `graph_case_id` from `parent_case_id`. Other services need the same resolution.
**Prevention**: 
1. ALWAYS verify Neptune graph label matches what the code queries BEFORE declaring a sync/reload complete
2. After ANY Neptune reload, run: `g.V().hasLabel('Entity_{case_id}').count()` with the AURORA case_id to confirm > 0
3. If 0, check `g.V().label().dedup()` to find the actual label and set `parent_case_id` accordingly
**Key mapping**:
- Aurora main case: `7f05e8d5-6a7b-4b1c-9c0e-3f4a5b6c7d8e`
- Neptune main graph: `7f05e8d5-4492-4f19-8894-25367606db96` (989K vertices)
- Aurora demo case: `ed0b6c27-4a8e-4f3b-9d1c-5e6f7a8b9c0d`
- Neptune demo graph: `ed0b6c27-3b6b-4255-b9d0-efe8f4383a99` (22K vertices)


## Issue 53: Case Creation Fails — CaseFileCompatService Routes to MatterService with Empty org_id

**Problem**: `POST /case-files` returns 500 with `"invalid input syntax for type uuid: \"\""`. Creating ANY new case file fails. This blocked all new case creation for the FMCSA Trucking demo.

**Root Cause Chain**:
1. `_build_case_file_service()` in `case_files.py` constructs a `CaseFileCompatService` (NOT `CaseFileService`)
2. `CaseFileCompatService.__init__` receives `default_org_id = os.environ.get("DEFAULT_ORG_ID", "")` 
3. Since `DEFAULT_ORG_ID` is NOT set on the Lambda, it defaults to `""` (empty string)
4. `CaseFileCompatService.create_case_file()` always delegated to `MatterService.create_matter(org_id="")`
5. `MatterService.create_matter()` inserts into `matters` table where `org_id` is a `UUID` column
6. PostgreSQL rejects `""` as invalid UUID → 500 error

**Why This Was Hard to Debug**:
- The error message from PostgreSQL shows a truncated VALUES clause that makes it look like `parent_case_id` is the empty string (position confusion in the error display)
- The actual service being called (`CaseFileCompatService`) is NOT `CaseFileService` — the file `case_file_service.py` is DEAD CODE for the create path
- The `list_case_files` method in `CaseFileCompatService` already had the fallback logic (`if self._default_org_id:` → use matters, else → query case_files directly), but `create_case_file` DID NOT have this fallback
- Multiple deploys were wasted fixing `case_file_service.py` which isn't in the code path

**Fix**: Added fallback logic to `CaseFileCompatService.create_case_file()`:
```python
if self._default_org_id:
    # Has org_id — use MatterService (multi-tenant path)
    matter = self._matter_service.create_matter(org_id=self._default_org_id, ...)
    return _matter_to_case_file(matter)

# No org_id — insert directly into legacy case_files table
with self._matter_service._db.cursor() as cur:
    cur.execute("INSERT INTO case_files (...) VALUES (%s, ...)", params)
```

**Files Modified**:
- `src/services/case_file_compat_service.py` — added direct INSERT fallback (the actual fix)
- `src/lambdas/api/case_files.py` — added `parent_case_id or None` coercion (belt-and-suspenders)
- `src/services/case_file_service.py` — added empty-string-to-None guard (defensive, not in active path)

**Architecture Note — The Case/Matter Hierarchy**:
```
_build_case_file_service() → CaseFileCompatService (shim layer)
    ├── If DEFAULT_ORG_ID is set → delegates to MatterService (inserts into `matters` table)
    └── If DEFAULT_ORG_ID is NOT set → inserts directly into `case_files` table (legacy path)

Active code path for POST /case-files:
  case_files.py:dispatch_handler → create_case_file_handler → _build_case_file_service()
    → CaseFileCompatService.create_case_file()  ← THE FIX IS HERE
    
DEAD CODE (not called by the handler):
  src/services/case_file_service.py:CaseFileService.create_case_file()  ← DO NOT FIX HERE
```

**Prevention**:
1. **ALWAYS check `_build_case_file_service()`** before fixing case creation bugs — it returns `CaseFileCompatService`, not `CaseFileService`
2. **ALWAYS ensure fallback paths exist** for all CRUD methods when `DEFAULT_ORG_ID` might be unset
3. **Test case creation after EVERY deploy** — add to the comprehensive test suite: `POST /case-files` with a test payload, verify 201
4. **Never assume the obvious file is the right one** — `case_file_service.py` is misleadingly named but is dead code for the API handler path
5. **Read the dispatcher factory function FIRST** when debugging any endpoint — it tells you which service class is actually instantiated

**How to Create a Case (verified working methods)**:
1. **API (Lambda invoke)**: 
```powershell
$payload = '{"httpMethod":"POST","path":"/case-files","body":"{\"topic_name\":\"...\",\"description\":\"...\"}","headers":{},"pathParameters":null,"queryStringParameters":null}'
aws lambda invoke --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --region us-east-1 --payload fileb://payload.json --cli-binary-format raw-in-base64-out out.json
```
2. **API (HTTP via API Gateway)**:
```powershell
$body = '{"topic_name":"...", "description":"..."}' 
Invoke-WebRequest -Uri "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files" -Method POST -Body $body -ContentType "application/json"
```
3. **Frontend**: Use the data-loader.html or investigator.html "New Case" button
4. **Direct SQL** (admin endpoint):
```sql
INSERT INTO case_files (case_id, topic_name, description, status, s3_prefix, neptune_subgraph_label, created_at, last_activity, search_tier)
VALUES (gen_random_uuid(), 'Name', 'Description', 'created', 'cases/<uuid>/', 'Entity_<uuid>', NOW(), NOW(), 'standard');
```

**Time Wasted**: ~90 minutes debugging the wrong file. Root cause: not reading `_build_case_file_service()` first.

**Lesson for Future AI Sessions**: When debugging ANY API endpoint failure:
1. Read the HANDLER function first (find it in dispatch_handler routing)
2. Read the SERVICE FACTORY function it calls (e.g., `_build_case_file_service()`)
3. Identify the ACTUAL class being instantiated (not the obvious-named one)
4. THEN trace the code path through that class


## Issue 58: Pipeline Reports SUCCESS but Documents/Embeddings/Edges Silently Fail (UUID Type Mismatch)

**Problem**: The data ingestion pipeline (Step Functions) reported SUCCEEDED for all executions, but only entity extraction actually worked. The `documents` table remained empty, embeddings were never stored, and Neptune edges were never created. This affected all cases loaded via `fast_load.py` or any batch loader that uses filename-derived document_ids (e.g., `carrier_0000`).

**Root Cause**: The `documents.document_id` column is type UUID. The pipeline passes string document IDs like `carrier_0000` (filename without extension). When the embed handler (`embed_handler.py`) called `aurora_pgvector_backend.index_documents()`, PostgreSQL rejected the INSERT with `InvalidTextRepresentation: invalid input syntax for type uuid: "carrier_0000"`. 

The crash in the embed handler (GenerateEmbedding step) catches to `LogDocumentFailure`, which means:
1. StoreExtractionArtifact never runs → no extraction JSONs in S3
2. The Map iteration ends as "failed" but the Map itself succeeds (graceful error handling)
3. The graph_load handler receives `document_results` with all items marked "failed" → 0 entities to load
4. Neptune edges: 0, Documents table: 0, Embeddings: 0

Entity extraction appeared to work because `extract_handler.py` has its own Aurora INSERT into the `entities` table BEFORE the embed step. The `entities.document_id` column is nullable UUID but was being set to NULL or silently ignored on conflict.

**Fix**: Added `_ensure_uuid()` helper to `src/services/aurora_pgvector_backend.py` that:
1. Checks if document_id is already a valid UUID → pass through
2. If not, generates a deterministic UUID v5 from the string (using a fixed namespace UUID)
3. Same string always → same UUID (idempotent upserts work correctly)

Also applied the same fix in `src/lambdas/ingestion/extract_handler.py` for the entities table INSERT.

**Files Changed**:
- `src/services/aurora_pgvector_backend.py` — added `_ensure_uuid()`, used in `index_documents()`
- `src/lambdas/ingestion/extract_handler.py` — added UUID conversion for `document_id` before INSERT

**Verification**: After fix deployment:
- All 56 FMCSA docs: SUCCEEDED across 3 SFN executions
- Documents table: populated (search returns 5+ results)
- Entities: 222 (up from 94)
- Neptune: 158 nodes, 138 edges loaded via bulk CSV
- Pattern discovery: 4 patterns found
- Demo case (ed0b6c27): unaffected

**Prevention**:
1. **Never assume column types match** — check the schema before INSERT
2. **Pipeline "SUCCESS" doesn't mean document processing succeeded** — the Map state's error handling is graceful (LogDocumentFailure → end). Always verify downstream tables.
3. **Use `verify_pipeline_completion.py`** after every pipeline run to confirm docs > 0, entities > 0, search works, patterns discoverable
4. **For any new batch loader**: generate UUIDs for document_ids, or ensure all INSERT paths handle non-UUID strings via `_ensure_uuid()`

**Verification Script**: `python scripts/verify_pipeline_completion.py --case-id <CASE_ID>`


## Issue 58: Neptune Bulk CSV Loader — Correct Procedure for Loading Entities at Scale

**Problem**: Individual Gremlin `addV()`/`addE()` upserts to sync entities from Aurora to Neptune
take HOURS for large casesets (thousands of entities). This violates the BULK OPERATIONS rule
(see kiro-builder-playbook.md 2.2.1) — any operation on 100+ items must use bulk APIs, not loops.

**Root cause**: Gremlin HTTP calls are synchronous, one entity at a time, with network round-trip
latency per call. At ~1000 entities/rate-limited-loop, this is unusably slow and also risks Neptune
throttling.

**Fix — Use the Neptune Bulk Loader API.** This is the CORRECT way to sync entities to Neptune at
scale, going from hours to minutes. Full working script: `scripts/neptune_bulk_sync.py`.

### The 5-Step Procedure

1. **Generate CSV from Aurora** — query filtered entities (master taxonomy types + occurrence
   count >= 2 to filter noise), write a Neptune-format CSV to a buffer, upload to S3.
2. **Clear old nodes for the case** (optional, use `--skip-clear` to skip) — drop existing
   `Entity_{case_id}` vertices before reloading, in batches of 500 via Gremlin
   (`g.V().hasLabel(label).limit(500).sideEffect(bothE().drop()).drop()`), looping until count is 0.
3. **Trigger the Neptune Bulk Loader API** — POST to `https://{NEPTUNE_ENDPOINT}:{PORT}/loader`
   with the S3 CSV location, format, and IAM role ARN. Returns a `loadId`.
4. **Poll the loader status** — GET `https://{NEPTUNE_ENDPOINT}:{PORT}/loader/{loadId}` every 5s
   until `overallStatus.status` is `LOAD_COMPLETED` (or `LOAD_FAILED`/`LOAD_CANCELLED`).
5. **Verify node count** — `g.V().hasLabel(label).count()` to confirm the load matches expectations.

### Neptune Bulk Loader CSV Format (exact column headers required)

**Vertices CSV** (`~id`, `~label` are Neptune-reserved, types after `:` are required):
```
~id,~label,canonical_name:String,entity_type:String,occurrence_count:Int,confidence:Double,case_file_id:String
```
- `~id` must be a deterministic, stable string ID. Convention used:
  `f"{label}_{entity_type}_{name}".replace(" ", "_").replace(",", "")[:200]`
  — deterministic IDs let re-loading act as an upsert (same ID = same vertex) rather than creating
  duplicates on every sync run.
- `~label` = `Entity_{case_id}` (see label convention in `src/db/neptune.py`)
- Skip any entity with `len(name) < 3` — filters OCR noise before it ever reaches Neptune.

**Edges CSV**:
```
~id,~from,~to,~label,relationship_type:String,confidence:Float,source_document_ref:String
```
- `~from`/`~to` reference vertex `~id` values from the vertices CSV — the vertex load should
  complete (or at least exist) before the edge load runs.
- `~label` for entity relationships is always `RELATED_TO` (see `EDGE_RELATED_TO` constant).

### Bulk Loader API Call Details

**Trigger** — `POST https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/loader`:
```json
{
  "source": "s3://research-analyst-data-lake-974220725866/neptune-bulk-load/{case_id}/vertices.csv",
  "format": "csv",
  "iamRoleArn": "arn:aws:iam::974220725866:role/NeptuneLoadFromS3",
  "region": "us-east-1",
  "failOnError": "FALSE",
  "parallelism": "HIGH",
  "updateSingleCardinalityProperties": "TRUE"
}
```
- `failOnError: "FALSE"` — required for large loads with any imperfect rows; a single bad row
  should not abort the whole batch.
- `updateSingleCardinalityProperties: "TRUE"` — required for the load to behave as an UPSERT when
  a vertex with the same `~id` already exists (otherwise properties won't update on re-sync).
- `iamRoleArn` MUST be a role that: (a) Neptune can assume, (b) has `s3:GetObject`/`s3:ListBucket`
  on the data bucket. This is the #1 failure point — see gotcha below.

**Poll** — `GET https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/loader/{loadId}` — check
`payload.overallStatus.status`. On `LOAD_COMPLETED`, also check `totalRecords` and `totalErrors`
in the response to confirm the load actually processed the expected row count.

### Gotchas

1. **Missing/wrong IAM role for the loader is the most common failure.** If the bulk loader
   returns `AccessDenied` or mentions "role" in the error body, Neptune's IAM role for S3 access
   isn't configured correctly. `neptune_bulk_sync.py` has a built-in fallback: on bulk loader
   failure, it automatically falls back to batched Gremlin `addV()` upserts (slow but functional)
   rather than failing outright. Keep this fallback pattern — don't remove it for "cleanliness."
2. **The bulk loader does NOT support property updates on existing vertices' individual
   properties reliably in all cases** — for some property-update-only operations (no new
   vertices/edges), Gremlin is still used directly (see `graph_load_handler.py` comment: "For
   properties, we still use Gremlin since Neptune bulk loader doesn't support property updates").
   Use bulk CSV loader for bulk vertex/edge CREATION, Gremlin for individual property patches.
3. **Deterministic IDs are what make re-running the sync safe.** If you generate random/UUID
   vertex IDs instead of a deterministic scheme, every re-sync duplicates all vertices instead of
   updating them. Always derive `~id` from stable fields (label + type + name), not a random UUID.
4. **Clear-before-reload can be slow at scale** (batches of 500, polling count until 0) — this is
   O(n/500) round trips. For very large caseloads, consider whether a full clear is necessary vs.
   relying on the deterministic-ID upsert behavior to avoid needing a clear step at all.
5. **CSV must be uploaded to S3 first** — the bulk loader reads from an S3 URI, it cannot be
   handed the CSV content directly in the API call. Always: generate CSV in memory (`io.StringIO`
   + `csv.writer`) → `s3.put_object()` → then trigger the loader pointing at that S3 key.

### Files

- `scripts/neptune_bulk_sync.py` — standalone CLI script, full 5-step procedure, Aurora → Neptune
- `src/lambdas/ingestion/graph_load_handler.py` — same pattern used inline in the ingestion
  pipeline (`_generate_and_upload_csv`, `_trigger_bulk_load`, `_poll_bulk_load` functions)
- `src/db/neptune.py` — CSV column format constants (`BULK_LOAD_NODES_COLUMNS`,
  `BULK_LOAD_EDGES_COLUMNS`), label conventions (`entity_label()`, `EDGE_RELATED_TO`)
- `scripts/load_rekognition_to_graph.py` — same bulk CSV pattern applied to visual/Rekognition
  entities (`Visual_Entity` nodes, `DETECTED_IN`/`CO_OCCURS_WITH` edges)

### Usage

```bash
python scripts/neptune_bulk_sync.py --case-id <CASE_ID>
python scripts/neptune_bulk_sync.py --case-id <CASE_ID> --skip-clear   # skip the clear-old-nodes step
```


## Issue 51: AOSS HEAD Returns 403 Instead of 404 for Non-Existent Indexes

**Problem**: OpenSearch Serverless (AOSS) returns HTTP 403 (not 404) when checking if an index exists via `HEAD /{index_name}` and the IAM principal's data access policy hasn't fully propagated. This causes the typology pipeline seed script to crash immediately with "HTTP Error 403" even after the data access policy is updated.

**Root cause**: AOSS data access policies take 30-120 seconds to propagate. During this window, HEAD/GET requests return 403 indistinguishable from a real auth failure. Additionally, HEAD requests on AOSS don't return a body — you can't distinguish "index doesn't exist" from "not authorized."

**Fix**: Use `GET /{index_name}/_settings` instead of `HEAD /{index_name}` to check index existence. Treat both 403 AND 404 as "index doesn't exist" responses. The create request will fail clearly if there's a real auth problem.

```python
def _index_exists(endpoint, region):
    try:
        _aoss_request(endpoint, region, "GET", f"/{INDEX_NAME}/_settings")
        return True
    except urllib.error.HTTPError as e:
        if e.code in (404, 403):
            return False
        raise
```

**Prevention**: 
- Never use HEAD requests against AOSS — always use GET with a specific sub-resource
- After updating AOSS data access policies, wait at least 60 seconds before testing
- When creating new Lambda functions that access AOSS, verify the Lambda's *actual* execution role (not assumed) is in the data access policy: `aws lambda get-function-configuration --function-name <name> --query Role`

**File**: `src/db/seeds/typology_patterns_index.py`


## Issue 52: Step Functions Parameters Reference Non-Existent Input Fields

**Problem**: New Step Functions state machine fails immediately with "The JSONPath '$.execution_id' specified for the field 'execution_id.$' could not be found in the input". The initial input `{"case_id": "...", "trigger_source": "manual"}` doesn't contain `execution_id` or `typology_modules`, which are outputs of later steps.

**Root cause**: The ASL Parameters block referenced fields (`$.execution_id`, `$.typology_modules`) that don't exist in the state's input context. These fields are created by ThresholdCheck (stored at `$.threshold_result`) and AcquireLock (stored at `$.lock`). You must reference them via their `ResultPath`: `$.threshold_result.typology_modules` and `$.lock.execution_id`.

**Fix**: Updated all Parameters blocks to reference the correct ResultPath locations:
- `$.typology_modules` → `$.threshold_result.typology_modules`
- `$.execution_id` → `$.lock.execution_id`
- Map item values use `$$.Map.Item.Value` (context object) not `$.Map.Item.Value`

**Prevention**: 
- When a Step Function state uses `ResultPath: "$.some_field"`, its output lives at `$.some_field.*` — not at `$.*`
- The initial state machine input only contains what the *caller* passes (e.g., `case_id`, `trigger_source`)
- Draw out the data flow before writing ASL: Input → State1 (ResultPath $.a) → State2 can access $.a.field
- Always test with `aws stepfunctions start-execution` using the minimal input the caller will actually provide

**File**: `infra/step_functions/typology_subgraph_pipeline.json`


## Issue 53: Step Functions IAM Role Must Allow lambda:InvokeFunction on New Lambdas

**Problem**: Pipeline state machine fails with "The principal states.amazonaws.com is not authorized to assume the provided role" or "AccessDeniedException" when trying to invoke pipeline Lambdas.

**Root cause**: Reused the existing ingestion pipeline Step Functions role, which only had `lambda:InvokeFunction` permission on the ingestion Lambdas (`ResearchAnalystStack-*`). The new `TypologyPipeline-*` Lambdas weren't covered.

**Fix**: Added inline policy to the role:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "lambda:InvokeFunction",
    "Resource": "arn:aws:lambda:us-east-1:974220725866:function:TypologyPipeline-*"
  }]
}
```

**Prevention**: When reusing an existing Step Functions role for a new state machine, always verify the role's policies cover the new Lambda function ARNs. Check with: `aws iam list-role-policies --role-name <role>` and `aws iam get-role-policy --role-name <role> --policy-name <policy>`

**File**: `scripts/_add_sfn_policy.json`


## Issue 54: Aurora case_files.entity_count = 0 Despite 248K Entities in entities Table

**Problem**: ThresholdCheck Lambda returns `entity_count: 0` for the Epstein Main case even though the `entities` table has 248,314 rows for that case_id. The `case_files.entity_count` column was never populated after entity extraction.

**Root cause**: The entity extraction pipeline (EC2/batch process) inserts into the `entities` table but never updates `case_files.entity_count`. The column defaults to 0 and stays there.

**Fix**: Manually updated via RDS Data API: `UPDATE case_files SET entity_count = 248314 WHERE case_id = '7f05e8d5-...'`. Long-term: add a post-extraction step that runs `UPDATE case_files SET entity_count = (SELECT COUNT(*) FROM entities WHERE case_file_id = case_files.case_id)`.

**Prevention**: Any pipeline that inserts entities should also update `case_files.entity_count` on completion. Add this to the entity extraction completion handler.

**File**: `scripts/_update_counts.py`


## Issue 55: Migrations Must Run via RDS Data API (Not psycopg2 Locally, Not Lambda Admin Endpoint)

**Problem**: Aurora migration failed to run because: (1) psycopg2 locally can't connect (Aurora is in VPC, not publicly accessible), (2) the main Lambda has no `run-sql` admin endpoint, (3) the pipeline Lambdas import ConnectionManager but psycopg2 isn't available locally.

**Root cause**: Aurora Serverless v2 in a VPC is only reachable from within the VPC (Lambdas, EC2) or via the RDS Data API (which is HTTP-based and works from anywhere with IAM credentials).

**Fix**: Use RDS Data API:
```python
import boto3
client = boto3.client("rds-data", region_name="us-east-1")
client.execute_statement(
    resourceArn="arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco",
    secretArn="arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL",
    database="research_analyst",
    sql="CREATE TABLE IF NOT EXISTS ..."
)
```

**Prevention**: ALWAYS use RDS Data API for migrations. Never assume psycopg2 will work locally. The pattern is documented in `scripts/run_migration_rds_data.py`.

**File**: `scripts/run_migration_rds_data.py`


## Issue 56: Step Functions 256KB State Output Limit — Never Pass Data Through States

**Problem**: The typology pipeline's ExtractSubgraphs Map state returned full entity/edge lists from Neptune, causing `States.DataLimitExceeded` error. Even capped at 50 entities × 100 edges per sub-category × 6 sub-categories × 11 typologies = far exceeds the 256KB Step Functions state output limit.

**Root cause**: Designed the pipeline to pass extracted graph data through Step Functions state outputs (ExtractSubgraphs → ScoreTypologies). Step Functions has a hard 256KB limit on state input/output. Any Map state aggregating results from multiple iterations will easily exceed this with real data.

**Correct pattern** (from the existing ingestion pipeline):
- Each Lambda **writes its output to Aurora/S3 directly** (not through state output)
- Step Functions states only pass **references** (case_id, typology_id, execution_id) — never data payloads
- Map states iterate over small arrays of IDs, not data objects
- Each subsequent Lambda **reads from the database** what the previous Lambda wrote

**Fix**: Redesign extract_subgraph to write extracted data directly to Aurora (`typology_precomputed_results` with key_entities populated), then score_typology reads from Aurora instead of receiving the data through Step Functions. The Map state only passes `{case_id, typology_module_id, execution_id}` between states.

**Prevention**: 
- NEVER return more than a few KB from any Step Functions task Lambda
- All inter-state data transfer must go through Aurora/S3 with only IDs in the state
- Before designing any new Step Functions pipeline, review the existing `ingestion_pipeline.json` pattern: small parameters in, status/ID out, data lives in the database

**File**: `infra/step_functions/typology_subgraph_pipeline.json`, `src/lambdas/pipeline/extract_subgraph.py`


## Issue 57: Neptune Relationship Types — Query Actual Data, Don't Assume

**Problem**: The typology query definitions used domain-specific relationship types (`contacted`, `recruited`, `communicated_with`, `traveled_to`) that don't exist in Neptune. The graph only contains generic types: `co-occurrence`, `thematic`, `causal`, `temporal`, `geographic`. All Neptune queries returned 0 results.

**Root cause**: The query configuration was written based on what relationship types SHOULD exist (from a domain modeling perspective) rather than what ACTUALLY exists in Neptune. The entity extraction pipeline uses generic relationship types from Bedrock's output, not domain-specific ones.

**Fix**: Removed the `relationship_type` filter from the Gremlin query template entirely. The `entity_type` filter provides sufficient typology-specific filtering (e.g., person + financial_amount for Financial Control). Relationship types in Neptune are too generic to be useful for typology differentiation.

**Correct query pattern**:
```python
# DON'T filter by relationship_type (they're all generic)
"g.V().hasLabel('{label}').has('entity_type', within('person','financial_amount')).bothE('RELATED_TO').limit(500)..."
```

**Prevention**: Before writing any Neptune query filter, run a sample query to see what values actually exist:
```
g.V().hasLabel('Entity_{case_id}').bothE('RELATED_TO').values('relationship_type').dedup().limit(20)
```

**File**: `src/services/typology_query_definitions.py`


## Issue 58: Typology Pipeline — Full End-to-End Working (Issue 56/57 Resolution)

**Status**: RESOLVED. The pipeline now runs end-to-end successfully:
- 11 typology modules × 6 sub-categories = 66 Neptune queries executed
- 314+ entities and 3000+ edges extracted per typology from the 248K entity graph
- All results written to Aurora `typology_precomputed_results` (66 rows) and `typology_precomputed_summary` (11 rows)
- Pipeline completes in ~57 seconds for the full 248K entity Epstein Main case
- Step Function state machine tracks execution status correctly

**Remaining**: OpenSearch `typology-patterns` k-NN index needs seeding (AOSS 403 for Lambda role). Once seeded, scores will populate with real cosine similarity values instead of 0.0. Current workaround: the architecture works without k-NN — entities are extracted and stored, just unscored.

**Key fixes applied**:
1. Removed relationship_type filter from Neptune queries (Issue 57) — types don't exist in graph
2. Changed to write-to-Aurora pattern (Issue 56) — no data through Step Functions states
3. Reduced edge limit to 500 per sub-category query
4. Extract Lambda writes key_entities to Aurora, Score Lambda reads from Aurora
5. State machine only passes `{case_id, typology_module_id, execution_id}` between states


## Issue 59: AOSS Collection Returns 403 for ALL Write Operations (Ongoing)

**Problem**: OpenSearch Serverless collection `research-analyst-search` (ID: u260nrrtc0q87ji8iu0k) returns 403 Forbidden on ALL write operations (PUT index, POST _bulk) for every identity including the account root and AdministratorAccess users. The data access policy lists the correct principals with CreateIndex/WriteDocument permissions. IAM policies grant aoss:APIAccessAll. Yet writes consistently fail.

**Context**: This may have NEVER worked. Issue 37 documents that enterprise tier embedding writes to AOSS fail with 401/403. All successful case processing uses the `standard` tier (Aurora pgvector). The AOSS collection exists but may be in a broken state from failed deployments (Issues 2/5 from earlier).

**Current Status**: NOT RESOLVED. The typology pipeline works end-to-end without k-NN scoring by using entity count density as a proxy score instead.

**Root cause hypothesis**: The AOSS collection may have been created with incorrect settings, or there's a cached/stale network or encryption policy preventing writes. The collection shows ACTIVE status but may need to be recreated.

**Workaround**: Score typologies based on Neptune graph density (entity_count / edge_count per sub-category) rather than k-NN cosine similarity against prosecution patterns. This still provides meaningful relative scoring — sub-categories with more entities and connections score higher.

**To fully resolve**: Either recreate the AOSS collection from scratch (delete and re-provision via CDK) or investigate whether there's a VPC endpoint issue specific to the AOSS write path. The existing embed step's success may have been from a time when the collection was correctly configured, before a failed CDK deploy corrupted the policies.


## Issue 60: AOSS 403 Root Cause — WRONG Collection Endpoint in Config

**Problem**: ALL OpenSearch Serverless writes returned 403 Forbidden. Spent hours debugging IAM policies, data access policies, and propagation timing. None of it mattered.

**Root cause**: The `OPENSEARCH_ENDPOINT` environment variable pointed to the WRONG collection (`u260nrrtc0q87ji8iu0k`). The CURRENT active collection is `hzrvvva3hodw069v9442`. The old collection was either deleted or from a previous failed deployment, but the endpoint config was never updated.

**How to verify**: `aws opensearchserverless list-collections` shows the actual active collections. Match the collection ID in the endpoint URL against the listed collections.

**Fix**: Updated `OPENSEARCH_ENDPOINT` on all Lambda functions to `https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com`. The correct endpoint was found via:
```bash
aws opensearchserverless batch-get-collection --names research-analyst-search --query "collectionDetails[0].collectionEndpoint"
```

**Prevention**: 
- ALWAYS verify the AOSS endpoint against `aws opensearchserverless list-collections` before debugging auth issues
- Add a startup health check in Lambda that verifies AOSS connectivity (GET /_cat/indices) and logs a clear error if it fails
- When a 403 persists after verifying all policies, CHECK THE ENDPOINT URL FIRST

**Additional fix**: Titan Embed v2 (`amazon.titan-embed-text-v2:0`) returns 1024-dim vectors by default, not 1536 (that's v1). The k-NN index dimension must be 1024 to match.

**Additional fix**: AOSS does NOT support custom `_id` in bulk index operations — remove all `_id` fields from bulk payloads.

**Files**: `scripts/_fix_opensearch_endpoint.py`, `src/db/seeds/typology_patterns_index.py`


## Issue 59 UPDATE: AOSS WORKS — Correct Endpoint is hzrvvva3hodw069v9442

**Status**: RESOLVED. Issue 60 identified the root cause — wrong endpoint in config. The correct collection works perfectly:
- `typology-patterns` index created ✓
- 264 prosecution pattern embeddings seeded (1024-dim Titan Embed v2) ✓
- PUT/POST/GET/DELETE all work ✓
- Endpoint: `https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com`

**Remaining for next session**: The Score Lambda's Aurora INSERT/UPSERT columns don't match the actual schema. Need to verify column names match between `_store_results()` in `score_typology.py` and the actual `typology_precomputed_results` table schema. The fix made earlier in this session may not have been deployed correctly (multiple deploys).


## Issue 34: Typology Pattern Lens Drill-Down Broke — Lambda Deploy Packaging Error + API Gateway Timeout

**Problem**: The Pattern Recognition Lens drill-down (the best demo feature — incident cards with network graphs, AI analyst briefs, and needle analysis) stopped working. Clicking a method card showed "Failed to load findings: Failed to fetch." This was broken for multiple days.

**Root Cause (TWO ISSUES compounded)**:

### Issue 34a: Lambda Deploy Zip Included `src/` Prefix
When deploying via `Compress-Archive -Path src\* -DestinationPath lambda-update.zip`, the resulting zip contained files at path `src/lambdas/api/case_files.py`. But the Lambda handler is `lambdas.api.case_files.dispatch_handler` — no `src/` prefix. Python couldn't find the module → `Runtime.ImportModuleError: No module named 'lambdas'`.

**CORRECT deploy command** (strip the `src/` prefix):
```python
import zipfile, os
with zipfile.ZipFile('lambda-update.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('src'):
        dirs[:] = [d for d in dirs if d not in {'data', 'frontend', '__pycache__', '.pytest_cache'}]
        for f in files:
            if f.endswith('.pyc'): continue
            filepath = os.path.join(root, f)
            arcname = os.path.relpath(filepath, 'src')  # STRIP src/ PREFIX
            zf.write(filepath, arcname)
```

**WRONG (what broke it)**:
```powershell
Compress-Archive -Path src\* -DestinationPath lambda-update.zip
# This creates src/lambdas/... inside the zip — WRONG
```

### Issue 34b: API Gateway 29-Second Timeout on AI Brief Generation
The typology findings endpoint generates Bedrock AI briefs for each detected situation. With 6+ situations × ~8 seconds each = ~48 seconds → exceeds API Gateway's 29-second hard limit. Browser gets "Failed to fetch" (timeout, not CORS).

**Fix**: Reduced AI brief generation from 6 situations to 3 (top 3 highest-confidence):
```python
# In src/services/sex_trafficking_typology.py, TypologyFindingsEngine.get_findings()
for situation in situations[:3]:  # Was [:6] — causes API Gateway timeout
    situation.ai_brief = self._generate_brief(category, situation)
```

### Issue 34c: Misleading Debugging (Entity Count Red Herring)
During investigation, entity counts showed 0 for all cases when queried through the Lambda API, but 248K existed when queried via RDS Data API. This led to 2+ hours of wrong-path debugging (checking schemas, clusters, proxy targets). The ACTUAL problem was 34a (broken Lambda module imports) — the Lambda was crashing before reaching any DB code.

**Lessons**:
1. ALWAYS verify `FunctionError` field in Lambda invoke response FIRST — if it says `Unhandled`, the Lambda is crashing, not returning empty data
2. ALWAYS check CloudWatch logs with `LogType='Tail'` when debugging Lambda issues
3. The `Compress-Archive` PowerShell cmdlet does NOT strip directory prefixes — use Python zipfile with `os.path.relpath(filepath, 'src')` instead
4. API Gateway REST API has a HARD 29-second integration timeout — any Bedrock operation that might exceed this MUST be capped

**Prevention**:
- Deploy script MUST use the Python zipfile method (added to `kiro-builder-playbook.md` Phase 3.5)
- Typology findings AI briefs capped at 3 situations maximum
- After ANY Lambda deploy, immediately test with `python scripts/_test_deploy.py` which checks `FunctionError` field
- NEVER deploy a Lambda zip > 250MB unzipped (data/ and frontend/ directories MUST be excluded)

**Files**: `src/lambdas/api/case_files.py`, `src/services/sex_trafficking_typology.py`
**Severity**: CRITICAL — broke the primary demo feature for multiple days
**Time to diagnose**: ~3 hours (much of it on the wrong track due to 34c)
**Time to fix**: 15 minutes once root cause identified
