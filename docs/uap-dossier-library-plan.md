# UAP Pattern Dossier Library — Plan

Adapts the Finding-Fentanyl "Mirror Trade" documentary/playbook format to UAP. Each **topic**
is a **Pattern Dossier**: a documentary that explains one phenomenon, backed by real firing
data, ending in a "how to investigate it" checklist and a bespoke AI investigator.

## The 3-level pyramid

```
LIBRARY  (this doc — ~8 strong topics + 3 thematic)
   │
   ▼
DOSSIER  (one topic = one documentary, ~5–10 chapters)
   │  each chapter has a VISUAL type that auto-renders from real data:
   │  stats | map | timeline | process | graph | corroboration | checklist
   ▼
CHAPTER  → drills to the RECEIPTS: the actual KNOWN firing reports (existing Case File view)
```

**Why this beats a catalog:** a sighting website shows you *one report*. A dossier shows you
*the pattern across many sources + languages, the confidence, the null we ruled out*, and lets
you drill to every firing report behind it. Every chapter is backed by real volume, not one anecdote.

## Dossier anatomy (same for every topic — the reusable template)

1. **The Hook** — one-line pattern statement; KNOWN vs ASSESSED up front. `visual: stats`
2. **The Signature, defined** — what the detector actually tests (the needles). `visual: process`
3. **Cross-source corroboration** — same pattern across independent sources/languages. `visual: corroboration`
4–6. **Landmark cases** — 1 chapter per anchor case, KNOWN record + source link. `visual: map|timeline|graph`
7. **The Skeptic's chapter** — prosaic causes + which the signature does/doesn't rule out. `visual: process`
8. **How to investigate it** — the training checklist: which UTS vectors to collect, what confidence each earns. `visual: checklist`
9. **The AI Investigator** — bespoke agent for this exact pattern (a trainee can run it on a real case).

---

## The Library — ~8 strong topics + 3 thematic (grounded in firing counts)

### Tier 1 — Strong standalone dossiers

| # | Dossier | Bundled signatures | Firing (approx) | Landmark anchors | Chapters |
|---|---------|--------------------|-----------------|------------------|----------|
| 1 | **The Silent Triangle** | cm-tri-001/002, cm-formation-001 | 58K / 58K / 112K | Phoenix Lights 1997, Belgian wave 1989-90 | 8 |
| 2 | **The Nuclear Sentinel** ⭐ FIRST | em-strat-001, ir-force-001 | 10,249 / 3,146 | Malmstrom 1967, 1975 SAC wave, Usovo 1982, Japanese SDF | 8 |
| 3 | **Radar-Visual Pilot Encounter** | em-rv-001/002/003, wr-cred-001 | 8K / 27K / 7K / 13K | JAL1628 1986, Nimitz 2004, Belgian F-16 1990, Chile Navy 2014 | 8 |
| 4 | **The Recurring Hotspot** | et-hotspot-001 | 63,537 | Hessdalen (NO), Senganmori (JP), Sedona (US) | 7 |
| 5 | **Impossible Kinematics** | fk-acc-001/002, fk-hov-001 | 9K / 12K / 30K | Nimitz "Tic Tac", GIMBAL/GOFAST 2015 | 7 |
| 6 | **Trans-Medium / USO** | fk-tm-001/002/003 | 7K / 28K / 27K | USS Omaha 2019, Colares 1977 | 7 |
| 7 | **Close Encounter / Occupant** | et-ce-001/002/003, et-landing-001 | 80K / 19K / 17K / 29K | Voronezh 1989, Kofu 1975, Rendlesham 1980 | 8 |
| 8 | **Discs, Orbs & Morphology** | cm-disc-001/002, cm-orb-001, cm-color-001, cm-plasma-001 | 54K / 125K / 30K / 71K / 7K | McMinnville 1950, Petrozavodsk 1977 | 8 |

### Tier 2 — Thematic dossiers (real, but cross-cutting; smaller high-value tails)

| # | Dossier | Bundled signatures | Firing | Role |
|---|---------|--------------------|--------|------|
| 9 | **Physical Evidence & Effects** | em-int-001/002, em-phys-001/002, em-mat-001 | 69K / 15K / 167 / 459 / 211 | The "detective" dossier — car stalls, ground traces, recovered material |
| 10 | **Institutional Response & Suppression** | ir-off-001, ir-sup-001 | 3,544 / 815 | Cross-cutting theme — threads through every other dossier |
| 11 | **The Skeptic's Toolkit** | wr-hoax-001/002 | 2,180 / 2,638 | How we rule things out — recurring chapter more than a standalone |

**Totals:** 8 strong + 3 thematic ≈ **11 dossiers**, each 5–10 chapters ≈ **~60–90 chapters** if fully built.
Do NOT build all at once — the volume exists to make each dossier deep and defensible.

---

## Build order (recommended)

1. **Nuclear Sentinel** — build FULLY as the reusable template (play + case-pull + 8 chapters + AI investigator + UI). ⭐ this session.
2. Then the engine is reused; each new dossier is mostly DATA (play steps, landmark cases, chapter list), not new code.
3. For a demo to an AWS colleague, 3–4 dossiers is plenty: **Nuclear Sentinel + Silent Triangle + Radar-Visual Pilot + Recurring Hotspot.**

## Honesty rules (carried from the enrichment work)
- Every chapter labels KNOWN (verbatim record) vs ASSESSED (inference + WEP term).
- Landmark cases link to the issuing body; we never fabricate a document.
- The Skeptic's chapter is mandatory — a dossier that can't state what it rules out isn't trustworthy.
- The payoff is "how to investigate rigorously," NOT "here's the proof" (UAP can't be proven; that discipline is the differentiator).

---
*Created 2026-08-22. Template source: Finding Fentanyl playbook (plays.ts / documentary-data.ts / playbook engine).*
