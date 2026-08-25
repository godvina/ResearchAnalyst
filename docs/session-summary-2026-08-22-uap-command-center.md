# Session Summary — UAP Command Center (2026-08-22)

## Purpose / framing
DEMO ONLY — never sold or distributed. It shows TALOS's pattern-detection concept
using public, government-released mystery data (UAP) as a stand-in for the DOJ/HSI
cases that can't be exposed. The dataset is a vehicle; the pattern-detection +
AI-investigator + audit discipline is the star.

## Data (see .kiro/steering/data-assets-registry.md)
- Primary source: `docs/updb/updb_reports.json` — UPDB, 296,600 reports, 221 countries.
- Quality profile: median description 658 chars (real narratives); 90% have city+country;
  dates sane (yr 100–2022); ~5.6K empty, ~12.6K short, ~19K dup-ish, ~20K no-detail (filterable).
- Sources in corpus: NUFORC 137,178 · MUFON 94,762 · UFODNA 38,269 · BLUEBOOK 14,027 ·
  NICAP 5,841 · UKGOV 2,837 (UK MoD files) · NIDS · CANADAGOV · SKINWALKER · PILOTS.
  (MUFON CMS itself is proprietary/paid/no-API; these are public MUFON-attributed records.)

## Pipeline: `scripts/ufo_global_updb_pipeline.py`
Tier-1 keyword filter (206,240 kept) → signature firing (178,475 fired ≥1) → geocode
(country centroid + curated cities; 174,455 placed) → emits:
- `src/frontend/uap-command-data.js` — window.UAP_DATA (typology_rollup, sig_meta,
  per_signature_fire, sig_points, cooccurrence_edges, country_rollup, map_points, tiers).
- `src/frontend/uap-case-store.js` — window.UAP_CASES: 1,400 curated rich reports
  (verbatim description, source, source_url, geo, fired_signatures) for the Case File view.

## Frontend: `src/frontend/uap-command-center.html` (+ uts-integrity.js, uap-investigator.js)
- **Discover** view: hero global map + sortable pattern/maturity list.
- **Investigate** view (full-screen 3-col): dossier (maturity 6-elements, documented
  precedent, real case files, KNOWN needles, UTS coverage, gaps, counter-indicators) |
  AI Smart Investigator center-stage (F3EAD, 3-beat WHY/FOUND/SO-WHAT steps, impact tags,
  Guided/Auto, approve/override/inject, verdict + diminishing returns) | supporting
  focused map + co-occurrence D3 graph.
- **Case File** (static, UTS audit-compliant): click a real report → modal with UTS
  provenance chain (source→extraction→pattern-match→analyst-review→ai-conclusion),
  ASSESSED tl;dr (grounded in record fields only), KNOWN verbatim record (unaltered),
  provenance + source-archive link (link out, never reproduce/fabricate the document).
- Confidence/WEP driven by elements-of-proof (investigationStrength), NOT volume share.
- Prosaic Excluder gives cited justification (which prosaic causes the behaviour
  defeats vs leaves open); never dismisses reports on a bare heuristic.

## Governing steering now active in this workspace
- uts-analytical-integrity.md (KNOWN/ASSESSED, UTS 5-vector, WEP, audit trail)
- ai-investigator-agent-standard.md (progressive F3EAD execution)
- data-assets-registry.md + session-continuity-protocol.md (durable memory)
- specs copied: .kiro/specs/playbook-planning-agent/requirements.md

## Verify: local static server (python -m http.server 8000 --bind 127.0.0.1 in src/frontend)
http://127.0.0.1:8000/uap-command-center.html  (hard-refresh; assets cache-busted ?v=22)

## Still HELD (per user): rolling the UTS + investigator + case-file pattern to the other frontend UIs.

---

## Convergence Lab — UAP × Ancient Sites × Mythology
- Script: `scripts/uap_convergence_analysis.py` (LOCAL only, no OpenSearch). Emits
  `scripts/uap_convergence_results.json` + `src/frontend/uap-convergence.js`.
- 22 sites: Irish (from file) + world wonders + data-rich US/UK megaliths (Avebury,
  Silbury, Callanish, Serpent Mound, Cahokia, Chaco Canyon, Glastonbury Tor, Mount
  Shasta, Sedona, Sacsayhuaman) + Spain (Canary Islands / Spanish AF hotspot).
- Method: confound-controlled. Metric = LIFT RATIO (near-site UAP density ÷ **mean of
  16 matched baseline control circles**, Laplace-smoothed so it is always finite). A
  baseline is flagged **unreliable** when fewer than 4/16 controls contain data — those
  sites are NOT scored (no divide-by-near-zero "∞" numbers). Plus a solstice-timing test.
- Radius: **60km** (tightened from 150km).

### IMPORTANT CORRECTION (supersedes the earlier 150km writeup)
The first pass at 150km reported Boyne Valley at 2.55×/4.26×. That was an **artifact**:
at 150km, neighbouring UK/Irish sites shared one report catchment, and the median-based
baseline could collapse to 0 and manufacture huge lifts. After tightening to 60km and
switching to a smoothed-mean baseline with a reliability gate, the honest result is a
**NULL RESULT**:
- Boyne Valley now sits **below** baseline (Newgrange 0.31×, Knowth 0.59×). No anomaly.
- UK stone circles below baseline too (Silbury 0.34×, Glastonbury 0.18×, Stonehenge 0.01×).
- Only **Giza clears 2× (4.92×)**, but on **11 reports in a data-sparse region** →
  small-sample inflation, LOW confidence, not robust.
- Teotihuacan / Avebury have reports but **unreliable baselines** → declined to score.
- Solstice timing FLAT everywhere (0.82–1.45, noise). No temporal signal.
- Conclusion (ASSESSED): UAP reports track **population and reporting culture**, not
  ancient sacred geography. The tool is built to surface this null plainly rather than
  chase a headline.

### UI
- "🔺 Convergence Lab" button opens a modal that leads with the null-result headline,
  then three sections: **Testable** (reports + trustworthy baseline), **Baseline
  unreliable** (declined to score), **No reports in range** (coverage gaps). All figures
  KNOWN, all readings ASSESSED. Cache-bust now **v=12**.

## Data sources added this session
- **ES-AIRFORCE** (Spanish Air Force declassified UFO files, public-domain CC0): fetch
  script `scripts/fetch_spanish_ufo_files.py` → `docs/spanish-ufo/spain_airforce_ufo.json`
  (78 records).
- **GEIPAN / France (CNES)** — we already had it: `docs/geipan/geipan_reports.json`
  (3,381 official cases, A/B/C/D dispositions, REAL lat/lng). Normalized via
  `scripts/build_geipan_pipeline_records.py` and merged into the global pipeline. The
  pipeline now honors source-supplied lat/lng, and French keywords/negatives were added.
  1,095 GEIPAN cases fire; corpus now **300,059**; France = 1,633 firing reports.
- Known remaining gaps (not cleanly obtainable): Russia, Brazil.

## Ley-Line Vertices tab (added to the Convergence Lab)
- Script: `scripts/uap_leyline_convergence.py` (imports the sites-analysis helpers) →
  `src/frontend/uap-leyline-convergence.js` (window.UAP_LEYLINE). Input:
  `src/data/uvg-grid-intersections.json` (20 Becker-Hagens UVG grid vertices).
- Same lift-ratio method PLUS the user's reporting-confound control: a 300km probe
  classifies each vertex **ocean / remote / populated**. A zero at a remote/ocean vertex
  is a **coverage gap, not a null**.
- FINDING (honest): **untestable, not debunked.** 9 vertices are open ocean, 10 are
  remote land (Gulf of Alaska, Aleutians, Siberia, Patagonia, outback, Bermuda Triangle)
  with 0 reports within 300km. Only 1 (INT-0019, Adriatic off Italy) is populated and it
  reads lift 0.15× (below baseline). The grid geometry lands almost entirely where no one
  can report — exactly the confound the user flagged.
- UI: Convergence Lab now has TWO tabs — "🗿 Ancient Sites × Mythology" and
  "🔗 Ley-Lines". Cache-bust now **v=14** (added uap-leyline-convergence.js).

## Ley-Line tab expanded (grid nodes + British St Michael line)
- `scripts/uap_leyline_convergence.py` now scores THREE sets → window.UAP_LEYLINE
  {vertices, grid_nodes, british_ley}:
  1. **20 grid vertices** (line crossings) — untestable (9 ocean, 10 remote, 1 populated below baseline).
  2. **62 grid NODES** — answers "which nations": Japan (Node 10) & Bermuda (Node 14) are
     OFFSHORE/untestable; Russia (2/3/52/53), Sedona, Uluru, Nazca are remote (0 reports
     within 300km); Giza (Node 7) baseline unreliable (2 reports). 0 reliable over-concentrations.
  3. **British St Michael / Apollo line** (populated, testable): Glastonbury Tor 4.29× +
     Burrow Mump 8.46× over-concentrate — BUT 17.3km apart, SAME 54 Somerset reports = one
     local cluster, not a line-wide effect. Other 7 waypoints at/below baseline. HONEST read
     built into the UI headline.
- Per-nation firing coverage recorded in the registry (JP 224, RU 114, KR 73, EG 32, BM 9…
  vs US 151,566) — non-US/UK nations too thin for reliable baselines.

## Data-source search (this turn) — honest outcome
- **Russia "Blue Folder":** searched twice, NO clean processed dataset found. Documented as
  a real gap; not fabricated.
- **US PURSUE (war.gov):** already local (docs/pursue/). **Ukraine Kyiv observatory:** real
  scientific dataset, candidate future add. Japan/Korea/Middle East: no standalone DB; covered
  via UPDB + PURSUE. See registry "Data-source search log".


## Russia + Ukraine added via the seed-first playbook (2026-08-22)
Followed the Finding-Fentanyl pattern: build a documented-precedent SEED, score it to find
signature gaps, author new signatures, THEN fetch a real corpus and merge.

- **Russia seed:** `src/data/conspiracy-seed/russia_soviet_uap/russia_seed.json` (6 famous
  Soviet cases) + `scripts/score_russia_seed.py`. Scoring exposed gaps → 4 NEW signatures.
- **4 new taxonomy signatures** (now 35, was 31): `uap-cm-plasma-001` (jellyfish/plasma; fires
  7,042× on full corpus), `uap-ir-force-001` (military engagement; 3,146×), `uap-em-mat-001`
  (recovered material; 211×), `uap-em-strat-001` (nuclear/missile interference; 157×). The seed
  surfaced patterns already latent in the global data but invisible until authored — the payoff.
- **Russia corpus (RU-SAMIZDAT):** `scripts/fetch_russia_ufo_files.py` → `docs/russia-ufo/russia_ufo.json`
  (211 records from archive.org 'UFO Chronicles of the Soviet Union: A Cosmic Samizdat', item
  B-001-002-573). Russia now 173 firing reports. (First search "found nothing"; the seed-vocabulary
  re-search found it — the recurring pattern.)
- **Ukraine corpus (UA-KYIV-OBS):** `scripts/build_ukraine_uap_records.py` → `docs/ukraine-uap/ukraine_uap.json`
  (8 instrument-measured events from the Kyiv Main Astronomical Observatory / Zhilyaev, arXiv
  2208.11215 / 2211.17085 / 2503.05627 — altitude/speed/size/colorimetry). Ukraine now 39 firing.
- **Pipeline:** both merged after the GEIPAN block in `ufo_global_updb_pipeline.py`; Russian/Cyrillic
  + EN keywords added to Tier-1. Corpus now **300,278**. Convergence + ley-line re-run (findings stable —
  no manufactured signal). Cache-bust now **v=15**.
- **Honest note:** the raw KGB/Popovich archive itself is still only scanned/press material (cited as
  precedent, not ingested). The Ukraine authors explicitly do not interpret their objects; we keep that.


## Japan iteration + enrichment-loop compounding (2026-08-22)
Ran the seed-first loop for Japan and surfaced the RU/UA cases + new signatures in Case Files.

- **Case Files now show the new sources:** case-store selection rewritten with a PRIORITY_SOURCES
  first pass so GEIPAN 40, RU-SAMIZDAT 40, UA-KYIV-OBS 5, ES-AIRFORCE 10, JP-SEED 4 are inspectable
  with source_url links (previously crowded out by dominant English corpora).
- **Japan seed:** `src/data/conspiracy-seed/japan_uap/japan_seed.json` (JAL1628, Kofu, Senganmori,
  SDF-nuclear, Kera) + `scripts/score_japan_seed.py`. Scoring exposed weak occupant/landing needles
  (also missed in the Russia Voronezh case) + a genuinely new recurring-hotspot pattern (Senganmori).
- **Taxonomy now 36** (+`uap-et-hotspot-001` recurring-cluster-at-geophysical-anomaly). Strengthened
  occupant/landing/nuclear indicator vocab; added Japanese kana/kanji Tier-1 keywords.
- **Japan corpus (JP-SEED):** `scripts/build_japan_pipeline_records.py` → `docs/japan-ufo/japan_uap.json`
  (5 documented cases). Honest note: no licence-clean BULK Japanese dataset exists (ufojapan.org curated,
  Enigma commercial) — Japan's contribution is documented cases, like Russia's.
- **Compounding result:** merged all → corpus 300,283, firing 180,952 → **186,907**, countries 195 → **198**.
  The strengthened needles + new signature caught ~6K reports that were previously below threshold — the
  enrichment loop compounding, as seen in the money-laundering work. Convergence + ley-line re-run (stable).
  Cache-bust now **v=16**.
- **NGO/instrument candidates** documented: Galileo Project (top pick — arXiv instrument data), Sol
  Foundation, Enigma Labs, UFODATA/UAPx.
- **Prioritized 10-source roadmap** recorded in the registry: Galileo → Belgium SOBEPS → Chile CEFAA →
  Brazil Colares → Argentina CEFORA → Peru DIFAA → Mexico → Enigma global → Uruguay CRIDOVNI → Italy CUN.


## Step D — data-driven signature gap-mining (2026-08-22)
Locked the signatures before adding more data (user directive: Step D after EVERY dataset).

- **Documented the mandatory loop:** `.kiro/steering/taxonomy-enrichment-master-loop.md` (step 3/4 now
  says run over the WHOLE combined corpus after every merge) + `enrichment-loop-process.md` (Step D section).
- **Gap-miner:** `scripts/mine_signature_gaps.py` -> `scripts/signature_gap_report.json`. Finds Tier-1
  survivors firing 0-1 signatures (near-misses) and clusters their vocabulary.
- **Run 1:** 53,255 near-misses (23,960 zero-fire + 29,295 one-fire). Top uncovered patterns:
  formation/fleet **7,700 (14.5%)**, color-shift 2,166, repeated-return 1,008, animal-reaction 826,
  hum/buzz 547. Bigram 'performance beyond capability known earthly aircraft' 802x.
- **+3 data-supported signatures (36 -> 39):** uap-cm-formation-001, uap-cm-color-001, uap-em-acoustic-001.
- **Compounding lift (biggest yet):** firing 186,907 -> **196,859** (+9,952), countries 198 -> **200**.
  This is mining data we ALREADY had, not adding new data — the iteration-3/4 payoff. Cache-bust **v=17**.
- **Next (queued):** Galileo Project (roadmap #1) — but per the documented rule, run Step D again after it.


## Batch: Galileo + government committees + 2 Step-D rounds + NGO search (2026-08-22)
- **Galileo Project (NGO instrument):** docs/galileo/galileo_uap.json (arXiv 2411.07956; Harvard all-sky
  IR array; ~500K trajectories, 144 ambiguous outliers the authors call LIKELY MUNDANE — framing kept).
- **Step D round 2 (after Galileo):** near-miss pool 53,255 → 35,061 (round-1 sigs absorbed ~18K); no new
  signature (diminishing returns).
- **Government committees (6 countries, one pass):** docs/govt-committees/govt_committees.json — BE-SOBEPS,
  CL-CEFAA, BR-CENIMAR (Colares), AR-CEFAe, PE-DIFAA, UY-CRIDOVNI. All inspectable in Case Files.
- **Step D round 3 (after govt):** near-miss pool unchanged (35,061), identical gap distribution → CONVERGENCE.
  Verdict: taxonomy solid at 39; more documented cases no longer surface new signatures. Honest stop signal.
- **Corpus 300,294 · 39 signatures · 200 countries.** Convergence + ley-line re-run (stable). Cache-bust **v=18**.
- **NGO search (honed vocab):** Project Hessdalen (Norway) = top future documented-case candidate (validates
  the hotspot signature); Sky360/Sky Hub = open-source sensor nets (code, not bulk cases); Enigma 12K+ (product).
  No clean BULK NGO dataset exists — Hessdalen is the recommended next seed.


## Data-source library + Hessdalen + roadmap tail (2026-08-22)
- **Created `docs/uap-data-source-library.md`** — mirrors the Finding-Fentanyl data-source-registry
  format: complete inventory table (source / raw records / path / firing / country / coords / processing),
  fully-ingested + roadmap + not-obtainable sections, taxonomy signature history, and grounded totals.
- **Project Hessdalen (Norway)** ingested: `docs/hessdalen/hessdalen_uap.json` (3 NO-HESSDALEN records) —
  the canonical instrumented recurring-hotspot; validates uap-et-hotspot-001.
- **Roadmap tail**: `docs/roadmap-tail/roadmap_tail_uap.json` — MX-SEDENA (2004 Campeche FLIR) + IT-CUN.
- **Step D round 4** (after Hessdalen+tail): near-miss pool unchanged at 35,061 — 4 consecutive rounds
  agree. Taxonomy CONVERGED at 39 signatures. All new sources inspectable in Case Files.
- **Corpus 300,299 · 39 signatures · 200 countries.** Convergence + ley-line re-run (stable). Cache-bust **v=19**.
- Remaining roadmap (P2/P3, no clean bulk dataset): Sky360/Sky Hub (code), Enigma (product), Hessdalen AMS raw feeds.


## Pattern Dossiers — "Nuclear Sentinel" (first dossier, UI shift) (2026-08-22)
Shifted from data enrichment to the UI/storytelling layer, adapting the Finding-Fentanyl
Mirror-Trade documentary format to UAP.

- **Library plan:** `docs/uap-dossier-library-plan.md` — ~11 dossier topics (Silent Triangle, Nuclear
  Sentinel, Radar-Visual Pilot, Recurring Hotspot, Impossible Kinematics, Trans-Medium/USO, Close
  Encounter, Discs&Morphology + thematic Physical-Evidence / Institutional-Suppression / Skeptic).
  3-level pyramid: Library -> Dossier (5-10 chapters) -> Chapter -> drills to real firing receipts.
- **Anchor cases added:** `docs/us-nuclear/us_nuclear_uap.json` (Malmstrom 1967, 1975 SAC wave,
  Rendlesham/Bentwaters 1980) — all fire uap-em-strat-001, inspectable in Case Files. Corpus 300,302.
- **Nuclear Sentinel dossier built:** `scripts/build_nuclear_sentinel_dossier.py` ->
  `src/frontend/uap-dossiers.js` (window.UAP_DOSSIERS). 9 chapters grounded in the live signal
  (10,252 firing / 18 sources), a 5-step investigation PLAY (SPOT->CONFIRM->CORROBORATE->RULE-OUT->
  ASSESS-WEP), and a bespoke AI investigator config. Chapter visual types: stats, process,
  corroboration, graph, timeline, map, checklist, investigator — each auto-renders from real data.
- **UI:** new "📕 Pattern Dossiers" top-bar button + dossier reader modal (openDossiers/renderDossier
  + per-visual renderers) that drills to the real Case File receipts. Cache-bust **v=20**; IIFE OK; page 200.
- Reusable template: dossiers #2+ are mostly DATA (play + chapters + anchors), not new engine.


## Nuclear Sentinel — full documentary narration (Phase 1 text) (2026-08-22)
The first pass had 1-sentence chapters (a skeleton). Expanded to full documentary scripts.
- Each chapter now has a `narration` (full script, ~190-230 words, Nova-neutral voice) + a short
  `caption`. Total ~1,903 words, ~13 min runtime, ~76-93s per chapter (the 1-2 min/chapter target).
- Grounding discipline: every NUMBER (10,252 firing, source breakdown) and every case detail (Malmstrom,
  Usovo, Rendlesham, Japanese SDF) is KNOWN/ASSESSED-labeled and pulled from the corpus/records;
  connective storytelling is authored prose that invents no fact, quote, or figure.
- UI: chapter header shows ~seconds + word count; Previous/Next chapter nav; hero shows ~13 min runtime.
- Cache-bust v=21. Rebuild: `python scripts/build_nuclear_sentinel_dossier.py`.
- NEXT (Phase 2): Polly audio per chapter (audioUrl) + optional play-episode mode. Check Finding-Fentanyl
  Polly generation script for reuse before building.


## Polly audio for Nuclear Sentinel + honest AI-agent status (2026-08-22)
- **Polly audio generated:** `scripts/generate_dossier_audio.py` reads narration from uap-dossiers.js,
  synthesizes one neural-voice MP3 per chapter (VoiceId=Matthew), writes to
  src/frontend/audio/dossiers/, and writes `audio` paths back into the dossier + a manifest.
  9/9 chapters have audio (~390-460 KB each). AWS Polly call succeeded (creds present).
- **UI:** each chapter now shows an <audio controls> player; hero has a "▶ Play episode
  (auto-advance)" button that autoplays and advances chapter-to-chapter on audio `ended`.
  Cache-bust v=22; IIFE OK; MP3 serves 200.
- **HONEST STATUS — the bespoke AI investigator is NOT yet functional.** It exists as a config
  (opening/play/prosaic-checklist/confidence-ladder) shown in the dossier; clicking a practice case
  opens the KNOWN record but does NOT yet run the 5 steps to a live verdict. The engine to run it
  (window.UAPInvestigator: newState/planNext/runAgent/verdictFor in uap-investigator.js) already
  exists — NEXT TASK is to wire the uap-nuclear-sentinel play into it so cases run live with reasoning
  + WEP confidence.
- Regenerate audio: `python scripts/generate_dossier_audio.py` (requires AWS creds + boto3).


## Dossier chapter visuals upgraded to real diagrams (2026-08-22)
The chapter visuals were plain divs (the map/graph chapters were just text + a list). Made real:
- **map chapter** → a live **Leaflet mini-map** (CartoDB dark tiles) with the nuclear-site anchor
  points plotted (Malmstrom, 1975 wave, Rendlesham, Usovo) + tooltips.
- **landmark (graph) chapter** → a live **D3 force network**: the case at center wired to the
  signatures it fired (nuclear-interference, formation, occupant, landing) + sibling cases (1975 SAC
  wave, Usovo). visualData.nodes/links added in build_nuclear_sentinel_dossier.py.
- **corroboration** → proportional **bar chart** (NUFORC 5,238 longest bar, etc.) instead of tiles.
- Added `dosMount(ch)` — after renderDossier injects innerHTML, a setTimeout(~110ms) spins up the
  Leaflet map / D3 sim into the chapter containers (invalidateSize + fitBounds), cleaning up prior
  instances on re-render. Reuses the page's existing Leaflet + D3 (already loaded).
- IMPORTANT build order: `build_nuclear_sentinel_dossier.py` OVERWRITES uap-dossiers.js (drops audio
  paths), so ALWAYS run `generate_dossier_audio.py` AFTER a rebuild to re-attach audio. Verified 9/9
  audio intact. Cache-bust v=23; IIFE OK; page 200.


## 2nd dossier: The Boyne Valley (Ireland trip companion) (2026-08-22)
- `scripts/build_boyne_valley_dossier.py` APPENDS a 2nd dossier to window.UAP_DOSSIERS (keeps Nuclear
  Sentinel). 8 chapters, ~11 min, 1,635 words, Nova-neutral, ON-LOCATION framing: Hook(map); Newgrange
  roofbox/110Hz/Boann (mythology D3 net); Knowth lunar art (stats); Dowth/Tara/Loughcrew sequence
  (process); Tuatha Dé Danann (mythology net, labelled tradition-not-history); Newgrange↔Giza global
  thread (map); the HONEST UAP chapter (Boyne lift 0.3/0.59 = at/below baseline, signal dissolved when
  method tightened); How to visit (field checklist).
- Grounded in tier2_deep_research.json (roofbox azimuth 134.5°, 110Hz, Loughcrew→Newgrange→Tara
  sequence, Newgrange↔Giza 110Hz), archon-crosswalk.json (12 deity→site mappings), convergence results.
  KNOWN=measured; ASSESSED=interpretation; myth labelled as tradition.
- Polly audio: 17 total clips now (9 Nuclear Sentinel + 8 Boyne Valley). build THEN audio (build
  overwrites audio paths).
- UI: openDossiers now shows a PICKER (dos-lib cards) when >1 dossier; "← All dossiers" back button in
  hero; renderDossierList(). Cache-bust v=24; IIFE OK; page + audio 200.
- OFFLINE PACK for the trip: `docs/boyne-valley-offline-pack.md` — exact file list (html + 6 uap-*.js +
  audio/dossiers/*.mp3), relative paths so it runs from a downloaded folder with no cell service. Caveat:
  Leaflet map tiles + D3 are CDN — audio/text/stats work offline; maps blank without signal (offer to
  bundle local leaflet/d3 + static map image if wanted).


## Fully-offline maps for the Ireland trip (2026-08-22)
- Vendored libs locally: src/frontend/vendor/ = leaflet.js, leaflet.css, leaflet.markercluster.js,
  MarkerCluster(.Default).css, d3.v7.min.js, images/marker-*.png. Page tags switched from unpkg/d3js
  CDN to vendor/ (verified: zero CDN refs remain).
- Dossier 'map' chapters now render as self-contained INLINE SVG (dosMount): markers + labels from
  lat/lng over a padded bounding box + dashed connector + faint graticule. No tiles, no network.
  Boyne Valley site map + Newgrange↔Giza map both draw offline.
- docs/boyne-valley-offline-pack.md updated: added vendor/ to the download list, removed the CDN caveat
  ("fully offline now"). Cache-bust v=25; IIFE OK; vendor + page 200.
- The Discover world map's satellite tiles still need signal (not part of the dossier); dossier = 100% offline.