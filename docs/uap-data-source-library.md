# UAP Data-Source Library — Complete Inventory

## Purpose

Single tracking document for ALL data sources that feed the UAP pattern-detection demo
(the UAP Command Center). Mirrors the Finding-Fentanyl `data-source-registry.md` format.
Tracks what's ingested, where it lives, how it was processed, and which signatures it drives.

**DEMO ONLY** — never sold or distributed. Public government / scientific / documented data
used as a stand-in for the DOJ/HSI cases that can't be exposed. The dataset is the vehicle;
the pattern-detection + AI-investigator + audit discipline is the product.

---

## Architecture

```
Raw sources (docs/) ──► ufo_global_updb_pipeline.py ──► frontend data (src/frontend/*.js)
  UPDB + merged national/scientific/committee sets       │
                                                         ├─ Tier 1 keyword/regex filter (FREE)
  Taxonomy: src/data/ufo-uap-taxonomy.json               ├─ signature firing (39 signatures)
  (6 typologies, 39 signatures)                          ├─ geocode (real coords honored; else centroid)
                                                         └─ emits: UAP_DATA, UAP_CASES, UAP_GEO,
  Step D gap-miner: scripts/mine_signature_gaps.py            UAP_CONVERGENCE, UAP_LEYLINE
```

- **Grounding rule:** coordinates are real when the source provides them (GEIPAN, Galileo,
  Ukraine, documented seeds); otherwise a public country-centroid / curated-city table. Reports
  that can't be placed are counted but excluded from map points (never given invented coords).
- **Enrichment loop:** every new source → Tier 1 → signature scan → **Step D gap-mine** →
  author only data-supported signatures → re-scan. See `taxonomy-enrichment-master-loop.md`.

---

## Data Sources — Complete Inventory

### FULLY INGESTED (merged into the pipeline; firing counts as of the latest scan)

| Source | Raw records | Location (path) | Firing | Country/Region | Coords | Processing |
|--------|-------------|-----------------|--------|----------------|--------|-----------|
| UPDB (global UAP DB) | 296,600 | `docs/updb/updb_reports.json` | ~192K¹ | 221 countries | centroid/city | Full (Tier1 + 39-sig scan) |
| NUFORC (in UPDB) | (subset) | via UPDB | 115,779 | mostly US | city | Full |
| MUFON-attributed (in UPDB) | (subset) | via UPDB | 65,865 | global | city | Full |
| UFODNA (in UPDB) | (subset) | via UPDB | 7,585 | global | city | Full |
| NICAP (in UPDB) | (subset) | via UPDB | 2,748 | US | city | Full |
| UK MoD (UKGOV, in UPDB) | (subset) | via UPDB | 547 | UK | city | Full |
| Project Blue Book (in UPDB) | (subset) | via UPDB | 526 | US | city | Full |
| Pilots (in UPDB) | (subset) | via UPDB | 471 | global | city | Full |
| Canada Gov (in UPDB) | (subset) | via UPDB | 179 | CA | city | Full |
| NIDS / BAASS / Skinwalker (in UPDB) | (subset) | via UPDB | 969 | US | city | Full |
| **GEIPAN** (French CNES, official A/B/C/D) | 3,381 | `docs/geipan/geipan_pipeline_records.json` | 2,042 | FR | **real** | Full; French keywords |
| **RU-SAMIZDAT** (Soviet UFO Chronicles) | 211 | `docs/russia-ufo/russia_ufo.json` | 85 | RU | city/centroid | Full; Russian keywords |
| **ES-AIRFORCE** (Spanish AF, CC0) | 78 | `docs/spanish-ufo/spain_airforce_ufo.json` | 44 | ES | city | Full; Spanish keywords |
| **UA-KYIV-OBS** (Kyiv Observatory, instrument) | 8 | `docs/ukraine-uap/ukraine_uap.json` | 5 | UA | **real** | Full; scientific |
| **GALILEO** (Harvard IR array, NGO instrument) | 3 | `docs/galileo/galileo_uap.json` | 2 | US | **real** | Full; scientific |
| **JP-SEED** (Japan documented cases) | 5 | `docs/japan-ufo/japan_uap.json` | 4 | JP | **real** | Full; documented |
| **BE-SOBEPS** (Belgian wave + F-16) | 2 | `docs/govt-committees/govt_committees.json` | 2 | BE | **real** | Full; documented |
| **CL-CEFAA** (Chile official) | 2 | (same) | 2 | CL | **real** | Full; documented |
| **BR-CENIMAR** (Colares / Operação Prato 1977) | 1 | (same) | 1 | BR | **real** | Full; documented |
| **AR-CEFAe** (Argentina) | 1 | (same) | 1 | AR | **real** | Full; documented |
| **PE-DIFAA** (Peru) | 1 | (same) | 1 | PE | **real** | Full; documented |
| **UY-CRIDOVNI** (Uruguay) | 1 | (same) | 1 | UY | **real** | Full; documented |
| **NO-HESSDALEN** (Norway field station) | 3 | `docs/hessdalen/hessdalen_uap.json` | 2 | NO | **real** | Full; instrument/hotspot |
| **MX-SEDENA** (Mexico Campeche FLIR 2004) | 1 | `docs/roadmap-tail/roadmap_tail_uap.json` | 1 | MX | **real** | Full; documented |
| **IT-CUN** (Italy national reporting) | 1 | (same) | 1 | IT | **real** | Full; documented |

¹ Geocoded signal points on the map ≈ 192K; total firing across all sources = **196,869**.

**Documented-precedent seeds (ground truth used to drive signatures, not bulk corpora):**
- `src/data/conspiracy-seed/russia_soviet_uap/russia_seed.json` — 6 cases (Petrozavodsk, Voronezh, Dalnegorsk, Usovo, Siberia, Setka)
- `src/data/conspiracy-seed/japan_uap/japan_seed.json` — 5 cases (JAL1628, Kofu, Senganmori, SDF-nuclear, Kera)
- `src/data/conspiracy-seed/govt_committees/govt_committees_seed.json` — 8 cases across 6 countries

### DOCUMENTED / OBTAINABLE BUT NOT YET INGESTED (prioritized roadmap)

| Source | Type | Country | Priority | Obtainability | Notes |
|--------|------|---------|----------|---------------|-------|
| Sky360 / Sky Hub | NGO open-source sensor net | global | P2 | GitHub (code + streaming data) | Not a tidy case CSV |
| Enigma Labs | Commercial structured DB | global | P2 | Product (per-country pages) | 12,000+ sightings; no bulk export |
| Hessdalen AMS raw feeds | Instrument telemetry | NO | P3 | Partial | AMS "Blue Box" magnetometer/camera streams (documented cases already ingested) |

**Recently ingested from the roadmap (now in the FULLY INGESTED table):**
- ✅ NO-HESSDALEN (Norway field station, 3 records) — validates the recurring-hotspot signature.
- ✅ MX-SEDENA (Mexico 2004 Campeche FLIR, 1 record).
- ✅ IT-CUN (Italy national reporting, 1 record).

### SEARCHED — NOT CLEANLY OBTAINABLE (documented, not fabricated)

| Source | Why not | Status |
|--------|---------|--------|
| Russia KGB "Blue Folder" (raw) | Only scanned/press material; no clean dataset | Cited as precedent; the public "Cosmic Samizdat" OCR WAS ingested (RU-SAMIZDAT) |
| MUFON CMS (live database) | Proprietary/paid/no-API | Public MUFON-attributed records already in UPDB (~66K firing) |
| AARO raw sensor data | No public unrestricted portal; much classified | PURSUE declassified docs held locally (docs/pursue/) |
| Japan bulk dataset | ufojapan.org curated; Enigma commercial | Contribution = documented JP-SEED cases |

---

## Taxonomy (signatures driven by these sources)

- **File:** `src/data/ufo-uap-taxonomy.json` — 6 typologies, **39 signatures**.
- **Signature-count history:** 31 (base) → 35 (Russia seed: plasma, strategic-weapons, recovered-material, military-engagement) → 36 (Japan seed: recurring-hotspot) → 39 (Step D gap-mining: formation, color, acoustic).
- **Step D convergence:** two consecutive gap-mining rounds (after Galileo, after govt batch) returned the same near-miss pool (~35K) with no new pattern clearing the bar → taxonomy assessed **solid at 39**.

---

## Totals (current state)

| Metric | Value |
|--------|-------|
| Raw corpus (all merged) | **300,299 reports** |
| Passed Tier 1 | ~212,270 (70.7%) |
| Fired ≥1 signature | **196,873** |
| Countries represented | **200** |
| Signatures | **39** (6 typologies) |
| National/scientific/committee sources added | GEIPAN, ES-AIRFORCE, RU-SAMIZDAT, UA-KYIV-OBS, GALILEO, JP-SEED, BE/CL/BR/AR/PE/UY, NO-HESSDALEN, MX-SEDENA, IT-CUN |
| Step-D convergence | 4 consecutive rounds; near-miss pool stable at ~35,061; taxonomy solid at 39 |
| Pattern Dossiers | **5 dossiers**, all with full documentary narration + **Polly audio** (34 neural-voice MP3s, "Matthew", auto-advance episode mode). Library plan in `docs/uap-dossier-library-plan.md` (~11 topics). |
| Frontend cache-bust | v=31 |
| Offline | Leaflet/D3/markercluster vendored locally (src/frontend/vendor/); dossier map chapters render as inline SVG (no tiles). Boyne Valley dossier fully offline for the trip. |
| Dossiers (8) | **UAP group (7):** ☢️ Nuclear Sentinel (9 ch) · 🔺 Silent Triangle (6 ch; tri-001=58,027) · 📡 Radar-Visual Encounter (6 ch; em-rv-002=27,125) · 📍 Recurring Hotspot (5 ch; hotspot=63,537) · 🌊 Transmedium Problem (5 ch; fk-tm-003=26,849) · 🔬 Physical Trace (4 ch; landing-001=29,456, mat-001=211) · 👤 Occupant Reports (5 ch; ce-003=17,438, capped at ANOMALOUS-MODERATE). **Ancient Mysteries group (1):** 🗿 **Boyne Valley** (12 ch, ~17 min, per-site deep dives, Explorer↔dossier linked). All narrated (Polly, 59 clips). Picker splits UAP vs Ancient Mysteries. Offline pack: `docs/boyne-valley-offline-pack.md`. |
| Dossier AI investigator | LIVE: `runNuclearInvestigator(caseId)` runs the 5-step play (SPOT→CONFIRM→CORROBORATE→RULE-OUT→ASSESS) against a real firing case's text + fired signatures; renders WHY/FOUND(KNOWN)/SO-WHAT per step + WEP verdict (EXPLAINED/INSUFFICIENT/ANOMALOUS-MODERATE/ANOMALOUS-HIGH) + collection gaps. Wired into the `investigator` chapter of every dossier. |
| Dossier visuals | REAL: map = offline inline-SVG (markers/labels/connectors from coords, no tiles); graph = D3 force network; corroboration = proportional bars (grounded firing counts); stats/timeline/process/checklist = styled. dosMount() runs after innerHTML. |

---

## Processing Rules

1. Every new source goes through `ufo_global_updb_pipeline.py` (Tier 1 → signature firing → geocode).
2. Sources with real coordinates are preserved; others use public reference geodata (never invented).
3. **Step D after EVERY source** (`mine_signature_gaps.py`) before adding the next — author only data-supported signatures.
4. Prefer public, licence-clean text/data. Check for a pre-processed version before re-processing raw scans.
5. Keep this library + `data-assets-registry.md` + the session summary updated.

---

*Last updated: 2026-08-22*
*Pipeline: scripts/ufo_global_updb_pipeline.py · Taxonomy: src/data/ufo-uap-taxonomy.json*
*Frontend: src/frontend/uap-command-center.html*
