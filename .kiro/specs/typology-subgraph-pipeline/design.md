# Technical Design Document

## Overview

This design implements a pre-computed typology subgraph pipeline that replaces real-time Neptune graph traversal for large cases (100K+ entities). The system runs asynchronously via AWS Step Functions, extracts typology-specific subgraphs from Neptune, scores them using OpenSearch k-NN and Bedrock, stores results in Aurora, and serves pre-computed data at page-load time.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INGESTION PIPELINE (existing)                     │
│  Documents → Parse → Extract → Embed → Neptune + OpenSearch          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ EventBridge: ingestion.complete
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              TYPOLOGY SUBGRAPH PIPELINE (new)                         │
│                                                                       │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────┐ │
│  │ Threshold│    │  Extract     │    │   Score     │    │ Build  │ │
│  │  Check   │───▶│  Subgraphs   │───▶│  Typologies │───▶│Summary │ │
│  │  Lambda  │    │  (11× Map)   │    │  (11× Map)  │    │ Graph  │ │
│  └──────────┘    └──────────────┘    └─────────────┘    └────────┘ │
│       │                 │                    │                │      │
│       │            Neptune                OpenSearch         Aurora   │
│       │            (read)               + Bedrock           (write)  │
│       ▼                                                      │      │
│  [Skip if < 100K]                                            ▼      │
│                                                    ┌─────────────┐  │
│                                                    │Aurora Tables │  │
│                                                    │(pre-computed)│  │
│                                                    └─────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INVESTIGATOR UI (existing)                         │
│  Case Click → GET /typology-precomputed → Aurora (< 500ms)           │
│  Small cases → existing real-time Neptune path (unchanged)           │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Step Functions State Machine: `TypologySubgraphPipeline`

**Trigger:** EventBridge rule on `ingestion.complete` event OR manual API invoke.

```json
{
  "Comment": "Pre-compute typology subgraphs for large cases",
  "StartAt": "ThresholdCheck",
  "States": {
    "ThresholdCheck": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:threshold-check",
      "Next": "IsLargeCase"
    },
    "IsLargeCase": {
      "Type": "Choice",
      "Choices": [
        { "Variable": "$.is_large_case", "BooleanEquals": true, "Next": "AcquireLock" }
      ],
      "Default": "SkipSmallCase"
    },
    "AcquireLock": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:acquire-pipeline-lock",
      "Next": "ExtractSubgraphs",
      "Catch": [{ "ErrorEquals": ["LockConflict"], "Next": "PipelineAlreadyRunning" }]
    },
    "ExtractSubgraphs": {
      "Type": "Map",
      "ItemsPath": "$.typology_modules",
      "MaxConcurrency": 3,
      "Iterator": { "StartAt": "ExtractSingle", "States": {
        "ExtractSingle": { "Type": "Task", "Resource": "arn:aws:lambda:...:extract-subgraph", "End": true }
      }},
      "Next": "ScoreTypologies"
    },
    "ScoreTypologies": {
      "Type": "Map",
      "ItemsPath": "$.extracted_subgraphs",
      "MaxConcurrency": 3,
      "Iterator": { "StartAt": "ScoreSingle", "States": {
        "ScoreSingle": { "Type": "Task", "Resource": "arn:aws:lambda:...:score-typology", "End": true }
      }},
      "Next": "BuildSummaryGraph"
    },
    "BuildSummaryGraph": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:build-summary-graph",
      "Next": "ReleaseLock"
    },
    "ReleaseLock": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:release-pipeline-lock",
      "Next": "PipelineComplete"
    },
    "PipelineComplete": { "Type": "Succeed" },
    "SkipSmallCase": { "Type": "Succeed" },
    "PipelineAlreadyRunning": { "Type": "Succeed" }
  }
}
```

### 2. Lambda Functions

#### 2.1 `threshold_check_lambda`
- Queries Aurora: `SELECT entity_count FROM case_files WHERE case_id = ?`
- Returns `{ is_large_case: bool, case_id, entity_count, typology_modules: [...] }`
- Determines incremental vs full: checks `staleness_flag` on existing results

#### 2.2 `acquire_pipeline_lock_lambda`
- Attempts INSERT into `pipeline_executions` with status='running'
- Uses `ON CONFLICT DO NOTHING` + row check for lock semantics
- Raises `LockConflict` if another execution is in progress

#### 2.3 `extract_subgraph_lambda` (runs per typology, up to 3 concurrent)
- Input: `{ case_id, typology_module_id, sub_categories: [...] }`
- For each sub-category, runs a targeted Neptune Gremlin query:

```python
# Example: Financial Control sub-category
TYPOLOGY_QUERIES = {
    "financial_control": {
        "entity_types": ["person", "organization", "financial_amount", "account_number"],
        "edge_filter": "has('relationship_type', within('financial','transaction','owns','controls'))",
        "query_template": """
            g.V().hasLabel('{label}')
            .has('entity_type', within({entity_types}))
            .bothE('RELATED_TO').{edge_filter}.limit(5000)
            .project('src','tgt','type','weight')
            .by(outV().values('canonical_name'))
            .by(inV().values('canonical_name'))
            .by('relationship_type')
            .by(coalesce(values('weight'), constant(1)))
        """
    },
    "transportation_movement": {
        "entity_types": ["person", "location"],
        "edge_filter": "has('relationship_type', within('geographic','temporal','co-occurrence'))",
        ...
    }
}
```

- Timeout per query: 300s (full Lambda budget)
- Returns: `{ typology_id, sub_categories: [{ id, entities: [...], edges: [...], entity_count }] }`

#### 2.4 `score_typology_lambda` (runs per typology, up to 3 concurrent)
- Input: extracted subgraph for one typology
- **Step 1 — Flag scoring:** Run existing `SexTraffickingTypologyEngine._score_category()` logic against the extracted entities/relationships (reuse existing weighted flag evaluation)
- **Step 2 — k-NN similarity:** For each sub-category, embed the evidence summary text via Titan Embed v2, then query OpenSearch for k-NN against stored prosecution pattern vectors:

```python
# Embed evidence summary
embedding = bedrock.invoke_model(modelId="amazon.titan-embed-text-v2:0", body={"inputText": evidence_text})

# k-NN query against typology pattern index
knn_query = {
    "query": { "knn": { "embedding": { "vector": embedding, "k": 5 } } },
    "post_filter": { "term": { "typology_id": typology_module_id } }
}
results = opensearch.search(index="typology-patterns", body=knn_query)
cosine_score = results[0]["_score"]  # highest match
```

- **Step 3 — Match strength classification:**
  - Strong: cosine ≥ 0.80
  - Moderate: 0.60 ≤ cosine < 0.80
  - Weak: cosine < 0.60

- **Step 4 — Bedrock narrative (Strong/Moderate only):**

```python
if match_strength in ("strong", "moderate"):
    narrative = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body={ "messages": [{"role": "user", "content": synthesis_prompt}] }
    )
```

- Returns: `{ typology_id, overall_score, sub_category_scores: [...], match_strength, key_entities: [...], narrative }`
- Writes results to Aurora `typology_precomputed_results` table

#### 2.5 `build_summary_graph_lambda`
- Reads all typology results for the case from Aurora
- Identifies Hub_Nodes: entities appearing in 2+ typology subgraphs
- For hub entities, queries Neptune for direct edges between them (small, bounded query):

```python
hub_names = [...]  # 30-50 entities max
query = f"""
    g.V().hasLabel('{label}')
    .has('canonical_name', within({hub_names}))
    .bothE('RELATED_TO')
    .where(otherV().has('canonical_name', within({hub_names})))
    .project('src','tgt','type')
    .by(outV().values('canonical_name'))
    .by(inV().values('canonical_name'))
    .by('relationship_type')
"""
```

- Annotates each node with typology participation and match strengths
- Stores to `typology_summary_graph` table as JSON (vis.js compatible format)

#### 2.6 `release_pipeline_lock_lambda`
- Updates `pipeline_executions` row: status='completed', end_time=NOW()
- Records per-typology timing metrics

### 3. Aurora Schema

```sql
-- Pre-computed typology results (one row per case × typology × sub-category)
CREATE TABLE typology_precomputed_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    typology_module_id VARCHAR(50) NOT NULL,        -- e.g. 'sex_trafficking'
    sub_category_id VARCHAR(50) NOT NULL,           -- e.g. 'financial_control'
    overall_score FLOAT NOT NULL,                   -- 0.0-1.0
    match_strength VARCHAR(20) NOT NULL,            -- 'strong','moderate','weak'
    cosine_similarity FLOAT,                        -- raw k-NN score
    flag_score FLOAT,                               -- weighted flag evaluation score (0-100)
    key_entities JSONB NOT NULL DEFAULT '[]',       -- top 10 entities for this sub-category
    subgraph_summary JSONB NOT NULL DEFAULT '{}',   -- { entity_count, edge_count, hub_entities }
    narrative TEXT,                                  -- Bedrock synthesis (null if weak/pending)
    synthesis_status VARCHAR(20) DEFAULT 'completed', -- 'completed','pending','failed'
    is_stale BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(case_id, typology_module_id, sub_category_id)
);

-- Typology-level aggregated scores (one row per case × typology)
CREATE TABLE typology_precomputed_summary (
    case_id UUID NOT NULL,
    typology_module_id VARCHAR(50) NOT NULL,
    overall_typology_score FLOAT NOT NULL,          -- average of sub-category scores
    match_strength VARCHAR(20) NOT NULL,
    dominant_sub_category VARCHAR(50),
    flags_triggered INTEGER DEFAULT 0,
    total_flags INTEGER DEFAULT 0,
    key_entities JSONB NOT NULL DEFAULT '[]',       -- top entities across all sub-categories
    narrative TEXT,                                  -- typology-level Bedrock summary
    is_stale BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(case_id, typology_module_id)
);

-- Cross-typology summary graph (one row per case)
CREATE TABLE typology_summary_graph (
    case_id UUID PRIMARY KEY,
    nodes JSONB NOT NULL,          -- [{name, type, typologies: [{id, match_strength}], degree}]
    edges JSONB NOT NULL,          -- [{from, to, type, typology_source}]
    hub_count INTEGER NOT NULL,
    cross_typology_entities JSONB, -- entities in 3+ typologies
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_stale BOOLEAN DEFAULT FALSE
);

-- Pipeline execution tracking (Req 9 + Req 10)
CREATE TABLE pipeline_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running','completed','failed','partial'
    trigger_source VARCHAR(50),                     -- 'ingestion','manual','incremental'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    per_typology_timing JSONB,                      -- {typology_id: {extract_ms, score_ms, status}}
    error_message TEXT,
    UNIQUE(case_id, status)                         -- only one 'running' per case (lock)
);

-- Index for fast lookups
CREATE INDEX idx_typology_results_case ON typology_precomputed_results(case_id);
CREATE INDEX idx_typology_results_stale ON typology_precomputed_results(case_id, is_stale) WHERE is_stale = TRUE;
CREATE INDEX idx_pipeline_exec_case ON pipeline_executions(case_id, status);
```

### 4. API Changes

#### New endpoint: `GET /case-files/{id}/typology-precomputed`

```python
def get_precomputed_typology(event, context):
    case_id = event["pathParameters"]["id"]
    
    # Check if pre-computed results exist
    with aurora.cursor() as cur:
        cur.execute("""
            SELECT typology_module_id, overall_typology_score, match_strength,
                   dominant_sub_category, flags_triggered, total_flags,
                   key_entities, narrative, is_stale, computed_at
            FROM typology_precomputed_summary
            WHERE case_id = %s
            ORDER BY overall_typology_score DESC
        """, (case_id,))
        rows = cur.fetchall()
    
    if not rows:
        return {"precomputed": False, "reason": "no_results"}
    
    # Also fetch summary graph
    cur.execute("SELECT nodes, edges, hub_count FROM typology_summary_graph WHERE case_id = %s", (case_id,))
    graph_row = cur.fetchone()
    
    return {
        "precomputed": True,
        "typologies": [row_to_dict(r) for r in rows],
        "summary_graph": graph_row_to_dict(graph_row) if graph_row else None,
        "any_stale": any(r["is_stale"] for r in rows),
    }
```

#### Modified: `GET /case-files/{id}/investigator-analysis`

```python
# In get_analysis():
# Before attempting Command Center compute, check for pre-computed data
entity_count = get_entity_count(case_id)
if entity_count > CASE_ENTITY_THRESHOLD:
    # Serve from Aurora — no Neptune/Bedrock calls
    precomputed = load_precomputed_typology(case_id)
    if precomputed:
        response_data["command_center"] = build_cc_from_precomputed(precomputed)
        return success_response(response_data)
    # else: fallback to time-budgeted live compute (existing logic)
```

### 5. Frontend Changes

#### typology-lens.js modifications:

```javascript
async function _loadTypologyData(caseId) {
    // Try pre-computed first
    try {
        var precomputed = await api('GET', '/case-files/' + caseId + '/typology-precomputed');
        if (precomputed && precomputed.precomputed) {
            _renderPrecomputedTypology(precomputed);
            return;
        }
    } catch(e) { /* fall through to live */ }
    
    // Fallback: existing live computation for small cases
    var data = await api('GET', '/case-files/' + caseId + '/typology');
    // ... existing rendering logic ...
}
```

#### New: Summary Graph panel in Command Center

```javascript
function renderSummaryGraph(graphData) {
    // graphData = { nodes: [...], edges: [...], hub_count }
    // Render using vis.js (already loaded)
    // Color nodes by dominant typology
    // Size nodes by number of typologies they participate in
    // Edge labels show typology source
}
```

### 6. Typology Query Definitions (per module × sub-category)

Each of the 11 modules defines Neptune query templates for its 6 sub-categories. Example for `sex_trafficking`:

```python
SEX_TRAFFICKING_QUERIES = {
    "recruitment_grooming": {
        "entity_types": ["person"],
        "relationship_filter": ["social_media", "contact", "co-occurrence"],
        "indicators": ["age_disparity", "communication_isolation", "love_bombing"],
        "query": "persons with age disparity + high communication frequency"
    },
    "transportation_movement": {
        "entity_types": ["person", "location"],
        "relationship_filter": ["geographic", "temporal"],
        "indicators": ["hotel_clustering", "geographic_velocity", "circuit_rotation"],
        "query": "person→location edges with compressed timeframes"
    },
    "financial_control": {
        "entity_types": ["person", "financial_amount", "account_number", "organization"],
        "relationship_filter": ["financial", "transaction", "controls"],
        "indicators": ["structuring", "controlled_accounts", "quota_evidence"],
        "query": "person→financial entities with structuring patterns"
    },
    "communication_networks": {
        "entity_types": ["person", "phone_number", "email"],
        "relationship_filter": ["communication", "co-occurrence"],
        "indicators": ["disposable_cluster", "star_topology", "coordination_window"],
        "query": "communication entity clusters with star topology"
    },
    "venue_infrastructure": {
        "entity_types": ["person", "location", "organization"],
        "relationship_filter": ["geographic", "co-occurrence", "temporal"],
        "indicators": ["venue_rotation", "multi_location", "ad_posting_cadence"],
        "query": "location entities with rotation patterns"
    },
    "power_control": {
        "entity_types": ["person"],
        "relationship_filter": ["coercive", "financial", "co-occurrence"],
        "indicators": ["debt_ledger", "document_control", "quota_enforcement"],
        "query": "person→person coercive relationship edges"
    }
}
```

### 7. k-NN Pattern Index (OpenSearch)

New dedicated index for prosecution pattern embeddings:

```json
{
  "settings": { "index": { "knn": true } },
  "mappings": {
    "properties": {
      "typology_module_id": { "type": "keyword" },
      "sub_category_id": { "type": "keyword" },
      "pattern_text": { "type": "text" },
      "embedding": {
        "type": "knn_vector",
        "dimension": 1536,
        "method": { "name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib" }
      },
      "source": { "type": "keyword" },
      "severity": { "type": "keyword" }
    }
  }
}
```

Seeded with prosecution pattern descriptions from existing `TYPOLOGY_CATEGORIES` indicators + `EvidenceExample` data from `sex_trafficking_typology.py`.

### 8. Incremental Update Logic

```python
def mark_stale_typologies(case_id: str, new_entity_types: list[str]):
    """After ingestion, determine which typologies need re-computation."""
    # Map entity types to typology modules
    TYPE_TO_TYPOLOGY = {
        "financial_amount": ["sex_trafficking", "money_laundering", "fraud_waste_abuse"],
        "location": ["sex_trafficking", "drug_trafficking", "organized_crime"],
        "phone_number": ["sex_trafficking", "drug_trafficking", "cybercrime"],
        "person": ALL_TYPOLOGIES,  # persons affect everything
        ...
    }
    
    affected = set()
    for etype in new_entity_types:
        affected.update(TYPE_TO_TYPOLOGY.get(etype, []))
    
    # Mark as stale
    with aurora.cursor() as cur:
        cur.execute("""
            UPDATE typology_precomputed_summary
            SET is_stale = TRUE
            WHERE case_id = %s AND typology_module_id = ANY(%s)
        """, (case_id, list(affected)))
        
        cur.execute("""
            UPDATE typology_summary_graph SET is_stale = TRUE WHERE case_id = %s
        """, (case_id,))
```

## Traceability Matrix

| Requirement | Design Component |
|---|---|
| Req 1: Pipeline Trigger | EventBridge rule + Step Functions state machine + ThresholdCheck Lambda |
| Req 2: Subgraph Extraction | extract_subgraph_lambda + TYPOLOGY_QUERIES config |
| Req 3: Scoring | score_typology_lambda + OpenSearch k-NN + Bedrock synthesis |
| Req 4: Aurora Storage | typology_precomputed_results + typology_precomputed_summary tables |
| Req 5: Aurora-First Serving | GET /typology-precomputed endpoint + frontend _loadTypologyData |
| Req 6: Summary Graph | build_summary_graph_lambda + typology_summary_graph table + vis.js render |
| Req 7: Incremental Updates | mark_stale_typologies() + is_stale columns + incremental trigger logic |
| Req 8: Backward Compatibility | ThresholdCheck + entity_count branching in frontend/API |
| Req 9: Health Monitoring | pipeline_executions table + CloudWatch alarm + health API |
| Req 10: Concurrency Safety | acquire_pipeline_lock_lambda + UNIQUE constraint on (case_id, status='running') |
