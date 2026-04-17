# Session Context Transfer — Theory Case File & Data Sync

## NEXT SESSION: Continue from here

Say "continue from docs/session-context-transfer.md" to pick up.

### Session Summary (April 16-17, 2026)

**Completed this session:**
1. ✅ Geospatial map fixed — added 11 location nodes + 22 edges to Neptune, fixed patterns API noise filter, fixed limit(200) timeout
2. ✅ Route Intelligence feature — AI-powered travel pattern analysis with click-to-isolate cards
3. ✅ Story mode respects Route Intel filter — only tours highlighted locations
4. ✅ Story mode narratives improved — "Epstein and Maxwell traveled from Paris to NYC" style
5. ✅ Route Intel panel moved to left side (was overlapping AI Analysis on right)
6. ✅ Timeline tab fixed — improved date parser handles DD MMM YYYY, DD.MM.YYYY, DD/MM/YYYY formats. Now shows 244 events, 24 clusters, 3 phases
7. ✅ Neptune addE() fix documented — must use __.V() not g.V() for anonymous traversals
8. ✅ Added query_aurora_entities Lambda action for Aurora→Neptune sync
9. ✅ Workspace file created: Research Analyst.code-workspace

**Running on EC2:**
- `i-00c6e8b609c5e062e` (entity-backfill-v3) — entity extraction for Epstein Main, 35K/94K done, ~60 hours remaining
- `i-03aa49215972f0019` (neptune-sync) — Aurora→Neptune entity sync for Epstein Main, ~30 min, self-terminates

**Still TODO:**
- Noise entity cleanup (after extraction completes)
- Re-sync Neptune after extraction finishes (94K entities)
- Case cleanup (remove 20+ test/duplicate cases)
- Deploy package update for colleague (include Route Intel)
- Refresh case stats for Epstein Main after sync completes

---

## 🔴 CRITICAL: Epstein Main Has 0 Docs in Aurora (345K in S3 Only)

**Discovery (2026-04-13):** The 345,898 "document count" was an S3 file count, NOT Aurora rows.
- S3: ~345,904 `.txt`/`.pdf` files under `cases/7f05e8d5.../` ✅
- Aurora `documents` table: **0 rows** for this case_id ❌
- Aurora `entities` table: 44,806 entities (from Neptune sync) ✅
- Aurora `relationships` table: 65,675 relationships ✅
- Neptune: Entity nodes and relationships ✅

**Root cause:** Files were uploaded to S3 but never processed through the Step Functions ingestion pipeline (parse → extract → embed → graph → store). The `case_files.document_count` was set from S3 file counts via `scripts/update_case_doc_counts.py`.

**Impact:** KNN semantic search, case file generation, and text search all query the Aurora `documents` table — which is empty. All features that depend on document content are non-functional for Epstein Main.

## 🟡 ACTION: Batch Pipeline Ingestion Plan (345K S3 → Aurora)

**Strategy:** Use existing `scripts/batch_loader.py` pipeline. Process in phases:

| Phase | Docs | Purpose | Est. Time | Est. Cost |
|-------|------|---------|-----------|-----------|
| Phase 1 | 10,000 | Validation batch — verify pipeline works | ~1-2 hours | ~$4 |
| Phase 2 | 90,000 | Overnight run — bulk of first 100K | ~8-12 hours | ~$35 |
| Phase 3 | 245,000 | Remaining docs — run over 1-2 days | ~24-36 hours | ~$96 |
| **Total** | **345,000** | **Full ingestion** | **~2-3 days** | **~$135** |

**Commands:**
```bash
# Phase 1: Validation batch (10K docs, ~2 batches at 5000/batch)
python scripts/batch_loader.py --confirm --max-batches 2

# Phase 2: Overnight run (90K docs, ~18 batches)
python scripts/batch_loader.py --confirm --max-batches 18

# Phase 3: Remaining (245K docs, ~49 batches)
python scripts/batch_loader.py --confirm --max-batches 49

# After each phase, refresh stats:
python scripts/sync_neptune_to_aurora.py --case-id 7f05e8d5-4492-4f19-8894-25367606db96
```

**What the pipeline does per doc:** Extract text (PyPDF2/Textract) → Filter blanks → Bedrock entity extraction → Titan Embed vectors → Aurora INSERT (documents + entities) → Neptune graph load → Entity resolution

**After ingestion:** KNN semantic search, case file generation, and all evidence-based features will work with real document content.

## ✅ RESOLVED: Neptune → Aurora Entity Sync

Neptune → Aurora entity sync completed for all cases:

| Case | Case ID | S3 Files | Aurora Docs | Aurora Entities | Relationships | Status |
|------|---------|----------|-------------|-----------------|---------------|--------|
| Epstein Main | `7f05e8d5-...` | 345,904 | **0** ❌ | 44,806 | 65,675 | **Needs pipeline ingestion** |
| Epstein Combined | `ed0b6c27-...` | 8,980 | 8,974 | 21,488 | — | ✅ Working |
| Ancient Aliens | `d72b81fc-...` | 240 | 40 | 36,358 | — | ✅ Working |

Script: `python scripts/sync_neptune_to_aurora.py --case-id <uuid>`

## ✅ RESOLVED: Theory Case File Feature (DEPLOYED)

13-section professional investigative case file for each theory:
1. Theory Statement, 2. Classification, 3. ACH Scorecard, 4. Evidence For,
5. Evidence Against, 6. Evidence Gaps, 7. Key Entities, 8. Timeline,
9. Competing Theories, 10. Investigator Assessment, 11. Recommended Actions,
12. Legal Analysis (adaptive), 13. Confidence Level

Key features:
- Generated by Bedrock on first view, persisted to Aurora `theory_case_files` table
- Loads instantly on subsequent views (no re-generation)
- Section editing via inline editor (pencil icon)
- Regenerate Case File button (preserves investigator notes)
- Promote to Sub-Case button (only on confirmed theories)
- Adaptive section 12: Legal Analysis (criminal/financial), Research Analysis (academic), Intelligence Assessment (OSINT)
- Spec: `.kiro/specs/theory-case-file/`

## ✅ RESOLVED: Bug Fixes Applied Previous Session

- `discovery_engine_service.py`: `filename` → `source_filename`, `content` → `raw_text`, `created_at` → `indexed_at`
- `theory_engine_service.py`: removed `file_type` reference, reduced evidence classification from 50 to 5 docs
- Theory detail endpoint: reduced evidence limit to avoid Lambda timeout
- Case file generation: single Bedrock call (removed second call that caused 504 timeout)
- Prompt size: reduced to 10 evidence docs at 150 chars, 20 entities max
- Frontend: handles missing sections gracefully (shows "Generate" placeholder)

## ✅ DEPLOYED: Evidence Starvation Bugfix (2026-04-13, Lambda v5)

**Spec:** `.kiro/specs/case-file-evidence-starvation/`

Fixes deployed:
- **refresh_case_stats** action: `POST /case-files/{id}/refresh-stats` — recalculates doc/entity/rel counts from source tables
- **Stuck briefing recovery**: 15-min expiry on `investigator_analysis_cache` processing rows
- **Per-service timeouts**: 60s timeout on pattern_discovery, hypothesis_generation, _generate_leads for large cases (>10K docs)
- **KNN evidence retrieval**: `_fetch_knn_evidence()` uses pgvector cosine similarity instead of blind recency query (30 docs at 300 chars)
- **KNN entity enrichment**: `_fetch_knn_entities()` extracts entities from KNN-retrieved documents (up to 40)
- **Two-pass Bedrock generation**: Pass 1 (sections 1-11, max_tokens=6144), Pass 2 (legal analysis, max_tokens=4096 with legal-focused KNN)
- **Confidence penalty**: 5 points per gap detected by `_detect_section_gaps()`
- **sync_neptune_to_aurora.py**: now calls `refresh_case_stats` after sync completes

## 🟡 Sidebar Doc Counts — NOW FIXABLE

Use `refresh_case_stats` action to fix stale counts:
```bash
# Via Lambda invoke:
aws lambda invoke --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --payload fileb://refresh-payload.json result.json

# Via API:
POST https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/{case_id}/refresh-stats
```

## 🟡 24 Cases — Many Are Test/Duplicates

The system has 24 cases. Many are test cases with 0 or 50 docs. The three real cases are listed above. Consider cleaning up test cases for demo clarity.

---

## NEXT PRIORITIES:

### 0. 🔴 MORNING: Clean-Room Deployment Test (No-Code Approach)
- **THIS IS THE #1 PRIORITY** — deploy a fresh instance to a new Isengard account with zero data
- Use the CloudFormation console approach (Section 5.4 of the deployment architecture doc)
- **BEFORE deploying**: run `cdk synth` to generate the template with all WAF changes + sidebar sort fix + rename action
- **SAMPLE DATA**: Create a zip of ~500 PDFs from `s3://doj-cases-974220725866-us-east-1/pdfs/` for the colleague to test with
  ```bash
  # Download 500 PDFs to local folder
  mkdir sample-data && aws s3 cp s3://doj-cases-974220725866-us-east-1/pdfs/ sample-data/ --recursive --max-items 500
  # Zip them
  Compress-Archive -Path sample-data\* -DestinationPath sample-epstein-500.zip
  ```
  Colleague uploads these to their data lake bucket under `pdfs/`, then runs the batch loader
- Steps:
  1. `cd infra/cdk && cdk synth` (generates `cdk.out/ResearchAnalystStack.template.json`)
  2. Open CloudFormation console in new Isengard account → Create Stack → Upload Template
  3. Fill in parameters → Create Stack → Wait ~20 min
  4. Run Aurora migrations: `python scripts/migrate_via_lambda.py`
  5. Upload frontend: `aws s3 cp src/frontend/investigator.html s3://<new-bucket>/frontend/investigator.html --content-type "text/html"`
  6. Upload sample data: unzip `sample-epstein-500.zip` to `s3://<new-source-bucket>/pdfs/`
  7. Create a case via UI, run batch loader: `python scripts/batch_loader.py --confirm --max-batches 1`
  8. Verify: theories generate, case health bar loads, search works
- Goal: validate deployment is reproducible and hand-off-ready for a colleague
- **PENDING DEPLOY**: Lambda v10 changes (sidebar sort by doc count, rename action, per-batch stats refresh) need to be deployed to current account AFTER batch 4 completes

### 0b. 🟡 OVERNIGHT: 90K Batch Running
- **KICKED OFF** at ~9:30pm ET on 2026-04-13
- Command: `python scripts/batch_loader.py --confirm --max-batches 18 --case-id 7f05e8d5-... --source-bucket research-analyst-data-lake-974220725866 --source-prefixes cases/7f05e8d5-.../raw/`
- 18 batches × 5,000 = 90K files
- Case tier fixed to `standard` (was `enterprise` — Issue 37)
- 50-doc test confirmed docs landing in Aurora (20+ docs verified)
- Neptune sync + stats refresh runs automatically at end
- Per-batch stats refresh updates sidebar counts incrementally
- Est. completion: ~8am ET (8-12 hours)
- **MORNING CHECK**: Refresh Epstein Main in UI — should show ~40-50K docs

### 1. 🔴 Run Pipeline Ingestion for Epstein Main (345K S3 files → Aurora)
- **CURRENT STATUS**: Batches 3-4 complete (10K validation). Neptune sync + stats refresh runs automatically.
- After batch 4: test the UI — Epstein Main should have ~5-8K docs in Aurora

**TONIGHT — 90K overnight run:**
```bash
python scripts/batch_loader.py --confirm --max-batches 18 --case-id 7f05e8d5-4492-4f19-8894-25367606db96 --source-bucket research-analyst-data-lake-974220725866 --source-prefixes cases/7f05e8d5-4492-4f19-8894-25367606db96/raw/
```
- Picks up from batch 5 (cursor-based resume)
- 18 batches × 5,000 = ~90K files
- Neptune sync + stats refresh runs automatically at end
- Est. time: 8-12 hours | Est. cost: ~$285

**TOMORROW — remaining ~245K files:**
```bash
python scripts/batch_loader.py --confirm --max-batches 49 --case-id 7f05e8d5-4492-4f19-8894-25367606db96 --source-bucket research-analyst-data-lake-974220725866 --source-prefixes cases/7f05e8d5-4492-4f19-8894-25367606db96/raw/
```
- Picks up from batch 23
- Est. time: 24-36 hours | Est. cost: ~$784
- Phase 1: 10K validation batch → verify → Phase 2: 90K overnight
- Command: `python scripts/batch_loader.py --confirm --max-batches 2`
- This is the #1 blocker — without Aurora docs, KNN search and case files have no evidence

### 2. Ingest DS6-8 Text from HuggingFace (172 MB, ~25K pages)
- Source: `huggingface.co/datasets/ishumilin/epstein-files-ocr-datasets-1-8-early-release`
- 42,182 OCR'd pages as Markdown, DS1-5 overlap (skip), net new ~25K pages from DS6-8
- Spec: `.kiro/specs/huggingface-text-ingestion/requirements.md`
- See: `docs/data-inventory-and-ingestion-plan.md`

### 2. Generate Theories for Epstein Main (345K docs)
- Now that entities are synced, generate theories and case files
- This is the scalability showcase — 345K docs, 77K entities

### 3. Full Dataset Ingestion (DS6-12, ~140 GB)
- EC2 in us-east-1 → download from DOJ/mirrors → stream to S3
- Run through existing pipeline (parse → extract → embed → graph)
- See: `docs/data-inventory-and-ingestion-plan.md` for full plan

### 4. Entity Deduplication
- Ancient Aliens has near-duplicates (Mayan/Maya/Mayans, Egyptian/Egyptians)
- Entity resolution service exists but needs to be run

### 5. Case Cleanup
- Remove or archive the 20+ test/duplicate cases
- Keep: Epstein Main, Epstein Combined, Ancient Aliens

---

## Key Infrastructure
- Lambda: `ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq` (timeout: 900s, memory: 512MB)
- S3 Data Lake: `research-analyst-data-lake-974220725866`
- S3 Source: `doj-cases-974220725866-us-east-1`
- API: `https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1` (29s timeout)
- Frontend: `src/frontend/investigator.html` → `s3://research-analyst-data-lake-974220725866/frontend/investigator.html`
- Epstein Main: `7f05e8d5-4492-4f19-8894-25367606db96` (345,898 docs, 77,900 entities)
- Epstein Combined: `ed0b6c27-3b6b-4255-b9d0-efe8f4383a99` (8,974 docs, 21,488 entities)
- Ancient Aliens: `d72b81fc-a4e1-4de5-a4d3-8c74a1a7e7f7` (240 docs, 36,358 entities)

## ✅ RESOLVED: Geospatial Map Missing Key Locations (April 16, 2026)

**Problem**: Marrakesh, Islip, Palm Beach, London, Manhattan, Little St. James Island, Virgin Islands, New Mexico, Santa Fe, Ohio were missing from the geospatial map.
**Root cause**: Two issues:
1. Location nodes were not in Neptune for the Combined case (previously added nodes may have been lost)
2. The patterns API `_get_graph()` used `.limit(200)` which missed low-degree location nodes
**Fix**:
1. Added 11 location vertices to Neptune via `scripts/fix_combined_locations_v3.py`
2. Added 22 person→location edges via `scripts/fix_combined_edges_final.py` (using `__.V()` not `g.V()`)
3. Fixed `patterns.py` to query locations separately (no limit) then merge with top-200 non-locations
4. Deployed Lambda with both fixes
**Verification**: Patterns API now returns all key locations with person→location edges. Map should show Marrakesh, Islip, Palm Beach, London, etc. with travel lines.

## 🔴 EC2 Entity Extraction Possibly Stuck (April 16, 2026)

EC2 `i-06144ab22c4a90751` running 27+ hours but entity count unchanged at 33,509/93,505.
Need to investigate — may need to terminate and relaunch.

## Deploy Commands
```bash
# Clean before deploy (MANDATORY)
Get-ChildItem -Path src -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path src -Recurse -Filter "*.pyc" | Remove-Item -Force

# Frontend
aws s3 cp src/frontend/investigator.html s3://research-analyst-data-lake-974220725866/frontend/investigator.html --content-type "text/html"

# Lambda
Compress-Archive -Path src\* -DestinationPath deploy-clean.zip -Force
aws s3 cp deploy-clean.zip s3://research-analyst-data-lake-974220725866/deploy/lambda-update.zip
aws lambda update-function-code --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --s3-bucket research-analyst-data-lake-974220725866 --s3-key deploy/lambda-update.zip
aws lambda wait function-updated --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq
aws lambda publish-version --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq
```

## Key Documentation
- `docs/data-inventory-and-ingestion-plan.md` — Full inventory, external sources, ingestion plan
- `docs/lessons-learned.md` — All issues and fixes (25+ entries)
- `.kiro/specs/theory-case-file/` — Theory Case File spec (requirements, design, tasks)

## User Preferences
- All changes EXTEND existing code, never REPLACE
- Always update documentation after fixes
- Always clean __pycache__ before Lambda deploy
- Always verify API endpoint works before telling user to test UI
- Always check which case the user is viewing
- Don't ask for approval on log searches — batch them efficiently
- Always check lessons-learned.md before debugging known issues
- User: David Eyre, Emerging Tech Solutions, AWS
