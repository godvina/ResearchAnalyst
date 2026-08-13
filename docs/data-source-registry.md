# Data Source Registry — Unified Pattern Library

## Purpose

Single tracking document for ALL data sources that feed the Crime Pattern Library.
Tracks what's been processed, where it lives, and which project owns it.

---

## Architecture (Corrected After Audit)

**Finding Fentanyl = Data Engine** (where signatures are built and processed)  
**Research Analyst = Application Platform** (where signatures are deployed and scored)  
**Shared: OpenSearch cluster `hzrvvva3hodw069v9442`** (both read/write same indexes)

```
Finding Fentanyl (DATA ENGINE — source of truth for pattern data)
├── taxonomy.json (master — 4 domains, 15 typologies, 150 signatures)
├── data/crime-pattern-library/patterns/ (1,100+ individual pattern JSONs)
├── 3-tier pipeline: filter-doj → embed → synthesize (Node.js/mjs)
├── doj-complete.jsonl (269K DOJ press releases — THE corpus)
├── fincen-scored-real.jsonl (3.5MB FinCEN SARs, already scored)
├── icij-scored-real.jsonl (165MB ICIJ offshore entities, scored)
├── Domain-specific TypeScript data (Pacific, ML, CBP, Travel, Tariff)
├── OpenSearch WRITES → 9 indexes on hzrvvva3hodw069v9442
└── Frontend: operational narcotics/trade interdiction UI

Research Analyst (APPLICATION PLATFORM)
├── src/data/pattern-library-taxonomy.json (local copy — sync FROM FF)
├── src/frontend/pattern-library.html (admin browse/search view)
├── Scoring engine (src/services/signal_scorer.py, score_typology.py)
├── Cultural calibration (succession-cultural-profiles.js)
├── Succession planning module (compensation, risk, readiness)
├── API Gateway → Lambda → reads same OpenSearch indexes
├── Aurora persistence (scoring decisions, audit trail)
└── Frontend: investigator, prosecutor, succession dashboards
```

**Key insight:** Both projects already share the same AWS infrastructure (OpenSearch, Neptune, Aurora). The data is unified at the cloud level. Only local dev files are split.

---

## OpenSearch Indexes (Shared Cluster)

| Index | Owner (writes) | Records | Content |
|-------|---------------|---------|---------|
| `typology-patterns` | Finding Fentanyl | 150 | Master 150 signatures as vectors |
| `talos-trade` | Finding Fentanyl | 665 | Trade domain embeddings |
| `talos-seizures` | Finding Fentanyl | 20,000 | CBP seizure vectors |
| `talos-fema-signatures` | Finding Fentanyl | 172 | FEMA fraud patterns |
| `hsi-reference` | Finding Fentanyl | ~100 | HSI landmark cases |
| `talos-karl-lee-entities` | Finding Fentanyl | ~50 | Specific case entities |
| `talos-snap-retailers` | Finding Fentanyl | ~200 | SNAP benefits fraud |
| `talos-crossref` | Finding Fentanyl | ~1,000 | ICIJ cross-reference |
| `talos-ml-pacific` | Finding Fentanyl | ~200 | Pacific ML patterns (NEW) |

**Research Analyst reads from:** `typology-patterns` (main scoring), plus k-NN queries across all indexes for cross-domain detection.

---

## Data Sources — Complete Inventory

### ✅ FULLY PROCESSED (In Finding Fentanyl, available via OpenSearch)

| Source | Records | Location | Signatures | Domain | Processing |
|--------|---------|----------|------------|--------|-----------|
| DOJ Press Releases | 269,000 | FF: `doj-complete.jsonl` | 150 master | All 15 typologies | Full 3-tier |
| ICIJ Offshore Entities | 165MB | FF: `icij-scored-real.jsonl` | Scored | Money Laundering | Tier 2+3 |
| FinCEN SARs | 3.5MB | FF: `fincen-scored-real.jsonl` | Scored | AML/Financial | Tier 2+3 |
| CBP Seizures | 20,000 | FF: OpenSearch `talos-seizures` | Embedded | Trade/Smuggling | Tier 2 |
| FEMA FWA Cases | ~500 | FF: OpenSearch `talos-fema-signatures` | 172 | Fraud/FWA | Full 3-tier |
| Immigration Fraud | ~600 | FF + RA: taxonomy | 215 | Fraud/Immigration | Full 3-tier |
| Antitrust (DOJ) | ~5,000 | RA: `pattern-library-taxonomy.json` | 100+ | Antitrust | Full 3-tier |
| Pacific Drug Trafficking | ~13,456 | FF: `doj-ml-pacific-tight.jsonl` | 55 | Drug Trafficking | Full 3-tier |
| ML Pacific Patterns | 190 briefs | FF: `tier3-ml-briefs.json` | 96 | Money Laundering | Full 3-tier |
| Epstein Files | 3,800 → 200 | RA: local JSON | 50+ | Conspiracy | Full 3-tier |
| SNAP Retailers | ~200 | FF: OpenSearch | Scored | Benefits Fraud | Tier 2 |
| WikiIran Convergence | 59 hits | FF: `convergence-results.json` | Cross-ref | Sanctions | Tier 3 |

### ✅ UNIQUE TO FINDING FENTANYL (Built Recently, Not Yet in RA)

| Source | Signatures | Domain | Merge Priority |
|--------|-----------|--------|---------------|
| `ml-pattern-data.ts` — 96 ML signatures (Chinese/Pacific focus) | 96 | Money Laundering | HIGH |
| `pacific-data.ts` — 55 Pacific drug trafficking signatures | 55 | Drug Trafficking | HIGH |
| `cbp-pattern-library.ts` — CBP border/travel patterns | ~30 | Trade/Border | MEDIUM |
| `ucpf-travel-needles-5level.json` — 5-level travel behavior | ~40 | Travel/Smuggling | MEDIUM |
| Tariff evasion taxonomy + 20K scored shipments | ~20 | Trade Fraud | MEDIUM |
| ML Method Convergence (Iran×Pacific cross-domain) | Cross-ref | Sanctions×ML | HIGH |
| Brand Protection + Selinko customer data | ~10 | Counterfeiting/IP | LOW |

**Total unique FF signatures not yet reflected in RA local taxonomy: ~250**
(But they ARE in the shared OpenSearch cluster, so RA can already score against them)

### ❌ NOT YET PROCESSED (Prioritized Backlog)

| Source | Location | Priority | Expected Output | Pipeline |
|--------|----------|----------|-----------------|----------|
| FinCEN Fentanyl Advisory (FIN-2024-A001) | Need download | **P0** | 30-50 signatures | FF 3-tier |
| FinCEN Chinese ML Networks (FIN-2025-A001) | Need download | **P0** | 40-60 signatures | FF 3-tier |
| FATF Trade-Based ML Typologies | Need download | **P1** | 50-80 signatures | FF 3-tier |
| FATF Virtual Assets Red Flags | Need download | **P1** | 30-50 signatures | FF 3-tier |
| FinCEN Ransomware (FIN-2020-A006) | RA: `docs/fincen/` | P1 | 20-30 signatures | FF 3-tier |
| FinCEN Elder Fraud (FIN-2022-A002) | RA: `docs/fincen/` | P1 | 15-25 signatures | FF 3-tier |
| FinCEN Identity SAR Trends | RA: `docs/fincen/` | P1 | 20-40 signatures | FF 3-tier |
| DOJ Counterfeiting cases | Filter from FF `doj-complete.jsonl` | P1 | 40-60 signatures | FF 3-tier |
| FATF Professional ML | Need download | P2 | 30-40 signatures | FF 3-tier |
| FATF Terror Financing Guidance | Need download | P2 | 25-35 signatures | FF 3-tier |
| FATF Proliferation Financing | Need download | P2 | 20-30 signatures | FF 3-tier |
| DOJ Cybercrime cases | Filter from FF `doj-complete.jsonl` | P2 | 30-50 signatures | FF 3-tier |

---

## Processing Rules

1. **All new data goes through Finding Fentanyl's 3-tier pipeline** (the scripts are there, the corpus is there)
2. **Output lands in OpenSearch** (shared cluster) — immediately available to both UIs
3. **Research Analyst's local taxonomy** (`pattern-library-taxonomy.json`) is updated via sync when needed for offline/demo use
4. **Never process the same data in both projects** — check this registry first
5. **FinCEN/FATF PDFs downloaded to RA** should be moved to FF for processing (that's where the pipeline lives)

---

## Sync Protocol

**Direction: Finding Fentanyl → Research Analyst**

When FF produces new signatures:
1. FF pipeline writes to OpenSearch (automatic — both UIs see it immediately)
2. For local/demo use: run `python scripts/sync_pattern_library.py` in RA (copies taxonomy)
3. Update this registry document

**The 3 downloaded FinCEN PDFs in RA (`docs/fincen/`) should be processed through FF's pipeline:**
```
# Copy to FF for processing:
copy "Research Analyst\docs\fincen\*.pdf" "Finding Fentanyl\data\fincen\"
# Then in FF: run the 3-tier pipeline on them
```

---

## Totals (Current State)

| Metric | Finding Fentanyl | Research Analyst | Shared (OpenSearch) |
|--------|-----------------|-----------------|---------------------|
| Domains | 4 (master taxonomy) | 5 (local copy) | All accessible |
| Typologies | 15 | 5 detailed + 10 stubs | 15 |
| Total signatures | 1,250+ (files) | ~533 (local taxonomy) | 150 embedded + growing |
| OpenSearch vectors | 22,000+ across 9 indexes | Reads all | 22,000+ |
| Raw corpus | 269K DOJ + 165MB ICIJ + 3.5MB FinCEN | 3 FinCEN PDFs | — |
| Pipeline scripts | Full 3-tier (Node.js) | Reference pattern only | — |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-07 | FF is data engine, RA is application platform | FF has 10x more data, full pipeline, 9 indexes |
| 2026-08-07 | Sync direction: FF → RA (not reverse) | Don't duplicate 269K corpus; RA reads from shared cloud |
| 2026-08-07 | New FinCEN/FATF processing goes through FF pipeline | That's where doj-complete.jsonl and embedder scripts live |
| 2026-08-07 | RA keeps local taxonomy for offline demo capability | Pattern-library.html needs to work without API |

---

*Last updated: 2026-08-07*
*Source of truth for data: Finding Fentanyl*
*Source of truth for architecture: Research Analyst*
