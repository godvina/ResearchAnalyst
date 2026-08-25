---
inclusion: auto
---

# Taxonomy Enrichment Master Loop (single source of truth)

This is the authoritative, end-to-end loop for building a detection taxonomy (signatures/needles)
and grounding it in real data. It CONSOLIDATES three older docs that fragmented the process:
- `enrichment-loop-process.md` (gap-assess → enrich → diminishing-returns)
- `tiered-data-processing.md` (Tier 1/2/3 + data-driven taxonomy generation)
- `data-processing-rules.md` (load steps + pre-processed-check)

When any of those conflict, THIS doc wins. Follow it AUTOMATICALLY for any new domain/dataset —
do not wait to be asked. It is a loop, not a one-shot.

## The Loop (canonical order)

0. **Knowledge seed.** Author an initial taxonomy from domain knowledge + known landmark cases
   (Domain → Typology → Method → Signature → Needle). This is the starting hypothesis, not the answer.
1. **Tier-1 filter** the target dataset (FREE keyword/regex scan). Discard noise, rank by priority.
2. **Test / score** the filtered set against the current signatures (needle scan; Tier-2 embed + Tier-3
   k-NN when depth is warranted).
3. **Gap analysis / gap-mining (aka "Step D" — MANDATORY AFTER EVERY DATASET MERGE, DO NOT SKIP).**
   Run this over the WHOLE combined firing corpus (all merged sources together), not just the dataset
   you just added. Find: which signatures never fire; which Tier-1 survivors fire 0–1 signatures
   (the "near-misses"); which recurring vocabulary/phrase clusters in those near-misses reveal a
   pattern the taxonomy still lacks — grouped by source/country/type. Tooling: `scripts/mine_signature_gaps.py`
   (near-miss extraction + phrase clustering with frequency + example reports).
   RULE: **after adding ANY new dataset (national source, NGO, scientific), you MUST return to Step D
   and re-mine before adding the next dataset.** Solidify the signatures first; then move on. This is
   the step that produced the compounding "iteration 3/4" gold in the money-laundering work.
4. **Augment from the data.** Derive NEW signatures from the gap clusters, grounded in real record text
   with a frequency count + a cited example per signature (only author what the corpus supports — no
   "looks right" signatures). Re-index the taxonomy. Re-score the existing seeds to confirm no
   regressions. Re-run the global scan and record the firing-count / country delta (the compounding lift).
5. **Diminishing-returns check (MANDATORY, every round).** Would another signature change what fires?
   If the remaining gaps are prosaic (correctly unmodeled) or too sparse (n too small to ground a
   signature), STOP augmenting this dataset — that IS the loop working. Max 3 augment rounds per dataset
   before a forced stop-check.
6. **Broaden: search the internet for BETTER/NEW sources** using the *refined* taxonomy vocabulary as
   the query (the specific signature/needle terms you just learned), NOT generic terms. See the search
   rules below.
7. **Acquire → check pre-processed first → Tier-1 → repeat from step 2** on the new source.
8. **Point of goodness (across sources).** Stop when every typology has 3+ independent confirmations
   across multiple sources, and new data would add volume but not change detection confidence. Document:
   per-dataset augmentation outcome + why you stopped.

## Search rules (why PURSUE was missed — do not repeat)
The external-source search (step 6) MUST be recency-aware, or major recent releases get missed:
- ALWAYS include a date/recency qualifier: `"<domain> dataset 2026"`, `"latest <domain> release"`,
  `"recent government <domain> files"`. A generic `"<domain> datasets"` query silently omits new releases.
- Run at least one query explicitly scoped to the CURRENT year and one to "government/official release".
- Prefer official + community-mirror pairs; per data-processing-rules, ALWAYS check for a pre-processed
  version (OCR/markdown/JSON) before re-processing raw PDFs/videos.
- Re-run the broaden-search whenever the taxonomy vocabulary materially changes (new signatures =
  new, better query terms).
FAILURE ON RECORD: initial UFO search used generic terms and missed PURSUE (US Dept of War UAP release,
May–Aug 2026). A date-bounded query surfaced it instantly. Recency qualifier is now mandatory.

## Automation
`scripts/taxonomy_enrichment_loop.py` runs steps 1–5 for a dataset in one command
(Tier-1 → signature scan → gap analysis → diminishing-returns verdict), and prints whether to
augment or stop. Steps 0/6/7 (authoring signatures, web search, acquisition) stay human-in-the-loop
by design, but the doc + script make the sequence repeatable and hard to skip.

## Per-dataset augmentation record (keep this updated)
| Dataset | Outcome |
|---|---|
| NUFORC 60K | scan-only (pre-automation); existing sigs validated |
| UPDB 297K (global+MUFON) | +3 signatures (CE3 occupant, landing, military-intercept) |
| GEIPAN 3,381 (French govt A/B/C/D) | calibration passed; assessed → no change (gaps prosaic/sparse) |
| PURSUE 120 docs (US govt) | assessed → no change (27/28 fire, 0 gaps) |
| ES-AIRFORCE 78 (Spanish AF) | merged; Spanish keywords added |
| GEIPAN merge into global pipeline | merged with real coords; French keywords |
| Russia seed (6 cases) + RU-SAMIZDAT 211 | +4 signatures (plasma/jellyfish, strategic-weapons interference, recovered-material, military-engagement) |
| Ukraine UA-KYIV-OBS 8 (Kyiv Obs instrument) | merged; scientific instrument data |
| Japan seed (5) + JP-SEED | +1 signature (recurring-hotspot); strengthened occupant/landing/nuclear needles; firing 180,952→186,907, countries 195→198 |
| **Step D on combined corpus (round 1)** | 53,255 near-misses mined -> +3 signatures (formation 14.5%, color 4.1%, acoustic); firing 186,907 -> 196,859, countries 198 -> 200 |
| Galileo Project (Harvard IR array, NGO) | merged as instrument source (methodology, not case corpus); no new signature |
| **Step D round 2 (after Galileo)** | near-miss pool 53,255 -> 35,061 (round-1 sigs absorbed ~18K). Diminishing-returns verdict: NO new signature — residual gaps all <=7.3% and already-covered or too sparse/prosaic. Taxonomy solid at 39. Loop converging. |
| Government committees (BE/CL/BR/AR/PE/UY, 8 cases) | merged as documented seeds; Step D round 3 unchanged (35,061) — no new signature |
| Hessdalen (NO) + roadmap tail (MX-SEDENA, IT-CUN) | merged; Step D round 4 unchanged (35,061) — no new signature. CONVERGED (4 consecutive rounds). |

## Signature count history
31 (base) → 35 (Russia seed) → 36 (Japan seed) → 39 (Step D gap-mining: formation, color, acoustic)

## Do NOT
- Skip step 3/4 and go straight from Tier-1 to load (the recurring shortcut).
- Hand-craft signatures with no data backing (they "look right" but never fire).
- Search for new sources with generic, non-date-bounded terms.
- Re-process raw docs when a community pre-processed OCR/markdown version exists.
