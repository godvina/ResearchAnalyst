# TALOS Platform — Product Overview & Competitive Positioning

## Executive Summary

TALOS (Threat Analysis & Logistics Operations System) is a full-stack intelligence platform that combines automated data ingestion, AI-powered entity extraction, prosecution-backed crime pattern detection, and cross-domain convergence analysis. It ingests any data format, automatically extracts entities and relationships, scores every document against 1,100+ prosecution-proven detection signatures across 15 crime types simultaneously, and surfaces cross-domain connections that human analysts would miss.

**One sentence:** "Other tools let you explore your data. We tell you what it means — and cite the prosecution that proves we're right."

---

## Platform Capabilities

### 1. Data Ingestion & Integration

| Feature | Description |
|---------|-------------|
| Multi-format ingestion | PDF, CSV, JSON, JSONL, Parquet, text, images — any format |
| Organization hierarchy | Org → Matter → Collection → Document (multi-tenant, role-based access) |
| AI entity extraction | Automatic extraction of people, organizations, locations, accounts, relationships via Amazon Bedrock |
| Entity resolution | Cross-document deduplication and merging (same person across 500 documents) |
| Graph construction | Automatic Neptune graph building — entities as nodes, relationships as edges |
| Bulk loading | Millions of records via async job pipeline with Redshift COPY, format auto-detection |
| 3-tier cost optimization | 90-95% of junk filtered before AI processing — saves 10x vs. processing everything |
| Provenance tracking | Every datum tagged with source, ingestion timestamp, processing tier |
| S3 data lake | Raw files preserved for audit, reprocessing, and legal discovery |

### 2. Crime Pattern Library (The Differentiator)

| Feature | Description |
|---------|-------------|
| 1,100+ pattern playbooks | Individual crime patterns with detection triggers, indicators, and legal outcomes |
| 15 crime typologies | Drug trafficking, money laundering, cybercrime, human trafficking, antitrust, FEMA fraud, immigration fraud, counterfeiting, sanctions evasion, terrorism financing, public corruption, organized crime, child exploitation, environmental crime, scam centers |
| 150 embedded signatures | Vector-embedded in OpenSearch for real-time k-NN matching |
| 5-level taxonomy | Domain → Typology → Method → Signature → Case Precedent |
| DOJ case backing | Every signature cites a real federal prosecution as validation |
| Self-service expansion | New domain in hours via 3-tier pipeline (filter DOJ corpus → embed → synthesize) |
| FATF/FinCEN integration | Red flag indicators from international standards bodies converted to machine-readable signatures |

### 3. Cross-Domain Convergence Detection

| Feature | Description |
|---------|-------------|
| Simultaneous scoring | Every document scored against ALL 15 typologies at once (not one at a time) |
| Cross-domain flagging | When a document matches 2+ domains it's flagged as "cross-cutting" (highest value) |
| Convergence matrices | Automated detection of method convergence across crime types (e.g., fentanyl × money laundering × sanctions evasion) |
| Example output | "This shipping manifest matches TBML signature AND fentanyl precursor diversion pattern AND sanctions evasion front company indicator" |

### 4. Graph Intelligence

| Feature | Description |
|---------|-------------|
| Relationship mapping | Multi-hop traversal (3-degree networks in <2s for 1M nodes) |
| Network centrality | Degree, betweenness, closeness centrality for entity importance ranking |
| Relationship decay | 3-year half-life on connections — recent relationships weighted higher |
| Staging subgraphs | New data loads into staging, QA reviewed, then promoted to production graph |
| Cross-case connections | Entities shared across matters are surfaced automatically |
| **Pluggable backend** | Adapts to customer's existing graph DB — no rip-and-replace |

#### Supported Graph Backends

| Backend | Query Language | When to use |
|---------|---------------|-------------|
| Aurora PostgreSQL (recursive CTEs) | SQL | Demo/POC, small-scale (<100K entities) |
| Amazon Neptune | Gremlin / openCypher | AWS-native production |
| Neo4j | Cypher | Customer already has Neo4j (banks, pharma) |
| TigerGraph | GSQL | Large-scale analytics (fraud detection) |
| Microsoft Cosmos DB | Gremlin | Azure customers |
| In-memory (JSON) | — | Demos, testing, offline |

Swap via environment variable (`GRAPH_BACKEND=neo4j`). Zero code changes to business logic. The value isn't in the graph database — it's in the intelligence that populates it.

### 5. OSINT Research Agent

| Feature | Description |
|---------|-------------|
| Live web research | Brave Search API + Bedrock Haiku for real-time intelligence gathering |
| Structured extraction | Raw web results → structured entities, relationships, risk scores |
| Multi-source fusion | Combines web search, public databases, news, conference bios, awards |
| Automated scoring | Research results automatically mapped to 25 selection criteria |
| Rate-limited & audited | All research queries logged with provenance |

### 6. Prosecution Support

| Feature | Description |
|---------|-------------|
| Legal reasoning engine | Automatic element analysis against federal statutes |
| Evidence strength assessment | Direct vs. circumstantial evidence classification |
| PCSF red flag taxonomy | Procurement Collusion Strike Force aligned indicators |
| Case readiness scoring | Quantified prosecution readiness with gap identification |
| Document assembly | Auto-generated case summaries, evidence matrices, charging recommendations |

### 7. Executive Succession Planning

| Feature | Description |
|---------|-------------|
| 3-layer scoring engine | Universal Core × Cultural Flex × Sector Parameters |
| 25 selection criteria | Scored against role-specific weight profiles |
| Cultural calibration | 25 countries, GLOBE clusters, Hofstede 6-dimension adjustments |
| Live candidate research | Web agent discovers and scores candidates in real-time |
| Compensation intelligence | Market ranges (P25/P50/P75), comp gaps, cost-of-hire analysis |
| Risk analysis | Flight risk, poachability, cultural adaptation, compliance, non-compete |
| Process tracking | 8-stage pipeline with SLA monitoring |

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                             │
│  Research Analyst UI │ Finding Fentanyl UI │ Succession UI   │
│  (investigator,     │ (trade interdiction,│ (executive      │
│   prosecutor,       │  Pacific ops,       │  talent intel)  │
│   pattern library)  │  FEMA, immigration) │                 │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                    API GATEWAY                                │
│  REST API + Lambda (auto-scaling, pay-per-request)          │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                INTELLIGENCE SERVICES                          │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │  Ingestion   │ │   Pattern    │ │  OSINT Research    │  │
│  │  Pipeline    │ │   Scoring    │ │  Agent             │  │
│  │  (v2 + bulk) │ │  (k-NN)     │ │  (Brave+Bedrock)   │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │  Entity      │ │  Legal       │ │  Succession        │  │
│  │  Extraction  │ │  Reasoning   │ │  Scoring           │  │
│  │  (Bedrock)   │ │  Engine      │ │  Engine            │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                    DATA LAYER                                 │
│  Aurora PostgreSQL │ Neptune Graph │ OpenSearch Serverless   │
│  (structured data, │ (entities,    │ (9 indexes, 22K+       │
│   audit trail,     │  relationships│  vectors, k-NN)        │
│   scoring history) │  centrality)  │                        │
│                    │               │ S3 Data Lake            │
│                    │               │ (raw files, provenance) │
└─────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                    AI LAYER (Amazon Bedrock)                  │
│  Claude (reasoning) │ Titan Embed (vectors) │ Nova (synthesis)│
└─────────────────────────────────────────────────────────────┘
```

### Pre-Processed Intelligence Assets

| Asset | Volume | Coverage |
|-------|--------|----------|
| DOJ Press Releases | 269,000 | 20+ years of federal prosecution history |
| ICIJ Offshore Entities | 165MB | Global offshore corporate structures |
| FinCEN SARs | 3.5MB | Suspicious activity reports, scored |
| CBP Seizures | 20,000 | Border seizure records, embedded |
| Pattern Playbooks | 1,100+ | Individual crime patterns with legal outcomes |
| OpenSearch Vectors | 22,000+ | Pre-embedded across 9 domain indexes |

---

## Competitive Comparison

### vs. Palantir Gotham ($5-20M/year)

| Capability | TALOS | Palantir |
|------------|-------|----------|
| Data ingestion (any format) | ✅ | ✅ |
| Entity extraction | ✅ AI-automatic (zero config) | ⚠️ Manual ontology mapping (weeks of professional services) |
| Entity resolution | ✅ | ✅ (stronger at extreme scale) |
| Graph construction | ✅ Automatic | ✅ Automatic |
| Crime pattern scoring | ✅ 1,100 patterns, automatic at ingest | ❌ None — analyst brings knowledge |
| Cross-domain detection | ✅ 15 domains simultaneous | ❌ |
| Prosecution case backing | ✅ Every signature cites DOJ case | ❌ |
| Cost optimization | ✅ 3-tier (90% savings) | ❌ Processes everything |
| Pre-built intelligence corpus | ✅ 269K DOJ + ICIJ + FinCEN + CBP | ❌ Customer brings all data |
| Self-service domain expansion | ✅ Hours (pipeline template) | ❌ Months (professional services) |
| Cultural/jurisdictional calibration | ✅ 25 countries | ❌ |
| Classified deployment (TS/SCI) | ⚠️ Architecture ready | ✅ Certified |
| Scale (petabytes, 10K+ users) | ⚠️ Not tested at that level | ✅ Proven |
| Professional services team | ❌ Small | ✅ Thousands of engineers |

**Summary:** TALOS has Palantir's data integration + automatic intelligence that Palantir lacks. Palantir has scale certification and professional services that TALOS lacks. For 90% of law enforcement use cases, TALOS delivers more value at lower cost.

### vs. Nasdaq Verafin ($150K-500K/year)

| Capability | TALOS | Verafin |
|------------|-------|---------|
| Transaction monitoring | ✅ | ✅ |
| Typology-based detection | ✅ 15 domains | ⚠️ Financial crime only |
| Multi-source (documents, OSINT, graph) | ✅ | ❌ Transactions only |
| Cross-domain scoring | ✅ | ❌ |
| Pre-built DOJ corpus | ✅ 269K cases | ❌ |
| Consortium insights | ❌ | ✅ (cross-bank data sharing) |
| Regulatory SAR filing | ❌ | ✅ Built-in |

**Summary:** TALOS is broader (multi-source, multi-domain). Verafin is deeper in AML compliance workflow (SAR filing, consortium). Different buyers.

### vs. NICE Actimize ($500K-5M/year)

| Capability | TALOS | NICE Actimize |
|------------|-------|---------------|
| AML transaction monitoring | ✅ | ✅ |
| Fraud detection | ✅ | ✅ |
| Multi-domain crime detection | ✅ 15 domains | ❌ Financial only |
| Document/OSINT analysis | ✅ | ❌ |
| Pre-built prosecution patterns | ✅ | ❌ Rules-based scenarios |
| Graph intelligence | ✅ | ⚠️ Limited |
| AI-powered (generative) | ✅ Bedrock | ⚠️ Traditional ML |

### vs. IBM i2 Analyst's Notebook

| Capability | TALOS | i2 |
|------------|-------|-----|
| Data visualization | ✅ | ✅ (superior link charts) |
| Automatic pattern detection | ✅ | ❌ Manual only |
| Entity extraction | ✅ AI-automatic | ❌ Manual import |
| Graph analysis | ✅ | ✅ |
| Scoring/ranking | ✅ | ❌ |
| Pre-built patterns | ✅ 1,100+ | ❌ |

### vs. Cellebrite / Digital Forensics

| Capability | TALOS | Cellebrite |
|------------|-------|-----------|
| Device data extraction | ❌ | ✅ (superior) |
| Communication pattern analysis | ✅ | ⚠️ Visualization only |
| Pattern scoring | ✅ | ❌ |
| Cross-case intelligence | ✅ | ❌ |
| Graph construction from comms | ✅ | ⚠️ Limited |

---

## Unique Value Propositions

### 1. "Day One Intelligence"
Customers don't start from zero. On day one, they have access to 269K prosecutions analyzed, 1,100+ detection patterns, and 22K+ pre-embedded vectors. No months of ontology mapping, no professional services engagement to "get value." Upload data → get scored intelligence back.

### 2. "Cross-Domain is the Highest-Value Intelligence"
A fentanyl case that also triggers money laundering AND sanctions evasion signatures is worth 100x a single-domain hit. Nobody else scores across all domains simultaneously. This is where the biggest cases live — and where siloed tools miss them entirely.

### 3. "Every Signature Has a Prosecution Behind It"
Not rules. Not ML models trained on synthetic data. Every detection signature is backed by a real DOJ case that went to trial or plea. When the system flags something, it can say: "This matches the pattern from United States v. [Name] — here's what the evidence looked like, here's what they were charged with, here's the sentence."

### 4. "AI Does the Analyst's First 80%"
Entity extraction, relationship mapping, pattern scoring, prosecution readiness assessment — all automatic. The analyst starts at the "investigate further" decision point, not at "read 500 documents and figure out if anything is suspicious."

### 5. "Self-Service Domain Expansion"
New crime type emerges? Filter the DOJ corpus with keywords → embed → synthesize → new domain live in hours. No vendor dependency. No 6-month professional services engagement. The platform learns from the federal prosecution record itself.

### 6. "90% Cost Reduction on Processing"
3-tier pipeline filters junk before spending on AI. A 50,000-document dataset costs $60 to process with TALOS vs. $600+ if you embed/LLM everything. At 1.4M documents: $50-70 vs. $1,800.

---

## Pricing

### Tier Structure

| Tier | Annual Price | What's Included |
|------|-------------|----------------|
| **DETECT** | $300K - $800K | Pattern library + scoring engine + 5 domains + web dashboard + API. 10K docs/month. 5 seats. |
| **INVESTIGATE** | $1M - $3M | Full platform: all 15 domains + 269K DOJ corpus + cross-domain convergence + OSINT agent + graph analysis + prosecution scoring. 100K docs/month. 25 seats. Custom domain development (1). |
| **ENTERPRISE** | $3M - $8M | Everything + unlimited domains + classified deployment option + executive succession module + dedicated support + unlimited volume + data integration services + on-premise/VPC deployment. |

### Add-Ons

| Add-On | Price |
|--------|-------|
| Custom domain development (per domain) | $75K - $150K |
| Additional seats (per seat) | $25K - $50K/year |
| Data integration services (per source) | $100K - $250K one-time |
| Dedicated analyst support | $200K - $400K/year |
| Executive succession module (standalone) | $150K - $500K/year |

### Volume-Based (API)

| Usage | Price |
|-------|-------|
| Per document scored | $0.01 - $0.05 |
| Per transaction monitored | $0.001 - $0.01 |
| Per OSINT research query | $0.50 - $2.00 |

### By Market Segment

| Segment | Typical Deal | Comparison |
|---------|-------------|------------|
| Federal law enforcement (DOJ, DHS, HSI) | $1.5M - $5M/year | Palantir: $5-20M. TALOS delivers more intelligence at lower cost. |
| State/local law enforcement | $100K - $750K/year | Most have NO tool today. TALOS fills the gap below Palantir's floor. |
| Financial institutions (banks) | $300K - $1.5M/year | Verafin: $150-500K. NICE: $500K-5M. TALOS adds multi-domain. |
| Intelligence community / DoD | $3M - $8M/year | Palantir: $10-20M. Requires classified deployment certification. |
| Compliance teams (corporate) | $150K - $500K/year | Currently using manual processes + $50K/year tools. |

---

## ROI Justification

| Scenario | Without TALOS | With TALOS | Impact |
|----------|--------------|------------|--------|
| Antitrust case identification | 6 months analyst time | 2 weeks (pattern match + AI brief) | 90% time reduction |
| SAR review (bank, 1000/month) | 8 analysts full-time | 2 analysts (AI triages, humans verify) | 75% headcount reduction |
| Cross-domain case discovery | Missed entirely (siloed teams) | Automatic flagging | New case revenue |
| DOJ prosecution assessment | 40 hours per case (manual) | 2 hours (auto-element analysis) | 95% time reduction |
| New crime domain build | 6 months + $500K consulting | Hours + $0.15 in AI cost | 99.97% cost reduction |

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Compute | AWS Lambda (serverless) | Auto-scaling, pay-per-invocation |
| Database | Aurora PostgreSQL (+ pgvector) | Structured data, audit trail, RLS multi-tenancy, AND vector search |
| Graph | Pluggable: Aurora SQL / Neptune / Neo4j / TigerGraph / Cosmos DB | Entity relationships, network analysis — customer's choice |
| Vector Search | Aurora pgvector (demo/POC) or OpenSearch Serverless (production scale) | k-NN pattern matching |
| AI | Amazon Bedrock (Claude, Titan, Nova) | Entity extraction, synthesis, reasoning, embeddings |
| Storage | S3 | Data lake, raw document preservation |
| API | API Gateway + Lambda | REST endpoints, auth, rate limiting |
| Frontend | Static HTML/JS + D3.js | Dashboards, visualizations, operational UIs |
| IaC | AWS CDK (Python) | Repeatable deployment |
| Auth | Cognito | User management, JWT tokens |

### Vector Search Strategy

| Scale | Backend | Monthly Cost | Latency |
|-------|---------|-------------|---------|
| Demo/POC (<1K signatures) | Aurora pgvector or in-memory JSON | $0-15 | <100ms |
| Mid-scale (1K-100K vectors) | Aurora pgvector with HNSW index | $15-90 | <200ms |
| Production (100K-10M vectors, high concurrency) | OpenSearch Serverless | $700-5,000 | <50ms |

### Pluggable Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    TALOS Intelligence Layer                   │
│   (Pattern scoring, entity extraction, cross-domain, OSINT) │
└───────────────────────────────┬─────────────────────────────┘
                                │ Adapters
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Vector Store │  │   Graph Store    │  │  Document Store  │
│              │  │                  │  │                  │
│ • pgvector   │  │ • Aurora SQL     │  │ • S3             │
│ • OpenSearch │  │ • Neptune        │  │ • Customer's DMS │
│ • Pinecone   │  │ • Neo4j          │  │                  │
│ • FAISS      │  │ • TigerGraph     │  │                  │
│              │  │ • Cosmos DB      │  │                  │
└──────────────┘  └──────────────────┘  └──────────────────┘
       ▲                    ▲                    ▲
       │         Customer chooses per layer      │
       └────────────────────┴────────────────────┘
```

---

## Deployment Cost Models

### Demo / Internal Development (stopped when idle)

| Service | Running | Idle (stopped) | Notes |
|---------|---------|---------------|-------|
| Aurora PostgreSQL (db.t4g.micro) | $0.018/hr (~$13/mo if 24/7) | **$0.10/mo** (storage only) | Stop cluster when not demoing |
| Lambda + API GW | Pay per request | $0 | Free tier covers demo usage |
| S3 | $0.023/GB | $0.023/GB | <1GB demo data = pennies |
| Bedrock | Pay per query | $0 | Only charged when invoked |
| **Total when stopped** | — | **$0.10 - $1/mo** | |
| **Total demo day** (4 hours) | — | **$0.50 - $2** | Start cluster → demo → stop |
| **Total active week** | — | **$5 - $15** | Running business hours M-F |

### Customer POC (always-on during evaluation)

| Service | Monthly | Notes |
|---------|---------|-------|
| Aurora Serverless v2 (0.5-2 ACU) | $44-175 | Scales with load, pgvector for patterns |
| Lambda + API GW | $5-20 | Light-moderate traffic |
| Bedrock | $50-200 | Entity extraction + scoring on customer data |
| S3 | $5-20 | Customer's uploaded documents |
| **Total** | **$100 - $400/mo** | No OpenSearch, no Neptune for POC |

### Production Deployment (full scale)

| Service | Monthly | Notes |
|---------|---------|-------|
| Aurora Serverless v2 (2-8 ACU) | $175-700 | Structured data + pgvector |
| OpenSearch Serverless | $700-5,000 | High-volume vector search (if needed) |
| Neptune Serverless (or customer's graph) | $90-500 | Graph at scale (if needed) |
| Lambda + API GW | $50-500 | Production traffic |
| Bedrock | $200-2,000 | Volume entity extraction + scoring |
| S3 | $20-200 | Data lake |
| **Total** | **$1,200 - $9,000/mo** | Full production, all features |

### Cost vs. Revenue

| Deployment | Our Cost | Customer Pays | Gross Margin |
|------------|----------|---------------|-------------|
| Demo (idle most of month) | ~$5/mo | — | — |
| POC (3 months) | ~$300/mo | $50K-100K engagement | 97%+ |
| Production (DETECT tier) | ~$1,500/mo | $25K/mo ($300K/yr) | 94% |
| Production (INVESTIGATE tier) | ~$5,000/mo | $125K/mo ($1.5M/yr) | 96% |
| Production (ENTERPRISE tier) | ~$9,000/mo | $400K/mo ($5M/yr) | 98% |

---

## Security & Compliance

| Requirement | Status |
|-------------|--------|
| Multi-tenancy (data isolation) | ✅ Row-Level Security on all tables |
| Audit trail | ✅ Append-only scoring decisions (5-year retention) |
| GDPR/CCPA consent tracking | ✅ Consent records + data rights request tables |
| EU AI Act Article 14 (human override) | ✅ Human override logging with rationale |
| Bias detection | ✅ Four-fifths rule + chi-squared analysis |
| Encryption at rest | ✅ AWS KMS (AES-256) |
| Encryption in transit | ✅ TLS 1.3 |
| GovCloud ready | ✅ Architecture compatible |
| FedRAMP certification | ⚠️ Not yet certified (AWS services are) |
| Classified (TS/SCI) | ⚠️ Architecture ready, not deployed |

---

## Current Scale

| Metric | Value |
|--------|-------|
| Pre-processed intelligence records | 450,000+ |
| Pattern playbooks | 1,100+ |
| OpenSearch vectors | 22,000+ |
| Crime domains | 15 |
| Prosecution-backed signatures | 150 embedded + 1,100 indexed |
| Countries with cultural calibration | 25 |
| Frontend dashboards | 15+ |
| Backend services | 20+ |
| API endpoints | 50+ |
| Unit/property tests | 100+ |

---

*Document version: 1.0 — 2026-08-07*
*Classification: BUSINESS CONFIDENTIAL*
