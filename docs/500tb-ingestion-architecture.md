# 500 TB Case File Ingestion — Architecture & Approach

## Context

Customer has ~500 TB of case files (documents, PDFs, images, scanned records) that need to be processed through an AI-powered investigation pipeline: text extraction, entity extraction, embedding generation, vector search indexing, and knowledge graph construction.

This document outlines the architecture changes needed to scale from our proven 3,800-doc Epstein pipeline to a 500 TB production workload.

---

## Scale Comparison

| Metric | Current (Epstein) | Target (500 TB) | Scale Factor |
|--------|-------------------|------------------|--------------|
| Total data | ~50 MB text | ~500 TB mixed | 10,000,000x |
| Documents | 3,804 | Est. 50-100 million | 15,000-25,000x |
| Processing time | ~4 hours | Target: days, not months | — |
| Bedrock cost | ~$19 | Est. $50K-150K | — |
| Concurrency | 5 Lambda | 100-500 concurrent | 20-100x |

---

## Phase 1: Document Text Extraction

### Scenario A: Searchable PDFs + Word Docs (No OCR Needed)

If documents are already searchable PDFs and Word files, skip Textract entirely. Use open-source libraries in Lambda for text extraction at near-zero cost.

**Cost: ~$0 (just Lambda compute)**

```
S3 (500 TB raw files)
    │
    ▼
SQS Queue (one message per file)
    │
    ▼
Lambda Fleet (500 concurrent, 512 MB, 120s timeout)
    ├── .pdf  → PyPDF2 or pdfplumber (text extraction)
    ├── .docx → python-docx (text extraction)
    ├── .doc  → antiword or LibreOffice headless
    ├── .txt  → direct read
    └── .html → BeautifulSoup
    │
    ▼
S3 (extracted-text/ prefix as JSON)
```

**Lambda Layer for PDF/DOCX libraries:**
```
# Build Lambda layer with extraction dependencies
pip install PyPDF2 pdfplumber python-docx beautifulsoup4 -t python/
zip -r extraction-layer.zip python/
aws lambda publish-layer-version --layer-name text-extraction \
  --zip-file fileb://extraction-layer.zip --compatible-runtimes python3.12
```

**Extraction code pattern:**
```python
import PyPDF2
from docx import Document
import io

def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    
    if ext == "pdf":
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    
    elif ext in ("docx", "doc"):
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    
    elif ext == "txt":
        return file_bytes.decode("utf-8", errors="replace")
    
    elif ext in ("html", "htm"):
        from bs4 import BeautifulSoup
        return BeautifulSoup(file_bytes, "html.parser").get_text()
    
    return ""
```

**Throughput estimate:**
- PyPDF2 extracts ~50 pages/sec on Lambda (512 MB)
- 100M documents × 5 pages avg = 500M pages
- At 500 concurrent Lambdas × 50 pages/sec = 25,000 pages/sec
- 500M pages / 25,000 = 20,000 seconds = ~5.5 hours

**Lambda cost:**
- 100M invocations × 10s avg × 512 MB = ~$8,300
- Compare to Textract: $750,000

### Scenario B: Mixed (Some Scanned, Some Searchable)

Detect whether a PDF is searchable or scanned, route accordingly:

```python
def is_searchable_pdf(file_bytes: bytes) -> bool:
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    # Check first 3 pages for extractable text
    for page in reader.pages[:3]:
        text = page.extract_text() or ""
        if len(text.strip()) > 50:
            return True
    return False
```

- Searchable → PyPDF2 (free)
- Scanned → Textract async ($1.50/1000 pages)
- Typical split: 70% searchable, 30% scanned
- Cost: 30% × $750K = $225K (vs $750K for all Textract)

### Scenario C: All Scanned (OCR Required)

Use Textract as originally planned. See cost optimization strategies in Phase 6.


---

## Phase 2: Entity Extraction & Embeddings (Bedrock)

### Problem
50-100M documents need entity extraction (Claude) and embedding generation (Titan). At current rates (~$0.005/doc for extraction), this is $250K-500K in Bedrock costs.

### Cost Optimization Strategies

1. **Batch Inference (Bedrock Batch)**: Up to 50% cheaper than on-demand
   - Submit batch jobs with thousands of prompts
   - Results delivered to S3 within hours
   - No Lambda needed — Bedrock handles orchestration

2. **Model Selection**: Use Claude Haiku (cheapest) for entity extraction
   - Current: ~14 Bedrock calls per doc (7 chunks × 2 passes)
   - Optimization: reduce to single-pass extraction with larger context window
   - Claude 3.5 Haiku has 200K context — can process entire documents without chunking

3. **Embedding Model**: Titan Embed v2 (1536 dims) at $0.0001/doc is already cheap
   - 100M docs × $0.0001 = $10K — not the cost driver

4. **Skip Small/Duplicate Documents**: Many case files are duplicates or near-empty
   - Hash-based dedup before processing
   - Skip files under 100 bytes of extracted text
   - Estimated 20-30% reduction in processing volume

### Recommended Architecture

```
S3 (textract output)
    │
    ▼
S3 Batch Operations → SQS Queue (100M messages)
    │
    ▼
Lambda Fleet (100-500 concurrent)
    ├── Read textract JSON from S3
    ├── Dedup check (DynamoDB hash table)
    ├── Entity extraction → Bedrock Batch or on-demand
    ├── Embedding generation → Bedrock Titan
    ├── Index to OpenSearch Serverless (bulk API)
    └── Write extraction artifact to S3
    │
    ▼
DynamoDB (processing status per document)
```

### Concurrency & Throughput

| Component | Limit | Requested | Throughput |
|-----------|-------|-----------|------------|
| Lambda concurrent | 1,000 default | 5,000 | — |
| Bedrock Haiku TPS | ~50 default | 500 | ~500 docs/sec |
| Bedrock Titan Embed TPS | ~100 default | 1,000 | ~1,000 docs/sec |
| OpenSearch Serverless bulk | No hard limit | — | ~10K docs/sec |
| SQS message throughput | Unlimited | — | — |

At 500 docs/sec entity extraction throughput: 100M docs / 500 = 200,000 seconds = ~2.3 days

### Bedrock Batch Inference (Preferred for Cost)

```
Prepare JSONL input files (1M prompts per file)
    │
    ▼
CreateModelInvocationJob (Bedrock Batch API)
    │  - Input: s3://bucket/batch-input/
    │  - Output: s3://bucket/batch-output/
    │  - Model: Claude 3.5 Haiku
    │  - Up to 50% discount vs on-demand
    ▼
Poll job status → Process output files
```

Estimated cost with batch: $125K-250K (vs $250K-500K on-demand)


---

## Phase 3: Vector Search (OpenSearch Serverless)

### Problem
100M documents with 1536-dim embeddings need to be searchable via keyword, semantic, and hybrid search.

### OpenSearch Serverless Scaling

- AOSS auto-scales compute (OCU) based on load
- Minimum: 2 OCU for indexing, 2 OCU for search
- At scale: expect 20-50 OCU during bulk indexing, 4-10 OCU for search
- Cost: ~$0.24/OCU/hour. 50 OCU × 48 hours bulk load = ~$576

### Index Strategy

Don't create one index per case (current approach) at this scale. Instead:

| Strategy | Pros | Cons |
|----------|------|------|
| One index per case | Isolation, easy deletion | Too many indexes at scale |
| One shared index with case_id field | Simple, efficient | Harder to delete case data |
| Time-based indexes (monthly) | Good for retention | Complex queries across time |

**Recommended**: Shared index with `case_id` as a filterable field. Use OpenSearch index templates for consistent mappings. Delete case data via delete-by-query.

### Bulk Indexing at Scale

```python
# Batch 1000 documents per _bulk request
# Use parallel bulk with 10 threads
# Target: 10K docs/sec sustained indexing rate
```

- Pre-create the index with correct shard count (1 primary shard per 30-50 GB)
- For 100M docs × ~2KB avg = ~200 GB → 4-7 primary shards
- Disable refresh during bulk load (`"refresh_interval": "-1"`), re-enable after

---

## Phase 4: Knowledge Graph (Neptune)

### Problem
100M documents will produce billions of entities and relationships. Neptune Serverless has limits.

### Neptune Scaling Considerations

- Neptune Serverless: 1-128 NCU, auto-scales
- At 100M docs: expect 500M-1B entity nodes, 1-5B relationship edges
- Neptune storage limit: 64 TB (sufficient)
- Bulk loader is essential — Gremlin queries won't scale

### Bulk Load Strategy

```
Entity Extraction Output (S3 JSON)
    │
    ▼
ETL Job (Glue or Lambda)
    │  - Convert extraction JSON to Neptune CSV format
    │  - Vertices CSV: ~id, ~label, canonical_name:String, entity_type:String, ...
    │  - Edges CSV: ~id, ~from, ~to, ~label, relationship_type:String, ...
    ▼
S3 (neptune-bulk-load/ prefix)
    │
    ▼
Neptune Bulk Loader API
    │  - POST /loader
    │  - Parallel loading with multiple files
    │  - IAM role with S3 read access
    ▼
Neptune Graph (queryable)
```

### Graph Partitioning

At 500M+ nodes, queries need to be scoped:
- Label per case: `Entity_{case_id}` (current approach — works but creates many labels)
- Property-based filtering: single label with `case_id` property + composite index
- Subgraph isolation: separate Neptune clusters per major investigation

**Recommended**: Keep label-per-case for isolation. Neptune handles millions of labels efficiently. Cross-case queries use property filters.

---

## Phase 5: Orchestration

### Problem
Step Functions has a 25,000 execution history event limit. A single execution processing 100M docs would exceed this.

### Recommended: Hierarchical Orchestration

```
Master Orchestrator (Step Functions)
    │
    ├── Batch 1 (1000 docs) → Step Functions Execution
    ├── Batch 2 (1000 docs) → Step Functions Execution
    ├── ...
    └── Batch 100,000 (1000 docs) → Step Functions Execution
    │
    ▼
DynamoDB (batch status tracking)
    │
    ▼
Dashboard (progress monitoring)
```

- Master orchestrator submits batches and tracks completion via DynamoDB
- Each batch is an independent Step Functions execution (1000 docs)
- Failed batches can be retried independently
- Progress dashboard reads from DynamoDB

### Alternative: SQS + Lambda (Simpler)

Skip Step Functions entirely for the bulk load:

```
SQS Queue (100M messages, one per document)
    │
    ▼
Lambda Fleet (500 concurrent)
    ├── Process single document
    ├── Write results to S3 + OpenSearch + DynamoDB
    └── Dead letter queue for failures
```

- Simpler, more scalable, cheaper
- No 25K event limit
- Built-in retry via SQS visibility timeout
- DLQ captures failures for investigation
- Progress tracking via CloudWatch metrics (ApproximateNumberOfMessagesVisible)

**Recommended for 500 TB**: SQS + Lambda fleet, not Step Functions


---

## Phase 6: Cost Estimates

### Assumptions
- 500 TB raw data → ~100M documents after extraction
- Average 5 pages per document
- 20% dedup reduction → 80M unique documents processed

### Cost Breakdown

#### Scenario A: Searchable PDFs + Word Docs (No Textract)

| Service | Calculation | Estimated Cost |
|---------|-------------|----------------|
| **Text Extraction (Lambda)** | 100M invocations × 10s × 512 MB | $8,300 |
| **Bedrock Entity Extraction** (batch) | 80M docs × $0.003/doc (batch pricing) | $240,000 |
| **Bedrock Embeddings** | 80M docs × $0.0001/doc | $8,000 |
| **OpenSearch Serverless** | 50 OCU × 72 hrs indexing + 10 OCU × 720 hrs/mo search | $2,600/mo |
| **Neptune Serverless** | 32 NCU × 72 hrs loading + 8 NCU × 720 hrs/mo | $2,100/mo |
| **Lambda (AI processing)** | 80M invocations × 30s avg × 512 MB | $20,000 |
| **S3 Storage** | 500 TB raw + 200 GB text + 50 GB artifacts | $11,500/mo |
| **Data Transfer** | Minimal (all within region) | ~$500 |
| **Total One-Time Processing** | | **~$277,000** |
| **Total Monthly Running** | Search + graph + storage | **~$16,200/mo** |

Savings vs Textract approach: **$743,000** (73% reduction)

#### Scenario B: Mixed (30% Scanned)

| Service | Calculation | Estimated Cost |
|---------|-------------|----------------|
| **Textract (scanned only)** | 150M pages × $1.50/1000 | $225,000 |
| **Text Extraction (Lambda)** | 70M invocations × 10s × 512 MB | $5,800 |
| **Bedrock + Lambda + Storage** | Same as above | $268,500 |
| **Total One-Time Processing** | | **~$500,000** |

### Cost Optimization Levers

1. **Textract is the biggest cost IF docs need OCR** ($750K). Alternatives:
   - If docs are searchable PDFs/Word: use PyPDF2/python-docx instead ($8K Lambda cost)
   - If docs are mixed: detect searchable vs scanned, route accordingly (30% scanned = $225K)
   - If all scanned: Textract required. Sample 1% first to validate quality

2. **Bedrock Batch Inference**: 50% savings on entity extraction
   - $240K batch vs $480K on-demand

3. **Reduce entity extraction passes**: Single-pass with Claude 3.5 Haiku 200K context
   - Process entire document in one call instead of chunking
   - Reduces Bedrock calls from ~14/doc to 2/doc (entities + relationships)
   - Estimated savings: 70% on extraction cost → $72K instead of $240K

4. **Tiered processing**: Not all documents need full AI extraction
   - Tier 1 (high-value): Full entity extraction + graph loading
   - Tier 2 (standard): Embeddings + keyword search only (skip entity extraction)
   - Tier 3 (archive): Text extraction + keyword search only (skip embeddings)
   - Could reduce Bedrock costs by 50-70%

---

## Phase 7: Implementation Timeline

### Week 1-2: Infrastructure Setup
- Deploy base CDK stack (Aurora, Neptune, OpenSearch, Lambda, API Gateway)
- Configure AOSS VPC endpoint (use lessons learned doc)
- Set up SQS queues + DLQ
- Request service limit increases (Lambda concurrency, Bedrock TPS, Textract TPS)

### Week 3-4: Textract Pipeline
- Build S3 → SQS → Lambda → Textract async pipeline
- Test with 1,000 documents
- Validate text quality
- Run full Textract extraction (runs for 3-5 days)

### Week 5-6: AI Processing Pipeline
- Build SQS → Lambda → Bedrock (entity extraction + embeddings) pipeline
- Implement dedup logic (DynamoDB hash table)
- Test with 10,000 documents
- Tune concurrency and batch sizes

### Week 7-8: Search & Graph
- Bulk index into OpenSearch Serverless
- Bulk load Neptune graph via CSV
- Build search API (keyword, semantic, hybrid)
- Build graph exploration API

### Week 9-10: Frontend & Testing
- Deploy Streamlit frontend (or customer's preferred UI)
- End-to-end testing with 100K documents
- Performance tuning
- Full production run

---

## Architecture Diagram (Target State)

```
                    ┌─────────────────────────────────────────┐
                    │           S3 Data Lake (500 TB)          │
                    │  raw/ │ textract/ │ extractions/ │ bulk/ │
                    └───┬───────┬───────────┬──────────┬──────┘
                        │       │           │          │
                   ┌────▼──┐ ┌──▼────┐  ┌───▼───┐  ┌──▼────┐
                   │Textract│ │Entity │  │Embed  │  │Neptune│
                   │ Async  │ │Extract│  │Generate│  │Bulk   │
                   │Pipeline│ │(Bedrock│  │(Titan) │  │Loader │
                   └────┬───┘ │Batch) │  └───┬───┘  └──┬────┘
                        │     └───┬───┘      │         │
                        ▼         ▼          ▼         ▼
                    ┌────────┐ ┌──────┐ ┌────────┐ ┌───────┐
                    │Textract│ │DynamoDB│ │OpenSearch│ │Neptune│
                    │Output  │ │Status │ │Serverless│ │Graph  │
                    │(S3)    │ │Table  │ │(AOSS)   │ │       │
                    └────────┘ └──────┘ └────┬───┘ └───┬───┘
                                             │         │
                                        ┌────▼─────────▼────┐
                                        │   API Gateway      │
                                        │  (Search + Graph)  │
                                        └────────┬──────────┘
                                                 │
                                        ┌────────▼──────────┐
                                        │   Frontend (UI)    │
                                        │  Keyword / Semantic│
                                        │  / Hybrid Search   │
                                        │  Graph Explorer    │
                                        └───────────────────┘

    Orchestration: SQS Queues + Lambda Fleet (not Step Functions)
    Monitoring: DynamoDB status table + CloudWatch dashboard
```

---

## Key Differences from Current Architecture

| Aspect | Current (3,800 docs) | Target (100M docs) |
|--------|---------------------|---------------------|
| Orchestration | Step Functions | SQS + Lambda fleet |
| Concurrency | 5 | 100-500 |
| Text extraction | Pre-extracted (Textract) | PyPDF2/python-docx in Lambda ($0) or Textract for scanned only |
| Entity extraction | On-demand Bedrock | Bedrock Batch Inference |
| Embedding storage | Aurora pgvector | OpenSearch Serverless only |
| Graph loading | Gremlin HTTP | Neptune Bulk Loader (CSV) |
| Index strategy | One index per case | Shared index with case_id filter |
| Status tracking | Step Functions state | DynamoDB table |
| Dedup | None | DynamoDB hash table |
| Cost model | ~$19 total | ~$1M one-time + $16K/mo |

---

## What We Can Reuse from Current Codebase

These components are proven and portable:

1. **OpenSearch Serverless backend** (`opensearch_serverless_backend.py`) — SigV4 signing, bulk indexing, kNN search. Just needs the `X-Amz-Content-Sha256` header fix (already applied).

2. **Entity extraction service** (`entity_extraction_service.py`) — chunking, merge, dedup logic. Works at any scale.

3. **Neptune graph loader** (`neptune_graph_loader.py`) — bulk CSV generation + loader API. Already handles batching.

4. **Document parser** (`document_parser.py`) — text parsing and section extraction.

5. **Search API** (`search.py`) — multi-backend routing, keyword/semantic/hybrid modes.

6. **Backend factory pattern** (`backend_factory.py`) — tier-based routing between Aurora and OpenSearch.

7. **VPC connectivity patterns** — all the AOSS VPC endpoint, security group, and IAM lessons apply directly.

8. **CDK stack** — base infrastructure (Aurora, Neptune, S3, Lambda, API Gateway). Add SQS queues and increase limits.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Textract cost overrun | Use PyPDF2/python-docx for searchable docs. Only Textract for scanned. Sample 1% first |
| PDF extraction quality | Some PDFs have embedded images or complex layouts. Test with pdfplumber as fallback for PyPDF2 |
| Bedrock rate limiting | Request limit increases early, use batch inference, implement exponential backoff |
| OpenSearch indexing bottleneck | Pre-size shards, disable refresh during bulk, use parallel bulk threads |
| Neptune graph too large | Partition by case, use property indexes, consider Amazon Neptune Analytics for large-scale graph queries |
| Lambda concurrency exhaustion | Request 5,000 concurrent limit, implement SQS-based backpressure |
| Data quality issues | Build validation pipeline: check text length, entity count, embedding dimension before indexing |
| Cost surprises | Set up AWS Budgets alerts at 25%, 50%, 75%, 100% of estimated cost |


---

## Phase 8: Cross-Case Investigation — The Core Value Proposition

### The Problem Analysts Face Today

An analyst working Case A finds a phone number in a document. That same phone number appears in Case B, worked by a different analyst in a different office. Neither analyst knows about the other's case. The connection is invisible.

With 500 TB of case files across thousands of cases, these hidden connections are everywhere — shared phone numbers, addresses, bank accounts, names, vehicles, companies, dates. Each one is a potential investigative lead that's currently buried.

### How This Platform Surfaces Those Connections

The platform creates three complementary search layers that work together:

```
Layer 1: OpenSearch (Full-Text + Semantic)
    "Find every document that mentions 555-0142"
    "Find documents about wire transfers to offshore accounts"
    → Keyword search finds exact matches (phone numbers, account numbers)
    → Semantic search finds conceptually similar content
    → Hybrid combines both for best recall

Layer 2: Neptune Knowledge Graph (Entity Relationships)
    "Show me all cases where entity 'John Smith' appears"
    "What other entities co-occur with phone number 555-0142?"
    "Find the shortest path between Person A and Company B"
    → Graph traversal finds multi-hop connections
    → Cross-case entity matching is a simple graph query

Layer 3: AI Analysis (Bedrock)
    "Analyze the relationship between these two cases"
    "What patterns exist across cases involving this address?"
    → LLM synthesizes findings from search + graph into narrative
    → Suggests investigation leads the analyst might not see
```

### Cross-Case Entity Matching — How It Works

During ingestion, every document gets entity extraction via Bedrock. Entities include:

| Entity Type | Examples | Cross-Case Value |
|-------------|----------|-----------------|
| phone_number | 555-0142, +1-202-555-0199 | Same number in different cases = connection |
| person | John Smith, J. Smith, Johnny Smith | Name resolution across cases |
| address | 123 Main St, 123 Main Street | Same location in different investigations |
| organization | Acme Corp, ACME Corporation | Corporate connections across cases |
| account_number | Bank account, routing number | Financial connections |
| vehicle | License plate, VIN | Vehicle appearing in multiple cases |
| date | March 15, 2024 | Temporal correlation |
| email | user@domain.com | Communication links |

### Neptune Graph Model for Cross-Case

```
Case_A ──contains──▶ Document_123 ──mentions──▶ Phone_555_0142
                                                      ▲
Case_B ──contains──▶ Document_456 ──mentions──────────┘

Query: g.V().has('canonical_name', '555-0142')
            .in('mentions')
            .out('belongs_to')
            .dedup()
            .values('case_id')

Result: [Case_A, Case_B]  ← These cases share a phone number
```

### Key Graph Queries for Analysts

```gremlin
// 1. Find all cases sharing an entity
g.V().has('canonical_name', '555-0142')
     .in('RELATED_TO').hasLabel(startingWith('Entity_'))
     .values('case_file_id').dedup()

// 2. Find entities that appear in 3+ cases (high-value connections)
g.V().hasLabel(containing('Entity_'))
     .group().by('canonical_name').by('case_file_id')
     .unfold().filter(select(values).count(local).is(gte(3)))

// 3. Shortest path between two entities across all cases
g.V().has('canonical_name', 'Person A')
     .repeat(both().simplePath()).until(has('canonical_name', 'Person B'))
     .path().limit(5)

// 4. "Who else is connected to this person across cases?"
g.V().has('canonical_name', 'John Smith')
     .both('RELATED_TO')
     .groupCount().by('canonical_name')
     .order(local).by(values, desc).limit(local, 20)
```

### OpenSearch Queries for Analysts

```json
// 1. Exact match: find a phone number across all cases
POST /case-*/_search
{
  "query": {
    "match_phrase": { "text": "555-0142" }
  },
  "aggs": {
    "by_case": { "terms": { "field": "case_file_id" } }
  }
}

// 2. Fuzzy match: find name variations
POST /case-*/_search
{
  "query": {
    "match": { "text": { "query": "John Smith", "fuzziness": "AUTO" } }
  }
}

// 3. Semantic: find documents about similar topics
POST /case-*/_search
{
  "query": {
    "knn": {
      "embedding": {
        "vector": [/* embedding of "wire transfers to offshore accounts" */],
        "k": 50
      }
    }
  },
  "aggs": {
    "by_case": { "terms": { "field": "case_file_id" } }
  }
}
```

### Analyst Workflow

```
1. Analyst searches for a phone number → OpenSearch keyword search
   Result: "Found in 3 documents across 2 cases"

2. Analyst clicks "Show connections" → Neptune graph query
   Result: Visual graph showing the phone number connected to
           Person A (Case 1), Person B (Case 2), Address X (both cases)

3. Analyst clicks "Analyze relationship" → Bedrock AI
   Result: "Cases 1 and 2 share phone number 555-0142 and address
           123 Main St. Person A in Case 1 and Person B in Case 2
           may be connected through Company X which appears in both
           cases. Recommend investigating Company X's financial records."

4. Analyst creates a cross-case investigation → Platform links the cases
   Result: New investigation combining entities from both cases,
           with a unified graph showing all connections
```

### Entity Extraction Prompt — Optimized for Cross-Case Matching

The entity extraction prompt should be tuned to extract the specific entity types that enable cross-case matching:

```
Extract ALL of the following from this document:
- Phone numbers (any format: xxx-xxxx, (xxx) xxx-xxxx, +1xxxxxxxxxx)
- Email addresses
- Physical addresses (street, city, state, zip)
- Person names (full names, aliases, nicknames)
- Organization names (companies, agencies, departments)
- Account numbers (bank accounts, routing numbers, case numbers)
- Vehicle identifiers (license plates, VIN numbers)
- Dates and date ranges
- Dollar amounts and financial figures
- Locations (countries, cities, landmarks)

For each entity, provide:
- canonical_name: normalized form (e.g., "(555) 012-3456" → "555-012-3456")
- entity_type: one of [phone_number, email, address, person, organization, 
  account_number, vehicle, date, financial_amount, location]
- confidence: 0.0-1.0
- context: the sentence where this entity appears
```

### Normalization is Critical

For cross-case matching to work, entities must be normalized:

| Raw Text | Normalized | Why |
|----------|-----------|-----|
| (555) 012-3456 | 555-012-3456 | Phone format consistency |
| +1-555-012-3456 | 555-012-3456 | Strip country code |
| John Smith | john smith | Case-insensitive matching |
| J. Smith | j. smith | Abbreviation preserved |
| 123 Main Street | 123 main st | Address normalization |
| 123 Main St. | 123 main st | Punctuation removal |
| ACME Corp. | acme corp | Company name normalization |
| Acme Corporation | acme corporation | Keep full form too |

The entity extraction service should normalize during extraction, and Neptune should store both the raw and normalized forms for flexible matching.

### Scale Considerations for Cross-Case

At 100M documents across thousands of cases:
- Neptune will have billions of entity nodes
- Cross-case queries need to be scoped (don't traverse the entire graph)
- Use Neptune composite indexes on (canonical_name, entity_type)
- Consider Neptune Analytics for large-scale graph analytics (OLAP-style queries)
- OpenSearch aggregations across all case indexes are fast (seconds for keyword, minutes for semantic)

### The "Aha Moment" for the Customer Demo

Show this sequence:
1. Upload 50 documents from 5 different cases
2. Search for a phone number that appears in 2 cases
3. Show the graph visualization connecting the two cases through shared entities
4. Click "Analyze" and let Bedrock explain the connection
5. Create a cross-case investigation linking the cases

This is the moment where the analyst realizes they can find connections that would take weeks of manual review — in seconds.
