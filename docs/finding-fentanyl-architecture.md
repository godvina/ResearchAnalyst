# Finding Fentanyl — Architecture Decision Document

**Date:** May 1, 2026  
**Status:** Strategic Planning  
**Decision:** New separate project, shared infrastructure modules from Investigative Intelligence  
**Stakeholders:** FDA, DEA, CBP (CTOs aligned, DEA CIO + Trump appointee aligned)  
**Data Partners:** Sayari (20-year enterprise license, graph format, fentanyl risk flags)

---

## 1. Problem Statement

~100,000 Americans die annually from fentanyl and synthetic opioid overdoses. For every death, multiple families are impacted and current users are at imminent risk. Federal agencies (CBP, DEA, FDA) each have pieces of the interdiction puzzle but operate in silos with limited AI-assisted decision support.

**Core challenge:** Filter millions of daily transactions (travelers, packages, cargo containers) to identify which ones to stop and inspect, then generate intelligent inspection protocols that maximize hit rates.

---

## 2. Decision: Separate Project

### Why Not Build in Investigative Intelligence?

| Dimension | Investigative Intelligence | Finding Fentanyl |
|-----------|---------------------------|------------------|
| Timing | Post-hoc analysis | Real-time decisioning |
| Volume | Thousands of case docs | Millions of daily transactions |
| Latency | Minutes acceptable | Sub-second for scoring |
| Users | Investigators, prosecutors | CBP officers, FDA inspectors, DEA agents |
| Core loop | Ingest → Extract → Graph → Analyze | Score → Triage → Inspect → Escalate |
| Data model | Documents, entities, relationships | Transactions, shipments, travelers, risk scores |

### What to Reuse (Shared Infrastructure)

- Neptune graph infrastructure (CDK constructs, graph loader patterns)
- Entity extraction service (adapted for shipping/trade entities)
- Entity resolution service (critical for phoenix company detection)
- Network discovery service (finding hidden connections)
- Pattern discovery service (anomaly detection patterns)
- AI analysis engine (adapted for risk explanation generation)
- Batch ingestion pipeline (for Sayari data loads)
- Access control framework (multi-department, need-to-know)
- Configurable pipeline concept (different configs per department)

---

## 3. Two-Step Process Architecture

### Step 1: Risk Scoring Engine (Filter)

Process millions of daily transactions through a multi-factor risk algorithm.

**Input streams:**
- ACE (Automated Commercial Environment) entry data
- AMS (Automated Manifest System) for cargo
- ABI (Automated Broker Interface) filings
- APIS (Advance Passenger Information System) for travelers
- Sayari graph data (20 years shipping history + fentanyl risk flags)
- FDA Prior Notice data
- Historical enforcement actions (DEA, CBP, FDA)

**Risk scoring dimensions:**

1. **Entity risk** — Is this shipper/importer/consignee flagged? Shell company indicators? Phoenix company (closed and reopened)?
2. **Route risk** — Known transshipment corridor? Sudden route change? Origin country risk level?
3. **Commodity risk** — Precursor chemical? Mislabeling indicators? HS code anomalies?
4. **Behavioral risk** — New importer? Volume spike? Pattern deviation from baseline?
5. **Network risk** — Connected to known bad actors in graph? Shared infrastructure with flagged entities?
6. **Financial risk** — Value anomalies? De minimis abuse? Undervaluation patterns?
7. **Temporal risk** — Timing patterns? Frequency anomalies?

**Output:** Composite risk score (0-100) with explainability — which factors fired and why.

### Step 2: Inspection Protocol Generator (Act)

For items/travelers exceeding the risk threshold, Gen AI generates contextual inspection guidance:

- Specific questions to ask the traveler based on their risk profile
- What to look for in the package/container based on commodity and risk factors
- Suggested field test priorities
- Related cases/seizures to reference
- Escalation criteria (when to call DEA vs handle at port)

---

## 4. Adversary Tactics (How Cartels Move Fentanyl)

Understanding the adversary is critical to building effective detection:

- **Precursor sourcing**: NPP, ANPP, 4-AP from China, mislabeled as "industrial chemicals," "pigments," or "pharmaceutical intermediates"
- **Transshipment**: Route through Mexico, increasingly Vietnam, India, Myanmar, West Africa to avoid scrutiny. Rotate routes based on enforcement heat.
- **Shell/Phoenix companies**: Open Company A, get caught, close it, open Company B next door with cousin's name. Same warehouse, same patterns.
- **Micro-dosing shipments**: Break bulk into thousands of small packages under de minimis threshold ($800) via e-commerce/postal
- **Legitimate business fronts**: Mix illicit with legitimate goods. 95% real auto parts, 5% precursors.
- **Traveler mules**: Body carry, luggage concealment on high-traffic routes
- **Cargo container hiding**: Concealed compartments, mixed with legitimate goods, mislabeled manifests
- **Pill press operations**: Ship precursors separately, assemble domestically. Press ships as "industrial equipment"
- **Dark web coordination**: Orders online, fulfilled through postal/courier
- **Tariff arbitrage overlap**: Same transshipment networks used for tariff evasion AND drug movement

---

## 5. Detection Patterns (How to Catch Them)

- **Velocity anomalies**: New company, sudden high volume. Legitimate importers ramp gradually.
- **Route anomalies**: Product X always from Country A, now suddenly from Country B
- **Network clustering**: Same beneficial owner, freight forwarder, customs broker across multiple "unrelated" companies
- **Weight/value mismatches**: Declared value doesn't match weight or commodity code. Fentanyl is extremely dense in value-per-gram.
- **Commodity code gaming**: Switching HS codes to avoid automated flags
- **Address clustering**: Multiple companies at same address, or residential/virtual offices for "chemical companies"
- **Temporal patterns**: Shipments timed for shift changes, holidays, low-staffing periods
- **Correspondent patterns**: Same sender in China shipping to multiple "unrelated" receivers
- **Return/refusal patterns**: High rates of refused/returned shipments (testing the system)
- **Financial signals**: Wire transfers from money laundering jurisdictions preceding shipments

---

## 6. Legitimate Trade Patterns (Minimize False Positives)

Legitimate importers have:
- Established history (years of consistent importing)
- Consistent commodity codes, volumes, and routes
- Proper documentation (certificates of analysis, MSDS sheets, FDA prior notice)
- Known customs brokers with clean records
- Gradual volume changes tied to business cycles
- Proper bonding and insurance
- Responsive to CBP inquiries with documentation
- CTPAT membership (trusted trader program)

---

## 7. Cross-Department Joint Solution

```
┌─────────────────────────────────────────────────────────┐
│              SHARED INTELLIGENCE LAYER                    │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Entity Graph │  │ Risk Scoring │  │ AI Analysis   │  │
│  │ (Neptune)    │  │ Engine       │  │ Engine        │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Sayari Data │  │ Pattern      │  │ Alert/Trawler │  │
│  │ Integration │  │ Discovery    │  │ System        │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │   CBP   │         │   DEA   │         │   FDA   │
    │ Module  │         │ Module  │         │ Module  │
    ├─────────┤         ├─────────┤         ├─────────┤
    │• Border │         │• Case   │         │• Package│
    │  scoring│         │  building│         │  triage │
    │• Cargo  │         │• Network│         │• Inspect│
    │  inspect│         │  mapping│         │  queue  │
    │• Traveler│        │• Precursor│       │• Lab    │
    │  question│        │  tracking│        │  priority│
    │• Tariff │         │• Seizure│         │• Import │
    │  evasion│         │  intel  │         │  alerts │
    └─────────┘         └─────────┘         └─────────┘
```

**Cross-department intelligence sharing:**
- CBP flags a shipment → DEA gets notified if it matches an active investigation
- DEA takes down a lab → CBP gets updated entity/address watchlist automatically
- FDA refuses a package → risk score increases for that shipper across all departments
- Sayari phoenix company detection → all three departments alerted simultaneously

---

## 8. FDA Inspection Hit Rate Improvement

**Current state:** Packages on a table, agents inspect semi-randomly or based on basic rules.

**Improved state:**
- **Pre-arrival scoring**: Before packages arrive, scored and ranked
- **Smart queue**: Highest-risk packages inspected first, lowest-risk fast-tracked
- **Inspection guidance**: AI tells inspector what to look for in THIS specific package
- **Feedback loop**: Inspection results feed back into model (hit/miss data improves scoring)
- **Throughput math**: If current hit rate is 2% and we get to 15%, that's 7.5x more effective use of inspector time

**FDA-specific process:**
- Prioritized inspection queue (highest risk first)
- AI-suggested inspection focus areas per package
- Expected vs. declared contents analysis
- Cross-reference with FDA import alerts and prior violations
- Recommended lab test priorities
- Track inspector efficiency metrics

---

## 9. Tariff Evasion / Transshipment Detection (Bonus Use Case)

Same engine, different risk factors:

- **Sudden origin shifts**: Product historically from China now routing through Vietnam/Cambodia/Malaysia
- **Value manipulation**: Declared values dropping to avoid tariff thresholds
- **Commodity code shifting**: Same product, different HS code for lower tariff rate
- **Transshipment indicators**: Minimal value-add in intermediate country, same packaging, same manufacturer
- **Country of origin fraud**: "Made in Vietnam" labels on products with Chinese characteristics

**Key insight:** The same network analysis that catches fentanyl transshipment catches tariff evasion transshipment. Same shell companies, same freight forwarders, same patterns. One investment, two missions.

---

## 10. Data Sources & Integration

### Sayari Data (Available Now)
- 20 years of shipping data (CBP enterprise license)
- Graph format (natural fit for Neptune)
- Fentanyl risk flag built in
- Phoenix company detection (closed → reopened next door)
- Corporate ownership chains
- Spreadsheet exports available for initial prototyping

### Custom Risk Algorithm (To Be Integrated)
- Multi-factor scoring model (to be shared)
- Multi-factor weighting
- Threshold configuration per department

### Government Data Feeds (To Be Connected)
- ACE/AMS/ABI (CBP trade data)
- APIS (traveler data)
- FDA Prior Notice
- DEA enforcement actions
- Historical seizure data

---

## 11. Technology Stack (Recommended)

- **Graph DB**: Amazon Neptune (shared with Investigative Intelligence)
- **Real-time scoring**: Lambda + Step Functions (or Kinesis for streaming)
- **AI/ML**: Bedrock for Gen AI question generation, SageMaker for risk model training
- **Search**: OpenSearch Serverless (anomaly detection, pattern matching)
- **Data Lake**: S3 + Glue (Sayari data, historical records)
- **Frontend**: Single-page app per department persona
- **Infrastructure**: CDK (reuse patterns from this project)
- **Access Control**: Multi-tenant, department-scoped (adapt from document-access-control spec)

---

## 12. Phased Approach

### Phase 1: POC Demo (4-6 weeks)
- Load Sayari sample data into Neptune
- Implement basic risk scoring algorithm
- Build CBP officer UI showing scored shipments
- Gen AI question generation for flagged items
- Demo with synthetic + Sayari data

### Phase 2: FDA Integration (4 weeks)
- FDA inspection queue UI
- Package triage scoring
- Inspection guidance generation
- Feedback loop (hit/miss tracking)

### Phase 3: Cross-Department Intelligence (6 weeks)
- DEA case building integration
- Cross-department alert system
- Phoenix company detection automation
- Tariff evasion detection module

### Phase 4: Production Hardening (8 weeks)
- Real-time streaming ingestion
- Model training on historical seizure data
- Performance optimization for millions of daily transactions
- Security hardening for classified data
- Audit trail and compliance

---

## 13. Transition Plan

### What to Copy from Investigative Intelligence Project
1. `infra/cdk/` — CDK patterns, Neptune setup, Lambda deployment
2. `src/services/entity_resolution_service.py` — Entity resolution logic
3. `src/services/network_discovery_service.py` — Network analysis
4. `src/services/pattern_discovery_service.py` — Anomaly detection
5. `src/services/entity_extraction_service.py` — Adapted for trade entities
6. `src/storage/s3_helper.py` — S3 utilities
7. `src/services/neptune_graph_loader.py` — Graph loading patterns
8. `scripts/batch_loader/` — Batch ingestion framework
9. `src/services/access_control_service.py` — Multi-tenant access control
10. `.kiro/steering/` — Development rules and procedures

### When to Transition
- **Now**: Save this document, create new repo
- **Week 1**: Copy shared modules, adapt for trade domain
- **Week 2-3**: Load Sayari data, implement risk scoring
- **Week 4-6**: Build demo UI, Gen AI integration
- **After POC success**: Extract shared library for both projects

---

## 14. Industry Best Practices to Incorporate

- UNODC guidelines on synthetic opioid detection in trade data
- WCO (World Customs Organization) risk management framework
- CBP's CTPAT trusted trader model as negative risk signal
- Machine learning on historical seizure data for continuous improvement
- Explainable AI — officers need to understand WHY (legal defensibility)
- Red team testing — regularly try to beat the system (think like cartel)
- Feedback loops — every inspection result improves the model
- Privacy by design — audit trails, data minimization, proper authorities

---

## 15. Success Metrics

- **Hit rate improvement**: % of inspected items that are actual violations (target: 5x current)
- **Throughput increase**: More legitimate goods flowing through faster
- **Time to flag**: Latency from transaction entry to risk score generation
- **Cross-department alerts**: Number of actionable intelligence shares between agencies
- **Phoenix company detection**: Time from company closure to new entity flagging
- **False positive rate**: Minimize disruption to legitimate trade
- **Lives saved**: Ultimate metric — reduction in overdose deaths attributable to interdiction improvements

---

## Next Steps

1. ✅ Architecture document saved (this file)
2. Create new project repo (`finding-fentanyl` or `trade-risk-intelligence`)
3. Start spec for risk scoring engine in new project
4. Load Sayari sample data for prototyping
5. Share risk algorithm for implementation
6. Schedule alignment meeting with FDA/DEA/CBP technical teams
