---
inclusion: auto
---

# Data Assets Registry — Research Analyst

## Purpose
A durable, always-loaded record of every dataset we have downloaded/processed and
WHERE it lives, so no future session ever re-downloads or "can't find" data we
already have. **Before proposing to download or re-acquire any dataset, CHECK THIS
FILE FIRST.** If a dataset is listed here, it is already on disk — use it.

## Rule (mandatory)
When we download, generate, or process a significant dataset, ADD A ROW here in the
same turn. Include: absolute path, row/record count, key fields, coverage, and the
script that produced/consumes it. Treat this as the single source of truth for "do
we have X data?"

---

## Registered Datasets

### UFO / UAP — GLOBAL (primary UAP source)
- **Path:** `docs/updb/updb_reports.json`
- **What:** UPDB (global UAP report database). **296,600 reports across 221 countries.**
- **Fields:** `id, source (NICAP/UFODNA/etc.), date, description, city, district, country (ISO-2), water`. NO coordinates (geocoded downstream).
- **Coverage:** US 232,845 · CA 13,855 · GB 9,876 · AU 4,405 · FR 2,501 · BR 1,563 · DE 1,446 · MX 1,122 · IN 1,118 · + 212 more countries.
- **Pipeline:** `scripts/ufo_global_updb_pipeline.py` (Tier-1 keyword filter -> signature firing -> geocode -> UI build). Also merges the ES-AIRFORCE source below at load time.
- **Derived outputs:** `scripts/updb_tier1_filtered.json`, `scripts/updb_signal_reports.json`, `src/frontend/uap-command-data.js`.
- **Result (after Step-D gap-mining, 300,283 total):** 212,265 passed Tier 1 (70.7%) -> **196,859 fired >=1 signature across 200 countries**, 192,419 geocoded. Taxonomy = **39 signatures**. (Firing rose 186,907 -> 196,859 = +9,952 after Step D added formation/color/acoustic signatures — the biggest single compounding jump.)

### Step D — signature gap-mining (mandatory after every dataset)
- **Tool:** `scripts/mine_signature_gaps.py` -> `scripts/signature_gap_report.json`. Finds Tier-1 survivors firing 0-1 signatures (near-misses) and clusters their vocabulary.
- **Run 1 result:** 53,255 near-misses (23,960 zero-fire + 29,295 one-fire). Top uncovered patterns: formation/fleet **7,700 (14.5%)**, color-shift 2,166 (4.1%), repeated-return 1,008, animal-reaction 826, hum/buzz 547.
- **Authored 3 data-supported signatures (36 -> 39):** `uap-cm-formation-001` (multi-object/fleet), `uap-cm-color-001` (color-changing/pulsating), `uap-em-acoustic-001` (hum/buzz — the anti-silent pattern). Each cites its near-miss frequency.
- Remaining probes (animal-reaction, time-loss, beam-abduction) left un-authored this round — lower frequency, revisit next Step D. No overfitting.

### UFO / UAP — France (GEIPAN / CNES, official government investigations)
- **Raw:** `docs/geipan/geipan_reports.json` — **3,381 official French cases** (from `scripts/_geipan_calibrate.py`, parsed from `export_cas.xlsx`). Fields: id, title, details (FR), year, official_identification, classification (A/B/C/D), disposition, departement, **lat, lng** (real per-case coords), phenomene, type, country=FR.
- **Normalizer:** `scripts/build_geipan_pipeline_records.py` → `docs/geipan/geipan_pipeline_records.json` (3,381 records in pipeline shape, source=GEIPAN, real lat/lng preserved; official identification + A/B/C/D folded into description). 106 unexplained (class D), 1,015 insufficient, 2,260 explained.
- **Merge:** loaded into `ufo_global_updb_pipeline.py` after the Spanish block. The pipeline now **honors a source-supplied lat/lng** (gtype=`source`) before falling back to city/country geocoding — so GEIPAN places on exact French coords. French keywords added to all Tier-1 categories + French misid negatives.
- **Result:** 1,095 GEIPAN cases fire ≥1 signature; France = 1,633 firing reports total. Corpus now **300,059**.
- **Provenance:** GEIPAN / CNES official French UAP investigations. Public French government open data.

### UAP ley-line convergence (UAP × Becker-Hagens grid vertices + 62 nodes + British St Michael line)
- **Script:** `scripts/uap_leyline_convergence.py` (LOCAL; imports helpers from `uap_convergence_analysis.py`).
- **Inputs:** `src/data/uvg-grid-intersections.json` (20 line-crossing vertices), `src/data/uvg-grid-62-points.json` (62 grid nodes; poles skipped → 60), and an inline `BRITISH_LEY` list (9 St Michael/Apollo-line waypoints: St Michael's Mount, Hurlers, Brentor, Burrow Mump, Glastonbury Tor, Avebury, Ogbourne St George, Bury St Edmunds, Hopton).
- **Outputs:** `scripts/uap_leyline_results.json`, `src/frontend/uap-leyline-convergence.js` (window.UAP_LEYLINE = {vertices, grid_nodes, british_ley, results=vertices}).
- **Method:** same lift ratio + reliability gate as sites, PLUS a **300km reporting-infrastructure probe** classifying each point ocean / remote / populated. A zero at a remote/ocean point = coverage gap, NOT a null.
- **KEY FINDINGS (60km):**
  - **Vertices:** UNTESTABLE — 9 ocean, 10 remote, only INT-0019 (Adriatic) populated (lift 0.15×, below baseline).
  - **62 grid nodes:** confirms *which nations* the grid hits. Japan (Node 10) and Bermuda (Node 14) are OFFSHORE (untestable). Russia (Nodes 2/3/52/53), Sedona (13), Uluru (40), Nazca (44) are remote with 0 reports within 300km. Giza (Node 7) has 2 reports (baseline unreliable). Node 56 (Ireland/UK) has 5,005 reports within 300km but its 60km circle is in the Irish Sea → below baseline. Populated 5, remote 30, ocean 25; ZERO reliable over-concentrations.
  - **British St Michael line (populated, testable):** Glastonbury Tor (4.29×) + Burrow Mump (8.46×) over-concentrate — BUT they're 17.3km apart and count the SAME 54 Somerset reports = one local cluster, not two independent hits. The other 7 waypoints are at/below baseline. ASSESSED: a real UAP cluster over the Somerset Levels, NOT evidence the alignment itself attracts sightings.
- **Per-nation firing coverage (grounds the "which nations" answer):** JP 224 · RU 114 · CN 122 · IR 106 · TR 90 · IL 77 · KR 73 · IQ 43 · EG 32 · AE 31 · SA 26 · BM 9 (vs US 151,566 · GB 5,334 · CA 8,454 · FR 1,633). Non-US/UK/CA nations are thin → most node baselines are unreliable.

### UFO / UAP — Spain (declassified Spanish Air Force / Ejército del Aire)
- **Path:** `docs/spanish-ufo/spain_airforce_ufo.json` — **78 records, `source = ES-AIRFORCE`, country = ES.**
- **Fetch script:** `scripts/fetch_spanish_ufo_files.py` (pulls public-domain CC0 `_djvu.txt` OCR derivatives from archive.org "SpanishUFOFiles"; NOT the multi-GB PDFs).
- **Provenance:** Spanish Ministry of Defence declassified UFO expedientes (public domain). Downloaded 2026-08-22.
- **Merge:** loaded into the pipeline with Spanish-language keywords + Spanish-city coords; registers ES coverage in the corpus/signal.

### UFO / UAP — Russia/Soviet (RU-SAMIZDAT) + documented-precedent seed
- **Seed (ground truth):** `src/data/conspiracy-seed/russia_soviet_uap/russia_seed.json` — 6 documented cases (Petrozavodsk 1977, Voronezh 1989, Dalnegorsk 1986, Usovo missile base 1982, Siberia 1987, Program Setka 1978) with source URLs + expected signatures. Scored via `scripts/score_russia_seed.py`.
- **Corpus:** `scripts/fetch_russia_ufo_files.py` → `docs/russia-ufo/russia_ufo.json` — 211 records (source=RU-SAMIZDAT, country=RU) segmented from the public archive.org OCR text 'UFO Chronicles of the Soviet Union: A Cosmic Samizdat' (item B-001-002-573). 36 city-placed (Voronezh, Moscow, Leningrad…); rest Moscow-centroid.
- **Precedent (NOT ingested):** the smuggled Soviet 'anomalous phenomena' archive (Popovich / KGB 127-page record), publicly revealed 2026 — cited, not scraped.
- **Result:** 58 RU-SAMIZDAT records fire; Russia now 173 firing reports total.

### UFO / UAP — Ukraine (UA-KYIV-OBS, instrument-based science)
- **Builder:** `scripts/build_ukraine_uap_records.py` → `docs/ukraine-uap/ukraine_uap.json` — 8 records (source=UA-KYIV-OBS, country=UA, real Kyiv/Vinarivka coords).
- **Source:** Main Astronomical Observatory, NAS of Ukraine (Zhilyaev et al.), arXiv 2208.11215 / 2211.17085 / 2503.05627. Synchronized meteor-station cameras; measured altitude/speed/size/colorimetric distance for 'Cosmics' and 'Phantoms'. KNOWN measured values, authors do not interpret.
- **Result:** 5 UA-KYIV-OBS records fire; Ukraine now 39 firing reports total.

### NEW signatures added from the Russian seed (taxonomy now 35, was 31)
- `uap-cm-plasma-001` — amorphous/jellyfish plasma form + light beams (Petrozavodsk). Fires **7,042×** on full corpus.
- `uap-em-strat-001` — strategic-weapons / nuclear-missile system interference (Usovo). Fires **157×**.
- `uap-em-mat-001` — recovered-material / metallurgical anomaly (Dalnegorsk). Fires **211×**.
- `uap-ir-force-001` — military engagement / interception-with-force (Siberia 1987). Fires **3,146×**.
- Lesson: the Soviet seed surfaced patterns already latent in the global corpus but invisible until the signatures existed — the seed-first payoff. Russian/Cyrillic + EN keywords added to the pipeline Tier-1 categories.

### UFO / UAP — Japan (JP-SEED) + documented-precedent seed
- **Seed:** `src/data/conspiracy-seed/japan_uap/japan_seed.json` (5 cases: JAL Flight 1628 1986, Kofu 1975, Mount Senganmori cluster, SDF nuclear-watch, Kera 1975) + `scripts/score_japan_seed.py`.
- **Corpus:** `scripts/build_japan_pipeline_records.py` → `docs/japan-ufo/japan_uap.json` (5 JP-SEED records, real coords). Honest note: NO licence-clean BULK Japanese dataset exists (ufojapan.org is curated/editorial; Enigma Labs' ~380 Japan reports are a commercial product) — so Japan's contribution is documented cases, same treatment as the Russia documented cases.
- **Scoring result:** JAL1628 fires radar-pacing + trained-observer + institutional; Kofu fires occupant + landing; SDF fires the nuclear-interference signature; Senganmori fires the new hotspot signature.

### NEW signature #5 (taxonomy now 36) + indicator strengthening from the Japan seed
- `uap-et-hotspot-001` — recurring-cluster-at-geophysical-anomaly (Senganmori magnetic hill; also Hessdalen, Sedona, Skinwalker). Cross-cutting.
- Strengthened indicator vocabulary: `uap-et-ce-003` (occupant/being/humanoid/entity/creature), `uap-et-landing-001` (landed/landing/touched down/on the ground), `uap-em-strat-001` (nuclear/nuclear power/power plant/reactor). Added Japanese kana/kanji keywords to Tier-1.
- **Compounding effect:** strengthened needles + new signature raised total firing 180,952 → 186,907 and countries 195 → 198 — reports that were previously below threshold now register. Corpus 300,283 / 36 signatures.

### NGO / nonprofit UAP research orgs (candidate instrument-data sources)
- **Galileo Project** (Harvard, Avi Loeb) — all-sky IR/visible/radio/audio observatories; published scientific data (arXiv/MDPI). Highest-value instrument source, like the Ukraine set.
- **Sol Foundation** — citizen-science UAP data initiative.
- **Enigma Labs** — largest structured public sighting app/DB (per-country pages, e.g. 380 Japan). Licence permitting.
- **UFODATA / UAPx** — scientific instrument monitoring networks.

### PRIORITIZED ENRICHMENT ROADMAP (next iterations, ranked obtainability × signal-richness)
1. **Galileo Project** (arXiv/MDPI instrument data) — clean, scientific, non-eyewitness. Top pick.
2. **Belgium — SOBEPS 1989-90 wave** (F-16 radar, official) — famous, well-documented.
3. **Chile — CEFAA** (official govt UAP committee; some public reports).
4. **Brazil — Operação Prato / CENIMAR** (1977 Colares wave; military docs).
5. **Argentina — CEFORA / Fuerza Aérea** (declassified AF files).
6. **Peru — DIFAA** (official air-force UAP office).
7. **Mexico — 2004 Campeche FLIR** + strong civilian corpus (UPDB has MX 520).
8. **Enigma Labs global** (structured multi-country reports).
9. **Uruguay — CRIDOVNI** (military UAP commission, decades of files).
10. **Italy — CUN / Aeronautica Militare** (national reporting body).

### UFO / UAP — Galileo Project (GALILEO, NGO instrument) + Government committees
- **GALILEO:** `scripts/build_galileo_records.py` → `docs/galileo/galileo_uap.json` (3 records). Harvard all-sky IR array (8 FLIR Boson 640), ADS-B calibration, ~500K trajectories/5mo, 144 ambiguous outliers the authors call LIKELY MUNDANE (not anomalous — framing preserved). Source arXiv:2411.07956 = Sensors 2025 25(3) 783.
- **Government committees (6 countries):** `scripts/build_govt_committees_records.py` → `docs/govt-committees/govt_committees.json` (8 cases). BE-SOBEPS (Belgian wave + F-16 intercept), CL-CEFAA (El Bosque 2010, Navy heli FLIR 2014), BR-CENIMAR (Colares/Operação Prato 1977), AR-CEFAe, PE-DIFAA, UY-CRIDOVNI. Documented-case seed pattern.
- **Corpus after batch:** 300,294 reports, 39 signatures, ~196,869 firing, 200 countries.

### Step D rounds 2 & 3 — CONVERGENCE reached (diminishing returns)
- Round 2 (after Galileo) and round 3 (after govt batch) both returned the SAME near-miss pool (35,061) and gap distribution; no new pattern cleared the bar. **Verdict: taxonomy solid at 39; adding more documented cases no longer surfaces new signatures.** This is the loop's point-of-goodness for signatures — the honest stop signal.

### NGO / citizen-science sensor networks (searched with honed vocabulary)
- **Project Hessdalen (Norway)** — scientific field station since 1983 (cameras, radar, magnetometers, spectrometers, IR); 53 events in an 18-day window; the canonical recurring-hotspot (validates uap-et-hotspot-001). Public. **Top future documented-case candidate.**
- **Sky360.org / Sky Hub** — open-source citizen sensor networks (GitHub: Sky360-Repository/sky360, "BOB" tracker). Code + methodology public; streaming sensor data, not a tidy case CSV.
- **Enigma Labs** — 12,000+ structured sightings processed (commercial product; per-country pages public, no bulk export).
- **HuggingFace `MTSlive/war-gov-uap-release-1`** — processed mirror of US PURSUE (already held locally).
- Honest note: NO NGO offers a clean BULK downloadable case dataset; Hessdalen is the best next documented-case seed.

### Data-source search log (2026-08-22) — what's obtainable vs. not
Searched for new national/govt UAP datasets after the France/Spain merges:
- **Russia "KGB Blue Folder":** UPDATE (2026-08-22, second search with the seed-first method): a public Russian/Soviet corpus WAS found — archive.org 'UFO Chronicles of the Soviet Union: A Cosmic Samizdat' (item B-001-002-573), now ingested as RU-SAMIZDAT (211 records). The raw KGB/Popovich 127-page record itself remains only as scanned/press material (cited as precedent, not a clean dataset). First search missed it; refining the query with the documented-case vocabulary surfaced it.
- **US Dept of War PURSUE (war.gov/UFO):** 5 official 2026 declassified tranches (375 docs; covers Middle East / Africa / INDOPACOM / western US). **ALREADY LOCAL** — `docs/pursue/`, `scripts/_build_pursue_*_seed.py`, `src/data/conspiracy-seed/ufos_uaps/pursue_*_claims.json`. Community mirror: [DenisSergeevitch/UFO-USA](https://github.com/DenisSergeevitch/UFO-USA).
- **Ukraine (Kyiv Main Astronomical Observatory / Zhilyaev):** a real *scientific* UAP dataset (calibrated meteor-station cameras; object classes) — obtainable via academia.edu PDFs; contested by Ukraine's science agency. Candidate future add.
- **Japan / South Korea / Middle East standalone national DBs:** none cleanly obtainable; covered indirectly via UPDB country records + PURSUE INDOPACOM/Middle East files.
- **Known remaining gaps:** Russia (processed), Brazil. (France/GEIPAN merged; see above.)

### UFO / UAP — US only (NUFORC, legacy)
- **Path:** `src/data/conspiracy-seed/ufo_sightings/ufo_sightings.csv` (also `docs/ufo_sightings.csv`)
- **What:** NUFORC US corpus. **60,632 reports, country = US only.** Has lat/lng + shape.
- **Pipeline:** `scripts/ufo_tiered_scan.py`, `scripts/ufo_full_corpus_signature_scan.py`, `scripts/ufo_event_clustering.py`, `scripts/_build_uap_ui_data.py`.
- **Note:** superseded by the UPDB global set for the Command Center map.

### UAP convergence (UAP × ancient sites × mythology)
- **Script:** `scripts/uap_convergence_analysis.py` (LOCAL, no OpenSearch). 22 sites (Irish from file + world wonders + data-rich US/UK + Spain).
- **Outputs:** `scripts/uap_convergence_results.json`, `src/frontend/uap-convergence.js` (window.UAP_CONVERGENCE).
- **Method:** lift ratio = near-site UAP density ÷ **mean** of 16 matched baseline control circles (Laplace-smoothed, always finite). A baseline is flagged **unreliable** when fewer than 4/16 controls contain data (prevents divide-by-near-zero blowups). Plus a solstice/equinox timing test. Uses irish_ancient_sites.json coords + archon-crosswalk.json myth links + geocoded UPDB signal.
- **Radius:** 60km (tightened from 150km — at 150km neighbouring UK sites shared one report pool, producing artifact lifts).
- **KEY FINDING (60km, honest): NULL RESULT.** No data-rich site with a trustworthy baseline over-concentrates UAP reports. Boyne Valley (Newgrange 0.31×, Knowth 0.59×) and UK stone circles sit **at/below** their regional baseline. The earlier 150km "2.5–4.3× Boyne Valley signal" was a coarse-radius artifact and has been retracted. Only Giza clears 2× (4.92×) but on 11 reports in a data-sparse region = LOW confidence, not robust. Solstice timing flat everywhere (~0.8–1.45, noise). This null is the credible outcome and the UI states it plainly.

### UFO / UAP — taxonomy
- **Path:** `src/data/ufo-uap-taxonomy.json`
- **What:** 6 typologies, 31 signatures. Each signature: `description`, `indicators` (needles), `severity`, `precedent_case`. Drives all UAP signature scoring.

### Other conspiracy-seed corpora (on disk, see `src/data/conspiracy-seed/`)
- VAERS (multiple years, 600MB+), JFK files (`jfk_assassination/jfk-files.csv`), Irish sacred sites, etc.
- DOJ press-release corpus referenced by crime pipelines: `doj-complete.jsonl` (~269K) — the "300K+" crime dataset (distinct from UAP data).

---

## When "do we already have this data?" comes up
1. Read this registry.
2. If unsure, search BOTH this workspace AND sibling workspaces under
   `c:\Users\eyreaws\Documents\Sales\2026\Art of Possible Demos\` (e.g. `Finding Fentanyl`)
   before concluding data is missing. Search tools are scoped to the current
   workspace root — widen manually with a recursive listing when needed.
3. Only propose downloading if it is genuinely absent from all of the above.
