---
inclusion: auto
---

# Data Pipeline Configuration — Always Check First

When working with the data pipeline (Lambda deploy, OpenSearch indexing, Bedrock calls, batch research), always check `docs/lessons-learned-data-pipeline.md` for the full reference. Key points below:

## Lambda Deploy
- ALWAYS use `scripts/_deploy_via_s3.py` — never direct upload (42MB times out)
- CaseFiles Lambda: `ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq`

## Loading Data into Aurora/Neptune/OpenSearch — THE REAL PATH (read before every load)
This is the #1 recurring failure. Follow exactly:

1. **Dropping JSON into `s3://.../data-lake/conspiracy-theories/{theory}/` does NOT ingest anything.** It only stores files. No Aurora case, no Neptune graph. The `_upload_conspiracy_to_s3.py` pattern is storage-only.
2. **The ONLY path that populates Aurora/OpenSearch/Neptune is the API:**
   - `POST /case-files`  body `{topic_name, description, search_tier}` → returns `case_id`
   - `POST /case-files/{case_id}/ingest`  body `{files:[{filename, content_base64}]}` (base64 text; batch ~25) → fires Step Function `research-analyst-ingestion` which does parse → extract entities (Haiku) → embed (Titan) → Aurora + OpenSearch + Neptune automatically.
   - Reference script: `scripts/_ingest_ufos_uaps.py`.
3. **`search_tier` allowed values are ONLY `standard` or `enterprise`.** NOT `intelligence`/`scientific`/`criminal_legal` (those are proof-engine standards, a different thing). Wrong value → 400.
4. **CANONICAL TABLE = `case_files` (NOT `matters`).** Create-case AND the ingestion Step Function must use `CaseFileService` (backed by `case_files`). All working cases (El Chapo, Ancient Aliens) live there. The `matters`/`MatterService`/`CaseFileCompatService` path is a half-finished multi-tenant refactor: create-case would write to `matters` but the pipeline's `update_status_handler` reads `case_files` → `KeyError: Case file not found`. Fixed durably in `src/lambdas/api/case_files.py` `_build_case_file_service()` (returns CaseFileService). Do NOT switch it back to the compat/matters service without also migrating every ingestion Lambda.
5. **`DEFAULT_ORG_ID`**: set in CDK `infra/cdk/cdk_constructs/lambda_construct.py` `build_lambda_env()` (defaults to seeded "Default Organization" `95bd7590-1e26-4822-8773-9fb7bf7abd37`). Only matters for the `matters`/lead-ingestion path now that create-case uses `case_files`, but keep it set. See docs/lessons-learned.md Issue 53.
6. Indexing taxonomy signatures into `typology-patterns`: clear the domain first (or use `scripts/_index_ufo_signatures_clean.py`); the per-signature search+delete dedup in `index_pattern_library.py` races AOSS refresh lag and duplicates docs.

## Search engine + write order + tier (CODE-VERIFIED — stop getting this wrong)
Verified against infra/step_functions/ingestion_pipeline.json, src/lambdas/ingestion/embed_handler.py, src/services/backend_factory.py:
- The ingestion Step Function order is: ResolveConfig → ProcessDocuments[Parse → ExtractEntities → **GenerateEmbedding** → StoreArtifact] → (Rekognition/image opt) → **GraphLoad(Neptune)** → UpdateCaseStatusIndexed. So embeddings (Aurora OR OpenSearch) are written DURING GenerateEmbedding; Neptune is written LAST at GraphLoad. Neptune depends on extracted entities, NOT on embeddings. Order does not break anything — the halves are independent.
- **Vector store is TIER-GATED, not OpenSearch-always:**
  - `search_tier="standard"` (DEFAULT) → embeddings → **Aurora pgvector** (`documents` table, semantic-only). OpenSearch is NOT written.
  - `search_tier="enterprise"` → embeddings → **OpenSearch Serverless** (index `data_case_{case_id}_v2`; semantic+keyword+hybrid).
  - Routing: embed_handler.py `backend_name = "opensearch" if search_tier=="enterprise" else "aurora"`.
  - `search_tier` is IMMUTABLE after case creation. To use OpenSearch you MUST create the case with search_tier="enterprise" (or apply the "financial_fraud" config template) BEFORE ingest.
- **If the goal is "data in OpenSearch as the engine" → create the case as enterprise tier.** Standard tier will silently route vectors to Aurora only. This is the #1 thing that gets missed.
- **typology-patterns** (the 31 UFO signatures + crime signatures) is a SEPARATE OpenSearch index seeded by index_pattern_library.py — always in OpenSearch regardless of tier. Cross-domain k-NN against signatures works; per-document k-NN only works for enterprise-tier cases.
- **S3 Vectors: NOT implemented** (grep-verified: no S3 Vectors / PutVectors / vector bucket in code). Vector storage is Aurora pgvector or OpenSearch only. If a cost-tiered S3-Vectors layer is wanted, it is a NEW build, not existing.
- The broad_scanner / taxonomy_scanner / cross_pattern agents (agent_orchestrator.py) are a SEPARATE research pipeline — they do NOT write to OpenSearch/Neptune during ingestion.

## Do NOT build new data loaders
The ingestion pipeline is already built. ALWAYS reference/reuse it — never hand-roll a loader:
- Load path: `POST /case-files` then `POST /case-files/{id}/ingest` (files+content_base64). Reference callers: `scripts/_ingest_conspiracy_to_pipeline.py`, `scripts/_ingest_ufos_uaps.py`.
- Deploy Lambda code changes with `scripts/_deploy_via_s3.py` (NOT direct upload, NOT `aws lambda update-function-configuration` for code).
- Only write new code when the built pipeline is genuinely missing a capability a requirement needs — and put the fix in source (CDK/service), not a runtime patch.

## Bedrock Models
- Use `us.anthropic.claude-sonnet-4-6` (must have `us.` prefix for inference profiles)
- Haiku: `anthropic.claude-3-haiku-20240307-v1:0` (legacy but works)
- Handle extended thinking: iterate content blocks, find `type == "text"`

## OpenSearch Serverless
- Endpoint: `https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com`
- Use `POST /{index}/_doc` (no document ID — AOSS limitation)
- Any index name works (wildcard policy on `research-analyst-search/*`)

## API Gateway
- 29s hard timeout — keep Sonnet calls under 1000 max_tokens for sync endpoints
- For longer research: bypass API Gateway, call Bedrock directly from scripts

## Batch Research
- Set `$env:BRAVE_SEARCH_API_KEY` before running
- Use `scripts/batch_research_direct.py` (bypasses API Gateway timeout)
- Two-pass: broad first, then taxonomy-guided
