# Data Inventory & Ingestion Plan

## Current Inventory (as of 2026-04-12)

### Cases in System

| Case | S3 Raw Files | Aurora Docs | Aurora Entities | Neptune Entities | Status |
|------|-------------|-------------|-----------------|-----------------|--------|
| Epstein Main (7f05e8d5) | 345,904 | 345,898 | 0 | Unknown (large) | **Needs entity sync** |
| Epstein Combined (ed0b6c27) | 8,980 | 8,974 | 21,488 | 21,488 | ✅ Working |
| Ancient Aliens (d72b81fc) | 240 | 40 | 36,358 | 36,358 | ✅ Working |

### Source Bucket (doj-cases-974220725866-us-east-1)

| Prefix | Files | Size | Notes |
|--------|-------|------|-------|
| pdfs/ | 4,036 | 2.1 GB | DS1-5 PDFs |
| bw-documents/ | 4,271 | 2.2 GB | DS1-5 black & white docs |
| photo-metadata/ | 3,804 | 1.4 MB | Rekognition metadata JSON |
| rekognition-output/ | 3,965 | 1.2 MB | Rekognition results |
| textract-output/ | 3,804 | 0.9 MB | Textract OCR results |
| DataSet8-12/ | 5 files | ~0 | Placeholder robots.txt only |

### Picture/Visual Value Assessment

- Face crops: 58 images (467 KB) for Epstein Combined
- Rekognition artifacts: 6 files (8.5 MB)
- Visual entities in Neptune: ~200 nodes from Rekognition (celebrities, labels, text detection)
- **Value**: The face crops power the photo gallery and face matching features. The visual entities (person detections, celebrity matches) feed into the Knowledge Graph. For a scalability demo, text is sufficient. For a complete investigative tool, visuals add face matching, photo evidence, and visual entity linking.

## Immediate Action: Entity Sync for Epstein Main

**Priority 1**: Run Neptune → Aurora entity sync for Epstein Main (345K docs, 0 entities)
- Script: `python scripts/sync_neptune_to_aurora.py --case-id 7f05e8d5-4492-4f19-8894-25367606db96`
- Estimated time: 1-2 minutes (Lambda async)
- Result: Entities from Neptune populated in Aurora entities table
- This unlocks: theories, case files, anomaly detection, legal analysis for 345K docs

## Outstanding Data: DOJ Datasets Not Yet Loaded

### What's Missing

| Dataset | Status | Est. Files | Est. Size | Content |
|---------|--------|-----------|-----------|---------|
| DS1-5 | ✅ Loaded | ~8,000 | 4.3 GB | Initial release (PDFs, images) |
| DS6 | ❌ Not loaded | ~10,000+ | ~20 GB | Additional documents |
| DS7 | ❌ Not loaded | ~10,000+ | ~20 GB | Additional documents |
| DS8 | ❌ Not loaded | ~15,000+ | ~30 GB | Additional documents |
| DS9 | ❌ Incomplete at source | ~10,000+ | ~20 GB | Known missing files |
| DS10 | ❌ Not loaded | ~15,000+ | ~30 GB | Additional documents |
| DS11 | ✅ Loaded | ~3,466 | ~2 GB | Phase 2 (loaded to Combined) |
| DS12 | ❌ Not loaded | ~10,000+ | ~20 GB | Latest release |

**Total gap: ~60-70K documents, ~140 GB raw**

## External Data Sources

### 1. HuggingFace: ishumilin/epstein-files-ocr (DS1-8)
- **Size**: ~172 MB (text only, Markdown format)
- **Files**: 42,182 page-level OCR files
- **Format**: page_N.md (one file per scanned page)
- **Coverage**: Datasets 1-8
- **Pros**: Tiny download, pre-OCR'd, CC0 license
- **Cons**: Page-level (not document-level), no entity extraction, no images, DS1-5 overlap with what we have
- **Net new**: DS6-8 pages (~25,000 pages)
- **Best for**: Quick text ingestion without OCR cost

### 2. HuggingFace: theelderemo/FULL_EPSTEIN_INDEX
- **Size**: ~8,530 rows (small structured dataset)
- **Format**: Structured index with metadata
- **Coverage**: All releases (House Oversight + DOJ + FBI)
- **Pros**: Unified index, good for cross-referencing
- **Cons**: Index only, not full text

### 3. HuggingFace: teyler/epstein-files-20k
- **Size**: 2.1M rows (filename + OCR text)
- **Format**: Parquet/Arrow
- **Coverage**: ~20K documents
- **Pros**: Large, pre-processed, includes text
- **Cons**: May overlap significantly with DS1-5

### 4. epstein-files.org (Sifter Labs)
- **Size**: 188 GB (106,000+ files)
- **Format**: Complete source code + processed database with embeddings
- **Coverage**: All available documents
- **Status**: Open-sourced Jan 2025, site shut down Feb 2025
- **Pros**: Most complete, includes embeddings
- **Cons**: 188 GB download, need to find the actual GitHub release

### 5. epstein-docs.github.io
- **Size**: ~8,175 documents with JSON results
- **Format**: JSON per document (OCR text + entities + metadata)
- **Coverage**: DS1-5 (same as what we have)
- **Pros**: Pre-extracted entities, AI summaries
- **Cons**: Overlaps with our existing data

### 6. DOJ Direct (justice.gov/epstein)
- **Size**: ~1.3 TB (raw scans, many blank pages)
- **Format**: ZIP archives per dataset
- **Pros**: Official source, complete
- **Cons**: Huge, requires OCR, many blank/duplicate pages

### 7. Community Mirrors (yung-megafone/Epstein-Files)
- **Size**: Same as DOJ (~1.3 TB total)
- **Format**: Torrent magnets + Internet Archive mirrors
- **Pros**: Faster downloads, resume-friendly
- **Cons**: Same raw format as DOJ

## Recommended Approach

### Phase 1: Immediate (no download needed)
1. Sync Neptune entities to Aurora for Epstein Main (345K docs)
2. Generate theories and case files for Epstein Main
3. This gives you 354K total docs with entities — strong scalability demo

### Phase 2: Quick text ingestion (~172 MB)
1. Download HuggingFace DS1-8 OCR dataset (172 MB)
2. Filter out DS1-5 pages (already loaded)
3. Ingest DS6-8 text pages (~25K pages) directly to Aurora
4. Skip images/OCR — text only
5. Run entity extraction on new pages via Bedrock

### Phase 3: Full dataset (EC2 → S3, ~140 GB)
1. Spin up t3.medium EC2 in us-east-1
2. Download DS6, DS7, DS8, DS10, DS12 from DOJ/mirrors
3. Stream directly to S3 source bucket
4. Run through existing ingestion pipeline (parse → extract → embed → graph)
5. Includes images for Rekognition processing
6. Terminate EC2 when done

### Text-Only vs Full (Decision Matrix)

| Factor | Text Only (Phase 2) | Full with Images (Phase 3) |
|--------|---------------------|---------------------------|
| Download size | ~172 MB | ~140 GB |
| Time to ingest | ~1 hour | ~24-48 hours |
| Cost | ~$5 (Bedrock entity extraction) | ~$50-100 (Bedrock + Textract + Rekognition) |
| Face matching | ❌ No | ✅ Yes |
| Photo gallery | ❌ No | ✅ Yes |
| Visual entities | ❌ No | ✅ Yes |
| Text search | ✅ Yes | ✅ Yes |
| Entity extraction | ✅ Yes | ✅ Yes |
| Scalability demo | ✅ Sufficient | ✅ Complete |
