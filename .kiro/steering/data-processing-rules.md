# Data Processing Rules

## Data Loading Process (Standard Procedure)

Every new dataset follows this pipeline:

### Step 1: Create Initial Taxonomy with LLM
- Use Bedrock Claude to generate domain-specific signatures based on known patterns
- These go into `TAXONOMY_SIGNATURES` in the processing scripts
- Always include ALL existing taxonomy domains (cross-domain scoring)

### Step 2: Find Seed Data
- Manually curate 10-50 representative examples with evidence for/against
- Store in `src/data/conspiracy-seed/{theory_name}/` as structured JSON
- This is the "known ground truth" for testing

### Step 3: Find Source Data
- Download real datasets (NTSB, NUFORC, VAERS, Voat, etc.)
- User downloads via browser, places in `docs/` folder
- Kiro moves to proper location and creates processing script

### Step 4: Test with Sample (50 records per source)
- Run `scripts/_taxonomy_test_50_each.py` to validate taxonomy coverage
- Target: 70%+ match rate per source
- If below 50%: expand taxonomy with source-specific signatures
- Re-test until acceptable

### Step 5: Expand Taxonomy Based on Gaps
- Identify unmatched record patterns
- Add new signatures to cover missing patterns
- Re-run test to confirm improvement

### Step 5.5: Tiered Filtering (MANDATORY for large datasets)
**NEVER load raw data directly into Aurora/Neptune/OpenSearch.** Always filter first.

Use the tiered approach (`scripts/epstein_tiered_scan.py` as reference):

1. **Tier 1 — FREE keyword/regex scan** ($0)
   - Read files, score against domain-specific keyword patterns
   - Discard blank pages, forms, duplicate headers, junk
   - Typical filter rate: 90-95% rejected (only 5-10% passes)
   - Output: ranked list of "interesting" files with category tags

2. **Tier 2 — Cheap Titan Embed** (~$0.0001/doc)
   - Only embed files that passed Tier 1
   - Saves 90%+ of embedding cost vs. full dataset
   - Output: embeddings for k-NN scoring

3. **Tier 3 — Targeted Claude Haiku** (~$0.0012/doc)
   - Score embeddings against taxonomy signatures (local cosine similarity)
   - Only send top-scoring files to Claude for entity extraction
   - Output: entities, relationships, red flags — ready for Neptune/Aurora

**WHY THIS MATTERS:**
- Neptune and OpenSearch get cluttered with noise (blank pages, forms, cover sheets)
- Noise makes k-NN search less accurate (irrelevant nearest neighbors)
- Noise inflates storage and compute costs with zero analytical value
- Only "rich data" (entities, relationships, patterns) belongs in the graph

**COST COMPARISON (Epstein 3,804 files):**
- Without tiering: ~$4.56 embed + $4.56 Haiku = $9.12
- With tiering: $0.02 embed + $0.25 Haiku = $0.27 (97% savings)
- At 345K files: $200 → $17-20 (90% savings)

### Step 6: Full Load (filtered data only)
- Process ONLY tier-filtered data through pipeline
- Score against ALL taxonomy domains (mandatory)
- Run Proof Engine on meta-theories derived from data
- Save results to `src/data/proof-engine-results-{theory_name}.json`

### Step 7: Cross-Domain Analysis
- Review cross-cutting findings (match 2+ domains)
- These are the highest-value discoveries
- Document in session summary

### Important Notes
- Kiro (AI assistant) IS the practical data loading interface for now
- Existing `ingestion_service.py` and `bulk_ingestion_service.py` are for VPC-deployed pipeline
- Local processing works without Aurora/OpenSearch — results saved as JSON
- Always `git add -f` data files (they're in .gitignore)

## Full Pipeline Integration (MANDATORY — DO NOT SKIP)

After local processing, ALWAYS push data into the deployed infrastructure:

### S3 Upload (triggers Lambda pipeline)
```python
import boto3
s3 = boto3.client('s3')
s3.upload_file(
    local_path,
    'research-analyst-data-lake-974220725866',
    f'data-lake/conspiracy-theories/{theory_name}/{filename}'
)
```

### What S3 Upload Triggers
The existing deployed Lambda pipeline automatically:
1. **Broad Scanner** → extracts entities, claims, behavioral indicators
2. **Taxonomy Scanner** → k-NN against `typology-patterns` OpenSearch index (ALL domains)
3. **Cross-Pattern Agent** → creates Neptune edges for cross-theory connections
4. Results write to **Aurora** (conspiracy schema), **OpenSearch** (embeddings), **Neptune** (graph)

### Existing Services (USE THESE — don't reinvent)
- `src/services/opensearch_serverless_backend.py` — handles SigV4 auth, k-NN search, indexing
- `src/services/pipeline_status_service.py` — monitors S3/Aurora/Neptune/OpenSearch status
- `src/services/ingestion_service.py` — document ingestion into pipeline
- `src/services/bulk_ingestion_service.py` — batch processing
- Connection via environment variables set in Lambda (OPENSEARCH_ENDPOINT, NEPTUNE_ENDPOINT, etc.)

### After Upload — Verify
```python
from src.services.pipeline_status_service import PipelineStatusService
status = pipeline_svc.get_status(case_id)
# Check: s3_stats, aurora_stats, neptune_stats, opensearch_stats
```

### NEVER do this:
- ❌ Save only to local JSON and call it "done"
- ❌ Skip OpenSearch indexing (k-NN search won't work without it)
- ❌ Skip Neptune edges (investigation graph won't show connections)
- ❌ Write new connection code when existing services already handle it
- ❌ Load raw/unfiltered data directly into Aurora/Neptune/OpenSearch
- ❌ Embed or LLM-process blank pages, forms, cover sheets, or junk
- ❌ Skip Tier 1 keyword filtering on datasets with >100 files
- ❌ Delete Neptune nodes based on entity_type alone — types like "object", "identifier", "product" may be legitimate crime taxonomy entities. Only delete based on canonical_name content (blank, "PAGE 1", boilerplate)

## Cross-Domain Scoring (MANDATORY)

When processing ANY dataset through the taxonomy pipeline, ALWAYS score against ALL taxonomy domains simultaneously — not just the domain the data "belongs to."

### Why
A document from the UFO dataset might match:
- A conspiracy theory "evidence suppression" signature
- A crime "document concealment" signature  
- An ancient mysteries "geographic clustering" signature

These cross-domain hits are the HIGHEST VALUE findings in the system. They reveal structural patterns that transcend subject matter.

### How
When running k-NN search against the `typology-patterns` OpenSearch index:
- Do NOT filter by `taxonomy_domain`
- Search against ALL signatures (ancient_mysteries + conspiracy_theory + crime)
- Tag each match with which domain it came from
- Cross-domain matches get flagged as "cross_cutting" in the results

### Cost Impact
- Zero additional embedding cost (one embedding per document regardless)
- Zero additional search cost (k-NN searches the full index in one operation)
- Only marginal Bedrock cost for evaluating additional cross-domain matches (~$0.001 per extra match)

### Implementation
In `conspiracy_taxonomy_scanner_handler` and any future taxonomy scanner:
```python
# CORRECT — search all domains
results = opensearch.knn_search(
    index="typology-patterns",
    vector=embedding,
    k=10,
    # NO taxonomy_domain filter — search everything
)

# Tag cross-domain hits
for hit in results:
    if hit['taxonomy_domain'] != current_tenant_domain:
        hit['is_cross_cutting'] = True
```

## Data Source Requirements

When ingesting new datasets:
1. Always record the source URL and download date
2. Store raw files in `src/data/conspiracy-seed/{theory_name}/`
3. Force-add to git with `git add -f` (data/ is in .gitignore)
4. Process through the full pipeline: adapters → agents → proof engine
5. Save results to `src/data/proof-engine-results-{theory_name}.json`
6. **Include geographic metadata**: country, region, county/state, coordinates for every entity with a physical location
7. **Define a region mapping**: county/state → logical region (e.g., "Meath" → "Boyne Valley")
8. **Build GEO_REGIONS lookup**: hierarchical Country → Region → Site IDs for sidebar navigation
9. **Update GeocodingService**: Add new locations to CURATED_LOCATIONS in `src/services/geocoding_service.py`

## Proof Engine Standard Selection

- Ancient Mysteries → `scientific` standard
- Conspiracy Theories → `intelligence` standard  
- Crime → `criminal_legal` standard
- But ALWAYS allow override via API parameter

## External Pre-Processed Data Sources (USE BEFORE RE-PROCESSING)

Before running expensive OCR/Textract/LLM processing on any dataset, CHECK if pre-processed
versions already exist. Community-built datasets save massive compute costs.

### Epstein Files (Pre-Processed Sources):
| Source | Size | What it has |
|--------|------|-------------|
| `rhowardstone/Epstein-research-data` (GitHub) | 2.3GB SQLite | Full text corpus, knowledge graph (524 entities, 2,096 rels), entity extractions, persons registry (1,614 people), image catalog, redaction analysis |
| `ishumilin/epstein-files-ocr-complete` (HuggingFace) | 1.41GB Parquet | 1.38M documents, page-level OCR, document_id + content fields |
| `promexdotme/epstein-justice-files-text` (GitHub) | ~2GB text | DOJ 5GB PDF set converted to clean RAG-compatible text |
| `notesbymuneeb/epstein-emails` (GitHub) | Structured JSON | 5,082 email threads (16,447 messages) with LLM extraction |
| `theelderemo/FULL_EPSTEIN_INDEX` (GitHub) | Full archive | All datasets unified with OCR |

### Decision Process:
1. **Check external sources first** — download pre-processed data if available
2. **Run tiered filter** — apply keyword/regex scan even on pre-processed data
3. **Only embed/LLM what passes filter** — never bulk-process without filtering
4. **Load into Aurora/Neptune/OpenSearch** — only rich, filtered data
