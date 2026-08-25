# UFO / UAP Global Dataset Landscape

*Best sources to feed the `ufos_uaps` slot and the TALOS tiered loop, ranked. MUFON is priority 1; the rest give global coverage so we can detect cross-national patterns, not just US ones.*

Content below was rephrased/summarized from public sources for licensing compliance; every source is linked to its primary origin.

---

## Priority 1 — MUFON (Mutual UFO Network)

The organization the director described. Its whole workflow is manual pattern-hunting on structured case reports — exactly what our typology + tiered loop automates.

- **MUFON CMS** (Case Management System) — [mufon.com](https://mufon.com/): the live intake DB. Case rows carry Case Number, Date Submitted, Date of Event, short description, City, State/Country, and attachments. **Global already** — the sample rows include non-US cases (e.g. Austria). ~500–1,000+ new cases/month per their [2025 CMS statistics](https://mufon.com/2025/09/10/mufon-cms-statistics-for-2025-the-first-seven-months/).
- **Project Aquarius / MARRS** — [projectaquarius.mufon.com](https://projectaquarius.mufon.com/marrs/): 25+ years of scanned historical case documents, witness-sketch gallery, news clippings, and a UFO reports map. This is rich Tier-3 material (narratives, sketches, investigator notes).
- **Access reality:** MUFON CMS full export is **members/licence-gated** — there is no open bulk download. Realistic paths: (a) MUFON data-sharing agreement/API for the case fields, (b) the MUFON-attributed records already embedded in NUFORC (we extracted 66), (c) third-party aggregations that include MUFON (see UPDB / UFOMAP below). **Recommend: pursue a MUFON data agreement for CMS fields; it is the highest-value structured feed and maps 1:1 to our `encounter_typology` + `witness_reliability` typologies.**

---

## Tier A — Large structured, downloadable now (best for the loop today)

| Source | Size / coverage | Access | Fit |
|---|---|---|---|
| **NUFORC** (we already have it) | ~80–100K+, 1906–present, mostly US but global entries | Open; scraped/cleaned mirrors on [GitHub (timothyrenner)](https://github.com/timothyrenner/nuforc_sightings_data), [Hugging Face (kcimc/NUFORC)](https://huggingface.co/datasets/kcimc/NUFORC) | Already loaded; refresh to current via the maintained mirror |
| **UPDB** (UFO Phenomenon DataBase) | Open-sourced full DB; combined with Hatch = **318,477 events** | Open; full DB dump, tooling at [jamsoft/uap-data-vis-tool](https://github.com/jamsoft/uap-data-vis-tool), analysis repo [ufo-optix/UAP_Sightings_Analysis](https://github.com/ufo-optix/UAP_Sightings_Analysis) | **Strong.** Multi-source, by-country breakdown → real global patterns. Best single next ingest after MUFON. |
| **UFOCAT** | Long-running catalog aggregated into unified DBs | Via aggregators (UFOMAP/UPDB) | Global historical depth |

---

## Tier B — Government / official (highest credibility, Tier-3 gold)

These feed the `sensor_em_signatures`, `witness_reliability` (trained observers), and `institutional_response` typologies — the credibility multipliers.

- **GEIPAN (France / CNES)** — [geipan.cnes.fr](https://geipan.cnes.fr/en/geipan-0): official state body, ~1,600 investigated cases with formal dispositions (explained / unexplained). [CNES opened the dossiers](https://cnes.fr/actualites/geipan-ouvre-dossiers). Structured, categorized, credibility-rated — ideal ground truth for scoring calibration.
- **AARO (US DoD)** — [aaro.mil](https://www.aaro.mil/UAP-Cases/Official-UAP-Imagery/) + [2026 DoW UAP file release](https://www.war.gov/News/Releases/Release/Article/4480582/): official US case reports and imagery with mission-report dispositions ("possible missile", "possible birds"). Sensor-based, military observers.
- **UK National Archives (MoD)** — [nationalarchives.gov.uk UFO guide](https://www.nationalarchives.gov.uk/help-with-your-research/research-guides/ufos/): decades of MoD case files (access is paid/on-site for some).
- **NASA UAP study** — [science.nasa.gov/uap](https://science.nasa.gov/uap/): methodology + scientific framing, useful for taxonomy validation.

---

## Tier C — Curated aggregators (global cross-referencing)

- **UPDB / UFOMAP** — [ufomap.ca](https://www.ufomap.ca/): claims **746,637 sightings** unified from NUFORC + UFOCAT + MUFON + UPDB + UFO-search, cross-referenced with military bases and nuclear plants. Excellent for the geographic-clustering detector (idea #4) — but treat as secondary/derived provenance, and run our Tier-1 filter on it (per steering: filter even pre-processed data).
- **UFO Atlas** — [ufoinsights.com](https://ufoinsights.com/): aggregates NUFORC, MUFON, GEIPAN, AARO + 23 national archives, geocoded + credibility-rated.
- **overclassified.org** — 299 deep case files + 168K raw sightings + 1,748 key figures, cross-referenced and credibility-scored. Good for `key figures` → Neptune entity linking.
- **Xeno / xeno.news** — curated index of primary-source government releases (US PURSUE, Navy videos, UK MoD, GEIPAN, Brazil AF).

---

## Recency-aware re-search (2026) — what the refined + date-bounded search found

Re-ran the source search per the master-loop rule (recency qualifier + refined signature vocab: trans-medium/USO, radar-kinematics, occupant/CE3). Results the earlier generic search missed:

- **PURSUE is now 5 tranches, not 1.** Releases 01–05 (May 8, May 22, Jun 12, Jul 10, Aug 7, 2026) = **~375 files / 333+ cataloged**. We only loaded Release 01 (120 docs). Missing 02–05. Source: [war.gov/UFO](https://www.war.gov/UFO/), [Wikipedia US UFO files](https://en.wikipedia.org/wiki/United_States_UFO_files).
- **PR067 — first officially-released USO footage** (Release 02): spherical objects moving "in and out of water" near a submarine. Directly confirms our new trans-medium/maritime signatures (`uap-fk-tm-001/002/003`). Also Lake Huron F-16 shootdown video + submarine transmedium footage. Sources: [ASIRP brief](https://asirpjournal.substack.com/p/asirp-special-brief-saturday-may), [warufo.com](https://warufo.com/).
- **AARO FY25 Consolidated Annual Report** ([aaro.mil PDF](https://www.aaro.mil/Portals/136/PDFs/FY25%20UAP%20Annual%20Report/AARO_FY2025_Consolidated_Annual_Report_on_UAP.pdf)) + AARO Presidential Transparency Initiative imagery catalog (new 2026 Army / Indo-Pacific cases).
- **Pre-processed community archives for all tranches:** [socialmediaforaliens.com](https://socialmediaforaliens.com/) (333 cataloged, 82 detailed case writeups w/ primary source + explanation + open question), [warufo.com](https://warufo.com/), [uapledger.com](https://uapledger.com/) (records + congressional hearings).
- **Caveat:** no single open dump of RAW military sensor files exists ([paraghosts](https://www.paraghosts.com/)) — public content is video/imagery + reports. Informs the vision-track scope.

*Content rephrased from sources for licensing compliance.*

### Next-source priority (post re-search)
1. **PURSUE Releases 02–05** — text docs via the community pre-processed archives (same path as Release 01). Highest value: PR067 USO footage transcript/writeup validates maritime signatures.
2. **AARO FY25 report** — structured official annual case data.
3. Vision track for the video tranches (separate build — see scope doc).

## Recommendation (mapped to the plan)

1. **Now:** we already have NUFORC loaded. Keep it as the baseline.
2. **Next ingest (open, high-value, global):** **UPDB full dump (~318K, by-country)** — run it through `ufo_tiered_scan.py` Tier 1, then load the survivors. This gives real cross-national patterns immediately, no licensing wait.
3. **Priority pursuit (gated but #1 in value):** **MUFON CMS data agreement** for the case fields + Project Aquarius narratives. Maps directly to `encounter_typology`/`witness_reliability`.
4. **Ground truth / calibration:** **GEIPAN** (1,600 officially-dispositioned cases) — use its explained/unexplained labels to calibrate our signature thresholds and validate the hoax/misID negative signals.
5. **Credibility layer:** **AARO + UK MoD + NASA** for the trained-observer / sensor / institutional signatures.
6. Always: run Tier-1 keyword filter even on pre-processed aggregators; tag every record with its source for provenance (steering rule).

**Global-pattern payoff:** UPDB's by-country breakdown + GEIPAN (France) + UK MoD + Brazil AF (via Xeno) let the geographic-clustering and cross-domain detectors find patterns that repeat across national datasets — e.g. do triangular-craft or EM-interference signatures cluster the same way in France's official cases as in US citizen reports? That cross-national concordance is the strongest possible signal, and it's exactly what MUFON can't do by hand.
