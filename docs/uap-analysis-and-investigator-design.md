# UAP Pattern Analysis, Global Map UI & AI Investigator — Design

*Written from the composite lens you asked for: a 20-year MUFON field director + criminal-intelligence analyst + investigative journalist. Covers how the pros actually work, how to prioritize/group findings for a MUFON VP, the global geospatial UI, and whether the investigator is a fixed "playbook" or a dynamic GenAI plan.*

---

## 1. How the pros actually do this (industry best practice)

Three disciplines converge on the same method, and our engine should mirror it:

- **Criminal intelligence analysts** (i2 Analyst's Notebook, Palantir Gotham) work **entity → link → pattern → hypothesis**. They don't read every report; they let the tool cluster, then chase the *anomalies* and the *connectors* (entities linking otherwise-separate cases). Key move: **ranking by corroboration and cross-case linkage, not raw volume.**
- **Investigative journalists** (ICIJ / Panama Papers method: Neo4j + Datashare + Elasticsearch) start from a **question**, follow documents, and let **full-text + graph** surface "who/what connects." Their discipline: every claim traces to a primary source (provenance), and they publish the *open question*, not just the answer.
- **MUFON field investigators** already do our loop by hand: intake → classify (Hynek/CE grade) → corroborate → dispose (IFO vs unexplained). Their pain is scale — they can't cross-reference 300K reports across 220 countries.

**What the best software does today:** graph DB (connections) + search engine (retrieval) + a case-management layer + a map. **What none of them do well:** *automated pattern-signature scoring* that says "this report fires the impossible-kinematics + radar-visual + military-witness signatures — investigate first." That is exactly our TALOS augment.

**Our augmentation thesis:** we bolt a **pattern-detection layer** (31 data-validated signatures) + **cross-domain scoring** + a **dynamic AI investigator** onto the classic graph+search+map stack. The analyst stops reading noise and starts at the ranked, corroborated, signature-firing cases — with an AI that drafts the next investigative step.

---

## 2. How to prioritize & group findings — the MUFON VP view

A director does not want 300K dots. They want a **triage board** answering "what's most worth my investigators' time, and why." Prioritize by a composite **Investigative Priority Score**, not volume:

```
priority = anomaly_strength (signature severity)
         × corroboration (multi-witness, radar-visual, physical trace)
         × source_credibility (pilot/military/govt > single civilian)
         − prosaic_penalty (hoax/misID signals; GEIPAN-calibrated)
         × cross_case_linkage (shared entities/locations/craft-type across cases)
```

**Group findings into a tiered board the VP navigates top-down:**

1. **Tier 1 — "Bring me these" (highest priority):** cases firing *critical* signatures WITH corroboration — e.g. `impossible_kinematics` + `radar_visual` + `credible_witness` (the Nimitz-class profile), or `trans_medium`/USO with naval witnesses. Small set, high confidence, official-grade.
2. **Tier 2 — Waves & clusters:** geo/temporal clusters (the event-clustering output) — mass sightings, recurring hotspots, cross-national concordance (same craft-morphology firing in France GEIPAN + US NUFORC + UK MoD). This is the "pattern that transcends one witness" tier.
3. **Tier 3 — Cross-cutting anomalies:** cases that fire signatures from *other* domains too (institutional_response ↔ conspiracy evidence_suppression) — the structurally interesting ones.
4. **Tier 4 — Explained/low-signal:** down-ranked (prosaic-penalty high), kept for baseline/calibration, collapsed by default.

**Drill path (what the VP clicks):** Tier → typology (e.g. flight_kinematics) → the **needles that fired** (the specific indicator strings: "no sonic boom", "tracked at 3,755 mph") → the underlying reports (primary source) → the AI-drafted investigation plan.

---

## 3. The global geospatial map (reuse Ancient Mysteries map)

Yes — reuse the Ancient Mysteries / geographic-explorer MapLibre component. It already does clustered markers, region drill-down, and a narrative sidebar. Adapt it for UAP:

- **Layer 1 — density heat/clusters:** all signature-firing reports by geo-cell (we have lat/lng on NUFORC + UPDB + GEIPAN). Instantly shows the hotspots (LA basin, Pacific Northwest, plus global: UK, France, Australia, Brazil).
- **Layer 2 — priority markers:** Tier-1 cases as distinct high-contrast pins (radar-visual, USO, military) so the VP sees the "bring me these" set on the map.
- **Layer 3 — signature filter:** toggle by typology (show only trans-medium/USO → the maritime cases light up along coasts; show only military-intercept → they cluster near bases/ranges). This is the "aha" — patterns have geography.
- **Layer 4 — cross-national concordance:** draw connectors when the SAME signature fires densely in multiple countries (the strongest signal — a pattern independent of any one nation's reporting culture).
- **Sidebar on click:** the case's fired signatures, needles, corroboration, disposition (GEIPAN A/B/C/D where present), and "Investigate" button → launches the AI investigator.

The map is the entry point; the triage board and drill-down hang off it.

---

## 4. Playbook vs. dynamic GenAI plan — the honest answer

**Both — it's a hybrid, and that's the right design.** Here's the distinction and why:

- **Money Laundering has a fixed playbook** because the *domain has settled typologies and a legal framework* (structuring, layering, shell companies → known investigative steps, subpoena this, trace that). The steps are stable.
- **UAP does NOT have a settled framework** — there's no "conviction," no legal endpoint, and the right next step depends entirely on what the *first* step finds. A rigid playbook would be false precision.

So the design is a **scaffolded dynamic plan**: a fixed *skeleton* (the investigative phases every good analyst follows) with **GenAI generating the specific steps per case, and each step's findings feeding the next** (your stated requirement).

**The fixed skeleton (from the three pro disciplines):**
1. **Establish the observable** — what fired, what's the physical claim (from signatures/needles).
2. **Corroborate** — find other reports of the same event/craft/location (graph + vector search across all cases). Multi-witness? Radar? Trace?
3. **Rule out the prosaic** — check the hoax/misID signals; cross-ref known aircraft/satellite/astronomical explanations (GEIPAN-style disposition).
4. **Assess credibility** — who are the witnesses (pilot/military/civilian)? official records?
5. **Find the cross-case pattern** — does this connect to other cases via craft-type, geography, time, or entity? (Neptune traversal.)
6. **State the open question** — what would resolve it; what evidence is missing.

**The dynamic part:** GenAI writes the *actual* step-2 query for THIS case ("search all cases for triangular craft within 50km of RAF Bentwaters, 1980±2yr"), runs it, reads the result, and *then* composes step 3 based on what step 2 returned — a chain, not a template. This is exactly the `agent_orchestrator` broad_scanner → taxonomy_scanner → cross_pattern pattern already in the codebase; we drive it with the pattern library + the case's fired signatures as the seed context.

**Verdict:** Money-Laundering-style *structure*, GenAI-generated *content*, findings-chained execution. Present it in the UI as a live "Investigation Plan" that fills in step-by-step, each step showing its finding and the AI's rationale for the next step.

---

## 5. What makes this genuinely better than today's tooling

| Classic tool | What it gives | Our augment |
|---|---|---|
| i2 / Palantir | link analysis, manual patterns | **automated signature scoring** ranks what to link first |
| ICIJ stack (Neo4j+ES) | search + graph, human-driven | **cross-domain k-NN** surfaces non-obvious cross-case/cross-domain matches |
| MUFON CMS | case intake, manual disposition | **31-signature auto-triage** + **GEIPAN-calibrated** prosaic down-ranking |
| Any UFO map | dots on a map | **signature-filtered geography** + cross-national concordance connectors |
| — | — | **dynamic AI investigator** that chains findings into a plan |

The unlock: an analyst opens the board, sees the Tier-1 corroborated anomalies ranked by a defensible score, filters the map by "trans-medium + military witness," clicks the top case, reads the exact needles that fired, and gets an AI-drafted, findings-chained investigation plan — in seconds, across 300K+ global reports they could never read by hand.

---

## 6. Build plan (what gets built next)

1. **UI** — `ufo-command-center.html`: global MapLibre map (reuse geographic-explorer) + priority triage board (4 tiers) + drill-down (typology → needles → reports) + "Investigate" launch. Powered by OpenSearch (hybrid + k-NN) once the enterprise-tier fix lands, Neptune for connections, Aurora for the cached AI findings.
2. **AI Investigator agent** — extend `agent_orchestrator.py`: a `uap_investigator` that takes a case_id, reads its fired signatures, and runs the scaffolded-dynamic plan (§4), persisting each step's finding to Aurora (the Bedrock cache) so re-runs are cheap and the UI can replay the plan.
3. Wire the "needles that fired" view to the full-corpus signature scan output we already produce.
