---
inclusion: auto
---

# Preflight Checklists (READ THE MATCHING TABLE BEFORE THE OPERATION)

Hard rule: before running an operation below, CITE the applicable known-issue row in your
response, then proceed with the correct approach. A PreToolUse hook (.kiro/hooks/aoss-preflight-guard.json)
enforces this on execute_pwsh. This exists because the same issues recur when acting-before-reading.
Cross-reference: docs/lessons-learned.md (numbered Issues) + docs/lessons-learned-data-pipeline.md.

## Operation: OpenSearch / AOSS write or index
| Known issue | Correct approach |
|---|---|
| AOSS rejects caller-supplied `_id` (`PUT /_doc/{id}` → 400) | Use `POST /_doc` (auto-id) or `_bulk` with `{"index":{"_index":...}}` (no _id). |
| `_delete_by_query` 404s on this collection | Search for `_id`s then `DELETE /_doc/{id}` in a loop; clear domain fully before re-index. |
| Index create must be kNN-ready | settings `index.knn: true`, dim **1024** (Titan Embed v2), hnsw, cosinesimil. |
| **Enterprise embed → OpenSearch fails 401/silently (Issue 26)** | Lambda IAM role needs `aoss:APIAccessAll` on data access policy `research-analyst-search-dap`. The embed_handler call to `backend.index_documents()` has NO try/except → errors are swallowed by the Step Function Catch and the run still reports SUCCESS. Verify the index actually exists (`_count`) after ingest; do not trust "SUCCEEDED". |
| AOSS index/writes lag on refresh | `_count`/`_cat/indices` can lag 1–3 min; a 404 after >4 min is a real failure, not lag. |
| **AOSS `HEAD /{index}` returns 403 for a non-existent index (Issue 51)** | NEVER use HEAD to check existence — AOSS gives 403 (not 404) and no body, so the code aborts thinking it's an auth failure. Use `GET /{index}/_settings` and treat BOTH 403 AND 404 as "does not exist". This was THE cause of the enterprise-embed silent failure — not IAM. Fixed in opensearch_serverless_backend.py `_index_exists`. After AOSS data-access policy edits, wait 60s+. |

## Operation: Lambda code deploy
| Known issue | Correct approach |
|---|---|
| Direct upload times out (42MB+) | Use `scripts/_deploy_via_s3.py`. |
| Deploy zip balloons >250MB (Lambda limit) | The script EXCLUDES `src/data` + data extensions. Never include data dirs in a code zip. |
| Env-var update replaces whole Environment block | Merge existing vars, don't overwrite (would drop STATE_MACHINE_ARN etc.). |

## Operation: Pipeline ingest (POST /case-files + /ingest)
| Known issue | Correct approach |
|---|---|
| Dropping JSON in data-lake does NOT ingest | Must call `POST /case-files` then `POST /case-files/{id}/ingest` (files+content_base64). |
| Canonical table = `case_files` | create-case + ingest both use CaseFileService(case_files). Not `matters`. |
| `search_tier` allowed = standard/enterprise ONLY | `standard` → Aurora pgvector; `enterprise` → OpenSearch. Tier is IMMUTABLE post-create. |
| `DEFAULT_ORG_ID` must be set on CaseFiles Lambda | else create-case 500s (empty UUID). In CDK build_lambda_env. |
| Step Function "SUCCEEDED" ≠ data landed | Always verify: Aurora entities count, Neptune, and (enterprise) the OpenSearch index `_count`. |

## Three-store roles (do not collapse to one)
- **Aurora**: system of record + relationships + Bedrock output CACHE (`ai_level_summaries`, `research_findings`, `ai_decisions`, 7-day TTL, path-prefix invalidation — avoids re-running expensive non-deterministic Bedrock) + pgvector (standard tier).
- **OpenSearch**: hybrid keyword+semantic + cross-domain k-NN vs `typology-patterns` (enterprise tier document vectors).
- **Neptune**: multi-hop graph traversal (connections OpenSearch/vectors cannot do).
- **S3 Vectors**: NOT implemented (cold/cheap tier candidate — new build if wanted).
