# Session Summary — 2026-08-02 Session 2: Sky Mirror + Conspiracy Theory Taxonomy Platform

## Session Handoff

### To resume, tell the next session:
> "Continue from `docs/session-summary-2026-08-02-session2.md`. Sky Mirror working on Orion Correlation page. Conspiracy Theory Taxonomy fully spec'd and implemented (code complete). Proof Engine live with Bedrock — evaluated 10 Ancient Alien theories. Next: download real NTSB Bermuda Triangle data, run Aurora migration, run full validation pipeline, build Theory Registry frontend."

---

## COMPLETED THIS SESSION

### Sky Mirror View (orion-correlation.html)
- [x] Sky Mirror v1-v5: full precessing star field reflected on satellite imagery
- [x] 5 constellations (Orion, Draco, Pleiades, Southern Cross, Sirius)
- [x] 6 sacred sites selectable (Giza, Angkor, Teotihuacán, Stonehenge, Sacsayhuamán, Easter Island)
- [x] Stars anchor to pyramid positions, precession rotates them away
- [x] Alignment lock detection at optimal epochs
- [x] Full explanatory text per site (THE STORY / THE PROOF / TRY IT)
- [x] Zoom/pan works — stars stay locked to coordinates
- [x] All 3 pyramids visible at initial zoom (level 15)
- [x] Duplicate lock badge fixed
- [x] Leaflet markers hidden in mirror mode

### Audio Player Fixes (grid-globe-3d.html)
- [x] Deep dive episodes merged with URLs from audio manifest (all 41 chapters playable)
- [x] Intro briefing added ("The Global Grid: What the AI Found", 7 chapters)
- [x] Auto-advance fixed (flows through all 9 episodes/41 chapters)
- [x] Episode dropdown shows 🔬 prefix for deep dives
- [x] Total: 9 episodes, 41 chapters of audio content

### Conspiracy Theory Taxonomy — Full Platform Architecture
- [x] **Spec: conspiracy-theory-taxonomy** (requirements + design + tasks)
  - 9 requirements, 10 universal domains, 20 correctness properties
  - Cross-industry methodology: FinCEN SARs, CMS Fraud, CIA SATs, Insurance SIU, PRISMA, Scientific Method
  - Documentary methodology integration (Hook → Counter-Narrative → Convergence → Reluctant Expert → Implications)
- [x] **Spec: proof-engine** (requirements)
  - 6 standards of proof: scientific, criminal_legal, civil_legal, intelligence, financial_audit, journalistic
  - Evidence checklists, weighted scoring, verdicts (PROVEN/UNPROVEN/INSUFFICIENT)
  - Research directions (what would change the verdict)
- [x] **Spec: theory-registry** (requirements)
  - Theory intake from Ancient Aliens + web expansion
  - Priority scoring, theory clusters, cascade effects
  - User-submitted evidence that changes verdicts

### Implementation (Code Complete)
- [x] Aurora migration: `migrations/conspiracy_taxonomy_schema.sql` (16 tables, all indexes, 6 proof standards seeded)
- [x] OpenSearch index script: `scripts/_create_conspiracy_opensearch_index.py`
- [x] Neptune graph script: `scripts/_create_conspiracy_neptune_schema.py`
- [x] File format adapters: `src/services/conspiracy_ingestion_adapters.py` (PDF, XML, CSV/JSON, HTML, TIFF, FASTA + registry)
- [x] Taxonomy service: `src/services/conspiracy_taxonomy_service.py` (CRUD, proper noun validation, coverage reporting)
- [x] ACH scoring: `src/services/ach_scoring_service.py` (4 hypotheses, Heuer scale, key assumptions check)
- [x] Proof engine: `src/services/proof_engine.py` (6 standards, checklist generation, verdict, research directions)
- [x] Seeding pipeline: `src/services/conspiracy_seeding_pipeline.py` (10-theory ingestion, pattern derivation, 3-theory threshold)
- [x] Validation pipeline: `src/services/conspiracy_validation_pipeline.py` (sequential gating, gap analysis)
- [x] Coverage API: `src/lambdas/api/conspiracy_coverage.py` (coverage, cross-theory report, proof endpoints)
- [x] Pipeline CLI: `scripts/run_conspiracy_pipeline.py` (seed, validate, prove, coverage, status)
- [x] Tenant configs: `src/config/tenants/` (ancient_mysteries, conspiracy_theories, crime)

### Proof Engine — LIVE Results
- [x] Bedrock connected (Titan Embed + Claude 3 Haiku working)
- [x] Evaluated 10 Ancient Alien theories against scientific standard
- [x] Results saved to `src/data/proof-engine-results-ancient-mysteries.json`
- [x] Summary: 0 PROVEN, 6 UNPROVEN, 4 INSUFFICIENT_EVIDENCE
- [x] Top by closeness to proof: Sphinx Water Erosion (0.65), Orion Correlation (0.57), Younger Dryas (0.57)

### Infrastructure Fixes
- [x] GitHub push script: incremental (only changed files), reads token from .env
- [x] .env file created with GitHub token (gitignored)

---

## DATA STATUS

### DATA STATUS

### Loaded and Ready:
| Dataset | Records | Source | Status |
|---------|---------|--------|--------|
| NTSB Bermuda Triangle accidents | 218 real accidents (81 fatal) | avall.mdb (official NTSB) | ✅ Extracted + saved |
| Bermuda Triangle historical incidents | 13 curated incidents | Wikipedia/Britannica | ✅ Seeded |
| Ancient Alien theories | 10 testable theories | Ancient Aliens show + researchers | ✅ Seeded + evaluated by Proof Engine |
| Proof Engine results | 10 verdicts | Live Bedrock evaluation | ✅ Saved to JSON |

### NOT Yet Downloaded:
- Flat Earth LOCO corpus (88M token JSON — available on GitHub)
- UFO/NUFORC CSV (80K sighting records — available on Kaggle)

### NOT Yet Deployed:
- Aurora migration (SQL file ready, not executed against cluster)
- OpenSearch conspiracy-documents index (script ready, not run)
- Neptune Theory/Domain vertices (script ready, not run)

---

## PROOF ENGINE RESULTS (Live AI Evaluation)

| Rank | Theory | Score | Verdict |
|------|--------|-------|---------|
| 1 | Great Sphinx Water Erosion (pre-5000 BCE) | 0.65 | INSUFFICIENT_EVIDENCE |
| 2 | Puma Punku Precision Machining | 0.57 | UNPROVEN |
| 3 | Orion Correlation Theory | 0.57 | INSUFFICIENT_EVIDENCE |
| 4 | Younger Dryas Impact + Lost Civilization | 0.57 | INSUFFICIENT_EVIDENCE |
| 5 | Global Flood Memory as Real Event | 0.50 | INSUFFICIENT_EVIDENCE |
| 6 | Elongated Skulls as Non-Human DNA | 0.42 | UNPROVEN |
| 7 | Nazca Lines as Landing Strips | 0.33 | UNPROVEN |
| 8 | Giza Pyramids as Power Plants | 0.15 | UNPROVEN |
| 9 | Acoustic Levitation of Megaliths | 0.15 | UNPROVEN |
| 10 | Angkor-Draco Correlation | 0.07 | UNPROVEN |

Scientific standard threshold: 0.70. Sphinx Water Erosion is closest (0.65) — needs one more critical item satisfied.

---

## KEY FILES (New This Session)

| File | Purpose |
|------|---------|
| `.kiro/specs/conspiracy-theory-taxonomy/` | Full spec (req + design + tasks) |
| `.kiro/specs/proof-engine/requirements.md` | Proof Engine spec |
| `.kiro/specs/theory-registry/requirements.md` | Theory Registry spec |
| `migrations/conspiracy_taxonomy_schema.sql` | Aurora schema (16 tables) |
| `src/services/conspiracy_ingestion_adapters.py` | 6 file format adapters |
| `src/services/conspiracy_taxonomy_service.py` | Taxonomy CRUD + validation |
| `src/services/ach_scoring_service.py` | ACH competing hypotheses |
| `src/services/proof_engine.py` | 6 standards of proof |
| `src/services/conspiracy_seeding_pipeline.py` | 10-theory seeding |
| `src/services/conspiracy_validation_pipeline.py` | Sequential validation gating |
| `src/lambdas/api/conspiracy_coverage.py` | Coverage + proof API |
| `scripts/run_conspiracy_pipeline.py` | CLI orchestration |
| `scripts/_run_proof_save_results.py` | Proof Engine live evaluation |
| `src/config/tenants/*.json` | 3 tenant configs |
| `src/data/conspiracy-seed/` | Seed data (Bermuda + Ancient Aliens) |
| `src/data/proof-engine-results-ancient-mysteries.json` | Live evaluation results |
| `src/frontend/orion-correlation.html` | Sky Mirror view (updated) |
| `docs/PLATFORM-EVOLUTION-IDEAS.md` | Updated with Proof Engine + Tenant Architecture |
| `docs/TODO-sky-mirror-next.md` | Sky Mirror future work |

---

## ACTIONS REMAINING (Priority Order)

### P0 — Next Session

1. **Download real NTSB Bermuda Triangle data** (XML from ntsb.gov)
   - Filter: latitude 18-33°N, longitude 64-80°W
   - Should yield 100-500 accident records
   - Time: 30 min

2. **Run Aurora migration** against live cluster
   - File ready: `migrations/conspiracy_taxonomy_schema.sql`
   - Creates conspiracy schema with all 16 tables
   - Time: 5 min

3. **Run full seeding pipeline** with Bedrock connected
   - `python scripts/run_conspiracy_pipeline.py seed`
   - Processes seed data through Broad Scanner → Taxonomy Scanner
   - Time: 15 min

4. **Run Bermuda Triangle validation**
   - `python scripts/run_conspiracy_pipeline.py validate bermuda_triangle`
   - First full validation gate test
   - Time: 30 min

5. **Build Theory Registry frontend** (new HTML page)
   - Priority queue view, theory detail, evidence checklist, verdicts
   - Separate from grid-globe (different UX paradigm)
   - Time: 2-3 hours

### P1 — High Priority

6. **Expand Ancient Alien theories** (web search for more claims)
   - Currently: 10 theories
   - Target: 50+ (cover all major Ancient Aliens claims)
   - Use Tavily to find researcher publications beyond the show

7. **Download Flat Earth LOCO corpus** (88M tokens, pre-structured JSON)
   - Available on GitHub: purpose-built for NLP
   - Would be the scale test for the pipeline

8. **Download UFO/NUFORC CSV** (80K sighting records)
   - Available on Kaggle/CORGIS
   - Tests the CSV adapter at scale

9. **Push to GitHub** (incremental — use `python scripts/push_to_github.py`)

### P2 — Medium Priority

10. **Connect ACH scoring to Proof Engine** (currently separate paths)
11. **Theory cluster detection** (identify connected theories)
12. **Proof Engine with Sonnet 4** (need IAM policy update for inference profile)
13. **Story mode for Sky Mirror** (text narration walkthrough)

---

## ARCHITECTURE STATE

```
Platform (this repo, evolving into multi-tenant)
├── Tenant: Ancient Mysteries (existing, working)
│   ├── Frontend: grid-globe-3d.html, orion-correlation.html
│   ├── Data: 62 nodes, 18 signatures, 8 agents
│   └── Proof Standard: scientific
├── Tenant: Conspiracy Theories (new, code complete, not deployed)
│   ├── Frontend: TBD (Theory Registry dashboard)
│   ├── Data: 10 theories seeded, 13 Bermuda incidents
│   ├── Pipeline: adapters → agents → seeding → validation
│   └── Proof Standard: intelligence
└── Tenant: Crime (future, planned)
    ├── Frontend: Case Management (separate repo)
    └── Proof Standard: criminal_legal

Shared Backend:
├── Aurora PostgreSQL (conspiracy schema ready to deploy)
├── OpenSearch Serverless (conspiracy-documents index ready)
├── Neptune Graph (Theory/Document/Signature vertices ready)
├── Bedrock: Titan Embed v2 (working) + Claude 3 Haiku (working)
├── S3 Data Lake (data-lake/conspiracy-theories/ prefix)
└── Proof Engine (6 standards, live with Bedrock)
```

---

## COSTS THIS SESSION

| Service | Usage | Cost |
|---------|-------|------|
| Bedrock Claude 3 Haiku | 50 invocations (proof evaluation) | ~$0.05 |
| Bedrock Titan Embed v2 | 2 test invocations | ~$0.001 |
| **Total session** | | **~$0.05** |

---

## How to Resume

```
"Continue from docs/session-summary-2026-08-02-session2.md.
Code is complete. Proof Engine live. 10 theories evaluated.
Priorities: Download real NTSB data, run Aurora migration,
run full pipeline, build Theory Registry frontend."
```
