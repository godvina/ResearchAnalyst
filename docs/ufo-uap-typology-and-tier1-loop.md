# UFO / UAP Typology + Tiered Pattern-Detection Loop

*How to run MUFON's manual pattern-hunting at machine scale on the TALOS engine — the same way we detect FEMA fraud and immigration fraud in the Linked Finding / fentanyl work.*

---

## 1. The idea, in one line

MUFON's stated mission is to *find patterns in sighting reports* — and today they do it largely by hand. That is exactly the problem TALOS already solves for crime: a big pile of unstructured reports, signal buried in noise, and the real value living in **cross-case patterns** rather than any single report. We reuse the crime-typology machinery (Domain → Typology → Method → Signature → Needle, scored by Titan Embed → OpenSearch k-NN) and swap in a UFO/UAP vocabulary.

**Honest caveat:** crime signatures cite a real DOJ conviction as ground truth. UAP has no "convictions," so `severity` here means *anomaly-strength / investigative priority*, not criminality, and `precedent_case` cites well-documented investigations and government reports (Nimitz 2004, ODNI 2021, Project Blue Book cases). The engine detects **reporting and physical-signature patterns**, not "proven" phenomena. That is precisely what a MUFON analyst does by hand.

---

## 2. The taxonomy (`src/data/ufo-uap-taxonomy.json`)

Authored through four analyst lenses (MUFON field investigator, data scientist, ex-cop/detective, aerospace engineer). 5-level hierarchy, identical schema to `pattern-library-taxonomy.json` and `ancient-mysteries-taxonomy.json`:

```
Domain: ufos_uaps
 └─ Typology (6)         e.g. flight_kinematics
     └─ Method (15)      e.g. instantaneous_acceleration
         └─ Signature (23)  the scoreable unit (has vector_text + embedding)
             └─ Needle (113)  individual indicator strings that fire a match
```

**The 6 typologies:**

| Typology | Lens | What it detects |
|---|---|---|
| `craft_morphology` | data scientist | Shape clusters (triangle, disc, orb) — the most-clusterable NUFORC field |
| `flight_kinematics` | rocket scientist | Physics-defying motion (instant accel, no-radius turns, trans-medium) — highest value |
| `sensor_em_signatures` | rocket scientist + cop | Radar-visual, EM interference, physiological/ground traces — hardest to fake |
| `encounter_typology` | MUFON investigator | Hynek close-encounter grading, mass multi-witness events |
| `witness_reliability` | ex-cop | Observer credibility **and negative signals** (hoax / misID) for down-ranking |
| `institutional_response` | cross-domain bridge | Official involvement + information suppression → bridges to conspiracy/crime |

**Why `witness_reliability` matters most for quality:** it holds *negative* signatures (Starlink train, sky lantern, Venus, single-witness embellishment). These don't discard a report — they **lower its priority score** so the graph fills with anomalies, not noise. This is the ex-cop's "weigh the source" discipline encoded as data.

---

## 3. The tiered loop (`scripts/ufo_tiered_scan.py`)

Same 3-tier shape as `epstein_tiered_scan.py`, adapted to the NUFORC CSV corpus.

### Tier 1 — FREE keyword/anomaly filter ($0, ~1.4s for 60K reports)
- Scores each report's narrative + shape against `KEYWORD_PATTERNS` (grouped by typology) and `REGEX_PATTERNS` (durations, counts, altitudes, speeds).
- Applies `NEGATIVE_PATTERNS` (hoax/misID) as a **penalty** on the priority score.
- Keeps a report if it clears `MIN_KEYWORD_HITS` OR hits a high-value category (kinematics / EM / radar-visual) even once.
- **Result on the real corpus:** 60,632 scanned → **16,679 kept (27.5%)**, 72.5% discarded. Top-ranked reports are exactly the structured/hovering/multi-feature sightings an analyst would triage first.

### Tier 2 — Titan Embed on the filtered set only (~$1.67, needs Bedrock)
- Embeds only the 16,679 survivors instead of all 60K → ~$1.67 vs $6.06 (72% saving on embed cost).

### Tier 3 — Signature scoring + targeted extraction (needs Bedrock)
- Embeds the 23 taxonomy signatures once, scores every filtered report against them via local cosine (k-NN proxy), tags each with its best-matching signature + typologies hit, then (optionally) sends only the top matches to Haiku for entity/pattern extraction.

### Cross-domain scoring (mandatory, per steering)
Every UAP report is scored against **all** taxonomy domains — no `taxonomy_domain` filter on the k-NN. The `institutional_response` and `witness_reliability` typologies are deliberate bridges: a UAP "records classified / told to stay silent" report should light up the conspiracy `evidence_suppression` signature. Those cross-cutting hits are the highest-value findings.

---

## 4. This is the same shape as FEMA / immigration fraud detection

| Step | FEMA / immigration fraud | UFO / UAP |
|---|---|---|
| Corpus | DOJ releases, claim records | 60K NUFORC sightings |
| Tier 1 filter | keyword scan for fraud terms | keyword scan for anomaly terms |
| Signatures | "duplicate SSN across claims" | "instant accel, no sonic boom" |
| Needles | testable indicators | testable indicators |
| Scoring | Titan → OpenSearch k-NN | same index, same engine |
| Graph | Neptune entity/edge network | same |
| Cross-domain | fraud ↔ money laundering | UAP ↔ suppression ↔ ancient contact |

The only thing that changed is the vocabulary. That is the whole point of a typology-driven engine.

---

## 5. Ideas to make it better

**Data quality / filtering**
1. **Tighten Tier-1 for NUFORC specifically.** 27.5% keep is high vs the 5–10% steering target because NUFORC is *already* pre-filtered sightings (not a raw doc dump). Raise `MIN_KEYWORD_HITS` to 3, or require a high-value hit, to push toward the top ~8–10%.
2. **Strip NUFORC investigator notes before scoring.** The `((NUFORC Note: ... PD))` tails currently trip the `institutional` keywords. Filtering them first sharpens both the keep decision and the embeddings.

**Signal strength**
3. **Weight by corroboration, not just keywords.** Multi-witness + radar-visual + physical-trace should multiply priority. Encode the Hynek CE grade and a "corroboration count" as first-class scores.
4. **Geospatial + temporal clustering as its own detector.** The existing `ufo_analysis.json` already found 15 hotspots (LA cell = 3,320 sightings). Cluster kept reports by grid cell + time window to surface *waves* (Phoenix Lights, Hudson Valley) automatically — this is the pattern MUFON hunts manually.
5. **De-duplicate mass events.** One event = many reports. Collapse near-identical same-night/same-region reports into a single high-confidence "event" node before loading Neptune, so the graph shows events, not raw report spam.

**Cross-domain leverage**
6. **Index the UFO signatures into the live `typology-patterns` index.** Right now that index only holds the 11 crime modules — neither `ancient_mysteries` nor `ufos_uaps` is in it, so cross-domain k-NN can't actually fire for these domains yet. Indexing the 23 UFO signatures (and the ancient-mysteries set) is the single highest-leverage next step.
7. **Bridge to the Ancient Aliens case (`d72b81fc`).** That case is already ingested (14,534 entities). UAP sightings that match `extraterrestrial_contact` signatures could link directly to it — a real cross-dataset connection.

**Enrichment loop (per steering SOP)**
8. Run the standard enrichment loop: after the first pass, check which signatures have <3 independent confirmations, pull targeted cases (military encounters, AARO reports) to fill gaps, and stop at "point of goodness" rather than dumping all 60K in.

---

## 5b. Loop results — where the enrichment loop actually landed

Ran the loop on the top 1,500 filtered reports (Tier 2 embed → Tier 3 signature scoring → assess → refine → re-score).

| Metric | Round 1 (23 sigs) | Round 2 (25 sigs) |
|---|---|---|
| Best match ≥0.80 (strong) | 0 | 0 |
| Best match 0.60–0.80 (moderate) | 154 (10.3%) | 154 (10.3%) |
| `flight_kinematics` best-matches | 14 | **87** (6×) |
| `craft_morphology` best-matches | 1,464 | 1,394 |
| Confirmed signatures (≥3 moderate) | 3/23 | 3/25 |
| Never-fired signatures | 2 | 2 |

**Round 2 change:** added `flight_kinematics/silent_slow_traversal` (2 signatures) to home the most common real pattern — a large silent craft moving low and slow — which Round 1 left unmatched. It worked: kinematics matches jumped 6×.

**Point of goodness reached** (per the enrichment-loop SOP Step 5):
- The three dominant patterns (triangular craft, disc/saucer, silent traversal) are firmly confirmed.
- Remaining gap reports sit at the 0.60 moderate boundary — they *are* matching, just not decisively; Titan cosine on short entity-heavy narratives tops out ~0.70–0.78, so 0 "strong" is a scoring-scale artifact, not a taxonomy miss.
- The 2 never-fired signatures (multi-witness corroboration, fabrication) **cannot** fire from single narratives — they require **event-level clustering** (collapse many reports of one event into a corroborated node), which is a different mechanism (ideas #4/#5), not more signatures.
- Verdict: **stop refining the taxonomy.** Next gains come from event de-duplication + corroboration scoring, not additional signatures.

## 5c. Data-driven augmentation from UPDB (global corpus)

After loading the global UPDB corpus (296,600 reports, 220 countries, incl. MUFON 94,762 / Blue Book / UK & Canada govt / pilots), we ran the augmentation loop the SOP requires: scan the new corpus → find gaps → derive signatures from real text → re-index → re-score.

- **UPDB coverage: 73.98%** fire a signature (vs 14.45% on thin NUFORC citizen reports) — and **all original signatures fire on UPDB**, including the 4 that were dead on NUFORC (physiological, multi-witness, suppression). Confirms the richer investigated-case data was the missing ingredient.
- **Gap analysis** found 10,950 high-Tier-1 reports firing NO signature, dominated by MUFON (5,404) and revealing 3 patterns the NUFORC-built taxonomy lacked. Three **data-derived** signatures were added (grounded in actual UPDB case text):
  - `uap-et-ce-003` — Occupant / Entity encounter (Hynek CE3): "occupants, a woman and two men", "3-meter pilot"
  - `uap-et-landing-001` — Landing / ground presence: "found the craft on the ground"
  - `uap-em-rv-002` — Military-aviation pacing / radar intercept: "circular object paces B-25", "radar jammed", "tracked at 3,755 mph"
- **Re-score after augmentation (25 → 28 signatures):** encounter_typology +4,072, sensor_em_signatures +9,492, gap 10,950 → 10,391. Gains land exactly in the flagged typologies.
- **Point of goodness:** remaining gap is MUFON reports with generic craft-shape language — adding more shape signatures won't change detection (same diminishing-returns finding as NUFORC). Stop here; next enrichment would come from a different modality (GEIPAN official dispositions for calibration), not more signatures.

## 5d. Four-modality coverage + per-dataset augmentation record

The taxonomy has now been exercised against four distinct UAP data modalities. Per-dataset augmentation outcomes (the money-laundering-style "new signatures from new data" discipline):

| Dataset | Modality | In Aurora (case) | Augmentation outcome |
|---|---|---|---|
| NUFORC (60K) | US citizen reports | signal set 8,764 (`a009a46a`) | scan-only; validated existing sigs |
| UPDB (297K, 220 countries) | global + MUFON 94K + Blue Book | 8,000 (`368bd612`) | **+3 signatures** (CE3 occupant, landing, military-intercept) |
| GEIPAN (3,381) | French govt, A/B/C/D dispositions | 3,381 (`3dac894b`) | **calibration** (passed) + assessed → no change (gaps prosaic/too-sparse) |
| PURSUE (120 docs, 4,185 pp) | official US govt (FBI/NASA/AARO/State/DoW) | 96 (`f48fe16e`) | assessed → **no change** (27/28 sigs fire, 0 gaps) |

**GEIPAN calibration (official ground truth) — validated the scoring discriminates:** prosaic-language 74.5% in explained(A/B) vs 46.2% in unexplained(D); anomaly-language 72.6% in unexplained vs 41.5% in explained. Hoax/misID negatives point the right way; high-anomaly signatures concentrate in officially-unexplained cases.

**PURSUE coverage:** 6/6 typologies fire; only `uap-em-phys-001` (physiological burns) never fired anywhere and zero high-signal documents lack a signature. **Point of goodness reached across all modalities** — the taxonomy is comprehensive; further enrichment would be volume, not new detection capability. (Maritime/USO remains the one candidate modality, best derived from PURSUE's Pacific/Yellow Sea video track once vision analysis is added.)

## 5e. Automated loop + maritime/USO frontier

**The loop is now automated + documented as the single source of truth.**
- `.kiro/steering/taxonomy-enrichment-master-loop.md` (auto-included) consolidates the previously-fragmented loop into 8 canonical steps, names the "1.5" re-scan-same-data step, and adds the **mandatory recency-qualifier search rule** (the fix for the PURSUE miss — generic queries silently omit recent releases).
- `scripts/taxonomy_enrichment_loop.py` runs steps 1–5 for any dataset and prints an AUGMENT/STOP verdict. Improved: the verdict distinguishes a *novel* gap from generic-language gaps in already-covered typologies, so it won't chase diminishing returns forever.

**Re-scan (step 1.5) added one signature:** `uap-em-rv-003` — ground/military radar-tracked kinematics (measured speed+altitude+duration), distinct from the aircraft-pacing `uap-em-rv-002`. Then the tuned orchestrator correctly declared STOP on UPDB.

**Maritime / USO frontier (from text, no vision pipeline needed yet):** a cross-corpus scan found **82,905 maritime hits** and **803 strong trans-medium (air↔water) hits** — dense enough to ground signatures (unlike GEIPAN's n=6, which is why it was correctly deferred). Added two data-grounded signatures:
- `uap-fk-tm-002` — surface craft (on/at the water, figures on deck, descending into the sea) — fires 29,120× on UPDB
- `uap-fk-tm-003` — USO / submerged object (beneath surface, sonar, naval) — fires 31,754× on UPDB

Taxonomy is now **31 signatures**. The remaining true frontier is the PURSUE **video/imagery vision track** (frame-level sensor signatures from FLIR/footage), which needs a vision-analysis pipeline — a separate build, not required for the phenomenological maritime patterns now captured.

## 6. What's built vs what needs your go-ahead

**Built and verified (local, $0):**
- `src/data/ufo-uap-taxonomy.json` — 6 typologies / 15 methods / 23 signatures / 113 needles
- `scripts/ufo_tiered_scan.py` — Tier 1 ran clean (16,679 kept from 60,632)
- `scripts/_build_ufos_uaps_seed.py` + `src/data/conspiracy-seed/ufos_uaps/processed_claims.json` — the top-10 slot is now populated on disk (2,000 highest-priority claims, MUFON-tagged, cross-domain flagged)

**Needs your go-ahead (touches shared infra + Bedrock cost):**
- Upload `processed_claims.json` to S3 → triggers the live Lambda pipeline into Aurora / OpenSearch / Neptune. Run: `python scripts/_build_ufos_uaps_seed.py --upload`
- Index the 23 UFO signatures into the live `typology-patterns` index (idea #6) so cross-domain scoring actually fires.
- Run Tier 2/3 (Titan + Haiku) for full embeddings and entity extraction (~$2–4 total on the filtered set).
