# Data Inventory & Ingestion Plan

## Current Inventory (as of 2026-04-21)

### What's Actually Loaded in Aurora (Verified by Audit)

**Epstein Main case (7f05e8d5): 75,805 documents with text**

| Source | Filename Pattern | Est. Count | Coverage |
|--------|-----------------|-----------|----------|
| DOJ Originals (DS1-5) | `DOJ-OGR-*` | ~36,000 | DS1-5 PDFs processed through pipeline |
| HuggingFace DS1-8 OCR | `page_*` | ~29,000 | Pages 17007-42178, DS1-8 fully loaded |
| Teyler/epstein-files-20k | `teyler_row_*` | ~5,000+ | Partial load (~25% of 20K dataset) |
| Other (misc sources) | Various | ~5,000+ | Mixed sources, names as filenames |

**Epstein Combined case (ed0b6c27): ~8,974 documents**
- Giuffre v. Maxwell civil case documents

**Aurora Entities: 247,720 distinct (Nova Pro extraction)**
- 71,163 with occurrence >= 2 (high quality)
- 61,145 core types with occurrence >= 2

**Neptune: 991K nodes, 13.17M edges (mixed old + new data)**
- Edge sync in progress: adding 27K new edges from Aurora relationships

### Data Sources — Complete Registry

| # | Source | Type | Size | Status | Notes |
|---|--------|------|------|--------|-------|
| 1 | DOJ DS1-5 (PDFs) | Raw PDFs | 345K files, 4.3 GB | ✅ Loaded | In S3 + Aurora |
| 2 | DOJ DS6-8 | Raw PDFs | ~30K files, ~60 GB | ❌ Not in S3 | Available from DOJ |
| 3 | DOJ DS9-12 (Jan 2026) | Raw PDFs | ~3M pages | ❌ Not loaded | Massive release |
| 4 | HuggingFace ishumilin/DS1-8 OCR | Pre-OCR'd text | 42,182 pages, 172 MB | ✅ Loaded | `page_*` filenames |
| 5 | HuggingFace teyler/epstein-files-20k | Pre-processed text | 20K docs, 2.1M rows | ⚠️ Partial (~5K) | `teyler_row_*` filenames |
| 6 | HuggingFace theelderemo/FULL_EPSTEIN_INDEX | Structured index | 8,530 rows | ❌ Not loaded | Metadata only |
| 7 | HuggingFace vikash06/EpsteinFiles | OCR text | 1,413 rows | ❌ Not loaded | Small, may overlap |
| 8 | epstein-files.org (Sifter Labs) | Full archive + embeddings | 106K files, 188 GB | ❌ Not loaded | Open-sourced Jan 2025 |
| 9 | epstein-docs.github.io | JSON with entities | 8,175 docs | ❌ Not loaded | Pre-extracted entities |
| 10 | House Oversight (Sep 2025) | Court docs, flight records | 33K pages | ❌ Not loaded | Flight logs = gold |
| 11 | DOJ DS11 | Documents | ~3,466 files | ✅ Loaded to Combined | In Combined case |
| 12 | Community mirrors | Same as DOJ | ~1.3 TB | N/A | Torrent/IA mirrors |

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
