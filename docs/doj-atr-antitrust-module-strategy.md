# DOJ ATR Antitrust Intelligence Module Strategy

## Overview

The Antitrust Intelligence Platform extends the Investigative Intelligence platform with 6 specialized case type modules. Each module implements the `AntitrustAnalysisModule` protocol and plugs into shared infrastructure (scoring, legal reasoning, decision workflow, knowledge graph).

**Pilot Module:** Procurement Collusion Detection (PCSF) — spec complete at `.kiro/specs/procurement-collusion-detection/`

## Architecture: Plugin Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                    Shared Infrastructure                          │
│  AntitrustScoringService │ AntitrustLegalReasoning │ RedFlagTaxonomy │
│  DecisionWorkflow │ Neptune Graph │ Aurora │ OpenSearch │ Bedrock  │
└─────────────────────────────────────────────────────────────────┘
        ▲           ▲           ▲           ▲           ▲           ▲
        │           │           │           │           │           │
   ┌────┴───┐  ┌───┴────┐  ┌───┴───┐  ┌───┴────┐  ┌───┴────┐  ┌──┴─────┐
   │ Module │  │ Module │  │Module │  │ Module │  │ Module │  │ Module │
   │   1    │  │   2    │  │  3    │  │   4    │  │   5    │  │   6    │
   │Procure-│  │Merger  │  │Price  │  │Market  │  │Monopo- │  │Criminal│
   │ment    │  │Review  │  │Fixing │  │Alloc.  │  │lization│  │Cartel  │
   │Collusion│  │(HSR)   │  │(Horiz)│  │        │  │(Sec 2) │  │        │
   └────────┘  └────────┘  └───────┘  └────────┘  └────────┘  └────────┘
```

## Module Summary

| # | Module | Status | Key Innovation | Primary Statute |
|---|--------|--------|---------------|-----------------|
| 1 | Procurement Collusion (PCSF) | ✅ Spec Complete | Statistical bid pattern detection + AI legal reasoning | Sherman Act §1 |
| 2 | Merger Review (HSR) | 📋 Shell | Market concentration modeling + competitive effects simulation | Clayton Act §7 |
| 3 | Price Fixing (Horizontal) | 📋 Shell | Parallel pricing detection + communication timing correlation | Sherman Act §1 |
| 4 | Market Allocation | 📋 Shell | Geographic/customer division via graph partitioning | Sherman Act §1 |
| 5 | Monopolization (Section 2) | 📋 Shell | Market power quantification + exclusionary conduct patterns | Sherman Act §2 |
| 6 | Criminal Cartel | 📋 Shell | Conspiracy network discovery + leniency program intelligence | Sherman Act §1 (criminal) |

## Shared Components (Built Once, Used by All)

These components are designed in the procurement-collusion-detection spec and shared across all modules:

1. **AntitrustAnalysisModule** (abstract base) — protocol all modules implement
2. **AntitrustScoringService** — generic weighted-factor scoring engine
3. **AntitrustLegalReasoning** — Bedrock prompt management for legal analysis
4. **RedFlagTaxonomy** — severity classification (Critical/High/Medium/Low)
5. **DecisionWorkflow integration** — AI_Proposed → Human_Confirmed → Human_Overridden
6. **Neptune graph extensions** — entity/relationship patterns for antitrust
7. **antitrust-investigator.html** — shared dashboard shell with module-specific tabs

## Platform Components (Already Built — Customer Gets These)

The DOJ ATR team deploys the base platform and gets:
- S3 data lake + Step Functions ingestion pipeline
- Aurora PostgreSQL (documents, entities, relationships)
- Neptune knowledge graph
- OpenSearch Serverless (semantic search, kNN)
- Amazon Bedrock (Claude + Titan)
- Entity extraction service
- Network discovery service
- Cross-case pattern analysis
- Prosecution readiness scoring
- Decision workflow
- Investigative playbooks
- Chat service
- API Gateway + Lambda dispatch pattern
- Frontend patterns (graph viz, geospatial map, timeline)

## Customer Handoff Strategy

For DOJ ATR to build in their GovCloud environment:
1. Deploy base platform via CDK (CloudFormation template)
2. Run Aurora migrations (001-007 for platform, 008+ for antitrust modules)
3. Upload frontend files to S3
4. Configure Bedrock model access
5. Load procurement data via batch loader or API
6. Each module spec (requirements + design) gives them everything needed to implement

## Timeline (12-Week Pilot)

| Week | Milestone |
|------|-----------|
| 1-2 | Platform deployment in GovCloud + data ingestion setup |
| 3-4 | Module 1 (Procurement Collusion) implementation |
| 5-6 | Module 1 testing with real procurement data |
| 7-8 | Module 2 (Merger Review) or Module 3 (Price Fixing) — based on ATR priority |
| 9-10 | Cross-case analysis + prosecution workflow integration |
| 11-12 | UAT, refinement, success criteria validation |

## Innovative Differentiators by Module

### Module 1: Procurement Collusion (PCSF) ✅
- **Benford's Law analysis** on bid amounts to detect fabricated numbers
- **Graph community detection** to find collusion rings automatically
- **Temporal pattern mining** — bid rotation detected via sequential pattern algorithms
- **AI prosecution memo generation** — one-click draft of Sherman Act §1 complaint

### Module 2: Merger Review (HSR)
- **HHI simulation engine** — model post-merger market concentration in real-time
- **Competitive effects prediction** — AI predicts price/output effects using economic models
- **Divestiture scenario modeling** — test different remedy packages against market impact
- **Coordinated effects detection** — identify markets where merger enables tacit collusion

### Module 3: Price Fixing (Horizontal)
- **Parallel pricing algorithm** — detect statistically improbable price synchronization
- **Plus factor analysis** — AI identifies "plus factors" beyond mere parallelism
- **Econometric damage modeling** — estimate overcharge using but-for pricing
- **Leniency race detection** — identify when cartel members may be seeking immunity

### Module 4: Market Allocation
- **Graph partitioning algorithms** — detect geographic/customer division via community detection
- **Territory mapping** — visualize allocation patterns on geospatial map
- **Customer switching analysis** — detect when customers are "steered" between competitors
- **Non-compete clause analysis** — AI identifies anticompetitive contract terms

### Module 5: Monopolization (Section 2)
- **Market definition engine** — AI-assisted relevant market definition using SSNIP test
- **Market power quantification** — compute market share, barriers to entry, buyer power
- **Exclusionary conduct taxonomy** — classify conduct types (tying, exclusive dealing, predatory pricing)
- **Recoupment analysis** — model whether predatory pricing can be recouped

### Module 6: Criminal Cartel
- **Conspiracy network discovery** — identify cartel structure from communication patterns
- **Meeting pattern analysis** — detect suspicious travel/meeting coincidences
- **Leniency program intelligence** — track which members are cooperating
- **Wiretap correlation** — match intercepted communications to market events
- **Sentencing guideline calculator** — estimate penalties based on volume of commerce
