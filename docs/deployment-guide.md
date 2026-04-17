# Research Analyst Platform — Deployment and Configuration Guide

## Purpose

This guide documents the complete infrastructure setup, configuration, and operational procedures for deploying the Research Analyst document ingestion pipeline. It covers the AWS serverless architecture that processes documents through AI-powered entity extraction, builds knowledge graphs in Neptune, and stores vector embeddings in Aurora pgvector for semantic search.

This guide is designed to be portable — a customer or colleague can follow it to stand up the pipeline in a new AWS account and process millions of documents without hitting the issues we resolved during initial deployment.

---

## Architecture Overview

```
Documents (S3)
    │
    ▼
Step Functions Ingestion Pipeline
    │
    ├── 1. Upload Raw Data → S3 (cases/{case_id}/raw/)
    ├── 2. Parse Document → structured text + sections
    ├── 3. Extract Entities → Bedrock Claude Haiku (chunked)
    │       └── entities + relationships per document
    ├── 4. Generate Embeddings → Bedrock Titan Embed v1
    │       └── 1536-dim vectors stored in Aurora pgvector
    ├── 5. Store Extraction Artifact → S3 JSON
    ├── 6. Graph Load → Neptune (Gremlin HTTP API)
    │       └── entity nodes + relationship edges
    └── 7. Update Case Status → Aurora metadata
```

### AWS Services Used

| Service | Purpose | Configuration |
|---|---|---|
| Aurora Serverless v2 (PostgreSQL + pgvector) | Document metadata, embeddings, case management | 0.5-8 ACU, PostgreSQL 15 |
| Neptune Serverless | Knowledge graph (entities + relationships) | 1-128 NCU |
| S3 | Raw document storage, extraction artifacts | Standard bucket |
| Lambda | All compute (13 functions) | Python 3.12, VPC-attached |
| Step Functions | Pipeline orchestration | Standard workflow |
| Bedrock | Entity extraction (Claude Haiku), embeddings (Titan) | On-demand |
| API Gateway | REST API for frontend/external access | Regional |
| RDS Proxy | Connection pooling for Aurora | PostgreSQL engine |
| Secrets Manager | Database credentials | Auto-rotated |

---

## Critical Infrastructure Configuration

These are the items that caused deployment failures and must be configured correctly from the start.

</text>
</invoke>

### 1. VPC Endpoint Security Groups (CRITICAL)

CDK creates a separate security group for each Lambda function. VPC Interface Endpoints (Bedrock, Secrets Manager, Step Functions) each have their own security group. **Every Lambda SG that needs to reach an endpoint must be added to that endpoint's SG inbound rules.**

Failure mode: Lambda gets "Connect timeout on endpoint URL" — it resolves the private DNS but the SG blocks the TCP connection.

**Required inbound rules:**

```
Bedrock Runtime VPC Endpoint SG (port 443):
  ← Extract Lambda SG
  ← Embed Lambda SG
  ← Search Lambda SG
  ← Patterns Lambda SG
  ← All other Lambda SGs that call Bedrock

Secrets Manager VPC Endpoint SG (port 443):
  ← ALL Lambda SGs (every Lambda needs DB credentials)

Step Functions VPC Endpoint SG (port 443):
  ← Ingestion API Lambda SG (triggers pipeline)

RDS Proxy SG (port 5432):
  ← ALL Lambda SGs that access Aurora

Neptune SG (port 8182):
  ← Graph Load Lambda SG
  ← Patterns Lambda SG
  ← CrossCase Lambda SG
  ← DrillDown Lambda SG
  ← Update Status Lambda SG
```

**CDK implementation pattern:**
```python
# After creating all Lambdas, collect their SGs and add to endpoint SGs
for lambda_fn in all_lambda_functions:
    bedrock_endpoint_sg.add_ingress_rule(
        lambda_fn.connections.security_groups[0],
        ec2.Port.tcp(443),
        "Lambda access to Bedrock"
    )
    secrets_endpoint_sg.add_ingress_rule(
        lambda_fn.connections.security_groups[0],
        ec2.Port.tcp(443),
        "Lambda access to Secrets Manager"
    )
    rds_proxy_sg.add_ingress_rule(
        lambda_fn.connections.security_groups[0],
        ec2.Port.tcp(5432),
        "Lambda access to RDS Proxy"
    )
```

### 2. VPC Endpoints Required

| Endpoint | Type | Private DNS | Purpose |
|---|---|---|---|
| `com.amazonaws.{region}.bedrock-runtime` | Interface | Yes | Entity extraction + embeddings |
| `com.amazonaws.{region}.secretsmanager` | Interface | Yes | DB credential retrieval |
| `com.amazonaws.{region}.states` | Interface | Yes | Step Functions API calls |
| `com.amazonaws.{region}.lambda` | Interface | Yes | Lambda self-invoke for async batch processing |
| `com.amazonaws.{region}.aoss` | Interface | Yes | OpenSearch Serverless vector search |
| `com.amazonaws.{region}.s3` | Gateway | N/A | S3 access (route table) |

VPC must have `enableDnsSupport: true` and `enableDnsHostnames: true` for private DNS resolution.

**CRITICAL: Lambda VPC Endpoint** — Without this, the batch loader's async self-invocation silently fails. The Lambda can receive API Gateway requests (API GW invokes it directly), but cannot call `lambda.invoke()` to trigger the async worker. The VPC endpoint's security group must allow inbound HTTPS (443) from the Lambda's security group.

### 2b. Consolidated Lambda Architecture (500-Resource Limit)

All API routes are consolidated into a single `case_files` Lambda dispatcher using `LambdaRestApi` with `proxy=True`. This reduces the stack from 567 resources to ~100, well under CloudFormation's 500-resource limit.

**Key design decisions:**
- Single API Lambda (`case_files.py` dispatch_handler) routes all HTTP requests
- 10 separate ingestion Lambdas (referenced by Step Functions)
- `LambdaRestApi` with `proxy=True` creates a single `{proxy+}` catch-all route
- `ACCESS_CONTROL_ENABLED=false` must be set in Lambda env vars (no auth layer yet)
- `batch_loader` modules must be copied from `scripts/batch_loader/` to `src/batch_loader/` with imports changed from `scripts.batch_loader.*` to `batch_loader.*`
- `config/aws_pricing.json` must be copied to `src/config/aws_pricing.json` for Lambda packaging

### 2c. Step Functions ASL Substitutions

The ASL definition uses placeholder names that must exactly match CDK `definition_substitutions` keys:

```python
definition_substitutions={
    "IngestionUploadLambdaArn": ingestion_lambdas["upload"].function_arn,
    "IngestionParseLambdaArn": ingestion_lambdas["parse"].function_arn,
    "IngestionExtractLambdaArn": ingestion_lambdas["extract"].function_arn,
    "IngestionEmbedLambdaArn": ingestion_lambdas["embed"].function_arn,
    "IngestionStoreArtifactLambdaArn": ingestion_lambdas["store_artifact"].function_arn,
    "IngestionGraphLoadLambdaArn": ingestion_lambdas["graph_load"].function_arn,
    "IngestionUpdateStatusLambdaArn": ingestion_lambdas["update_status"].function_arn,
    # ASL uses shorter names for these three:
    "ResolveConfigLambdaArn": ingestion_lambdas["resolve_config"].function_arn,
    "ClassificationLambdaArn": ingestion_lambdas["extract"].function_arn,
    "RekognitionLambdaArn": ingestion_lambdas["rekognition"].function_arn,
}
```

### 3. Document Chunking for Entity Extraction (CRITICAL)

Large documents (>10K characters) must be chunked before sending to Bedrock for entity extraction. Without chunking, Bedrock response times exceed Lambda timeout limits.

**Configuration:**
```python
CHUNK_SIZE = 10_000       # characters per chunk
CHUNK_OVERLAP = 500       # overlap to catch boundary entities
```

**How it works:**
1. Split document text into overlapping chunks
2. Extract entities from each chunk independently via Bedrock
3. Merge entities across chunks: deduplicate by (canonical_name, entity_type), sum occurrence counts, keep max confidence, union source document refs
4. Extract relationships from each chunk (passing the full merged entity list for context)
5. Deduplicate relationships by (source_entity, target_entity, relationship_type)

**Why overlap:** Entities mentioned at chunk boundaries (e.g., a name split across chunks) are captured by both adjacent chunks and deduplicated during merge.

**Fault tolerance:** If one chunk fails extraction, remaining chunks still produce results. The pipeline continues with partial data rather than failing the entire document.

### 4. Embedding Text Truncation

Bedrock Titan Embed v1 has an 8,192 token limit (~25,000 characters). Documents exceeding this are truncated to 25,000 characters for embedding generation.

```python
embed_text = raw_text[:25_000] if len(raw_text) > 25_000 else raw_text
```

This is acceptable because:
- The first portion captures primary topics for semantic search
- Full text is stored in Aurora `raw_text` column for retrieval
- Entity extraction uses chunking (above) so no entities are lost

### 5. Bedrock Client Configuration

All Lambda functions calling Bedrock must use explicit timeout configuration:

```python
from botocore.config import Config

bedrock_config = Config(
    read_timeout=120,       # 2 min max per Bedrock call
    connect_timeout=10,     # 10s TCP connection timeout
    retries={"max_attempts": 2, "mode": "adaptive"},
)
bedrock = boto3.client("bedrock-runtime", config=bedrock_config)
```

Without this, the default boto3 client will hang indefinitely if the VPC endpoint connection stalls.

### 6. Neptune HTTP API (Not WebSocket)

Neptune Gremlin queries must use the HTTP API, not the WebSocket-based gremlinpython library.

**Why:** Lambda functions in a VPC experience cold starts where the WebSocket handshake exceeds the init phase timeout. The HTTP API uses standard HTTPS requests through the VPC endpoint.

```python
import urllib.request, json, ssl

def gremlin_http(query: str, endpoint: str, port: str = "8182") -> dict:
    url = f"https://{endpoint}:{port}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))
```

### 7. Secrets Manager for Database Credentials

Lambda functions in a VPC cannot use environment variable credentials directly. Database credentials must be retrieved from Secrets Manager via the VPC endpoint.

```python
import boto3, json

_cached_secret = None

def get_db_secret(secret_arn: str) -> dict:
    global _cached_secret
    if _cached_secret is not None:
        return _cached_secret
    try:
        sm = boto3.client("secretsmanager")
        resp = sm.get_secret_value(SecretId=secret_arn)
        _cached_secret = json.loads(resp["SecretString"])
        if not _cached_secret.get("password"):
            raise ValueError("Secret missing 'password' field")
        return _cached_secret
    except Exception as e:
        _cached_secret = None  # Don't cache failures
        raise RuntimeError(f"Failed to get DB secret: {e}") from e
```

**Key:** Never cache a failed secret retrieval. Set `_cached_secret = None` on failure so the next invocation retries.

### 8. JSON Response Parsing Resilience

Bedrock LLM responses sometimes include text preambles before the JSON array. Use a two-pass parser:

```python
def parse_json_response(text: str) -> list[dict]:
    cleaned = text.strip()
    # Strip markdown code fences
    if cleaned.startswith("```"):
        cleaned = cleaned[cleaned.index("\n") + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    # Pass 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Pass 2: find JSON array in text
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass
    return []  # Return empty rather than crash
```


---

## Lambda Function Configuration

| Function | Handler | Timeout | Memory | Purpose |
|---|---|---|---|---|
| CaseFiles (mega-dispatcher) | `lambdas.api.case_files.dispatch_handler` | 300s | 512 MB | All API routes + batch loader async worker |
| IngestionUpload | `lambdas.ingestion.upload_handler.handler` | 120s | 512 MB | Upload raw files to S3 |
| IngestionParse | `lambdas.ingestion.parse_handler.handler` | 60s | 256 MB | Parse documents to structured text |
| IngestionExtract | `lambdas.ingestion.extract_handler.handler` | 300s | 512 MB | Entity extraction via Bedrock (chunked) |
| IngestionEmbed | `lambdas.ingestion.embed_handler.handler` | 300s | 512 MB | Embedding generation via Bedrock |
| IngestionStoreArtifact | `lambdas.ingestion.store_artifact_handler.handler` | 60s | 256 MB | Store extraction JSON to S3 |
| IngestionGraphLoad | `lambdas.ingestion.graph_load_handler.handler` | 900s | 1024 MB | Load entities/relationships to Neptune |
| IngestionUpdateStatus | `lambdas.ingestion.update_status_handler.handler` | 60s | 256 MB | Update case status in Aurora |
| IngestionResolveConfig | `lambdas.ingestion.resolve_config_handler.handler` | 60s | 256 MB | Resolve pipeline config per case |
| IngestionRekognition | `lambdas.ingestion.rekognition_handler.handler` | 900s | 1024 MB | Image analysis via Rekognition |
| EntityResolution | `lambdas.ingestion.entity_resolution_handler.handler` | 900s | 1024 MB | Cross-document entity dedup |

### Required Environment Variables (all Lambda functions)

```
AURORA_PROXY_ENDPOINT    = <RDS Proxy endpoint>
AURORA_DB_NAME           = research_analyst
AURORA_SECRET_ARN        = <Secrets Manager ARN for DB credentials>
NEPTUNE_ENDPOINT         = <Neptune cluster endpoint>
NEPTUNE_PORT             = 8182
S3_DATA_BUCKET           = <S3 bucket name>
S3_BUCKET_NAME           = <S3 bucket name>  (alias)
BEDROCK_LLM_MODEL_ID    = anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_EMBEDDING_MODEL_ID = amazon.titan-embed-text-v2:0
BULK_LOAD_THRESHOLD      = 20
ACCESS_CONTROL_ENABLED   = false  (CRITICAL — without this, all API calls return 401)
STATE_MACHINE_ARN        = <Step Functions state machine ARN>  (CaseFiles Lambda only)
OPENSEARCH_ENDPOINT      = <AOSS collection endpoint>
OPENSEARCH_COLLECTION_ID = <AOSS collection ID>
```

---

## Step Functions Pipeline Configuration

The ingestion pipeline is defined in `infra/step_functions/ingestion_pipeline.json`.

### Pipeline Flow

```
CheckUploadResult (Choice)
  ├── upload_result exists → ProcessDocuments
  └── no upload_result → UploadRawData → ProcessDocuments

ProcessDocuments (Map, concurrency=5)
  └── Per document:
      ParseDocument → ExtractEntities → GenerateEmbedding → StoreExtractionArtifact
      (failures route to LogDocumentFailure, non-fatal)

ChooseGraphLoadStrategy (Choice)
  ├── document_count >= 20 → BulkCSVLoad
  └── document_count < 20 → GremlinLoad

UpdateCaseStatusIndexed → PipelineComplete (Succeed)

Errors → SetStatusError → PipelineFailed (Fail)
```

### Key Configuration

- **Pipeline timeout:** 24 hours (for large batches)
- **Map concurrency:** 5 (balances throughput vs Bedrock rate limits)
- **Retry policy:** 3 attempts, exponential backoff (2x), starting at 2-5 seconds
- **CheckUploadResult:** Enables re-running the pipeline without re-uploading files

### Triggering the Pipeline

```bash
# Create input JSON
cat > sfn-input.json << 'EOF'
{
  "case_id": "<case-uuid>",
  "upload_result": {
    "document_ids": ["<doc-uuid-1>", "<doc-uuid-2>", ...],
    "document_count": <N>
  }
}
EOF

# Start execution
aws stepfunctions start-execution \
  --state-machine-arn <state-machine-arn> \
  --name "run-$(date +%Y%m%d%H%M%S)" \
  --input file://sfn-input.json
```

---

## Database Schema

### Aurora PostgreSQL

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE case_files (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'created'
        CHECK (status IN ('created','ingesting','indexed','investigating','archived','error')),
    parent_case_id UUID REFERENCES case_files(case_id) ON DELETE SET NULL,
    s3_prefix VARCHAR(512) NOT NULL,
    neptune_subgraph_label VARCHAR(255) NOT NULL,
    document_count INT DEFAULT 0,
    entity_count INT DEFAULT 0,
    relationship_count INT DEFAULT 0,
    error_details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_file_id UUID NOT NULL REFERENCES case_files(case_id) ON DELETE CASCADE,
    source_filename VARCHAR(512),
    source_metadata JSONB,
    raw_text TEXT,
    sections JSONB,
    embedding vector(1536),
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_documents_case ON documents(case_file_id);
CREATE INDEX idx_documents_embedding ON documents
    USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
```

### Neptune Graph Model

```
Node label:  Entity_{case_id}
Node properties:
  - canonical_name (String)
  - entity_type (String: person|location|date|artifact|civilization|theme|event)
  - confidence (Float: 0.0-1.0)
  - occurrence_count (Integer)
  - case_file_id (String)

Edge label:  RELATED_TO
Edge properties:
  - relationship_type (String: co-occurrence|causal|temporal|geographic|thematic)
  - confidence (Float: 0.0-1.0)
  - case_file_id (String)
```

---

## Processing Estimates

| Document Count | Avg Doc Size | Extract Time | Embed Time | Graph Load | Total |
|---|---|---|---|---|---|
| 10 docs | 60K chars | ~3 min | ~2 min | ~1 min | ~6 min |
| 100 docs | 60K chars | ~30 min | ~15 min | ~5 min | ~50 min |
| 1,000 docs | 60K chars | ~5 hrs | ~2.5 hrs | ~30 min | ~8 hrs |
| 4,000 docs | varies | ~20 hrs | ~8 hrs | ~2 hrs | ~30 hrs |

With Map concurrency of 5, divide extract + embed times by 5.

### Cost Estimates (Bedrock on-demand pricing)

- Entity extraction: ~$0.005/doc (Haiku, ~14 calls/doc for 7 chunks × 2 passes)
- Embeddings: ~$0.0001/doc (Titan Embed)
- Total for 4,000 docs: ~$20-25
- Total for 240 docs: ~$1.50

---

## Operational Procedures

### Monitoring a Running Pipeline

```bash
# Check execution status
aws stepfunctions describe-execution \
  --execution-arn <execution-arn> \
  --query "{status:status,startDate:startDate,stopDate:stopDate}"

# Watch entity extraction progress
aws logs tail /aws/lambda/<extract-lambda-name> \
  --since 5m --format short | grep "Extraction complete"

# Watch embedding progress
aws logs tail /aws/lambda/<embed-lambda-name> \
  --since 5m --format short | grep "Stored embedding"

# Check for failures
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn> --reverse-order \
  --query "events[?type=='LambdaFunctionFailed'].lambdaFunctionFailedEventDetails"
```

### Verifying Graph Data in Neptune

```bash
# Count entities for a case
curl -s -X POST "https://<neptune-endpoint>:8182/gremlin" \
  -H "Content-Type: application/json" \
  -d '{"gremlin": "g.V().hasLabel(\"Entity_<case_id>\").count()"}'

# Count relationships
curl -s -X POST "https://<neptune-endpoint>:8182/gremlin" \
  -H "Content-Type: application/json" \
  -d '{"gremlin": "g.V().hasLabel(\"Entity_<case_id>\").outE().count()"}'
```

### Common Failure Modes and Fixes

| Symptom | Root Cause | Fix |
|---|---|---|
| "Connect timeout on endpoint URL" | Lambda SG not in VPC endpoint SG inbound | Add Lambda SG to endpoint SG on port 443 |
| "fe_sendauth: no password supplied" | Secrets Manager call failing silently | Check Secrets Manager VPC endpoint SG rules; verify secret has password field |
| "Sandbox.Timedout" at 120s | Lambda timeout too low for chunked extraction | Increase to 300s |
| "expected maxLength: 50000" | Embedding text exceeds Titan limit | Truncate to 25K chars |
| "Too many input tokens: 8192" | Embedding text exceeds Titan token limit | Truncate to 25K chars |
| "Expecting value: line 1 column 1" | Bedrock returned non-JSON response | Use two-pass JSON parser with array search fallback |
| WebSocket timeout on Neptune | gremlinpython WebSocket fails in VPC Lambda | Use Neptune HTTP API instead |
| "CaseFileService missing argument" | Old Lambda code deployed | Redeploy all Lambdas from updated zip |
| 401 UNAUTHORIZED on all API calls | ACCESS_CONTROL_ENABLED not set to "false" | Add `ACCESS_CONTROL_ENABLED=false` to Lambda env vars |
| "No module named 'scripts'" in Lambda | batch_loader modules not in Lambda package | Copy `scripts/batch_loader/` to `src/batch_loader/` and fix imports |
| Batch stuck in "discovery" phase | Lambda self-invoke fails (no Lambda VPC endpoint) | Create `com.amazonaws.{region}.lambda` VPC endpoint with Lambda SG access |
| AOSS policies "already exists" on deploy | Orphaned AOSS resources from failed deploys | Delete via AWS CLI before redeploying (see cleanup section below) |
| AOSS VPC endpoint DNS conflict | Orphaned VPC endpoint from rollback | Delete orphaned endpoint: `aws ec2 delete-vpc-endpoints --vpc-endpoint-ids <id>` |
| Step Functions "invalid resource ARN" | ASL placeholder names don't match CDK substitutions | Ensure CDK `definition_substitutions` keys match ASL `${...}` placeholders exactly |
| CloudFormation 500-resource limit | Too many individual Lambdas + API Gateway routes | Consolidate into single Lambda dispatcher + `LambdaRestApi` with `proxy=True` |
| Security group DELETE_FAILED during cleanup | Old Lambda ENIs still attached | Harmless — CloudFormation retries; doesn't affect running stack |
| POST/PUT returns 500 but Lambda works directly | `{proxy+}` pathParameters missing `id` | Deploy updated `case_files.py` with `_normalize_resource` pathParameters extraction (Issue 15) |
| `create-deployment` fails "No integration defined" | Orphaned routes from `add_routes.py` | Delete all routes except `/` and `/{proxy+}`, recreate OPTIONS MOCK, redeploy (Issue 16) |

### AOSS Orphan Cleanup Procedure

When CDK deploys fail and roll back, OpenSearch Serverless resources become orphaned. Run this before redeploying:

```bash
# 1. Delete orphaned AOSS VPC endpoints
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=com.amazonaws.us-east-1.aoss" \
  --query "VpcEndpoints[].VpcEndpointId" --output text | \
  xargs -r aws ec2 delete-vpc-endpoints --vpc-endpoint-ids

# 2. Delete orphaned AOSS collection
aws opensearchserverless list-collections \
  --query "collectionSummaries[?name=='research-analyst-search'].id" --output text | \
  xargs -r -I{} aws opensearchserverless delete-collection --id {}

# 3. Delete orphaned AOSS policies
aws opensearchserverless delete-security-policy --name research-analyst-search-enc --type encryption 2>/dev/null
aws opensearchserverless delete-security-policy --name research-analyst-search-net --type network 2>/dev/null
aws opensearchserverless delete-access-policy --name research-analyst-search-dap --type data 2>/dev/null

# 4. Wait for VPC endpoint deletion (takes ~30s)
sleep 30

# 5. Verify clean
aws ec2 describe-vpc-endpoints --filters "Name=service-name,Values=com.amazonaws.us-east-1.aoss" --query "VpcEndpoints[].State"
aws opensearchserverless list-collections --query "collectionSummaries[?name=='research-analyst-search']"
```

---

## File Structure Reference

```
src/
├── db/
│   ├── connection.py              # Aurora connection via Secrets Manager + RDS Proxy
│   ├── neptune.py                 # Neptune connection helper
│   └── schema.sql                 # Aurora DDL
├── lambdas/
│   ├── api/                       # API Gateway handlers
│   │   ├── case_files.py
│   │   ├── ingestion.py
│   │   ├── search.py
│   │   ├── patterns.py
│   │   ├── cross_case.py
│   │   └── drill_down.py
│   └── ingestion/                 # Step Functions pipeline handlers
│       ├── upload_handler.py
│       ├── parse_handler.py
│       ├── extract_handler.py     # Chunked entity extraction
│       ├── embed_handler.py       # Truncated embedding generation
│       ├── store_artifact_handler.py
│       ├── graph_load_handler.py  # Neptune HTTP API
│       └── update_status_handler.py
├── models/                        # Pydantic data models
├── services/                      # Business logic
│   ├── entity_extraction_service.py  # Chunking + merge logic
│   ├── ingestion_service.py
│   ├── case_file_service.py
│   ├── neptune_graph_loader.py
│   ├── pattern_discovery_service.py
│   ├── semantic_search_service.py
│   └── cross_case_service.py
└── storage/
    └── s3_helper.py

infra/
├── cdk/
│   ├── app.py
│   └── stacks/
│       └── research_analyst_stack.py  # Full CDK stack
├── step_functions/
│   └── ingestion_pipeline.json        # ASL definition
└── api_gateway/
    └── api_definition.yaml            # OpenAPI spec
```
