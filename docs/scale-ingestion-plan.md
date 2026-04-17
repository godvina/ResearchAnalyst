# Scale Ingestion Plan — Phased Data Loading Strategy

**Date:** April 14, 2026
**Goal:** Test platform at client-realistic scale (150-200GB, 100K+ docs)

---

## Current State

- Epstein Main: 5,042 docs in Aurora (from batches 1-4)
- 88,603 entities, 129,609 relationships
- Overnight 90K batch FAILED — graph load Lambda timeout (900s) + embed token overflow (8,397 > 8,192 limit)
- Embed handler fix applied: truncation tightened from 25K to 20K chars (not yet deployed to Lambda)

---

## Phase 1: HuggingFace DS6-8 Text Ingestion (TODAY — ~1 hour)

**Source:** `huggingface.co/datasets/ishumilin/epstein-files-ocr-datasets-1-8-early-release`
**What:** 42,182 page-level OCR files (Markdown), DS6-8 = ~25K net new pages
**Size:** 172 MB download
**Cost:** ~$5 Bedrock (entity extraction only)
**Time:** ~1 hour

### Steps:
1. ✅ Embed handler fix applied (20K char truncation)
2. Deploy embed fix to Lambda
3. Build `scripts/load_huggingface_text.py` (spec exists: `.kiro/specs/huggingface-text-ingestion/`)
4. Run: `python scripts/load_huggingface_text.py --case-id 7f05e8d5-4492-4f19-8894-25367606db96`
5. Verify: refresh stats, check UI, test KNN search quality
6. Expected result: ~30K total docs in Aurora (5K existing + 25K new)

### What this tests:
- Direct-to-Aurora text ingestion (bypasses Step Functions)
- Entity extraction at moderate scale
- KNN search quality with real content
- Case file generation with substantial evidence

### Dedup strategy:
- DS1-5 pages filtered out by dataset tag (already loaded)
- `source_metadata.source = "huggingface"` tag on all new docs

---

## Phase 2: epstein-files.org Processed Database (THIS WEEK)

**Source:** Sifter Labs open-source release (Jan 2025)
**What:** 106,000+ documents with OCR text + pre-computed embeddings
**Size:** Database export ~5-10GB (text + embeddings), full archive 188GB
**Cost:** ~$15-25 Bedrock (entity extraction only — skip OCR, skip embedding if compatible)
**Time:** ~4-8 hours

### Steps:
1. Locate the Sifter Labs GitHub release / database export
2. Download just the processed database (not the full 188GB raw files)
3. Assess embedding compatibility:
   - If their embeddings are 1536-dim (Titan compatible) → import directly
   - If different dimension → re-embed with Titan (add ~$10 cost, ~2 hours)
4. Build import script: `scripts/import_sifterlabs_db.py`
   - Read their database format (likely SQLite or PostgreSQL dump)
   - Extract: filename, OCR text, embeddings (if compatible)
   - Insert into Aurora `documents` table for Epstein Main case
   - Dedup: skip docs where `source_filename` already exists
5. Run entity extraction on new docs (Bedrock Haiku, batched)
6. Sync entities to Neptune
7. Refresh case stats
8. Expected result: ~100K+ total docs in Aurora

### What this tests:
- Bulk data import from external processed sources
- Entity extraction at large scale
- Neptune graph with 100K+ doc entities
- KNN search across 100K+ embeddings
- Case file generation with massive evidence corpus

### Dedup strategy:
- Check `source_filename` against existing Aurora docs before insert
- Tag with `source_metadata.source = "sifterlabs"`
- HuggingFace docs (Phase 1) have different filenames — no conflict

---

## Phase 3: Full 188GB Raw Ingestion (NEXT WEEK — Client Architecture Proof)

**Source:** DOJ releases DS6-12 via community mirrors / Internet Archive
**What:** Full raw PDFs + images, ~60-70K new documents
**Size:** ~140-188GB raw
**Cost:** ~$50-100 (Bedrock + Textract OCR)
**Time:** ~24-48 hours processing, ~4-8 hours download

### Steps:
1. Spin up t3.xlarge EC2 in us-east-1 (same region as S3/Aurora)
2. Download in chunks via torrent or Internet Archive:
   - DS6: ~20GB
   - DS7: ~20GB
   - DS8: ~30GB
   - DS10: ~30GB
   - DS12: ~20GB
   - (DS9 incomplete at source — skip or partial)
3. Stream each dataset to S3: `s3://research-analyst-data-lake-974220725866/cases/7f05e8d5-.../raw/`
4. Process through existing Step Functions pipeline (with embed fix deployed):
   - Parse (Textract OCR for PDFs/images)
   - Extract entities (Bedrock Haiku, chunked)
   - Generate embeddings (Titan Embed, 20K char truncation)
   - Graph load (Neptune bulk CSV)
5. Run in batches of 5,000 docs, overnight runs
6. Dedup: pipeline skips docs already in Aurora by `source_filename`
7. Terminate EC2 when done
8. Expected result: 100K-150K+ total docs, 188GB in S3

### What this tests:
- **Full ingestion pipeline at client scale (150GB+)**
- Textract OCR throughput
- Step Functions with large Map concurrency
- Aurora pgvector with 100K+ embeddings
- Neptune graph at scale
- S3 data lake at 188GB
- Cost model validation for client proposals

### Dedup strategy:
- Phase 1 (HuggingFace) docs tagged `source = "huggingface"`, filenames like `DS6_page_001.md`
- Phase 2 (Sifter Labs) docs tagged `source = "sifterlabs"`, filenames like `EFTA02255838`
- Phase 3 (raw pipeline) docs have original DOJ filenames like `EFTA02255838.pdf`
- Dedup on `source_filename` (strip extension) catches overlap between Phase 2 text and Phase 3 raw

---

## Bug Fixes Required Before Resuming Pipeline

| Fix | Status | Impact |
|-----|--------|--------|
| Embed handler: 25K → 20K char truncation | ✅ Code fixed | Prevents token overflow on dense docs |
| Deploy embed fix to Lambda | ⏳ Pending | Required before any pipeline run |
| Graph load timeout (900s) | ⏳ Needs investigation | Blocks overnight batch runs via Step Functions |

### Graph Load Timeout Options:
1. Reduce docs per Step Functions execution (50 → 20)
2. Split graph load into sub-batches within the Lambda
3. Skip Neptune graph load for bulk ingestion, run Neptune sync after (current workaround)
4. Use Neptune bulk CSV loader with smaller payloads

---

## Cost Summary

| Phase | Docs Added | Bedrock Cost | Other Cost | Total |
|-------|-----------|-------------|------------|-------|
| Phase 1 (HuggingFace) | ~25K | ~$5 | $0 | ~$5 |
| Phase 2 (Sifter Labs DB) | ~70K | ~$15-25 | $0 | ~$15-25 |
| Phase 3 (Full 188GB) | ~60-70K | ~$50-100 | ~$5 EC2 | ~$55-105 |
| **Total** | **~155K docs** | **~$70-130** | **~$5** | **~$75-135** |

---

## Quick Reference Commands

```bash
# Phase 1: HuggingFace ingestion
python scripts/load_huggingface_text.py --case-id 7f05e8d5-4492-4f19-8894-25367606db96

# Deploy embed fix
Get-ChildItem -Path src -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Compress-Archive -Path src\* -DestinationPath deploy-clean.zip -Force
aws s3 cp deploy-clean.zip s3://research-analyst-data-lake-974220725866/deploy/lambda-update.zip
aws lambda update-function-code --function-name ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq --s3-bucket research-analyst-data-lake-974220725866 --s3-key deploy/lambda-update.zip

# Check doc count anytime
curl.exe -s -X POST https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1/case-files/7f05e8d5-4492-4f19-8894-25367606db96/refresh-stats
```
