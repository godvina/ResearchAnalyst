# Lessons Learned — Data Pipeline Configuration

Last updated: 2026-07-31

These are hard-won configuration findings that will save hours on the next data pipeline load. Check this document FIRST before running any pipeline.

---

## Lambda Deployment

### Deploy via S3 (NEVER direct upload for large packages)
- The Lambda code package is ~42MB (includes pymupdf, pillow, psycopg2 .so files)
- Direct `update_function_code(ZipFile=bytes)` TIMES OUT over network
- **Always use**: Upload zip to S3 first, then `update_function_code(S3Bucket=..., S3Key=...)`
- Script: `scripts/_deploy_via_s3.py`
- S3 key: `deploy/lambda-code-latest.zip`

### Lambda Function Name
- CaseFiles Lambda: `ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq`
- Region: us-east-1

### API Gateway Timeout
- **Hard limit: 29 seconds** — cannot be increased
- Any synchronous endpoint must complete within 29s
- For Sonnet: limit max_tokens to 1000, cap search input to 8 results
- For long-running research: call Bedrock DIRECTLY (bypass API Gateway) using `scripts/batch_research_direct.py`

---

## Bedrock Model IDs

### Working Models (as of 2026-07-31)
- **Sonnet 4.6**: `us.anthropic.claude-sonnet-4-6` — ACTIVE, use for research
- **Haiku**: `anthropic.claude-3-haiku-20240307-v1:0` — LEGACY but still works for summaries

### CRITICAL: Use Inference Profile IDs
- Direct model IDs (e.g., `anthropic.claude-sonnet-4-5-20250929-v1:0`) return "on-demand throughput isn't supported"
- **Must prefix with `us.` or `global.`** for cross-region inference profiles
- Check available: `bedrock.list_inference_profiles()`

### Dead Models (DO NOT USE)
- `anthropic.claude-3-5-sonnet-20241022-v2:0` — End of life
- `anthropic.claude-sonnet-4-20250514-v1:0` — Legacy, access denied after 30 days inactive

### Extended Thinking
- Sonnet 4.6 may return multiple content blocks (thinking + text)
- Always iterate `resp["content"]` blocks and find `type == "text"`, don't just grab `[0]`

---

## OpenSearch Serverless (AOSS)

### Correct Endpoint
- Collection: `research-analyst-search`
- Endpoint: `https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com`
- **NOT** the old endpoint `u260nrrtc0q87ji8iu0k` (that's from env vars/config — outdated)

### Document IDs NOT Supported
- AOSS **does not support** `PUT /{index}/_doc/{id}` (returns 400)
- **Must use** `POST /{index}/_doc` (auto-generated ID)
- For bulk: use `POST /_bulk` with ndjson format (see `index_pattern_library.py`)
- For idempotent upserts: delete + re-index, or use a separate tracking mechanism

### Data Access Policy
- Policy name: `research-analyst-search-dap`
- Allows: `index/research-analyst-search/*` (wildcard — any index name works)
- If you get 403: you're hitting the WRONG endpoint, not a policy issue

### Index Creation
- kNN indexes require `"index": {"knn": true}` in settings
- Embedding dimension: 1024 (Titan Embed v2)
- Method: hnsw, space_type: cosinesimil, engine: nmslib

---

## S3 Data Locations

### Pattern Library Data
- `pattern-library/pattern-library-taxonomy.json`
- `pattern-library/ancient-mysteries-taxonomy.json`
- `pattern-library/uvg-grid-investigation-database.json`
- `pattern-library/uvg-grid-hagens-official.json`
- `pattern-library/uvg-grid-hagens-lines.json`
- `pattern-library/grid-investigation-taxonomy.json`
- `pattern-library/ley-line-taxonomy-presentation.json`

### Frontend
- `frontend/pattern-library.html`
- `frontend/grid-globe.html`
- `frontend/config.js`

### Neptune Bulk Load
- `neptune-bulk-load/uvg-grid-nodes.csv` (90 nodes)
- `neptune-bulk-load/uvg-grid-edges.csv` (287 edges)

### Lambda Code
- `deploy/lambda-code-latest.zip`

---

## Neptune

### Graph Loader Pattern
- Generate nodes.csv + edges.csv → upload to S3 → call Neptune REST loader API
- Existing loader: `src/services/neptune_graph_loader.py`
- UVG grid CSVs: `scripts/load_grid_to_neptune.py`
- IAM role needed for Neptune to read from S3

---

## Brave Search API

### Key
- Stored in Lambda env var: `BRAVE_SEARCH_API_KEY`
- For local scripts: `$env:BRAVE_SEARCH_API_KEY = "BSAVzpY_CQ_4vRXyiTC5s_SwSDBtZxSr"`
- Max query length: 400 characters (Brave returns 422 if longer)

### Rate Limiting
- No explicit rate limit hit in testing
- Self-imposed 2-3s delay between requests in batch scripts

---

## Aurora / PostgreSQL

### CHECK Constraints
- `ai_level_summaries.taxonomy_level` only allows: domain, typology, method, signature, precedent_case
- **Does NOT allow**: concept_research, research (migration 024 adds these but hasn't been applied)
- Non-blocking: cache writes fail silently, research still works

### research_findings Table
- Migration 023 creates it but hasn't been applied
- Writes fail with "relation does not exist" — non-blocking

---

## JSON Parsing from LLM Output

### Sonnet 4.6 Quirks
- Sometimes wraps output in ```json fences (even when told not to)
- May produce truncated JSON when max_tokens is hit
- Always strip markdown fences before parsing
- Implement truncation repair: find last `},` or `}`, close open brackets

### Repair Strategy
```python
for trim_to in [text.rfind('},'), text.rfind('}'), text.rfind('"]')]:
    if trim_to <= 0: continue
    candidate = text[:trim_to + 1]
    candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
    candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
    try: return json.loads(candidate)
    except: continue
```

### Token Budget for 29s Timeout
- max_tokens=1000 → completes in ~25-27s (safe)
- max_tokens=1100+ → often hits 29s timeout
- Put most important JSON fields FIRST in the schema (they get generated before truncation)

---

## Frontend Deployment

### Upload HTML to S3
```python
s3.put_object(Bucket=bucket, Key='frontend/pattern-library.html', Body=f.read(), ContentType='text/html')
```

### Common Errors
- Duplicate code from str_replace → blank page (check `<script>` balance)
- Always verify: `c.count('<script') == c.count('</script>')`
- Check brace balance per script block before uploading

---

## Batch Research (Direct Bedrock)

### When to Use
- Any research that takes >29s (which is most Sonnet + Brave combinations)
- Run from local machine with `$env:BRAVE_SEARCH_API_KEY` set
- Script: `scripts/batch_research_direct.py`

### Performance
- ~17-20s per node (3 Brave searches + 1 Sonnet synthesis)
- 62 nodes ≈ 18 minutes total
- Results accumulate (merges with existing file)

### Two-Pass Strategy
1. `batch_research_direct.py --all` → broad findings
2. `batch_research_taxonomy_guided.py --all` → targeted signature matching
3. `run_scoring_pipeline.py` → score findings against 18 taxonomy signatures
4. `index_grid_to_opensearch.py` → embed + index for k-NN queries
