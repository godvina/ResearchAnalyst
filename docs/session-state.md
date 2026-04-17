# Session State — April 1, 2026 (End of Day)

## Resume Instructions
Start with: "Continue from session state. CDK deployed successfully, batch loader working via UI. First 109-file batch ran through extraction phase. Next: monitor batch completion, run larger batches, improve batch loader UX."

## COMPLETED THIS SESSION

### CDK Stack Consolidation & Deployment
- Consolidated all API Lambdas into single `case_files` mega-dispatcher (567 → 100 resources)
- `LambdaRestApi` with `proxy=True` — single `{proxy+}` catch-all route
- Fixed Step Functions ASL substitutions (ResolveConfigLambdaArn, ClassificationLambdaArn, RekognitionLambdaArn)
- Cleaned up orphaned AOSS resources (VPC endpoint, collection, 3 policies)
- Added `ACCESS_CONTROL_ENABLED=false` to Lambda env vars
- Added Lambda VPC endpoint (`com.amazonaws.us-east-1.lambda`) for async self-invoke
- Added SG ingress rule: Lambda SG → default SG on port 443 for VPC endpoint access
- Stack deployed successfully: `UPDATE_COMPLETE`

### Batch Loader Fixes
- Copied `scripts/batch_loader/` to `src/batch_loader/` (Lambda package doesn't include scripts/)
- Fixed all imports: `from scripts.batch_loader.*` → `from batch_loader.*` (handler + 8 modules)
- Copied `config/aws_pricing.json` to `src/config/aws_pricing.json`
- Fixed `CostEstimator._load_pricing()` path resolution for Lambda environment
- Lambda code redeployed via `aws lambda update-function-code`
- First batch of 109 files started and progressed through Discovery → Extraction

### Infrastructure State
- Stack: `ResearchAnalystStack` — `UPDATE_COMPLETE`
- API URL: `https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1`
- Lambda: `ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq`
- 100 CloudFormation resources (well under 500 limit)
- 12 Lambda functions (1 API + 10 ingestion + 1 S3 auto-delete)

### VPC Endpoints (all in vpc-0b42c848c0b11ed25)
- S3 (Gateway): vpce-033801845df7fcafd
- Bedrock Runtime: vpce-01b9c9a600544c81b
- Secrets Manager: vpce-01a2855b6f6e413f7
- Step Functions: vpce-05a694ebaa33ae87a
- AOSS: vpce-045bde08a9ce9d9f2
- Lambda: vpce-086f81c7cfcb4953c (NEW — required for batch loader async)

### Key Cases
- Epstein Main (7f05e8d5): ~3,362 docs — BASELINE
- Epstein Combined (ed0b6c27): 5,142 docs + batch in progress
- Ancient Aliens (d72b81fc): 240 docs

## DEPLOYMENT CHECKLIST (for fresh deploy)

1. `cd infra/cdk ; cdk deploy --require-approval never`
2. If AOSS errors: run AOSS cleanup procedure (see deployment-guide.md)
3. Set `ACCESS_CONTROL_ENABLED=false` on CaseFiles Lambda env vars
4. Verify Lambda VPC endpoint exists with correct SG rules
5. Copy batch_loader modules: `scripts/batch_loader/` → `src/batch_loader/`
6. Copy pricing config: `config/aws_pricing.json` → `src/config/aws_pricing.json`
7. Install PyPDF2 into src: `pip install PyPDF2 -t src/`
8. Deploy Lambda code: zip `src/` and update function code
9. Run migration 007: `python scripts/migrate_via_lambda.py src/db/migrations/007_document_access_control.sql`

## POST-INGESTION RUNBOOK (run after each batch load completes)

After docs are ingested and images extracted to `cases/{case_id}/extracted-images/`:

1. **Classify images** (Pillow heuristics — photo vs doc vs redacted vs blank):
   ```
   python scripts/classify_images.py --case-id {CASE_ID} --target-case ed0b6c27-3b6b-4255-b9d0-efe8f4383a99
   ```
   First time: test with `--limit 100 --dry-run` to verify threshold sanity.
   Has resume support — re-run same command if interrupted.

2. **Detect faces on photos only** (Rekognition detect_faces, ~100ms/image):
   ```
   python scripts/detect_faces.py --case-id {CASE_ID}
   ```
   Only runs on images classified as "photograph". Produces face_crop_metadata.json.

3. **Crop detected faces** (Pillow crop + resize to 200x200):
   ```
   python scripts/crop_faces.py --case-id {CASE_ID} --target-case ed0b6c27-3b6b-4255-b9d0-efe8f4383a99
   ```

4. **Match faces against known entities** (Rekognition compare_faces):
   ```
   python scripts/match_faces.py --case-id {CASE_ID}
   ```
   Incremental — skips already-matched pairs on re-runs.

5. **Verify in UI**: Open Evidence Library tab → should see classification toggle (Photos Only default) with counts, entity badges on matched images.

### Notes
- Steps 1-4 are standalone scripts, NOT wired into Step Functions yet
- Each step produces S3 artifacts consumed by the next step
- Backend is backward compatible — if artifacts don't exist, Evidence Library shows all images unfiltered
- TODO: Wire these steps into the batch loader UI so they run automatically after ingestion and notify the user when complete

## PENDING
- Monitor first 109-file batch completion
- Run migration 007 for access control tables
- Improve batch loader UX (show batch ID after start, better Live Progress)
- Wire post-ingestion pipeline (classify → detect → crop → match) into batch loader UI with step notifications
- Run larger batches (6000 files, then 30k)
- Update session-state after batch completes
